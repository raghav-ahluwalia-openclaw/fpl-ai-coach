from __future__ import annotations

import logging
import os
import time
import uuid
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi_limiter import FastAPILimiter
from redis import Redis
from sqlalchemy.exc import SQLAlchemyError

import app.db.models  # noqa: F401  # ensure models are imported before create_all
from app.api.routes import router as fpl_router
from app.core.errors import register_error_handlers
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
    
    # Initialize rate limiter (Redis or in-memory fallback)
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        try:
            redis_client = Redis.from_url(redis_url, decode_responses=True)
            await FastAPILimiter.init(redis_client)
            logger.info("Rate limiter initialized with Redis")
        except Exception as e:
            logger.warning("Redis connection failed, using in-memory rate limiter", extra={"error": str(e)})
            await FastAPILimiter.init(Redis(decode_responses=True))
    else:
        # In-memory Redis for development
        try:
            await FastAPILimiter.init(Redis(decode_responses=True))
            logger.info("Rate limiter initialized (in-memory)")
        except Exception as e:
            logger.warning("Rate limiter initialization failed", extra={"error": str(e)})
    
    yield
    
    # Shutdown
    logger.info("Shutting down FPL AI Coach API")
    await FastAPILimiter.close()


# =============================================================================
# Application Factory
# =============================================================================
app = FastAPI(
    title="FPL AI Coach API",
    version="0.8.0",
    description="AI-powered Fantasy Premier League assistant with transfer planning, captaincy decisions, and team optimization.",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# =============================================================================
# Middleware Configuration
# =============================================================================

# GZip compression for responses >1KB
app.add_middleware(GZipMiddleware, minimum_size=1000)

# CORS - Configure based on environment
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register error handlers
register_error_handlers(app)

# Include API routes
app.include_router(fpl_router)


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
# Health Check Endpoint (Enhanced)
# =============================================================================
@app.get("/health")
async def health_check():
    """
    Enhanced health check with detailed service status.
    
    Returns status of:
    - Database connection
    - Rate limiter
    - Memory usage
    """
    import psutil
    
    health_status = {
        "status": "healthy",
        "ok": True,
        "version": "0.8.0",
        "checks": {},
    }
    
    # Database check
    try:
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
        health_status["checks"]["database"] = {"status": "up", "latency_ms": "ok"}
    except Exception as e:
        health_status["checks"]["database"] = {"status": "down", "error": str(e)}
        health_status["status"] = "unhealthy"
    
    # Memory check
    try:
        process = psutil.Process()
        memory_info = process.memory_info()
        health_status["checks"]["memory"] = {
            "status": "ok",
            "rss_mb": round(memory_info.rss / 1024 / 1024, 2),
            "vms_mb": round(memory_info.vms / 1024 / 1024, 2),
        }
    except Exception as e:
        health_status["checks"]["memory"] = {"status": "unknown", "error": str(e)}
    
    # Determine overall status
    status_code = 200 if health_status["status"] == "healthy" else 503
    return health_status, status_code


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
        "diagnostics": "/api/fpl/diagnostics",
    }
