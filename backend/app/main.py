"""FastAPI application entry point."""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .services.discovery_service import discover_configured_feeds
if __package__ and __package__.startswith("backend."):
    from backend.src.config import settings
else:
    from src.config import settings
from .routes import admin, auth, chat, documents, eligibility, health, schemes

logger = logging.getLogger(__name__)


async def _scheduled_discovery() -> None:
    interval_seconds = settings.scheme_discovery_interval_hours * 60 * 60
    while True:
        await asyncio.sleep(interval_seconds)
        result = await asyncio.to_thread(discover_configured_feeds)
        if result["errors"]:
            logger.error("Scheduled scheme discovery completed with errors: %s", result["errors"])
        else:
            logger.info(
                "Scheduled scheme discovery found %d new signals",
                result["new_discoveries"],
            )


@asynccontextmanager
async def lifespan(_app: FastAPI):
    task = None
    if settings.scheme_discovery_interval_hours > 0 and settings.scheme_discovery_feed_urls:
        task = asyncio.create_task(_scheduled_discovery())
    try:
        yield
    finally:
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


app = FastAPI(
    title="Yojana Sahayak API",
    version="1.0.0",
    lifespan=lifespan,
)
allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "X-CSRF-Token"],
)
app.include_router(auth.router, prefix="/api", tags=["authentication"])
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(documents.router, prefix="/api", tags=["documents"])
app.include_router(schemes.router, prefix="/api", tags=["schemes"])
app.include_router(eligibility.router, prefix="/api", tags=["eligibility"])
app.include_router(chat.router, prefix="/api", tags=["chat"])
app.include_router(admin.router, prefix="/api", tags=["administration"])


@app.get("/")
def root() -> dict[str, Any]:
    """Expose the API name and health endpoint."""
    return {"name": app.title, "health": "/api/health"}
