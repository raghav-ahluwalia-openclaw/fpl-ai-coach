from __future__ import annotations

import logging
import os
import time
import uuid
from contextlib import asynccontextmanager

import httpx
import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi_limiter import FastAPILimiter
from prometheus_fastapi_instrumentator import Instrumentator
from redis import Redis
from sqlalchemy.exc import SQLAlchemyError

import app.db.models  # noqa: F401  # ensure models are imported before create_all
from app.api.routes import router as fpl_router
from app.core.errors import register_error_handlers
from app.core.security import ENVIRONMENT
from app.db import Base, engine

# =============================================================================
# Structured Logging Configuration
# =============================================================================
LOG_FORMAT = os.getenv("LOG_FORMAT", "console")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

if LOG_FORMAT == "json":
    # Production: JSON structured logging
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, LOG_LEVEL, logging.INFO)),
        logger_factory=structlog.PrintLoggerFactory(),
    )
else:
    # Development: Console with colors
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(colors=True),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, LOG_LEVEL, logging.INFO)),
        logger_factory=structlog.PrintLoggerFactory(),
    )

logger = structlog.get_logger("fpl")


# =============================================================================
# Application Lifespan Manager
# =============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager for startup/shutdown events.
    
    Handles:
    - Database initialization
    - Rate limiter setup
    - Structured logging
    - Graceful shutdown
    """
    # Startup
    logger.info("Starting FPL AI Coach API", extra={"version": "0.8.0"})
    
    # Initialize database
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database initialized successfully")
    except SQLAlchemyError as e:
        logger.error("Database initialization failed", extra={"error": str(e)})
        raise
    
    # Initialize optional Redis-backed limiter (route-level in-memory limiter still applies)
    app.state.fastapi_limiter_ready = False
    redis_url = os.getenv("REDIS_URL", "").strip()
    if redis_url:
        try:
            redis_client = Redis.from_url(redis_url, decode_responses=True)
            await FastAPILimiter.init(redis_client)
            app.state.fastapi_limiter_ready = True
            logger.info("Rate limiter initialized with Redis")
        except Exception as e:
            logger.warning("Redis connection failed; continuing with in-process limiter", extra={"error": str(e)})
    else:
        logger.info("REDIS_URL not set; using in-process limiter only")

    yield

    # Shutdown
    logger.info("Shutting down FPL AI Coach API")
    if getattr(app.state, "fastapi_limiter_ready", False):
        try:
            await FastAPILimiter.close()
        except Exception as e:
            logger.warning("Rate limiter shutdown skipped after error", extra={"error": str(e)})


# =============================================================================
# Application Factory
# =============================================================================
# Security: API docs are disabled by default in production.
# Explicitly set ENABLE_API_DOCS=true in .env to override.
enable_api_docs = os.getenv("ENABLE_API_DOCS", "1" if ENVIRONMENT != "production" else "0").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

app = FastAPI(
    title="FPL AI Coach API",
    version="0.8.0",
    description="AI-powered Fantasy Premier League assistant with transfer planning, captaincy decisions, and team optimization.",
    docs_url="/docs" if enable_api_docs else None,
    redoc_url="/redoc" if enable_api_docs else None,
    openapi_url="/openapi.json" if enable_api_docs else None,
    lifespan=lifespan,
)

# =============================================================================
# Middleware Configuration
# =============================================================================

# GZip compression for responses >1KB
app.add_middleware(GZipMiddleware, minimum_size=1000)

# CORS - strict by default in production
cors_default = "http://localhost:3000,http://127.0.0.1:3000" if ENVIRONMENT != "production" else ""
cors_origins_raw = os.getenv("CORS_ORIGINS", cors_default)
allow_origins = [origin.strip() for origin in cors_origins_raw.split(",") if origin.strip()]
allow_credentials = bool(allow_origins) and "*" not in allow_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=allow_credentials,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key", "X-Admin-Token"],
)

# Register error handlers
register_error_handlers(app)

# Include API routes
app.include_router(fpl_router)

# Prometheus metrics — exposes /metrics for Prometheus scraping
Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)


# =============================================================================
# Request Logging Middleware (Enhanced)
# =============================================================================
@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    """
    Enhanced request logging with structured logging support.
    
    Adds:
    - Request ID tracing
    - Timing metrics
    - User agent logging
    - Client IP (anonymized)
    """
    req_id = str(uuid.uuid4())[:8]
    started = time.perf_counter()
    client_host = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")[:100]
    
    try:
        response = await call_next(request)
        
        duration_ms = int((time.perf_counter() - started) * 1000)
        
        # Use named methods for structlog compatibility
        log_method = logger.warning if response.status_code >= 400 else logger.info
        log_method(
            "HTTP request completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
            request_id=req_id,
            client_ip=client_host,
            user_agent=user_agent,
        )
        
        # Pro-level Cache Strategy: "Deadline Rush"
        # Stale-While-Revalidate (SWR) headers for pre-deadline performance
        # Allows browsers/CDNs to serve slightly stale content while fetching fresh
        if request.method == "GET" and response.status_code == 200:
            if "Cache-Control" not in response.headers:
                response.headers["Cache-Control"] = "public, max-age=60, stale-while-revalidate=300"
        
        response.headers["x-request-id"] = req_id
        return response
    except Exception as e:
        duration_ms = int((time.perf_counter() - started) * 1000)
        logger.exception(
            "HTTP request failed with exception",
            method=request.method,
            path=request.url.path,
            status_code=500,
            duration_ms=duration_ms,
            request_id=req_id,
            client_ip=client_host,
            error=str(e),
        )
        raise


# =============================================================================
# Health and Readiness Endpoints
# =============================================================================
def _check_database() -> dict:
    started = time.perf_counter()
    try:
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
        return {
            "status": "up",
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        }
    except Exception as exc:
        return {
            "status": "down",
            "error": str(exc),
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        }


async def _check_fpl_upstream() -> dict:
    if os.getenv("HEALTHCHECK_FPL_UPSTREAM", "1") != "1":
        return {"status": "skipped", "reason": "disabled"}

    url = os.getenv("FPL_HEALTHCHECK_URL", "https://fantasy.premierleague.com/api/bootstrap-static/")
    timeout = float(os.getenv("FPL_HEALTHCHECK_TIMEOUT_SECONDS", "2.5"))
    started = time.perf_counter()

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(url)
        return {
            "status": "up" if response.status_code < 500 else "degraded",
            "http_status": response.status_code,
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        }
    except Exception as exc:
        return {
            "status": "down",
            "error": str(exc),
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        }


@app.get("/health")
async def health_check() -> JSONResponse:
    """Deep health check for backend + dependencies."""
    import psutil

    db = _check_database()
    fpl_upstream = await _check_fpl_upstream()

    process = psutil.Process()
    memory_info = process.memory_info()

    checks = {
        "database": db,
        "fpl_upstream": fpl_upstream,
        "memory": {
            "status": "ok",
            "rss_mb": round(memory_info.rss / 1024 / 1024, 2),
            "vms_mb": round(memory_info.vms / 1024 / 1024, 2),
        },
    }

    unhealthy = db["status"] != "up"
    payload = {
        "ok": not unhealthy,
        "status": "healthy" if not unhealthy else "unhealthy",
        "version": "0.8.0",
        "checks": checks,
    }

    return JSONResponse(payload, status_code=200 if payload["ok"] else 503)


@app.get("/readyz")
async def readiness_check() -> JSONResponse:
    """Readiness probe (strict): traffic should flow only when DB is healthy."""
    db = _check_database()
    ok = db["status"] == "up"
    return JSONResponse(
        {
            "ok": ok,
            "status": "ready" if ok else "not_ready",
            "checks": {"database": db},
        },
        status_code=200 if ok else 503,
    )


@app.get("/livez")
async def liveness_check() -> dict:
    """Liveness probe for process supervision."""
    return {"ok": True, "status": "alive"}


# =============================================================================
# Root Endpoint
# =============================================================================
@app.get("/")
async def root():
    """API root with helpful links."""
    return {
        "name": "FPL AI Coach API",
        "version": "0.8.0",
        "docs": "/docs",
        "health": "/health",
        "readyz": "/readyz",
        "livez": "/livez",
        "diagnostics": "/api/fpl/diagnostics",
    }
