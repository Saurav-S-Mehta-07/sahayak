"""Application services that adapt the existing RAG pipeline."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from functools import lru_cache
from pathlib import PurePosixPath
from typing import Any

from ..database import connect
if __package__ and __package__.startswith("backend."):
    from backend.src.rag_pipeline import RAGPipeline
    from backend.src.retriever import normalize_document
else:
    from src.rag_pipeline import RAGPipeline
    from src.retriever import normalize_document

logger = logging.getLogger(__name__)


def _filter_inactive_managed_documents(
    results: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    source_paths = {
        metadata.get("source")
        for result in results
        if isinstance(result, dict)
        and isinstance((metadata := result.get("metadata")), dict)
        and isinstance(metadata.get("source"), str)
    }
    if not source_paths:
        return list(results)
    placeholders = ",".join("?" for _ in source_paths)
    with connect() as connection:
        rows = connection.execute(
            f"""
            SELECT storage_path, verification_status, indexing_status
            FROM scheme_documents
            WHERE storage_path IN ({placeholders})
            """,
            tuple(source_paths),
        ).fetchall()
    managed_status = {
        row["storage_path"]: (
            row["verification_status"] == "verified"
            and row["indexing_status"] == "indexed"
        )
        for row in rows
    }
    return [
        result
        for result in results
        if not isinstance(result, dict)
        or not isinstance(result.get("metadata"), dict)
        or result["metadata"].get("source") not in managed_status
        or managed_status[result["metadata"]["source"]]
    ]


@lru_cache(maxsize=1)
def get_rag_pipeline() -> RAGPipeline:
    """Return one reusable pipeline instance without running ingestion."""
    return RAGPipeline(retrieval_filter=_filter_inactive_managed_documents)


def get_health_status() -> dict[str, Any]:
    """Report persisted vector-store availability and collection size."""
    pipeline = get_rag_pipeline()
    return {
        "status": "ok",
        "vector_store": "ready",
        "document_chunks": pipeline.vector_store.collection.count(),
    }


def _source_filename(source: Any) -> str | None:
    if not isinstance(source, str) or not source.strip():
        return None
    return PurePosixPath(source.replace("\\", "/")).name or None


def list_indexed_documents() -> list[dict[str, Any]]:
    """List PDFs that have real metadata in the persistent vector store."""
    collection = get_rag_pipeline().vector_store.collection
    records = collection.get(
        include=["metadatas"],
        limit=max(collection.count(), 1),
    )
    grouped: dict[str, dict[str, Any]] = {}
    for metadata in records.get("metadatas") or []:
        if not isinstance(metadata, dict):
            continue
        filename = _source_filename(metadata.get("source"))
        if filename is None or not filename.lower().endswith(".pdf"):
            continue
        key = filename.casefold()
        entry = grouped.setdefault(
            key,
            {
                "filename": filename,
                "source": filename,
                "chunk_count": 0,
                "pages": set(),
                "page_count": 0,
            },
        )
        entry["chunk_count"] += 1
        page = metadata.get("page")
        if isinstance(page, int) and page >= 0:
            entry["pages"].add(page)
        total_pages = metadata.get("total_pages")
        if isinstance(total_pages, int) and total_pages > entry["page_count"]:
            entry["page_count"] = total_pages

    documents: list[dict[str, Any]] = []
    for entry in grouped.values():
        pages = entry.pop("pages")
        if not entry["page_count"] and pages:
            entry["page_count"] = len(pages)
        if not entry["page_count"]:
            entry.pop("page_count")
        documents.append(entry)
    documents.sort(key=lambda item: item["filename"].casefold())
    return documents


def answer_question(
    query: str,
    conversation_id: str | None,
    response_language: str = "English",
    active_topic: str | None = None,
    input_language: str = "en",
    conversation_summary: str = "",
) -> dict[str, Any]:
    """Run one user query through the existing pipeline and preserve citations."""
    result = get_rag_pipeline().query(
        query,
        conversation_id=conversation_id,
        response_language=response_language,
        active_topic=active_topic,
        input_language=input_language,
        conversation_summary=conversation_summary,
    )
    sources: list[dict[str, Any]] = []
    retrieved_documents = result.get("retrieved_documents", [])
    normalized_documents = [
        (item, normalize_document(item)) for item in retrieved_documents
    ]
    source_paths = {
        document["metadata"].get("source")
        for _, document in normalized_documents
        if document is not None
        and isinstance(document["metadata"].get("source"), str)
    }
    verified_metadata: dict[str, dict[str, str]] = {}
    if source_paths:
        placeholders = ",".join("?" for _ in source_paths)
        with connect() as connection:
            rows = connection.execute(
                f"""
                SELECT documents.storage_path, documents.source_url, schemes.name
                FROM scheme_documents AS documents
                JOIN schemes ON schemes.id = documents.scheme_id
                WHERE documents.storage_path IN ({placeholders})
                  AND documents.verification_status = 'verified'
                  AND documents.indexing_status = 'indexed'
                """,
                tuple(source_paths),
            ).fetchall()
        verified_metadata = {
            row["storage_path"]: {
                "source_url": row["source_url"],
                "scheme_name": row["name"],
            }
            for row in rows
        }

    for item, document in normalized_documents:
        if document is None:
            logger.warning("Skipping retrieved result without passage content")
            continue
        metadata = document["metadata"]
        verified = verified_metadata.get(metadata.get("source"), {})
        filename = _source_filename(metadata.get("source"))
        if filename is None:
            logger.warning("Skipping retrieved result without source metadata")
            continue
        sources.append(
            {
                "filename": filename,
                "source": filename,
                "page": metadata.get("page"),
                "content": document["document"],
                "score": item.get("similarity_score")
                if isinstance(item, dict)
                else None,
                "scheme_name": verified.get("scheme_name"),
                "source_url": verified.get("source_url"),
            }
        )
    return {
        "answer": result["answer"],
        "sources": sources,
        "conversation_id": result["conversation_id"],
    }
