"""Route each chat message to conversational handling or the existing RAG pipeline."""

from __future__ import annotations

import re
import unicodedata
import json
from typing import Any

from ..database import connect
from . import rag_service

_LANGUAGES = {
    "english": ("en", "Latin", "English"),
    "hindi": ("hi", "Devanagari", "Hindi"),
    "urdu": ("ur", "Arabic", "Urdu"),
    "bengali": ("bn", "Bengali", "Bengali"),
    "bangla": ("bn", "Bengali", "Bengali"),
    "tamil": ("ta", "Tamil", "Tamil"),
    "telugu": ("te", "Telugu", "Telugu"),
    "marathi": ("mr", "Devanagari", "Marathi"),
    "gujarati": ("gu", "Gujarati", "Gujarati"),
    "kannada": ("kn", "Kannada", "Kannada"),
    "malayalam": ("ml", "Malayalam", "Malayalam"),
    "punjabi": ("pa", "Gurmukhi", "Punjabi"),
    "hinglish": ("hinglish", "Latin", "Hinglish (Hindi-English mix)"),
    "roman-hindi": ("roman_hindi", "Latin", "Hindi written in Latin script"),
    "roman-urdu": ("roman_urdu", "Latin", "Urdu written in Latin script"),
}
_LANGUAGE_NAMES = {
    "en": "English",
    "hi": "Hindi",
    "ur": "Urdu",
    "bn": "Bengali",
    "ta": "Tamil",
    "te": "Telugu",
    "mr": "Marathi",
    "gu": "Gujarati",
    "kn": "Kannada",
    "ml": "Malayalam",
    "pa": "Punjabi",
    "hinglish": "Hinglish (Hindi-English mix)",
    "roman_hindi": "Hindi written in Latin script",
    "roman_urdu": "Urdu written in Latin script",
}
_LANGUAGE_SCRIPTS = {
    "en": "Latin",
    "hi": "Devanagari",
    "ur": "Arabic",
    "bn": "Bengali",
    "ta": "Tamil",
    "te": "Telugu",
    "mr": "Devanagari",
    "gu": "Gujarati",
    "kn": "Kannada",
    "ml": "Malayalam",
    "pa": "Gurmukhi",
    "hinglish": "Latin",
    "roman_hindi": "Latin",
    "roman_urdu": "Latin",
}
_SCRIPT_LANGUAGES = {
    "Arabic": ("ur", "Urdu"),
    "Bengali": ("bn", "Bengali"),
    "Tamil": ("ta", "Tamil"),
    "Telugu": ("te", "Telugu"),
    "Gujarati": ("gu", "Gujarati"),
    "Kannada": ("kn", "Kannada"),
    "Malayalam": ("ml", "Malayalam"),
    "Gurmukhi": ("pa", "Punjabi"),
}
_TRANSFORMS = {
    "greeting": re.compile(r"^(hi|hello|hey|namaste|salaam|assalamu alaikum)[!. ]*$", re.I),
    "thanks": re.compile(
        r"^(thanks?( so much)?|thank you( very much| so much)?|"
        r"धन्यवाद|शुक्रिया|شکریہ)[!. ]*$",
        re.I,
    ),
    "help": re.compile(r"^(help me|what can you do|how do i use (this|the app)|help)[?.! ]*$", re.I),
    "simplify": re.compile(
        r"^(explain (it |that |this )?simply|explain in simple (language|words)|"
        r"simplify( that| it| this)?|make (that|it|this) simpler)[?.! ]*$",
        re.I,
    ),
    "repeat": re.compile(
        r"^(repeat( that| it)?|say that again|repeat yourself|rephrase (that|it|this))[?.! ]*$",
        re.I,
    ),
    "acknowledgment": re.compile(r"^(okay|ok|got it|understood|alright)[!. ]*$", re.I),
}
_LANGUAGE_DIRECTIVE = re.compile(
    r"\b(?:in|into|to)\s+([a-z]+(?:-[a-z]+)?)(?:\s+(?:please|language))?\b|"
    r"\b([a-z]+)\s+(?:me|mein|mein batao)\b",
    re.I,
)


