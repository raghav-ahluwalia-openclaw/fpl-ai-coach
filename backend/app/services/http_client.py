from __future__ import annotations

from typing import Any

import httpx
from fastapi import HTTPException


async def fetch_json_async(
    url: str,
    *,
    timeout: int = 25,
    not_found_detail: str | None = None,
    upstream_error_prefix: str = "Upstream request failed",
) -> Any:
    """
    Async HTTP GET request with proper error handling.
    
    Uses httpx for non-blocking I/O, improving performance under load.
    
    Args:
        url: Target URL to fetch
        timeout: Request timeout in seconds
        not_found_detail: Custom 404 error message
        upstream_error_prefix: Prefix for upstream error messages
    
    Returns:
        Parsed JSON response
    
    Raises:
        HTTPException: With appropriate status code and detail
    """
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=timeout)
            if response.status_code == 404 and not_found_detail:
                raise HTTPException(status_code=404, detail=not_found_detail)
            response.raise_for_status()
            return response.json()
        except HTTPException:
            raise
        except httpx.TimeoutException as exc:
            raise HTTPException(
                status_code=504,
                detail=f"{upstream_error_prefix}: Request timed out after {timeout}s"
            ) from exc
        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=502,
                detail=f"{upstream_error_prefix}: {exc}"
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise HTTPException(
                status_code=exc.response.status_code,
                detail=f"{upstream_error_prefix}: {exc.response.status_code}"
            ) from exc


# Backward compatibility wrapper for sync code (deprecated - migrate to async)
def fetch_json(
    url: str,
    *,
    timeout: int = 25,
    not_found_detail: str | None = None,
    upstream_error_prefix: str = "Upstream request failed",
) -> Any:
    """
    DEPRECATED: Synchronous wrapper for backward compatibility.
    
    Migrate to fetch_json_async() for better performance.
    """
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    if loop.is_running():
        # If we're in an async context, we can't use run_until_complete
        # This shouldn't happen in properly migrated code
        raise RuntimeError(
            "fetch_json() called from async context. "
            "Use fetch_json_async() instead."
        )
    
    return loop.run_until_complete(
        fetch_json_async(
            url,
            timeout=timeout,
            not_found_detail=not_found_detail,
            upstream_error_prefix=upstream_error_prefix,
        )
    )


__all__ = ["fetch_json_async", "fetch_json"]
