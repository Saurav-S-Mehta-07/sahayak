"""Similarity retrieval and result normalization."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from langchain_core.documents import Document

from .config import settings
from .embeddings import EmbeddingManager
from .vector_database import VectorStoreManager

logger = logging.getLogger(__name__)


def _content_from(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, Document):
        return value.page_content
    if isinstance(value, Mapping):
        content = value.get("document")
        if content is None:
            content = value.get("page_content")
        return content if isinstance(content, str) else ""
    content = getattr(value, "page_content", None)
    return content if isinstance(content, str) else ""


def normalize_document(value: Any) -> dict[str, Any] | None:
    """Normalize supported document shapes into a consistent result mapping."""
    if isinstance(value, Mapping):
        document = _content_from(value)
        metadata = value.get("metadata", {})
        result = dict(value)
    else:
        document = _content_from(value)
        metadata = getattr(value, "metadata", {})
        result = {}
    if not document.strip():
        return None
    result["document"] = document
    result["metadata"] = dict(metadata) if isinstance(metadata, Mapping) else {}
    return result


def _similarity_from_distance(distance: float, space: str) -> float:
    if space == "l2":
        return 1 / (1 + max(distance, 0))
    return 1 - distance


class RAGRetriever:
    """Retrieve relevant Chroma records using the notebook's embedding model."""

    def __init__(
        self, embedding_manager: EmbeddingManager, vector_store: VectorStoreManager
    ) -> None:
        self.embedding_manager = embedding_manager
        self.vector_store = vector_store

    def retrieve(
        self,
        query: str,
        top_k: int | None = None,
        score_threshold: float | None = None,
    ) -> list[dict[str, Any]]:
        """Return normalized documents, ranked by Chroma similarity."""
        if not isinstance(query, str) or not query.strip():
            raise ValueError("Query must be a non-empty string")
        limit = settings.retrieval_top_k if top_k is None else top_k
        threshold = (
            settings.retrieval_score_threshold
            if score_threshold is None
            else score_threshold
        )
        if limit < 1:
            raise ValueError("top_k must be at least 1")
        if self.vector_store.collection.count() == 0:
            logger.info("No documents are available for retrieval")
            return []

        query_embedding = self.embedding_manager.embed_query(query)
        try:
            results = self.vector_store.collection.query(
                query_embeddings=[query_embedding.tolist()],
                n_results=min(limit, self.vector_store.collection.count()),
                include=["documents", "metadatas", "distances"],
            )
        except Exception:
            logger.exception("Vector retrieval failed")
            raise

        retrieved: list[dict[str, Any]] = []
        seen_documents: set[tuple[str, str, str]] = set()
        configuration = getattr(self.vector_store.collection, "configuration", {})
        hnsw = configuration.get("hnsw", {}) if isinstance(configuration, Mapping) else {}
        distance_space = hnsw.get("space", "cosine") if isinstance(hnsw, Mapping) else "cosine"
        documents = (results.get("documents") or [[]])[0] or []
        metadatas = (results.get("metadatas") or [[]])[0] or []
        distances = (results.get("distances") or [[]])[0] or []
        ids = (results.get("ids") or [[]])[0] or []
        for index, content in enumerate(documents):
            metadata = metadatas[index] if index < len(metadatas) else {}
            distance = distances[index] if index < len(distances) else None
            normalized = normalize_document(
                {
                    "id": ids[index] if index < len(ids) else None,
                    "document": content,
                    "metadata": metadata,
                }
            )
            if normalized is None:
                logger.warning("Skipping retrieval result without document content")
                continue
            source = str(normalized["metadata"].get("source", ""))
            source_name = source.replace("\\", "/").rsplit("/", 1)[-1].casefold()
            page = str(normalized["metadata"].get("page", ""))
            canonical_content = " ".join(normalized["document"].split()).casefold()
            deduplication_key = (source_name, page, canonical_content)
            if deduplication_key in seen_documents:
                continue
            seen_documents.add(deduplication_key)
            similarity = (
                _similarity_from_distance(float(distance), distance_space)
                if distance is not None
                else None
            )
            if similarity is not None and similarity < threshold:
                continue
            normalized.update(
                distance=distance,
                similarity_score=similarity,
                rank=len(retrieved) + 1,
            )
            retrieved.append(normalized)
        logger.info("Retrieved %d documents", len(retrieved))
        return retrieved
