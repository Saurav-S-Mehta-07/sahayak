"""Sentence-transformer embedding helpers."""

from __future__ import annotations

import logging
from collections.abc import Sequence

import numpy as np
from sentence_transformers import SentenceTransformer

from .config import settings

logger = logging.getLogger(__name__)


class EmbeddingManager:
    """Lazily initialized wrapper around the notebook's SentenceTransformer."""

    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or settings.embedding_model
        self._model: SentenceTransformer | None = None

    @property
    def model(self) -> SentenceTransformer:
        if self._model is None:
            logger.info("Loading embedding model %s", self.model_name)
            self._model = SentenceTransformer(self.model_name)
            logger.info("Embedding dimension: %d", self._model.get_embedding_dimension())
        return self._model

    @property
    def embedding_dimension(self) -> int:
        return self.model.get_embedding_dimension()

    def generate_embeddings(self, texts: str | Sequence[str]) -> np.ndarray:
        """Return a 2D array of embeddings for one or more texts."""
        inputs = [texts] if isinstance(texts, str) else list(texts)
        if not inputs:
            return np.empty((0, self.embedding_dimension), dtype=np.float32)
        if any(not isinstance(text, str) or not text.strip() for text in inputs):
            raise ValueError("Embedding inputs must be non-empty strings")
        try:
            return np.asarray(
                self.model.encode(inputs, show_progress_bar=False), dtype=np.float32
            )
        except Exception:
            logger.exception("Embedding generation failed")
            raise

    def embed_query(self, query: str) -> np.ndarray:
        """Return a one-dimensional embedding for a query."""
        return self.generate_embeddings(query)[0]
