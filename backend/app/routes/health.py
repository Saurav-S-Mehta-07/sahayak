"""Backend health endpoint."""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException

from ..services.rag_service import get_health_status

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health")
def health() -> dict[str, Any]:
    """Report API and persisted vector-store readiness."""
    try:
        return get_health_status()
    except Exception as exc:
        logger.exception("Health check could not access the vector store")
        raise HTTPException(
            status_code=503, detail="Vector store is unavailable"
        ) from exc
