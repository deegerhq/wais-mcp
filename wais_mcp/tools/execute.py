"""Tool: wais_execute — Execute an action at a WAIS-compatible site."""

import json
from typing import Optional

import httpx

from ..auth import auth_headers
from ..http import safe_request
from ..manifest import WAISManifest
from ..polling import poll_for_result
from ..session import get_manifest, get_token, store_resolution


async def wais_execute(
    site_url: str,
    action_id: str,
    params: Optional[dict] = None,
) -> str:
    """Execute an action at a WAIS-compatible site.

    Uses the agents.json from wais_discover to resolve the action's endpoint,
    HTTP method, and required scopes. If the site has an api_base_url, requests
    are routed there automatically. Tokens and DPoP proofs are handled internally.

    Pass site.url (from agents.json) as site_url, the action id, and params
    matching the action's input_schema.

    Examples:
        wais_execute("https://serphub.deeger.io", "search", {"query": "python"})
        wais_execute("https://serphub.deeger.io", "get_usage")
        wais_execute("https://serphub.deeger.io", "list_jobs", {"limit": 5})

    Args:
        site_url: The site.url from agents.json (shown in discover output).
        action_id: The action id from agents.json (e.g. "search", "get_usage").
        params: Parameters matching the action's input_schema.
    """
    manifest = await get_manifest(site_url)
    site_identity = manifest.site_url or site_url
    scopes = manifest.get_all_scopes()
    token = await get_token(site_identity, scopes)

    action = manifest.get_action(action_id)

    if action:
        method = action.get("method", "POST").upper()
        full_url = manifest.resolve_endpoint(action_id, params)
    else:
        valid_ids = manifest.list_action_ids()
        if valid_ids:
            return (
                f"Unknown action_id: '{action_id}'. "
                f"Valid action_ids for this site: {', '.join(valid_ids)}. "
                "Run wais_discover to see details for each action."
            )
        method = "POST"
        full_url = f"{manifest.api_base_url.rstrip('/')}/wais/api/{action_id}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        request_headers = auth_headers(token, method, full_url)

        if method in ("POST", "PUT", "PATCH"):
            resp = await safe_request(
                client, method, full_url, headers=request_headers, json=params or {},
            )
        else:
            resp = await safe_request(client, method, full_url, headers=request_headers)

        # ── 402: Confirmation required ─────────────────────────
        if resp.status_code == 402:
            return _handle_402(resp.json(), action_id, manifest)

        # ── 202: Async action ──────────────────────────────────
        if resp.status_code == 202:
            return await _handle_202(resp.json(), action, manifest, token)

        # ── Error responses ────────────────────────────────────
        if resp.status_code in (401, 403):
            return _handle_auth_error(resp.json())

        resp.raise_for_status()
        data = resp.json()

    return json.dumps(data, indent=2, ensure_ascii=False)


def _handle_402(data: dict, action_id: str, manifest: WAISManifest) -> str:
    """Format a 402 confirmation challenge response."""
    challenge = data.get("wais_confirmation", {})
    display = challenge.get("display_to_user", {})
    payment = challenge.get("payment")
    resolution = challenge.get("resolution")

    lines = [
        "CONFIRMATION REQUIRED",
        f"Action: {challenge.get('action', action_id)}",
        f"Risk level: {challenge.get('risk_level', 'high')}",
        f"Challenge ID: {challenge.get('challenge_id', '')}",
        "",
    ]
    for k, v in display.items():
        if isinstance(v, list):
            lines.append(f"{k}:")
            for item in v:
                lines.append(f"  - {item}")
        else:
            lines.append(f"{k}: {v}")

    if payment:
        lines.append("")
        amount = payment.get("amount", "")
        currency = payment.get("currency", "")
        provider = payment.get("provider", "")
        if amount:
            lines.append(f"Payment: {amount} {currency} via {provider}")
        pay_url = payment.get("url")
        if pay_url:
            lines.append(f"Payment link: {pay_url}")

    if resolution:
        challenge_id = challenge.get("challenge_id", "")
        if challenge_id:
            store_resolution(challenge_id, resolution, manifest.site_url, manifest.api_base_url)
        lines.append("")
        lines.append("This action supports automatic polling for completion.")
        lines.append("After the user approves/pays, call wais_confirm with the challenge_id.")
    else:
        lines.append("")
        lines.append("Ask the user if they want to proceed, then call wais_confirm with the challenge_id.")

    return "\n".join(lines)


async def _handle_202(initial_data: dict, action: Optional[dict], manifest: WAISManifest, token: str) -> str:
    """Handle async action with optional polling."""
    async_config = action.get("async") if action else None

    if async_config:
        ref_values = {}
        for key in ("job_id", "task_id", "submission_id", "request_id", "id"):
            if key in initial_data:
                ref_values[key] = initial_data[key]
                break

        result = await poll_for_result(
            resolution=async_config,
            site_url=manifest.api_base_url,
            ref_values=ref_values,
            token=token,
        )
        if result["status"] == "completed":
            return json.dumps(result["data"], indent=2, ensure_ascii=False)
        return json.dumps(result, indent=2, ensure_ascii=False)

    return json.dumps(initial_data, indent=2, ensure_ascii=False)


def _handle_auth_error(data: dict) -> str:
    """Format auth error with contextual hints."""
    detail = data.get("detail", "")
    hint = ""
    if "htu" in detail.lower() or "dpop" in detail.lower():
        hint = " (DPoP URL mismatch — verify site_url matches site.url from agents.json)"
    elif "scope" in detail.lower():
        hint = " (try wais_discover to refresh agents.json)"
    elif "audience" in detail.lower() or "aud" in detail.lower():
        hint = " (site_url should be site.url from agents.json)"
    elif not detail:
        hint = " (is the user registered? try wais_register)"
    return f"Access denied: {detail}{hint}"
