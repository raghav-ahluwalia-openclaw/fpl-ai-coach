from __future__ import annotations

import hashlib
import hmac
import os
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Deque

from fastapi import HTTPException, Request, status


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


ENVIRONMENT = os.getenv("ENVIRONMENT", "development").strip().lower()
API_KEY = os.getenv("API_KEY", "").strip()
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "").strip()

RATE_LIMIT_TIMES = int(os.getenv("RATE_LIMIT_TIMES", "10"))
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))

# By default, diagnostics are protected in production and open in development.
DIAGNOSTICS_REQUIRE_ADMIN = _env_bool(
    "DIAGNOSTICS_REQUIRE_ADMIN",
    default=(ENVIRONMENT == "production"),
)


@dataclass(frozen=True)
class AuthContext:
    authenticated: bool
    is_admin: bool
    identity: str


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._hits: dict[str, Deque[float]] = defaultdict(deque)

    def enforce(self, key: str, limit: int, window_seconds: int) -> None:
        now = time.time()
        floor = now - window_seconds

        with self._lock:
            bucket = self._hits[key]
            while bucket and bucket[0] < floor:
                bucket.popleft()

            if len(bucket) >= limit:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded ({limit}/{window_seconds}s)",
                )

            bucket.append(now)


_rate_limiter = InMemoryRateLimiter()


def _extract_bearer_token(request: Request) -> str:
    auth = request.headers.get("authorization", "").strip()
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return ""


def _safe_prefix(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:12]


def _configured_tokens() -> tuple[str, str]:
    return API_KEY, ADMIN_API_KEY


def _misconfigured_auth_response() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Auth is not configured: set API_KEY and ADMIN_API_KEY",
    )


def get_auth_context(request: Request) -> AuthContext:
    api_key, admin_key = _configured_tokens()
    if not api_key or not admin_key:
        # Fail closed for protected operations.
        raise _misconfigured_auth_response()

    presented = (
        request.headers.get("x-admin-token", "").strip()
        or request.headers.get("x-api-key", "").strip()
        or _extract_bearer_token(request)
    )

    if not presented:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing API token")

    if hmac.compare_digest(presented, admin_key):
        return AuthContext(authenticated=True, is_admin=True, identity=f"admin:{_safe_prefix(presented)}")

    if hmac.compare_digest(presented, api_key):
        return AuthContext(authenticated=True, is_admin=False, identity=f"user:{_safe_prefix(presented)}")

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API token")


def require_authenticated(request: Request) -> AuthContext:
    return get_auth_context(request)


def require_admin(request: Request) -> AuthContext:
    auth = get_auth_context(request)
    if not auth.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin token required")
    return auth


def diagnostics_access_check(request: Request) -> None:
    if DIAGNOSTICS_REQUIRE_ADMIN:
        require_admin(request)


def request_scope_identity(request: Request) -> str:
    """Stable scope identity without trusting spoofable forwarding headers."""
    try:
        auth = get_auth_context(request)
        return auth.identity
    except HTTPException:
        pass

    client_ip = request.client.host if request.client else "unknown"
    ua = request.headers.get("user-agent", "unknown")[:120]
    digest = hashlib.sha256(f"{client_ip}|{ua}".encode("utf-8")).hexdigest()[:16]
    return f"anon:{digest}"


def enforce_write_rate_limit(request: Request, bucket: str = "write") -> None:
    identity = request_scope_identity(request)
    key = f"{bucket}:{identity}"
    _rate_limiter.enforce(key=key, limit=RATE_LIMIT_TIMES, window_seconds=RATE_LIMIT_WINDOW_SECONDS)


def rate_limit_write_ops(request: Request) -> None:
    enforce_write_rate_limit(request, bucket="write")


def rate_limit_admin_ops(request: Request) -> None:
    # Admin endpoints can still share same global policy; separate bucket for clearer telemetry.
    enforce_write_rate_limit(request, bucket="admin")
