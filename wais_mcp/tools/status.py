"""Tool: wais_status — Check account status at a WAIS-compatible site."""

import json

import httpx

from ..auth import auth_headers
from ..http import safe_request
from ..session import get_manifest, get_token


async def wais_status(site_url: str) -> str:
    """Check the user's account status at a WAIS-compatible site.

    Returns plan, credits, usage stats. The user must be registered first.
    Looks for a 'get_usage' or 'status' action in agents.json.

    Args:
        site_url: The site.url from agents.json.
    """
    manifest = await get_manifest(site_url)
    site_identity = manifest.site_url or site_url
    scopes = manifest.get_all_scopes()
    token = await get_token(site_identity, scopes)

    status_action = manifest.get_action("get_usage") or manifest.get_action("status")
    if status_action:
        endpoint = status_action.get("endpoint", "/wais/api/status")
        method = status_action.get("method", "GET").upper()
    else:
        endpoint = "/wais/api/status"
        method = "GET"

    full_url = f"{manifest.api_base_url.rstrip('/')}{endpoint}"

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await safe_request(
            client, method, full_url,
            headers=auth_headers(token, method, full_url),
            **({"json": {}} if method != "GET" else {}),
        )

        if resp.status_code == 404:
            return f"No status endpoint at {site_url}. Check agents.json actions for alternatives like 'get_usage'."
        if resp.status_code in (401, 403):
            return f"Not authenticated at {site_url}. Register first with wais_register."
        resp.raise_for_status()
        data = resp.json()

    lines = []
    if "plan" in data:
        lines.append(f"Plan: {data['plan']}")
    if "credits" in data or "credits_remaining" in data:
        lines.append(f"Credits: {data.get('credits', data.get('credits_remaining'))}")
    if "status" in data:
        lines.append(f"Status: {data['status']}")
    if "identity" in data:
        lines.append(f"Identity: {data['identity']}")
    if "period_end" in data:
        lines.append(f"Period ends: {data['period_end']}")
    if not lines:
        return json.dumps(data, indent=2, ensure_ascii=False)
    return "\n".join(lines)
