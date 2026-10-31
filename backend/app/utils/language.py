from __future__ import annotations

import re
from collections.abc import Iterable

DEVANAGARI = re.compile(r"[\u0900-\u097f]")
HINGLISH_MARKERS = {
    "hai", "hain", "kya", "kaise", "kaun", "ke", "ki", "liye", "mein",
    "mujhe", "mera", "meri", "par", "chahiye", "batao",
}

_TERM_EXPANSIONS = {
    "eligibility": "eligibility पात्रता कौन पात्र eligible",
    "eligible": "eligibility पात्रता पात्र",
    "patra": "eligible eligibility पात्रता",
    "documents": "documents required papers दस्तावेज़",
    "dastavez": "documents required papers दस्तावेज़",
    "apply": "application process आवेदन कैसे करें",
    "aavedan": "application process आवेदन",
    "benefit": "benefit assistance लाभ राशि",
    "income": "income limit annual income आय सीमा",
    "age": "age limit आयु सीमा",
    "महिला": "women girls women empowerment",
    "महिलाओं": "women girls women empowerment",
    "लड़कियों": "girl child girls",
    "लड़की": "girl child girls",
    "mahila": "women girls women empowerment",
    "mahilaon": "women girls women empowerment",
    "कौन": "who eligible eligibility पात्र",
    "पात्र": "eligible eligibility पात्रता",
    "पात्रता": "eligibility eligible",
    "दस्तावेज़": "documents required papers",
    "दस्तावेज": "documents required papers",
    "आवेदन": "apply application process",
    "लाभ": "benefit assistance",
    "आय": "income limit",
    "योजना": "scheme",
    "किसान": "farmer farmers",
}


def detect_language(text: str, requested: str = "auto") -> str:
    if requested != "auto":
        return requested
    if DEVANAGARI.search(text):
        return "hindi"
    words = set(re.findall(r"[a-z]+", text.lower()))
    if words & HINGLISH_MARKERS:
        return "hinglish"
    return "english"


def expand_query(query: str) -> list[str]:
    """Keep the original query and add a lightweight cross-language variant."""
    terms = re.findall(r"[\w\u0900-\u097f-]+", query.lower())
    expansions: list[str] = []
    for term in terms:
        expansions.extend(_TERM_EXPANSIONS.get(term, "").split())
    if not expansions:
        return [query]
    expanded = f"{query} {' '.join(dict.fromkeys(expansions))}"
    return [query, expanded] if expanded.casefold() != query.casefold() else [query]


def language_fallback(language: str) -> str:
    if language == "hindi":
        return (
            "इस जानकारी की पुष्टि मेरे उपलब्ध सरकारी दस्तावेज़ों से नहीं हो पा रही है। "
            "कृपया आधिकारिक योजना पोर्टल या संबंधित सरकारी कार्यालय से पुष्टि करें।"
        )
    if language == "hinglish":
        return (
            "Is information ko main apne available government documents se verify "
            "nahi kar pa raha/rahi hoon. Kripya official scheme portal ya relevant "
            "government office se confirm karein."
        )
    return (
        "I cannot verify this information from the government documents currently "
        "available in my knowledge base. Please confirm it through the official "
        "scheme portal or the relevant government office."
    )


def merge_terms(values: Iterable[str]) -> str:
    return " ".join(dict.fromkeys(value.strip() for value in values if value.strip()))
