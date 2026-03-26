"""WAISManifest — parser for agents.json manifests.

Local implementation for wais-mcp. When wais-pod publishes manifest.py,
this can be replaced with: from pod.manifest import WAISManifest
"""

import sys
from typing import Optional

import httpx


class WAISManifest:
    """Parse and work with agents.json manifests."""

    def __init__(self, data: dict) -> None:
        self._data = data
        self._site = data.get("site", {})
        self._actions = data.get("actions", [])
        self._actions_by_id = {a["id"]: a for a in self._actions if "id" in a}

    @classmethod
    async def from_url(cls, url: str) -> "WAISManifest":
        """Fetch and parse agents.json from a site."""
        agents_url = f"{url.rstrip('/')}/.well-known/agents.json"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(agents_url)
            resp.raise_for_status()
            return cls(resp.json())

    @classmethod
    def from_dict(cls, data: dict) -> "WAISManifest":
        """Parse from a dict (already loaded JSON)."""
        return cls(data)

    @property
    def raw(self) -> dict:
        """Access the raw agents.json dict."""
        return self._data

    @property
    def site_url(self) -> str:
        """Site identity URL (used as token audience)."""
        return self._site.get("url", self._data.get("site_url", ""))

    @property
    def api_base_url(self) -> str:
        """Base URL for API requests. Falls back to site_url."""
        return self._site.get("api_base_url", "") or self.site_url

    @property
    def name(self) -> str:
        return self._site.get("name", self._data.get("name", "Unknown"))

    @property
    def description(self) -> str:
        return self._site.get("description", self._data.get("description", ""))

    @property
    def wais_version(self) -> str:
        return self._data.get("wais_version", "?")

    @property
    def auth_methods(self) -> list[str]:
        auth = self._data.get("authentication", {})
        return auth.get("methods", self._data.get("auth_methods", []))

    @property
    def constraints(self) -> dict:
        return self._data.get("constraints_supported", {})

    @property
    def payment(self) -> dict:
        return self._data.get("payment", {})

    def resolve_endpoint(self, action_id: str, params: Optional[dict] = None) -> str:
        """Full URL for an action: api_base_url + action.endpoint.

        Interpolates path params if provided (e.g. /v1/jobs/{job_id}).
        """
        action = self.get_action(action_id)
        if not action:
            return ""
        endpoint = action.get("endpoint", f"/wais/api/{action_id}")
        if params:
            try:
                endpoint = endpoint.format(**params)
            except KeyError:
                pass
        return f"{self.api_base_url.rstrip('/')}{endpoint}"

    def get_action(self, action_id: str) -> Optional[dict]:
        """Find an action by ID."""
        return self._actions_by_id.get(action_id)

    def list_actions(self) -> list[dict]:
        """All actions from agents.json."""
        return self._actions

    def list_action_ids(self) -> list[str]:
        """All action IDs."""
        return list(self._actions_by_id.keys())

    def get_effective_risk(self, action_id: str) -> str:
        """Resolve risk level using hybrid model + override rules."""
        action = self.get_action(action_id)
        if not action:
            return "unknown"
        return action.get("risk_level", "standard")

    def get_required_scopes(self, action_id: str) -> list[str]:
        """Scopes required for a specific action."""
        action = self.get_action(action_id)
        if not action:
            return []
        scopes = []
        scope = action.get("scope", "")
        if scope:
            scopes.append(scope)
        scopes.extend(action.get("required_scopes", []))
        return scopes

    def get_all_scopes(self) -> list[str]:
        """Collect all scopes from agents.json (new or legacy format)."""
        if self._actions:
            scopes = set()
            for action in self._actions:
                scope = action.get("scope", "")
                if scope:
                    scopes.add(scope)
                for s in action.get("required_scopes", []):
                    scopes.add(s)
            return list(scopes) if scopes else ["api.access"]
        return list(self._data.get("scopes", {}).keys()) or ["api.access"]

    def is_async(self, action_id: str) -> bool:
        """Whether an action uses async polling."""
        action = self.get_action(action_id)
        if not action:
            return False
        return "async" in action

    def get_resolution(self, action_id: str) -> Optional[dict]:
        """Get async resolution config for an action."""
        action = self.get_action(action_id)
        if not action:
            return None
        return action.get("async")

    def get_registration_claims(self) -> tuple[list[str], list[str]]:
        """Returns (required_claims, optional_claims)."""
        reg = self._data.get("data_requirements", {}).get("registration", {})
        return (
            reg.get("required_claims", []),
            reg.get("optional_claims", []),
        )
