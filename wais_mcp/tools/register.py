"""Tool: wais_register — Register at a WAIS-compatible site."""

from typing import Optional

from .._tool_client import get_client


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
    client = get_client()
    manifest = await client._get_manifest(site_url)

    try:
        data = await client.register(manifest, claims)
    except Exception as e:
        err = str(e)
        if "401" in err:
            return "Not authenticated with WAIS Provider. Check WAIS_API_KEY."
        if "404" in err:
            return "No identity credential in vault. Store personal data first at your WAIS Provider."
        if "409" in err:
            return "Already registered at this site. Proceed with wais_execute."
        raise

    disclosed = data.get("disclosed_claims", claims or [])
    return (
        f"Registered at {manifest.name}! "
        f"Shared only: {', '.join(disclosed)}. "
        f"Your other personal data was NOT disclosed."
    )
