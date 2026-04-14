"""Tool: wais_status — Check account status at a WAIS-compatible site."""

import json

from .._tool_client import get_client


async def wais_status(site_url: str) -> str:
    """Check the user's account status at a WAIS-compatible site.

    Returns plan, credits, usage stats. The user must be registered first.
    Looks for a 'get_usage' or 'status' action in agents.json.

    Args:
        site_url: The site.url from agents.json.
    """
    client = get_client()
    manifest = await client._get_manifest(site_url)

    try:
        data = await client.status(manifest)
    except Exception as e:
        err = str(e)
        if "404" in err:
            return f"No status endpoint at {site_url}. Check agents.json actions for alternatives like 'get_usage'."
        if "401" in err or "403" in err:
            return f"Not authenticated at {site_url}. Register first with wais_register."
        raise

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
