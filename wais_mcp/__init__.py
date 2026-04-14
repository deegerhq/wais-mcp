"""Universal WAIS MCP server and SDK for any WAIS-compatible site."""

__version__ = "0.2.2"

from .client import WAISClient
from .manifest import WAISManifest

__all__ = ["WAISClient", "WAISManifest"]
