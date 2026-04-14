"""Shared WAISClient singleton for MCP tools.

The MCP server tools all share one WAISClient instance (one DPoP keypair,
one token cache, one site cache per session). This module lazily creates it
from environment variables.
"""

from .auth import PLATFORM_URL, WAIS_API_KEY
from .client import WAISClient

_client: WAISClient | None = None


def get_client() -> WAISClient:
    """Get or create the shared WAISClient for MCP tools."""
    global _client
    if _client is None:
        _client = WAISClient(api_key=WAIS_API_KEY, platform_url=PLATFORM_URL)
    return _client
