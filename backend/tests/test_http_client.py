from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import HTTPException

from app.services.http_client import fetch_json, fetch_json_async


def _mock_response(status_code: int, json_data=None, raise_for_status=None):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    if raise_for_status:
        resp.raise_for_status.side_effect = raise_for_status
    else:
        resp.raise_for_status.return_value = None
    return resp


@pytest.mark.asyncio
async def test_successful_request():
    resp = _mock_response(200, {"url": "https://example.com/get"})
    mock_client = AsyncMock()
    mock_client.get.return_value = resp
    with patch("app.services.http_client.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await fetch_json_async("https://example.com/get", timeout=10)

    assert result is not None
    assert "url" in result


@pytest.mark.asyncio
async def test_404_handling():
    exc = httpx.HTTPStatusError(
        "404", request=MagicMock(), response=MagicMock(status_code=404)
    )
    resp = _mock_response(404)
    mock_client = AsyncMock()
    mock_client.get.return_value = resp
    with patch("app.services.http_client.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        with pytest.raises(HTTPException) as exc_info:
            await fetch_json_async(
                "https://example.com/status/404",
                timeout=10,
                not_found_detail="Resource not found",
            )

    assert exc_info.value.status_code == 404
    assert "Resource not found" in exc_info.value.detail


@pytest.mark.asyncio
async def test_timeout_handling():
    mock_client = AsyncMock()
    mock_client.get.side_effect = httpx.TimeoutException("timed out")
    with patch("app.services.http_client.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        with pytest.raises(HTTPException) as exc_info:
            await fetch_json_async("https://example.com/delay/5", timeout=2)

    assert exc_info.value.status_code == 504
    assert "timed out" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_500_error_handling():
    mock_resp = MagicMock(status_code=500)
    mock_client = AsyncMock()
    mock_client.get.side_effect = httpx.HTTPStatusError(
        "500", request=MagicMock(), response=mock_resp
    )
    with patch("app.services.http_client.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        with pytest.raises(HTTPException) as exc_info:
            await fetch_json_async("https://example.com/status/500", timeout=10)

    assert exc_info.value.status_code == 500


@pytest.mark.asyncio
async def test_custom_error_prefix():
    mock_resp = MagicMock(status_code=502)
    mock_client = AsyncMock()
    mock_client.get.side_effect = httpx.HTTPStatusError(
        "502", request=MagicMock(), response=mock_resp
    )
    with patch("app.services.http_client.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        custom_prefix = "Custom upstream error"
        with pytest.raises(HTTPException) as exc_info:
            await fetch_json_async(
                "https://example.com/status/502",
                timeout=10,
                upstream_error_prefix=custom_prefix,
            )

    assert custom_prefix in exc_info.value.detail


@pytest.mark.asyncio
async def test_json_parsing():
    payload = {"slideshow": {"title": "Sample Slide Show"}}
    resp = _mock_response(200, payload)
    mock_client = AsyncMock()
    mock_client.get.return_value = resp
    with patch("app.services.http_client.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await fetch_json_async("https://example.com/json", timeout=10)

    assert isinstance(result, dict)
    assert "slideshow" in result


class TestFetchJsonSync:
    def test_sync_wrapper_works(self):
        resp = _mock_response(200, {"url": "https://example.com/get"})
        mock_client = AsyncMock()
        mock_client.get.return_value = resp
        with patch("app.services.http_client.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            result = fetch_json("https://example.com/get", timeout=10)

        assert result is not None
        assert "url" in result

    def test_sync_wrapper_raises_in_async_context(self):
        async def try_sync_call():
            return fetch_json("https://example.com/get", timeout=10)

        with pytest.raises(RuntimeError) as exc_info:
            asyncio.run(try_sync_call())

        assert "async context" in str(exc_info.value)
        assert "fetch_json_async" in str(exc_info.value)
