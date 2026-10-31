from __future__ import annotations

import hmac

from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import FileResponse

from app.api.dependencies import get_runtime
from app.core.config import settings
from app.models.schemas import DocumentSummary, IngestionSummary

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", response_model=list[DocumentSummary])
def list_documents() -> list[dict]:
    return get_runtime().documents.list_documents()


@router.get("/ingestion-status")
def ingestion_status() -> dict:
    return get_runtime().documents.ingestion_status()


@router.post("/ingest", response_model=IngestionSummary)
def ingest_documents(
    x_ingestion_key: str | None = Header(default=None, alias="X-Ingestion-Key"),
) -> dict:
    if not settings.ingestion_api_key:
        raise HTTPException(
            status_code=503,
            detail="Document ingestion API is disabled; configure INGESTION_API_KEY.",
        )
    if not x_ingestion_key or not hmac.compare_digest(
        x_ingestion_key, settings.ingestion_api_key
    ):
        raise HTTPException(status_code=401, detail="Invalid ingestion credentials")
    return get_runtime().ingestion.ingest()


@router.get("/{document_id}/file")
def get_document_file(
    document_id: str,
    page: int = Query(default=1, ge=1),
) -> FileResponse:
    path = get_runtime().documents.pdf_path(document_id)
    if path is None:
        raise HTTPException(status_code=404, detail="PDF not found")
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=path.name,
        content_disposition_type="inline",
        headers={"X-PDF-Page": str(page)},
    )


@router.get("/{document_id}", response_model=DocumentSummary)
def get_document(document_id: str) -> dict:
    document = get_runtime().documents.get_document(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    document["pdf_url"] = f"/api/v1/documents/{document_id}/file"
    return document
