"""WAISClient — SDK for interacting with WAIS-compatible sites.

Works with any Python agent framework (OpenAI, LangChain, CrewAI, etc.)
or standalone scripts. No MCP required.

Usage:
    from wais_mcp import WAISClient

    client = WAISClient(api_key="...")
    site = await client.discover("https://serphub.deeger.io")
    await client.register(site)
    result = await client.execute(site, "search", {"query": "python"})
"""

import base64
import json
import sys
import time
from typing import Optional

import httpx
from pod.dpop import DPoPKeyPair

from .http import safe_request
from .manifest import WAISManifest
from .polling import poll_for_result


class WAISClient:
    """Async client for interacting with WAIS-compatible sites.

    Manages DPoP keypairs, token caching, site discovery, and all
    5 WAIS operations: discover, register, execute, confirm, status.
    """

    def __init__(
        self,
        api_key: str = "",
        platform_url: str = "https://pod.deeger.io",
    ) -> None:
        self._api_key = api_key
        self._platform_url = platform_url
        self._dpop = DPoPKeyPair.generate()
        self._token_cache: dict = {}
        self._sites: dict[str, WAISManifest] = {}
        self._pending_resolutions: dict = {}

    # ── Token management ─────────────────────────────────────

    async def _get_token(self, audience: str, scopes: list[str]) -> str:
        cache_key = (audience, tuple(sorted(scopes)))
        cached = self._token_cache.get(cache_key)
        if cached and cached["exp"] > time.time() + 60:
            return cached["token"]

        body = {
            "audience": audience,
            "scopes": scopes,
            "constraints": {},
            "ttl_seconds": 3600,
            "dpop_jwk": self._dpop.public_jwk,
        }
        headers = {}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        async with httpx.AsyncClient(base_url=self._platform_url, timeout=10.0) as client:
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
        self._token_cache[cache_key] = {"token": token, "exp": payload["exp"]}
        return token

    def _auth_headers(self, token: str, method: str, url: str) -> dict:
        return {
            "Authorization": f"DPoP {token}",
            "DPoP": self._dpop.create_proof(method, url, token),
        }

    # ── Site cache ───────────────────────────────────────────

    def _norm_url(self, url: str) -> str:
        return url.rstrip("/").lower()

    def _cache_manifest(self, site_url: str, manifest: WAISManifest) -> None:
        self._sites[self._norm_url(site_url)] = manifest
        if manifest.site_url:
            self._sites[self._norm_url(manifest.site_url)] = manifest

    async def _get_manifest(self, site_url: str) -> WAISManifest:
        cached = self._sites.get(self._norm_url(site_url))
        if cached:
            return cached
        manifest = await WAISManifest.from_url(site_url)
        self._cache_manifest(site_url, manifest)
        return manifest

    async def _site_token(self, manifest: WAISManifest, site_url: str) -> str:
        site_identity = manifest.site_url or site_url
        scopes = manifest.get_all_scopes()
        return await self._get_token(site_identity, scopes)

    # ── Public API ───────────────────────────────────────────

    async def discover(self, site_url: str) -> WAISManifest:
        """Discover what a WAIS-compatible site offers.

        Fetches /.well-known/agents.json and returns a WAISManifest.

        Args:
            site_url: The site's URL (e.g. "https://serphub.deeger.io").

        Returns:
            WAISManifest with all site info, actions, scopes, etc.
        """
        url = f"{site_url.rstrip('/')}/.well-known/agents.json"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()

        manifest = WAISManifest.from_dict(resp.json())
        self._cache_manifest(site_url, manifest)
        return manifest

    async def register(
        self,
        site: WAISManifest,
        claims: Optional[list[str]] = None,
    ) -> dict:
        """Register the user at a site using SD-JWT selective disclosure.

        Args:
            site: WAISManifest from discover().
            claims: Claims to disclose. Defaults to site's required_claims.

        Returns:
            Registration response dict.
        """
        if claims is None:
            req_claims, _ = site.get_registration_claims()
            claims = req_claims or ["email"]

        register_action = site.get_action("register")
        register_endpoint = "/wais/api/register"
        if register_action:
            register_endpoint = register_action.get("endpoint", register_endpoint)

        # Get SD-JWT presentation from provider
        headers = {}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        async with httpx.AsyncClient(base_url=self._platform_url, timeout=10.0, headers=headers) as client:
            resp = await client.post("/api/vault/present", json={"disclose": claims})
            resp.raise_for_status()
            presentation = resp.json().get("presentation", "")

        # Register at the site
        token = await self._site_token(site, site.site_url)
        register_url = f"{site.api_base_url.rstrip('/')}{register_endpoint}"

        async with httpx.AsyncClient(timeout=10.0) as client:
            hdrs = self._auth_headers(token, "POST", register_url)
            hdrs["X-WAIS-Identity"] = presentation
            resp = await safe_request(client, "POST", register_url, headers=hdrs, json={"claims": claims})
            return resp.json()

    async def execute(
        self,
        site: WAISManifest,
        action_id: str,
        params: Optional[dict] = None,
    ) -> dict:
        """Execute an action at a WAIS-compatible site.

        Handles token auth, DPoP, endpoint resolution, async polling,
        and 402 confirmation challenges automatically.

        Args:
            site: WAISManifest from discover().
            action_id: Action ID from agents.json.
            params: Parameters matching the action's input_schema.

        Returns:
            Response dict. If 402, includes wais_confirmation challenge.
        """
        token = await self._site_token(site, site.site_url)
        action = site.get_action(action_id)

        if not action:
            valid_ids = site.list_action_ids()
            raise ValueError(
                f"Unknown action_id: '{action_id}'. "
                f"Valid: {', '.join(valid_ids)}"
            )

        method = action.get("method", "POST").upper()
        full_url = site.resolve_endpoint(action_id, params)

        async with httpx.AsyncClient(timeout=30.0) as client:
            request_headers = self._auth_headers(token, method, full_url)

            if method in ("POST", "PUT", "PATCH"):
                resp = await safe_request(
                    client, method, full_url, headers=request_headers, json=params or {},
                )
            else:
                resp = await safe_request(client, method, full_url, headers=request_headers)

            # 402: Confirmation required
            if resp.status_code == 402:
                data = resp.json()
                challenge = data.get("wais_confirmation", {})
                resolution = challenge.get("resolution")
                challenge_id = challenge.get("challenge_id", "")
                if resolution and challenge_id:
                    self._pending_resolutions[challenge_id] = {
                        "resolution": resolution,
                        "site_url": site.site_url,
                        "base_url": site.api_base_url,
                    }
                return data

            # 202: Async action
            if resp.status_code == 202:
                initial_data = resp.json()
                async_config = action.get("async")
                if async_config:
                    ref_values = {}
                    for key in ("job_id", "task_id", "submission_id", "request_id", "id"):
                        if key in initial_data:
                            ref_values[key] = initial_data[key]
                            break
                    result = await poll_for_result(
                        resolution=async_config,
                        site_url=site.api_base_url,
                        ref_values=ref_values,
                        token=token,
                    )
                    return result
                return initial_data

            resp.raise_for_status()
            return resp.json()

    async def confirm(
        self,
        site: WAISManifest,
        challenge_id: str,
    ) -> dict:
        """Confirm a high-risk action or complete a payment.

        Args:
            site: WAISManifest from discover().
            challenge_id: Challenge ID from a 402 response.

        Returns:
            Confirmation result dict.
        """
        token = await self._site_token(site, site.site_url)

        cached = self._pending_resolutions.pop(challenge_id, None)
        if cached:
            result = await poll_for_result(
                resolution=cached["resolution"],
                site_url=cached.get("base_url", site.api_base_url),
                ref_values={"challenge_id": challenge_id},
                token=token,
            )
            return result

        endpoint = f"{site.api_base_url.rstrip('/')}/wais/api/confirm"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await safe_request(
                client, "POST", endpoint,
                headers=self._auth_headers(token, "POST", endpoint),
                json={"challenge_id": challenge_id},
            )
            return resp.json()

    async def status(self, site: WAISManifest) -> dict:
        """Check account status at a site.

        Args:
            site: WAISManifest from discover().

        Returns:
            Status dict (plan, credits, usage, etc.)
        """
        token = await self._site_token(site, site.site_url)

        status_action = site.get_action("get_usage") or site.get_action("status")
        if status_action:
            endpoint = status_action.get("endpoint", "/wais/api/status")
            method = status_action.get("method", "GET").upper()
        else:
            endpoint = "/wais/api/status"
            method = "GET"

        full_url = f"{site.api_base_url.rstrip('/')}{endpoint}"

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await safe_request(
                client, method, full_url,
                headers=self._auth_headers(token, method, full_url),
                **({"json": {}} if method != "GET" else {}),
            )
            resp.raise_for_status()
            return resp.json()