def detect_script_and_language(text: str) -> tuple[str, str]:
    """Detect Unicode script and a best-effort language label, not translation."""
    counts: dict[str, int] = {}
    for character in text:
        if not character.isalpha():
            continue
        name = unicodedata.name(character, "")
        script = next(
            (
                candidate
                for candidate in (
                    "Devanagari",
                    "Arabic",
                    "Bengali",
                    "Tamil",
                    "Telugu",
                    "Gujarati",
                    "Kannada",
                    "Malayalam",
                    "Gurmukhi",
                )
                if candidate.upper() in name
            ),
            "Latin",
        )
        counts[script] = counts.get(script, 0) + 1
    script = max(counts, key=counts.get) if counts else "Latin"
    if script == "Devanagari":
        language = "mr" if re.search(r"(आहे|मला|साठी|काय)", text) else "hi"
    elif script == "Latin":
        lower = text.casefold()
        non_english = re.search(
            r"\b(kya|hai|kaise|mujhe|chahiye|batao|yojana|aap|hain|kijiye)\b",
            lower,
        )
        english_words = re.search(
            r"\b(what|tell|explain|benefit|eligibility|documents|scheme|amount)\b",
            lower,
        )
        if re.search(r"\b(ap|hain|kijiye|batayein)\b", lower):
            language = "roman_urdu"
        elif non_english and english_words:
            language = "hinglish"
        elif non_english:
            language = "roman_hindi"
        else:
            language = "en"
    else:
        language = _SCRIPT_LANGUAGES.get(script, ("en", "English"))[0]
    return script, language


def _explicit_language(text: str) -> tuple[str, str, str] | None:
    match = _LANGUAGE_DIRECTIVE.search(text)
    if not match:
        return None
    name = (match.group(1) or match.group(2) or "").casefold()
    return _LANGUAGES.get(name)


def _intent(text: str) -> str:
    for intent, pattern in _TRANSFORMS.items():
        if pattern.fullmatch(text.strip()):
            return intent
    # Greetings in common scripts should not invoke document retrieval.
    script, _ = detect_script_and_language(text)
    normalized = text.strip()
    if script == "Devanagari" and re.fullmatch(r"(नमस्ते|नमस्कार|हाय)[!. ]*", normalized):
        return "greeting"
    if script == "Arabic" and re.fullmatch(r"(السلام عليكم|مرحبا|سلام)[!. ]*", normalized):
        return "greeting"
    if _TRANSFORMS["help"].fullmatch(normalized):
        return "help"
    return "factual"


def _is_language_transform(text: str) -> bool:
    return bool(
        re.search(
            r"\b(explain|translate|repeat|say|rephrase)\b.*\b(in|into|to)\s+"
            r"(english|hindi|urdu|bengali|bangla|tamil|telugu|marathi|gujarati|"
            r"kannada|malayalam|punjabi|hinglish|roman-hindi|roman-urdu)\b",
            text,
            re.I,
        )
        and not _matched_scheme(text)
    )


def _previous_sources(conversation_id: str) -> list[dict[str, Any]]:
    with connect() as connection:
        row = connection.execute(
            """
            SELECT citations.sources_json
            FROM conversation_messages AS messages
            JOIN conversation_citations AS citations
              ON citations.assistant_message_id = messages.id
            WHERE messages.conversation_id = ? AND messages.role = 'assistant'
            ORDER BY messages.id DESC LIMIT 1
            """,
            (conversation_id,),
        ).fetchone()
    if row is None:
        return []
    sources = json.loads(row["sources_json"])
    return sources if isinstance(sources, list) else []


def _conversation_context(conversation_id: str) -> dict[str, Any]:
    with connect() as connection:
        row = connection.execute(
            """
            SELECT preferred_language, preferred_script, active_scheme_id
                   , rolling_summary
            FROM conversation_context WHERE conversation_id = ?
            """,
            (conversation_id,),
        ).fetchone()
    return dict(row) if row else {
        "preferred_language": "en",
        "preferred_script": "Latin",
        "active_scheme_id": None,
        "rolling_summary": "",
    }


