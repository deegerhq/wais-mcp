"""Session state — token cache, site registry."""

import base64
import json
import sys
import time
from typing import Optional

import httpx

from .auth import PLATFORM_URL, WAIS_API_KEY, dpop_keypair
from .manifest import WAISManifest


# ── Token cache ──────────────────────────────────────────────

_token_cache: dict = {}  # {(audience, scopes_tuple): {token, exp}}


async def get_token(audience: str, scopes: list[str]) -> str:
    """Get or create a PoD token for a site, with caching.

    Access tokens are reusable within their lifetime. Per-request
    uniqueness is provided by DPoP proofs (unique jti per request).
    """
    cache_key = (audience, tuple(sorted(scopes)))
    cached = _token_cache.get(cache_key)
    if cached and cached["exp"] > time.time() + 60:
        return cached["token"]

    body = {
        "audience": audience,
        "scopes": scopes,
        "constraints": {},
        "ttl_seconds": 3600,
        "dpop_jwk": dpop_keypair.public_jwk,
    }
    headers = {}
    if WAIS_API_KEY:
        headers["Authorization"] = f"Bearer {WAIS_API_KEY}"
    async with httpx.AsyncClient(base_url=PLATFORM_URL, timeout=10.0) as client:
        resp = await client.post("/api/tokens", json=body, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    token = data["token"]
    parts = token.split(".")
    if len(parts) < 2:
        raise ValueError("Platform returned malformed token")
    payload_b64 = parts[1]
    padding = 4 - len(payload_b64) % 4
    if padding != 4:
        payload_b64 += "=" * padding
    payload = json.loads(base64.urlsafe_b64decode(payload_b64))
    _token_cache[cache_key] = {"token": token, "exp": payload["exp"]}
    return token


# ── Site registry (discovered sites) ────────────────────────

_sites: dict[str, WAISManifest] = {}  # {normalized_url: WAISManifest}
_pending_resolutions: dict = {}  # {challenge_id: {resolution, site_url, base_url}}


def _norm_url(url: str) -> str:
    """Normalize a URL for consistent cache lookups."""
    return url.rstrip("/").lower()


def store_manifest(site_url: str, manifest: WAISManifest) -> None:
    """Cache a manifest by URL, including canonical URL."""
    _sites[_norm_url(site_url)] = manifest
    if manifest.site_url:
        _sites[_norm_url(manifest.site_url)] = manifest


async def get_manifest(site_url: str) -> WAISManifest:
    """Look up cached manifest, auto-discovering if not found."""
    cached = _sites.get(_norm_url(site_url))
    if cached:
        return cached

    print(f"[wais-mcp] Cache miss for {site_url}, auto-discovering...", file=sys.stderr)
    try:
        manifest = await WAISManifest.from_url(site_url)
        store_manifest(site_url, manifest)
        print(f"[wais-mcp] Auto-discovered: api_base_url={manifest.api_base_url}", file=sys.stderr)
        return manifest
    except Exception as e:
        print(f"[wais-mcp] Auto-discover failed: {e}", file=sys.stderr)
    return WAISManifest({})


def store_resolution(challenge_id: str, resolution: dict, site_url: str, base_url: str) -> None:
    """Store a pending resolution for later confirmation polling."""
    _pending_resolutions[challenge_id] = {
        "resolution": resolution,
        "site_url": site_url,
        "base_url": base_url,
    }


def pop_resolution(challenge_id: str) -> Optional[dict]:
    """Pop a pending resolution by challenge ID."""
    return _pending_resolutions.pop(challenge_id, None)
