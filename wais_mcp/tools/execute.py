"""Tool: wais_execute — Execute an action at a WAIS-compatible site."""

import json
from typing import Optional

from .._tool_client import get_client


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
    client = get_client()
    manifest = await client._get_manifest(site_url)

    try:
        data = await client.execute(manifest, action_id, params)
    except ValueError as e:
        # Unknown action_id
        return str(e) + " Run wais_discover to see details for each action."
    except Exception as e:
        err = str(e)
        if "401" in err or "403" in err:
            return _handle_auth_error(err)
        raise

    # 402: Confirmation required
    if "wais_confirmation" in data:
        return _format_402(data, action_id)

    return json.dumps(data, indent=2, ensure_ascii=False)


def _format_402(data: dict, action_id: str) -> str:
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
        lines.append("")
        lines.append("This action supports automatic polling for completion.")
        lines.append("After the user approves/pays, call wais_confirm with the challenge_id.")
    else:
        lines.append("")
        lines.append("Ask the user if they want to proceed, then call wais_confirm with the challenge_id.")

    return "\n".join(lines)


def _handle_auth_error(err: str) -> str:
    hint = ""
    lower = err.lower()
    if "htu" in lower or "dpop" in lower:
        hint = " (DPoP URL mismatch — verify site_url matches site.url from agents.json)"
    elif "scope" in lower:
        hint = " (try wais_discover to refresh agents.json)"
    elif "audience" in lower or "aud" in lower:
        hint = " (site_url should be site.url from agents.json)"
    else:
        hint = " (is the user registered? try wais_register)"
    return f"Access denied: {err}{hint}"
