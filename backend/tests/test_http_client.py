"""
Unit tests for HTTP client service.

Tests cover:
- Async HTTP requests
- Error handling
- Timeout behavior
- Status code handling
"""
import pytest
from fastapi import HTTPException
import httpx

from app.services.http_client import fetch_json_async


@pytest.mark.asyncio
async def test_successful_request():
    """Test successful HTTP request with httpbin."""
    url = "https://httpbin.org/get"
    result = await fetch_json_async(url, timeout=10)
    
    assert result is not None
    assert "url" in result
    assert result["url"] == url


@pytest.mark.asyncio
async def test_404_handling():
    """Test 404 error handling with custom message."""
    url = "https://httpbin.org/status/404"
    
    with pytest.raises(HTTPException) as exc_info:
        await fetch_json_async(
            url,
            timeout=10,
            not_found_detail="Resource not found"
        )
    
    assert exc_info.value.status_code == 404
    assert "Resource not found" in exc_info.value.detail


@pytest.mark.asyncio
async def test_timeout_handling():
    """Test timeout error handling."""
    # httpbin.org/delay/5 will delay for 5 seconds
    url = "https://httpbin.org/delay/5"
    
    with pytest.raises(HTTPException) as exc_info:
        await fetch_json_async(url, timeout=2)
    
    assert exc_info.value.status_code == 504
    assert "timed out" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_500_error_handling():
    """Test 500 error handling."""
    url = "https://httpbin.org/status/500"
    
    with pytest.raises(HTTPException) as exc_info:
        await fetch_json_async(url, timeout=10)
    
    assert exc_info.value.status_code == 500


@pytest.mark.asyncio
async def test_custom_error_prefix():
    """Test custom error prefix in error messages."""
    url = "https://httpbin.org/status/502"
    custom_prefix = "Custom upstream error"
    
    with pytest.raises(HTTPException) as exc_info:
        await fetch_json_async(
            url,
            timeout=10,
            upstream_error_prefix=custom_prefix
        )
    
    assert custom_prefix in exc_info.value.detail


@pytest.mark.asyncio
async def test_json_parsing():
    """Test that response is properly parsed as JSON."""
    url = "https://httpbin.org/json"
    result = await fetch_json_async(url, timeout=10)
    
    assert isinstance(result, dict)
    assert "slideshow" in result


class TestFetchJsonSync:
    """Test backward compatibility sync wrapper."""
    
    def test_sync_wrapper_works(self):
        """Test that sync wrapper still works for backward compatibility."""
        from app.services.http_client import fetch_json
        
        url = "https://httpbin.org/get"
        result = fetch_json(url, timeout=10)
        
        assert result is not None
        assert "url" in result
    
    def test_sync_wrapper_raises_in_async_context(self):
        """Test that sync wrapper raises error if called from async context."""
        from app.services.http_client import fetch_json
        import asyncio
        
        async def try_sync_call():
            url = "https://httpbin.org/get"
            return fetch_json(url, timeout=10)
        
        with pytest.raises(RuntimeError) as exc_info:
            asyncio.run(try_sync_call())
        
        assert "async context" in str(exc_info.value)
        assert "fetch_json_async" in str(exc_info.value)
