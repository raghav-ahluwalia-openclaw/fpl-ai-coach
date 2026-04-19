from __future__ import annotations

import asyncio
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
    """Async HTTP GET — use this in async route handlers."""
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
                detail=f"{upstream_error_prefix}: Request timed out after {timeout}s",
            ) from exc
        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=502,
                detail=f"{upstream_error_prefix}: {exc}",
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise HTTPException(
                status_code=exc.response.status_code,
                detail=f"{upstream_error_prefix}: {exc.response.status_code}",
            ) from exc


def fetch_json(
    url: str,
    *,
    timeout: int = 25,
    not_found_detail: str | None = None,
    upstream_error_prefix: str = "Upstream request failed",
) -> Any:
    """Synchronous HTTP GET for use in sync route handlers (runs in FastAPI threadpool).

    Uses asyncio.run() which is safe in threadpool threads (no running event loop).
    Do NOT call from within an async function — use fetch_json_async() there.
    """
    try:
        return asyncio.run(
            fetch_json_async(
                url,
                timeout=timeout,
                not_found_detail=not_found_detail,
                upstream_error_prefix=upstream_error_prefix,
            )
        )
    except RuntimeError as exc:
        if "running event loop" in str(exc):
            raise RuntimeError(
                "fetch_json() cannot be called from an async context. "
                "Use fetch_json_async() instead."
            ) from exc
        raise


__all__ = ["fetch_json_async", "fetch_json"]
