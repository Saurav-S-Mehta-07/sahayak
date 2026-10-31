from __future__ import annotations

import logging
from pathlib import Path
from threading import Lock
from typing import Any

import chromadb
from langchain_core.documents import Document

from app.core.config import settings
from app.core.constants import COLLECTION_NAME
from app.core.exceptions import ServiceUnavailableError
from app.rag.embeddings import EmbeddingManager

logger = logging.getLogger(__name__)


def _chromadb_metadata(metadata: dict[str, Any]) -> dict[str, str | int | float | bool]:
    supported: dict[str, str | int | float | bool] = {}
    for key, value in metadata.items():
        if isinstance(value, (str, int, float, bool)):
            supported[key] = value
    return supported


class VectorStore:
    def __init__(
        self,
        embeddings: EmbeddingManager,
        persist_directory: Path = settings.vector_dir,
        collection_name: str = COLLECTION_NAME,
    ):
        self.embeddings = embeddings
        self.persist_directory = persist_directory
        self.collection_name = collection_name
        self._client: chromadb.PersistentClient | None = None
        self._collection: Any = None
        self._lock = Lock()

    @property
    def collection(self) -> Any:
        if self._collection is None:
            with self._lock:
                if self._collection is None:
                    try:
                        self.persist_directory.mkdir(parents=True, exist_ok=True)
                        self._client = chromadb.PersistentClient(path=str(self.persist_directory))
                        self._collection = self._client.get_or_create_collection(
                            name=self.collection_name,
                            metadata={
                                "description": "PDF page and passage embeddings for Yojana Sahayak",
                                "hnsw:space": "cosine",
                                "embedding_model": self.embeddings.model_name,
                            },
                        )
                        logger.info(
                            "Opened Chroma collection %s with %s vectors",
                            self.collection_name,
                            self._collection.count(),
                        )
                    except Exception as exc:
                        raise ServiceUnavailableError("Vector store is unavailable") from exc
        return self._collection

    @property
    def count(self) -> int:
        return int(self.collection.count())

    def ids_for_document(self, document_id: str) -> list[str]:
        result = self.collection.get(where={"document_id": document_id}, include=["metadatas"])
        return list(result.get("ids", []))

    def upsert(self, chunks: list[Document], vectors: list[list[float]]) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("Chunk and embedding counts do not match")
        if not chunks:
            return
        try:
            self.collection.upsert(
                ids=[str(chunk.metadata["chunk_id"]) for chunk in chunks],
                embeddings=vectors,
                documents=[chunk.page_content for chunk in chunks],
                metadatas=[_chromadb_metadata(chunk.metadata) for chunk in chunks],
            )
        except Exception as exc:
            raise ServiceUnavailableError("Could not write chunks to the vector store") from exc

    def delete_ids(self, ids: list[str]) -> None:
        if ids:
            self.collection.delete(ids=ids)

    def delete_document(self, document_id: str) -> None:
        self.collection.delete(where={"document_id": document_id})

    def query(
        self,
        vector: list[float],
        top_k: int,
        where: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        if self.count == 0:
            return []
        try:
            results = self.collection.query(
                query_embeddings=[vector],
                n_results=min(top_k, self.count),
                where=where,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as exc:
            raise ServiceUnavailableError("Vector retrieval failed") from exc
        output: list[dict[str, Any]] = []
        for doc_id, text, metadata, distance in zip(
            results["ids"][0],
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            similarity = 1.0 - float(distance)
            output.append(
                {
                    "id": doc_id,
                    "document": text,
                    "metadata": metadata,
                    "distance": float(distance),
                    "similarity_score": similarity,
                }
            )
        return output

    def list_documents(self) -> list[dict[str, Any]]:
        all_items = self.collection.get(include=["metadatas"])
        grouped: dict[str, dict[str, Any]] = {}
        for metadata in all_items.get("metadatas", []):
            if not metadata:
                continue
            document_id = str(metadata.get("document_id", ""))
            entry = grouped.setdefault(
                document_id,
                {
                    "document_id": document_id,
                    "document_name": metadata.get("document_name", ""),
                    "scheme_name": metadata.get("scheme_name", ""),
                    "source_path": metadata.get("source_path", ""),
                    "page_count": 0,
                    "chunk_count": 0,
                    "status": "indexed",
                },
            )
            entry["chunk_count"] += 1
            entry["page_count"] = max(entry["page_count"], int(metadata.get("page_number", 0)))
        return list(grouped.values())
