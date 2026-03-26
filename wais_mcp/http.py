"""HTTP helpers — safe request execution with error handling."""

import httpx


async def safe_request(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    **kwargs,
) -> httpx.Response:
    """Execute an HTTP request, raising a descriptive error on 5xx.

    Instead of a generic httpx error, includes the response body
    when available for better debugging.
    """
    resp = await client.request(method, url, **kwargs)
    if resp.status_code >= 500:
        try:
            body = resp.json()
            detail = body.get("detail", body.get("error", resp.text[:500]))
        except Exception:
            detail = resp.text[:500] if resp.text else f"HTTP {resp.status_code}"
        raise httpx.HTTPStatusError(
            f"Server error {resp.status_code}: {detail}",
            request=resp.request,
            response=resp,
        )
    return resp
