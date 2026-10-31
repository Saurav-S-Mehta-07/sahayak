from __future__ import annotations

from dataclasses import dataclass

from app.utils.language import detect_language, expand_query


@dataclass(frozen=True)
class ProcessedQuery:
    original: str
    variants: list[str]
    language: str


class QueryProcessor:
    def process(
        self,
        query: str,
        requested_language: str = "auto",
        current_scheme: str | None = None,
    ) -> ProcessedQuery:
        language = detect_language(query, requested_language)
        resolved_query = query
        if current_scheme and current_scheme.casefold() not in query.casefold():
            resolved_query = f"{current_scheme} {query}"
        return ProcessedQuery(
            original=query,
            variants=expand_query(resolved_query),
            language=language,
        )
