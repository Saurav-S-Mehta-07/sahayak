from __future__ import annotations

import logging
from threading import Lock

from sentence_transformers import SentenceTransformer

from app.core.config import settings
from app.core.exceptions import ServiceUnavailableError

logger = logging.getLogger(__name__)


class EmbeddingManager:
    def __init__(self, model_name: str = settings.embedding_model):
        self.model_name = model_name
        self._model: SentenceTransformer | None = None
        self._lock = Lock()

    @property
    def model(self) -> SentenceTransformer:
        if self._model is None:
            with self._lock:
                if self._model is None:
                    try:
                        logger.info("Loading embedding model %s", self.model_name)
                        self._model = SentenceTransformer(self.model_name)
                        dimension_method = getattr(
                            self._model, "get_embedding_dimension", None
                        )
                        if dimension_method is None:
                            dimension_method = self._model.get_sentence_embedding_dimension
                        logger.info(
                            "Embedding model ready; dimensions=%s",
                            dimension_method(),
                        )
                    except Exception as exc:
                        raise ServiceUnavailableError(
                            f"Could not load embedding model {self.model_name}"
                        ) from exc
        return self._model

    @property
    def dimensions(self) -> int:
        dimension_method = getattr(self.model, "get_embedding_dimension", None)
        if dimension_method is None:
            dimension_method = self.model.get_sentence_embedding_dimension
        return int(dimension_method())

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            vectors = self.model.encode(
                texts,
                normalize_embeddings=True,
                show_progress_bar=False,
                convert_to_numpy=True,
            )
        except Exception as exc:
            raise ServiceUnavailableError("Embedding generation failed") from exc
        return vectors.tolist()
