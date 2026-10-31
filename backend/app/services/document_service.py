from __future__ import annotations

from typing import Any

from app.rag.ingestion import IngestionService


class DocumentService:
    def __init__(self, ingestion: IngestionService):
        self.ingestion = ingestion

    def list_documents(self) -> list[dict[str, Any]]:
        return self.ingestion.documents()

    def get_document(self, document_id: str) -> dict[str, Any] | None:
        return self.ingestion.document(document_id)

    def pdf_path(self, document_id: str):
        return self.ingestion.pdf_path(document_id)

    def ingestion_status(self) -> dict[str, Any]:
        documents = self.list_documents()
        return {
            "indexed_documents": len(documents),
            "indexed_chunks": sum(int(document["chunk_count"]) for document in documents),
            "documents": documents,
        }
