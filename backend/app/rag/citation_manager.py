from __future__ import annotations

import re
from typing import Any

from app.models.schemas import Citation
from app.rag.context_builder import Evidence

_CITATION_PATTERN = re.compile(r"\[(CIT-\d{3})\]")


class CitationManager:
    @staticmethod
    def extract_ids(answer: str) -> set[str]:
        return set(_CITATION_PATTERN.findall(answer))

    @staticmethod
    def citations(evidence: list[Evidence], answer: str) -> list[Citation]:
        cited_ids = CitationManager.extract_ids(answer)
        citations: list[Citation] = []
        for item in evidence:
            if item.citation_id not in cited_ids:
                continue
            citations.append(
                Citation(
                    citation_id=item.citation_id,
                    document_id=item.document_id,
                    document_name=item.document_name,
                    scheme_name=item.scheme_name,
                    page_number=item.page_number,
                    section=CitationManager.section_from_text(item.content),
                    supporting_excerpt=item.content[:500],
                    pdf_url=(
                        f"/api/v1/documents/{item.document_id}/file"
                        f"#page={item.page_number}"
                    ),
                )
            )
        return citations

    @staticmethod
    def valid(answer: str, citations: list[Citation], evidence: list[Evidence]) -> bool:
        evidence_ids = {item.citation_id for item in evidence}
        cited_ids = CitationManager.extract_ids(answer)
        returned_ids = {item.citation_id for item in citations}
        return bool(cited_ids) and cited_ids <= evidence_ids and cited_ids == returned_ids

    @staticmethod
    def section_from_text(text: str) -> str | None:
        for line in text.splitlines():
            cleaned = line.strip()
            if 3 < len(cleaned) < 100 and cleaned.isupper():
                return cleaned
        return None

    @staticmethod
    def as_dicts(citations: list[Citation]) -> list[dict[str, Any]]:
        return [citation.model_dump() for citation in citations]
