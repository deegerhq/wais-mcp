"""Tool: wais_confirm — Confirm high-risk actions or complete payments."""

import json

import httpx

from ..auth import auth_headers
from ..http import safe_request
from ..polling import poll_for_result
from ..session import get_manifest, get_token, pop_resolution


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
    manifest = await get_manifest(site_url)
    site_identity = manifest.site_url or site_url
    scopes = manifest.get_all_scopes()
    token = await get_token(site_identity, scopes)

    # Check if we have a cached resolution for automatic polling
    cached = pop_resolution(challenge_id)
    if cached:
        resolution = cached["resolution"]
        poll_base = cached.get("base_url", manifest.api_base_url)
        result = await poll_for_result(
            resolution=resolution,
            site_url=poll_base,
            ref_values={"challenge_id": challenge_id},
            token=token,
        )
        if result["status"] == "completed":
            return json.dumps(result["data"], indent=2, ensure_ascii=False)
        if result["status"] == "timeout":
            return f"Timed out waiting for confirmation. {result.get('error', '')}"
        if result["status"] == "expired":
            return "Challenge expired. Please try the action again."
        return json.dumps(result, indent=2, ensure_ascii=False)

    # No cached resolution — send a single confirmation POST
    endpoint = f"{manifest.api_base_url.rstrip('/')}/wais/api/confirm"

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await safe_request(
            client, "POST", endpoint,
            headers=auth_headers(token, "POST", endpoint),
            json={"challenge_id": challenge_id},
        )

        if resp.status_code == 404:
            return "Challenge not found or expired. Try the action again."
        if resp.status_code == 410:
            return "Challenge expired. Please try the action again."
        if resp.status_code == 402:
            return "Payment not yet completed. The user must complete the payment link first."
        if resp.status_code == 202:
            body = resp.json()
            return f"Still processing: {body.get('status', 'pending')}. Try again in a few seconds."
        if resp.status_code in (401, 403):
            return f"Access denied: {resp.json().get('detail', '')}"

        resp.raise_for_status()
        data = resp.json()

    return json.dumps(data, indent=2, ensure_ascii=False)
