from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.dependencies import get_runtime
from app.api.routes import chat, documents, eligibility, health, schemes, sessions
from app.core.config import settings
from app.core.constants import API_PREFIX
from app.core.exceptions import SahayakError
from app.core.logging import configure_logging


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging()
    settings.pdf_dir.mkdir(parents=True, exist_ok=True)
    settings.processed_dir.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title="Yojana Sahayak API",
    version="1.0.0",
    description="Document-grounded multilingual government scheme assistant.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "X-Ingestion-Key"],
)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    _: Request, exc: RequestValidationError
) -> JSONResponse:
    errors = [
        {"field": ".".join(str(item) for item in error["loc"]), "message": error["msg"]}
        for error in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": errors})


@app.exception_handler(SahayakError)
async def service_error_handler(_: Request, exc: SahayakError) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok", "service": "yojana-sahayak-api"}


app.include_router(chat.router, prefix=API_PREFIX)
app.include_router(schemes.router, prefix=API_PREFIX)
app.include_router(eligibility.router, prefix=API_PREFIX)
app.include_router(documents.router, prefix=API_PREFIX)
app.include_router(sessions.router, prefix=API_PREFIX)
app.include_router(health.router, prefix=API_PREFIX)
