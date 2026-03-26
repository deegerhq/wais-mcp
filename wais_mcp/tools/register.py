"""Tool: wais_register — Register at a WAIS-compatible site."""

from typing import Optional

import httpx

from ..auth import PLATFORM_URL, WAIS_API_KEY, auth_headers
from ..http import safe_request
from ..session import get_manifest, get_token


async def wais_register(
    site_url: str,
    claims: Optional[list[str]] = None,
) -> str:
    """Register the user at a WAIS-compatible site using their WAIS identity.

    Uses SD-JWT selective disclosure — only shares the claims listed in
    agents.json data_requirements.registration.required_claims.

    Call wais_discover first to see what claims the site needs.

    Args:
        site_url: The site.url from agents.json.
        claims: Claims to disclose (e.g. ["email"]). If not provided,
                uses required_claims from agents.json automatically.
    """
    manifest = await get_manifest(site_url)

    if claims is None:
        req_claims, _ = manifest.get_registration_claims()
        claims = req_claims or ["email"]

    register_action = manifest.get_action("register")
    register_endpoint = "/wais/api/register"
    if register_action:
        register_endpoint = register_action.get("endpoint", register_endpoint)

    # Step 1: Get SD-JWT presentation from provider
    headers = {}
    if WAIS_API_KEY:
        headers["Authorization"] = f"Bearer {WAIS_API_KEY}"

    async with httpx.AsyncClient(base_url=PLATFORM_URL, timeout=10.0, headers=headers) as client:
        resp = await client.post("/api/vault/present", json={"disclose": claims})
        if resp.status_code == 401:
            return "Not authenticated with WAIS Provider. Check WAIS_API_KEY."
        if resp.status_code == 404:
            return "No identity credential in vault. Store personal data first at your WAIS Provider."
        resp.raise_for_status()
        presentation_data = resp.json()

    presentation = presentation_data.get("presentation", "")

    # Step 2: Get a token for the site
    site_identity = manifest.site_url or site_url
    scopes = manifest.get_all_scopes()
    token = await get_token(site_identity, scopes)

    # Step 3: Register at the site
    register_url = f"{manifest.api_base_url.rstrip('/')}{register_endpoint}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        hdrs = auth_headers(token, "POST", register_url)
        hdrs["X-WAIS-Identity"] = presentation
        resp = await safe_request(client, "POST", register_url, headers=hdrs, json={"claims": claims})
        if resp.status_code == 409:
            return "Already registered at this site. Proceed with wais_execute."
        if resp.status_code in (401, 403):
            detail = resp.json().get("detail", "")
            return f"Registration denied: {detail}"

    data = resp.json()
    disclosed = data.get("disclosed_claims", claims)
    return (
        f"Registered at {manifest.name}! "
        f"Shared only: {', '.join(disclosed)}. "
        f"Your other personal data was NOT disclosed."
    )
