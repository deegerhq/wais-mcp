"""Async polling for WAIS operations (async APIs, payment confirmation)."""

import asyncio
import time
from typing import Optional

import httpx

from .auth import auth_headers


async def poll_for_result(
    resolution: dict,
    site_url: str,
    ref_values: Optional[dict] = None,
    token: Optional[str] = None,
) -> dict:
    """Universal polling function for any async WAIS operation.

    Works for: async APIs, payment confirmation, long-running actions.

    Args:
        resolution: The resolution/async object from agents.json or 402 challenge.
        site_url: Base URL of the WAIS site.
        ref_values: Values to interpolate into endpoint template,
            e.g. {"job_id": "j_123"} or {"challenge_id": "conf_abc"}.
        token: PoD token for authenticated polling.
    """
    endpoint_template = resolution.get("endpoint", resolution.get("status_endpoint", ""))
    if ref_values:
        try:
            endpoint = endpoint_template.format(**ref_values)
        except KeyError:
            endpoint = endpoint_template
    else:
        endpoint = endpoint_template
    full_url = f"{site_url.rstrip('/')}{endpoint}"

    interval = resolution.get("interval_seconds", 5)
    max_attempts = resolution.get("max_attempts", 60)
    timeout = resolution.get("timeout_seconds", 300)
    statuses = resolution.get("statuses", {
        "pending": 202, "completed": 200, "failed": 422, "expired": 410,
    })

    pending_code = statuses.get("pending", 202)
    completed_code = statuses.get("completed", 200)
    failed_code = statuses.get("failed", 422)
    expired_code = statuses.get("expired", 410)

    start_time = time.time()

    async with httpx.AsyncClient(timeout=30.0) as client:
        for attempt in range(max_attempts):
            if time.time() - start_time > timeout:
                return {"status": "timeout", "error": "Operation timed out"}

            headers = auth_headers(token, "GET", full_url) if token else {}
            resp = await client.get(full_url, headers=headers)

            if resp.status_code == completed_code:
                return {"status": "completed", "data": resp.json()}

            if resp.status_code == pending_code:
                await asyncio.sleep(interval)
                continue

            if resp.status_code == failed_code:
                return {"status": "failed", "error": resp.json()}

            if resp.status_code == expired_code:
                return {"status": "expired", "error": "Operation expired or cancelled"}

            return {"status": "error", "error": f"Unexpected status {resp.status_code}"}

    return {"status": "timeout", "error": f"Max attempts ({max_attempts}) reached"}
