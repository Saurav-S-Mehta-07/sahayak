from __future__ import annotations

import re
from dataclasses import dataclass

from app.models.schemas import Citation, GroundingResult
from app.rag.citation_manager import CitationManager
from app.rag.context_builder import Evidence

_NUMBER_PATTERN = re.compile(
    r"(?<![A-Za-z])\d[\d,]*(?:\.\d+)?\s*"
    r"(?:%|percent|years?|rupees?|rs\.?|₹|lakhs?|crores?|thousand|million|billion)?",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Verification:
    grounding: GroundingResult
    safe: bool


class HallucinationChecker:
    def verify(
        self,
        answer: str,
        citations: list[Citation],
        evidence: list[Evidence],
        user_message: str = "",
    ) -> Verification:
        citation_valid = CitationManager.valid(answer, citations, evidence)
        evidence_text = " ".join(
            [item.content for item in evidence]
        )
        normalized_numbers = self._numbers(evidence_text)
        evidence_by_id = {item.citation_id: item for item in evidence}
        unsupported: list[str] = []
        for sentence in re.split(
            r"(?<=[.!?।])\s+(?!\[CIT-\d{3}\])|\n+",
            answer,
        ):
            sentence_numbers = [
                value.strip()
                for value in _NUMBER_PATTERN.findall(
                    re.sub(r"\[CIT-\d{3}\]", "", sentence)
                )
                if value.strip()
            ]
            cited_ids = CitationManager.extract_ids(sentence)
            for value in sentence_numbers:
                normalized = self._normalize_number(value)
                supported_by_citation = any(
                    normalized in self._numbers(evidence_by_id[citation_id].content)
                    and self._units_supported(
                        sentence, evidence_by_id[citation_id].content
                    )
                    for citation_id in cited_ids
                    if citation_id in evidence_by_id
                )
                user_context = (
                    normalized in self._numbers(user_message)
                    and bool(
                        re.search(
                            r"\b(?:you said|you told me|you mentioned|your age|you are)\b"
                            r"|(?:आपने बताया|आपकी उम्र|आपकी आयु|आपकी उम्र)\b",
                            sentence,
                            re.IGNORECASE,
                        )
                    )
                )
                if normalized not in normalized_numbers and not user_context:
                    unsupported.append(value)
                elif not supported_by_citation and not user_context:
                    unsupported.append(value)
        if not evidence:
            status = "insufficient_evidence"
        elif not citation_valid or unsupported:
            status = "verification_failed"
        else:
            status = "verified"
        grounded = status == "verified"
        return Verification(
            grounding=GroundingResult(
                grounded=grounded,
                verification_status=status,
                unsupported_claims=unsupported,
                citation_valid=citation_valid,
            ),
            safe=grounded,
        )

    @staticmethod
    def _normalize_number(value: str) -> str:
        return re.sub(r"\D", "", value)

    @classmethod
    def _numbers(cls, text: str) -> set[str]:
        return {
            cls._normalize_number(value)
            for value in _NUMBER_PATTERN.findall(text)
            if value.strip()
        }

    @staticmethod
    def _units_supported(answer: str, evidence: str) -> bool:
        unit_patterns = (
            (r"₹|\b(?:rs\.?|rupees?)\b", r"₹|\b(?:rs\.?|rupees?)\b"),
            (r"%|\bpercent\b", r"%|\bpercent\b"),
            (r"\bper\s+month\b|\bmonthly\b", r"\bper\s+month\b|\bmonthly\b"),
            (r"\bper\s+year\b|\bannually\b|\byearly\b", r"\bper\s+year\b|\bannually\b|\byearly\b"),
            (r"\blakhs?\b", r"\blakhs?\b"),
            (r"\bcrores?\b", r"\bcrores?\b"),
            (r"\bthousand\b", r"\bthousand\b"),
            (r"\bmillion\b", r"\bmillion\b"),
            (r"\bbillion\b", r"\bbillion\b"),
        )
        return all(
            not re.search(answer_pattern, answer, re.IGNORECASE)
            or bool(re.search(evidence_pattern, evidence, re.IGNORECASE))
            for answer_pattern, evidence_pattern in unit_patterns
        )
