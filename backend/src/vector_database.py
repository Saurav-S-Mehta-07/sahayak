"""Persistent Chroma vector-store operations."""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Sequence
from pathlib import Path

import chromadb
import numpy as np
from langchain_core.documents import Document

from .config import settings

logger = logging.getLogger(__name__)


class VectorStoreManager:
    """Initialize and reuse the notebook's persistent Chroma collection."""

    def __init__(
        self,
        persist_directory: str | Path | None = None,
        collection_name: str | None = None,
    ) -> None:
        self.persist_directory = str(persist_directory or settings.vector_store_dir)
        self.collection_name = collection_name or settings.collection_name
        Path(self.persist_directory).mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=self.persist_directory)
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"description": "vector store collection for pdf embeddings in RAG"},
        )
        logger.info(
            "Initialized Chroma collection %s with %d records",
            self.collection_name,
            self.collection.count(),
        )

    @staticmethod
    def _document_id(document: Document, chunk_index: int) -> str:
        source = str(document.metadata.get("source", ""))
        page = str(document.metadata.get("page", ""))
        digest = hashlib.sha256(
            f"{source}\0{page}\0{chunk_index}\0{document.page_content}".encode("utf-8")
        ).hexdigest()
        return f"doc_{digest}"

    def add_documents(
        self,
        documents: Sequence[Document],
        embeddings: Sequence[Sequence[float]] | np.ndarray,
    ) -> int:
        """Upsert documents and their embeddings; return the number processed."""
        if len(documents) != len(embeddings):
            raise ValueError("Number of documents must match number of embeddings")
        if not documents:
            return 0

        ids: list[str] = []
        contents: list[str] = []
        metadatas: list[dict[str, str | int | float | bool]] = []
        vectors: list[list[float]] = []
        for chunk_index, (document, vector) in enumerate(zip(documents, embeddings)):
            if not document.page_content.strip():
                raise ValueError("Cannot store a document with empty content")
            metadata = {
                key: value
                for key, value in document.metadata.items()
                if isinstance(value, (str, int, float, bool))
            }
            metadata["content_length"] = len(document.page_content)
            ids.append(self._document_id(document, chunk_index))
            contents.append(document.page_content)
            metadatas.append(metadata)
            vectors.append(np.asarray(vector, dtype=np.float32).tolist())

        try:
            self.collection.upsert(
                ids=ids,
                metadatas=metadatas,
                documents=contents,
                embeddings=vectors,
            )
        except Exception:
            logger.exception("Failed to persist documents in Chroma")
            raise
        logger.info("Upserted %d documents; collection now has %d", len(ids), self.collection.count())
        return len(ids)

    def remove_documents_for_source(self, source: str) -> int:
        """Remove all chunks for one managed source after a failed ingestion."""
        records = self.collection.get(
            where={"source": source},
            include=["metadatas"],
        )
        ids = records.get("ids") or []
        if ids:
            self.collection.delete(ids=ids)
            logger.warning("Removed %d partially ingested chunks for %s", len(ids), source)
        return len(ids)