def _matched_scheme(query: str) -> str | None:
    compact_query = re.sub(r"[^a-z0-9]+", "", query.casefold())
    with connect() as connection:
        rows = connection.execute("SELECT id, name FROM schemes").fetchall()
    for row in rows:
        compact_name = re.sub(r"[^a-z0-9]+", "", row["name"].casefold())
        if compact_name and compact_name in compact_query:
            return row["id"]
    aliases = {
        "pmkisan": "pm-kisan",
        "pmjay": "ayushman-bharat-pmjay",
        "fasalbima": "pmfby",
    }
    for alias, scheme_id in aliases.items():
        if alias in compact_query:
            return scheme_id
    return None


def _scheme_name(scheme_id: str | None) -> str | None:
    if not scheme_id:
        return None
    with connect() as connection:
        row = connection.execute(
            "SELECT name FROM schemes WHERE id = ?", (scheme_id,)
        ).fetchone()
    return row["name"] if row else None


def _save_context(
    conversation_id: str,
    language: str,
    script: str,
    active_scheme_id: str | None,
    rolling_summary: str,
) -> None:
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO conversation_context
                (conversation_id, preferred_language, preferred_script, active_scheme_id, rolling_summary)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(conversation_id) DO UPDATE SET
                preferred_language = excluded.preferred_language,
                preferred_script = excluded.preferred_script,
                active_scheme_id = COALESCE(excluded.active_scheme_id, conversation_context.active_scheme_id),
                rolling_summary = excluded.rolling_summary,
                updated_at = CURRENT_TIMESTAMP
            """,
            (conversation_id, language, script, active_scheme_id, rolling_summary),
        )


def process_message(
    query: str,
    conversation_id: str,
    response_language: str = "auto",
) -> dict[str, Any]:
    """Orchestrate language preference, context, intent, and grounded retrieval."""
    pipeline = rag_service.get_rag_pipeline()
    previous_context = _conversation_context(conversation_id)
    script, detected_language = detect_script_and_language(query)
    explicit_language = _explicit_language(query)
    if explicit_language:
        language, script, language_name = explicit_language
    elif response_language in _LANGUAGE_NAMES and response_language != "en":
        language, script, language_name = (
            response_language,
            _LANGUAGE_SCRIPTS[response_language],
            _LANGUAGE_NAMES[response_language],
        )
    elif response_language == "en":
        language, script, language_name = "en", "Latin", "English"
    elif detected_language != "en":
        language = detected_language
        language_name = _LANGUAGE_NAMES.get(language, "English")
    else:
        language = previous_context["preferred_language"]
        language_name = _LANGUAGE_NAMES.get(language, "English")
        script = previous_context["preferred_script"]

    active_scheme_id = _matched_scheme(query) or previous_context["active_scheme_id"]
    intent = _intent(query)
    active_topic = _scheme_name(active_scheme_id)
    summary = (
        f"Active topic: {active_topic or 'not identified'}. "
        f"Preferred language/script: {language}/{script}. Latest intent: {intent}."
    )

    language_transform = bool(explicit_language and _is_language_transform(query))
    if intent in {"greeting", "thanks", "help", "simplify", "repeat", "acknowledgment"} or language_transform:
        # A language switch transforms the preceding answer, without new retrieval.
        transform = "translate" if language_transform else intent
        result = pipeline.respond_without_retrieval(
            query=query,
            conversation_id=conversation_id,
            response_language=language_name,
            intent=transform,
            previous_sources=_previous_sources(conversation_id),
            input_language=detected_language,
        )
        sources = result["sources"]
    else:
        result = rag_service.answer_question(
            query,
            conversation_id,
            response_language=language_name,
            active_topic=active_topic,
            input_language=detected_language,
            conversation_summary=summary,
        )
        sources = result["sources"]

    _save_context(conversation_id, language, script, active_scheme_id, summary)
    return {
        "answer": result["answer"],
        "sources": sources,
        "conversation_id": conversation_id,
        "language": language,
        "direction": "rtl" if language == "ur" else "ltr",
    }
