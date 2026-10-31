from __future__ import annotations

from backend.app.services.conversation_orchestrator import (
    _intent,
    _is_language_transform,
    detect_script_and_language,
)
from backend.app.schemas.chat import ChatRequest


def test_script_detection_labels_supported_unicode_scripts() -> None:
    assert detect_script_and_language("नमस्ते, मुझे योजना बताइए") == (
        "Devanagari",
        "hi",
    )
    assert detect_script_and_language("السلام عليكم") == ("Arabic", "ur")
    assert detect_script_and_language("வணக்கம்") == ("Tamil", "ta")
    assert detect_script_and_language("Hello, tell me about PM-KISAN") == (
        "Latin",
        "en",
    )
    assert detect_script_and_language("বাংলা") == ("Bengali", "bn")
    assert detect_script_and_language("తెలుగు") == ("Telugu", "te")
    assert detect_script_and_language("ગુજરાતી") == ("Gujarati", "gu")
    assert detect_script_and_language("ಕನ್ನಡ") == ("Kannada", "kn")
    assert detect_script_and_language("മലയാളം") == ("Malayalam", "ml")
    assert detect_script_and_language("ਪੰਜਾਬੀ") == ("Gurmukhi", "pa")
    assert detect_script_and_language("मला योजना पाहिजे") == (
        "Devanagari",
        "mr",
    )
    assert detect_script_and_language("Yojana benefit kya hai?") == (
        "Latin",
        "hinglish",
    )
    assert detect_script_and_language("Mujhe kya karna chahiye?") == (
        "Latin",
        "roman_hindi",
    )
    assert detect_script_and_language("Aap eligibility batayein") == (
        "Latin",
        "roman_urdu",
    )


def test_non_factual_messages_are_classified_without_triggering_rag() -> None:
    assert _intent("Hi") == "greeting"
    assert _intent("Thank you") == "thanks"
    assert _intent("What can you do?") == "help"
    assert _intent("Okay") == "acknowledgment"
    assert _intent("What documents do I need?") == "factual"


def test_language_switch_is_transform_unless_query_names_a_scheme() -> None:
    assert _is_language_transform("Explain everything in Hindi")
    assert not _is_language_transform("Tell me about PM-KISAN in Hindi")
    assert _is_language_transform("Explain that in Roman-Urdu")


def test_chat_request_accepts_only_configured_response_languages() -> None:
    supported = (
        "auto", "en", "hi", "ur", "bn", "ta", "te", "mr", "gu", "kn",
        "ml", "pa", "hinglish", "roman_hindi", "roman_urdu",
    )
    for language in supported:
        assert ChatRequest(query="Hello", response_language=language).response_language == language
