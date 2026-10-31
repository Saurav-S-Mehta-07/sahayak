from __future__ import annotations

import re
from typing import Any

from app.models.schemas import EligibilityProfile, EligibilityResult
from app.rag.citation_manager import CitationManager
from app.rag.context_builder import ContextBuilder
from app.rag.retriever import Retriever
from app.utils.text_utils import slugify

_AGE_RANGE = re.compile(
    r"(?:\b(?:age|aged)\s*(?:group\s*)?(?:between|from)?\s*(\d{1,3})\s*(?:to|-|and)\s*(\d{1,3})\b"
    r"|\bbetween\s*(\d{1,3})\s*(?:to|-|and)\s*(\d{1,3})\s*(?:years?\s*)?(?:of\s*age)?\b)",
    re.IGNORECASE,
)
_AGE_MINIMUM = re.compile(r"\b(?:minimum age|at least|aged)\D{0,20}(\d{1,3})\b", re.I)
_AGE_MAXIMUM = re.compile(r"\b(?:maximum age|not more than|below age|up to age)\D{0,20}(\d{1,3})\b", re.I)
_INCOME_LIMIT = re.compile(
    r"(?:annual|family|household)?\s*income[^\n]{0,60}?"
    r"(?:not exceed|not more than|less than|up to|below|maximum|limit)"
    r"\s*(?:of\s*)?(?:₹|rs\.?\s*)?([\d,]{4,})"
    r"|(?:₹|rs\.?\s*)?([\d,]{4,})[^\n]{0,40}?"
    r"(?:annual|family|household)?\s*income[^\n]{0,30}?"
    r"(?:limit|maximum|not exceed)",
    re.IGNORECASE,
)


class EligibilityService:
    """Conservative evaluator; unsupported or unparsed scheme rules stay unresolved."""

    def __init__(self, retriever: Retriever, context_builder: ContextBuilder | None = None):
        self.retriever = retriever
        self.context_builder = context_builder or ContextBuilder()

    def evaluate(
        self,
        scheme_id: str,
        profile: EligibilityProfile,
        scheme_name: str | None = None,
    ) -> EligibilityResult:
        query = (
            f"{scheme_id} eligibility beneficiary criteria qualification age income "
            "occupation exclusions land ownership documents application"
        )
        results = self.retriever.retrieve(
            [query], scheme_id=slugify(scheme_id), top_k=8
        )
        evidence = self.context_builder.build(results)
        display_name = (
            str(results[0]["metadata"].get("scheme_name"))
            if results
            else scheme_name or scheme_id
        )
        matched: list[str] = []
        unmatched: list[str] = []
        missing: list[str] = []
        recognized = 0
        criteria_text = "\n".join(item.content for item in evidence)

        for match in _AGE_RANGE.finditer(criteria_text):
            recognized += 1
            lower = int(match.group(1) or match.group(3))
            upper = int(match.group(2) or match.group(4))
            if profile.age is None:
                missing.append(f"age (documented range: {lower}–{upper})")
            elif lower <= profile.age <= upper:
                matched.append(f"Age is within the documented range {lower}–{upper}")
            else:
                unmatched.append(f"Age does not meet the documented range {lower}–{upper}")

        for match in _AGE_MINIMUM.finditer(criteria_text):
            recognized += 1
            minimum = int(match.group(1))
            if profile.age is None:
                missing.append(f"age (minimum {minimum})")
            elif profile.age >= minimum:
                matched.append(f"Age meets the documented minimum {minimum}")
            else:
                unmatched.append(f"Age is below the documented minimum {minimum}")

        for match in _AGE_MAXIMUM.finditer(criteria_text):
            recognized += 1
            maximum = int(match.group(1))
            if profile.age is None:
                missing.append(f"age (maximum {maximum})")
            elif profile.age <= maximum:
                matched.append(f"Age meets the documented maximum {maximum}")
            else:
                unmatched.append(f"Age exceeds the documented maximum {maximum}")

        for match in _INCOME_LIMIT.finditer(criteria_text):
            recognized += 1
            raw_limit = match.group(1) or match.group(2)
            limit = int(raw_limit.replace(",", ""))
            snippet = criteria_text[max(0, match.start() - 30) : match.end() + 30].lower()
            if profile.annual_income is None:
                missing.append(f"annual income (documented value: {limit})")
            elif any(term in snippet for term in ("maximum", "not exceed", "below", "up to", "limit")):
                if profile.annual_income <= limit:
                    matched.append(f"Annual income is within the documented limit {limit}")
                else:
                    unmatched.append(f"Annual income exceeds the documented limit {limit}")
            else:
                missing.append("the meaning of the documented income amount")

        if not evidence:
            missing.append("indexed scheme eligibility information")
        if evidence and re.search(r"\beligib(?:le|ility)|beneficiar", criteria_text, re.I):
            missing.append("scheme-specific non-numeric criteria and exclusions")
        if not recognized and evidence:
            missing.append("explicit, machine-readable eligibility criteria")

        if unmatched:
            status = "LIKELY_NOT_ELIGIBLE"
            explanation = (
                "At least one provided detail does not meet a clearly documented "
                "criterion. This is a preliminary indication, not an official decision."
            )
        else:
            status = "INSUFFICIENT_INFORMATION"
            explanation = (
                "The indexed documents do not provide enough structured criteria to "
                "confirm likely eligibility. Unparsed or scheme-specific conditions "
                "must be checked against the cited source."
            )

        citation_answer = " ".join(f"[{item.citation_id}]" for item in evidence)
        citations = CitationManager.citations(evidence, citation_answer)
        return EligibilityResult(
            scheme_name=display_name,
            status=status,
            matched_criteria=matched,
            unmatched_criteria=unmatched,
            missing_information=list(dict.fromkeys(missing)),
            explanation=explanation,
            citations=citations,
            disclaimer="This is guidance based only on indexed documents, not official approval or a guarantee of benefits.",
        )
