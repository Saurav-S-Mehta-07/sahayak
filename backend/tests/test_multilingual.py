from app.rag.query_processor import QueryProcessor
from app.utils.language import detect_language, expand_query


def test_detects_devanagari_hindi():
    assert detect_language("पीएम किसान योजना में कौन पात्र है?") == "hindi"


def test_detects_roman_hindi():
    assert detect_language("PM Kisan ke liye eligibility kya hai?") == "hinglish"


def test_detects_english():
    assert detect_language("What documents are required for PM Kisan?") == "english"


def test_cross_language_expansion_preserves_original_query():
    variants = expand_query("PM Kisan ke liye eligibility kya hai?")
    assert variants[0] == "PM Kisan ke liye eligibility kya hai?"
    assert "eligible" in variants[1]


def test_hindi_scheme_query_expands_without_replacing_original():
    variants = expand_query("महिलाओं के लिए सरकारी योजनाएं")
    assert variants[0] == "महिलाओं के लिए सरकारी योजनाएं"
    assert "women" in variants[1]


def test_explicit_language_preference_is_respected():
    processed = QueryProcessor().process("PM Kisan docs", "hindi")
    assert processed.language == "hindi"
    assert processed.original == "PM Kisan docs"
