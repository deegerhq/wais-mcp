"""Tool: wais_confirm — Confirm high-risk actions or complete payments."""

import json

from .._tool_client import get_client


async def wais_confirm(
    site_url: str,
    challenge_id: str,
) -> str:
    """Confirm a high-risk action or complete a payment challenge.

    Call after wais_execute returned a 402 confirmation challenge and the
    user has approved. If there was a payment link, the user must complete
    payment first. Polls for completion automatically if the challenge
    included a resolution object.

    Args:
        site_url: The site.url from agents.json.
        challenge_id: The challenge_id from the 402 response.
    """
    client = get_client()
    manifest = await client._get_manifest(site_url)

    result = await client.confirm(manifest, challenge_id)

    status = result.get("status")
    if status == "timeout":
        return f"Timed out waiting for confirmation. {result.get('error', '')}"
    if status == "expired":
        return "Challenge expired. Please try the action again."

    return json.dumps(result, indent=2, ensure_ascii=False)
