from __future__ import annotations

import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError

import app.db.models  # noqa: F401  # ensure models are imported before create_all
from app.api.routes import router as fpl_router
from app.core.errors import register_error_handlers
from app.db import Base, engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

app = FastAPI(title="FPL AI Coach API", version="0.7.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_error_handlers(app)
app.include_router(fpl_router)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    req_id = str(uuid.uuid4())[:8]
    started = time.perf_counter()
    try:
        response = await call_next(request)
        duration_ms = int((time.perf_counter() - started) * 1000)
        logging.getLogger("fpl.http").info(
            "%s %s -> %s (%sms) req=%s",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            req_id,
        )
        response.headers["x-request-id"] = req_id
        return response
    except Exception:
        duration_ms = int((time.perf_counter() - started) * 1000)
        logging.getLogger("fpl.http").exception(
            "%s %s -> 500 (%sms) req=%s",
            request.method,
            request.url.path,
            duration_ms,
            req_id,
        )
        raise


@app.on_event("startup")
def on_startup() -> None:
    try:
        Base.metadata.create_all(bind=engine)
    except SQLAlchemyError as e:
        print(f"[startup] DB init warning: {e}")
