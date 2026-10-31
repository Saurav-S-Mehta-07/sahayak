from __future__ import annotations

from typing import Any

from app.rag.ingestion import IngestionService
from app.utils.text_utils import slugify


class SchemeService:
    def __init__(self, ingestion: IngestionService):
        self.ingestion = ingestion

    def list_schemes(self, query: str | None = None) -> list[dict[str, Any]]:
        grouped: dict[str, dict[str, Any]] = {}
        for document in self.ingestion.documents():
            scheme_name = str(document["scheme_name"])
            scheme_id = slugify(scheme_name)
            entry = grouped.setdefault(
                scheme_id,
                {
                    "scheme_id": scheme_id,
                    "scheme_name": scheme_name,
                    "document_count": 0,
                    "documents": [],
                },
            )
            entry["document_count"] += 1
            entry["documents"].append(document)
        results = list(grouped.values())
        if query:
            needle = query.casefold()
            results = [
                item
                for item in results
                if needle in item["scheme_name"].casefold()
                or needle in " ".join(
                    document["document_name"] for document in item["documents"]
                ).casefold()
            ]
        return results

    def get_scheme(self, scheme_id: str) -> dict[str, Any] | None:
        return next(
            (scheme for scheme in self.list_schemes() if scheme["scheme_id"] == scheme_id),
            None,
        )
