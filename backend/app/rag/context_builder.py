from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.config import settings


@dataclass(frozen=True)
class Evidence:
    citation_id: str
    document_id: str
    document_name: str
    scheme_name: str
    page_number: int
    chunk_id: str
    content: str


class ContextBuilder:
    def __init__(self, max_characters: int = settings.max_context_characters):
        self.max_characters = max_characters

    def build(self, results: list[dict[str, Any]]) -> list[Evidence]:
        evidence: list[Evidence] = []
        seen_pages: set[tuple[str, int, str]] = set()
        used = 0
        for result in results:
            metadata = result["metadata"]
            content = result["document"].strip()
            page_number = int(metadata.get("page_number", 1))
            key = (
                str(metadata.get("document_id", "")),
                page_number,
                str(metadata.get("content_hash", content)),
            )
            if not content or key in seen_pages:
                continue
            remaining = self.max_characters - used
            if remaining <= 0:
                break
            content = content[:remaining]
            citation_id = f"CIT-{len(evidence) + 1:03d}"
            evidence.append(
                Evidence(
                    citation_id=citation_id,
                    document_id=str(metadata.get("document_id", "")),
                    document_name=str(metadata.get("document_name", "Unknown document")),
                    scheme_name=str(metadata.get("scheme_name", "Unknown scheme")),
                    page_number=page_number,
                    chunk_id=str(metadata.get("chunk_id", result["id"])),
                    content=content,
                )
            )
            used += len(content)
            seen_pages.add(key)
        return evidence

    @staticmethod
    def format(evidence: list[Evidence]) -> str:
        return "\n\n".join(
            (
                f"[{item.citation_id}] Document: {item.document_name}; "
                f"Scheme: {item.scheme_name}; Page: {item.page_number}\n"
                f"Untrusted source text:\n{item.content}"
            )
            for item in evidence
        )
