"""Indexed document listing endpoint."""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException

from ..services.rag_service import list_indexed_documents

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/documents")
def documents() -> dict[str, list[dict[str, Any]]]:
    """List PDF documents represented in persisted Chroma metadata."""
    try:
        return {"documents": list_indexed_documents()}
    except Exception as exc:
        logger.exception("Could not read document metadata")
        raise HTTPException(
            status_code=503, detail="Document metadata is unavailable"
        ) from exc
