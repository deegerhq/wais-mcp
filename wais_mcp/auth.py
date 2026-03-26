"""Authentication helpers — API key loading, header construction."""

import os
import subprocess
import sys

from pod.dpop import DPoPKeyPair


PLATFORM_URL = os.environ.get("PLATFORM_URL", "https://pod.deeger.io")


def _load_api_key() -> str:
    """Load API key from env var, falling back to macOS Keychain."""
    key = os.environ.get("WAIS_API_KEY", "")
    if key:
        return key
    if sys.platform == "darwin":
        try:
            result = subprocess.run(
                ["security", "find-generic-password", "-s", "wais-api", "-a", "api-key", "-w"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
    return ""


WAIS_API_KEY = _load_api_key()

# One DPoP keypair per session
dpop_keypair = DPoPKeyPair.generate()


def auth_headers(token: str, method: str, url: str) -> dict:
    """Build Authorization + DPoP headers with a fresh proof."""
    print(f"[wais-mcp] DPoP proof: htm={method} htu={url}", file=sys.stderr)
    return {
        "Authorization": f"DPoP {token}",
        "DPoP": dpop_keypair.create_proof(method, url, token),
    }
