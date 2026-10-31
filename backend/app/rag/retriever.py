from __future__ import annotations

import re
from typing import Any

from app.core.config import settings
from app.rag.embeddings import EmbeddingManager
from app.rag.vector_store import VectorStore


class Retriever:
    def __init__(
        self,
        embeddings: EmbeddingManager,
        vector_store: VectorStore,
        top_k: int = settings.retrieval_top_k,
        min_similarity: float | None = settings.retrieval_min_similarity,
    ):
        self.embeddings = embeddings
        self.vector_store = vector_store
        self.top_k = top_k
        self.min_similarity = min_similarity

    def retrieve(
        self,
        query_variants: list[str],
        scheme_id: str | None = None,
        document_id: str | None = None,
        top_k: int | None = None,
    ) -> list[dict[str, Any]]:
        requested = max(1, top_k or self.top_k)
        where: dict[str, Any] | None = None
        if scheme_id and document_id:
            where = {"$and": [{"scheme_id": scheme_id}, {"document_id": document_id}]}
        elif scheme_id:
            where = {"scheme_id": scheme_id}
        elif document_id:
            where = {"document_id": document_id}

        by_chunk: dict[str, dict[str, Any]] = {}
        for query in query_variants:
            vector = self.embeddings.embed([query])[0]
            for result in self.vector_store.query(vector, requested * 2, where):
                if (
                    self.min_similarity is not None
                    and result["similarity_score"] < self.min_similarity
                ):
                    continue
                content_key = result["metadata"].get("content_hash") or re.sub(
                    r"\s+", " ", result["document"].strip().lower()
                )
                previous = by_chunk.get(str(content_key))
                if previous is None or result["similarity_score"] > previous["similarity_score"]:
                    by_chunk[str(content_key)] = result

        ranked = sorted(
            by_chunk.values(),
            key=lambda result: (
                result["similarity_score"] + self._keyword_bonus(query_variants, result["document"]),
                result["similarity_score"],
            ),
            reverse=True,
        )
        return ranked[:requested]

    @staticmethod
    def _keyword_bonus(queries: list[str], text: str) -> float:
        words = {
            token
            for query in queries
            for token in re.findall(r"[a-z0-9]{3,}", query.casefold())
        }
        content = set(re.findall(r"[a-z0-9]{3,}", text.casefold()))
        if not words:
            return 0.0
        return min(0.08, 0.08 * len(words & content) / len(words))
