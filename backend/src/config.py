"""Configuration for the RAG pipeline."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def _int_setting(name: str, default: int) -> int:
    value = os.getenv(name)
    try:
        return int(value) if value is not None else default
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


def _float_setting(name: str, default: float) -> float:
    value = os.getenv(name)
    try:
        return float(value) if value is not None else default
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc


def _path_setting(name: str, default: str) -> Path:
    value = Path(os.getenv(name, default)).expanduser()
    return value if value.is_absolute() else PROJECT_ROOT / value


@dataclass(frozen=True)
class Settings:
    pdf_dir: Path = _path_setting("PDF_DIR", "data/pdfs")
    vector_store_dir: Path = _path_setting("VECTOR_STORE_DIR", "vector_store")
    collection_name: str = os.getenv("CHROMA_COLLECTION", "pdf_documents")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    chunk_size: int = _int_setting("CHUNK_SIZE", 500)
    chunk_overlap: int = _int_setting("CHUNK_OVERLAP", 50)
    retrieval_top_k: int = _int_setting("RETRIEVAL_TOP_K", 5)
    retrieval_score_threshold: float = _float_setting(
        "RETRIEVAL_SCORE_THRESHOLD", 0.0
    )
    groq_model: str = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    groq_temperature: float = _float_setting("GROQ_TEMPERATURE", 0.1)
    max_response_tokens: int = _int_setting("MAX_RESPONSE_TOKENS", 1024)
    context_window_tokens: int = _int_setting("CONTEXT_WINDOW_TOKENS", 12000)
    history_budget_tokens: int = _int_setting("HISTORY_BUDGET_TOKENS", 1800)
    document_budget_tokens: int = _int_setting("DOCUMENT_BUDGET_TOKENS", 7000)
    max_recent_messages: int = _int_setting("MAX_RECENT_MESSAGES", 12)
    sqlite_path: Path = _path_setting(
        "SQLITE_PATH", "data/conversations.sqlite3"
    )
    scheme_discovery_feed_urls: tuple[str, ...] = tuple(
        feed.strip()
        for feed in os.getenv("SCHEME_DISCOVERY_FEEDS", "").split(",")
        if feed.strip()
    )
    scheme_discovery_interval_hours: int = _int_setting(
        "SCHEME_DISCOVERY_INTERVAL_HOURS", 0
    )


settings = Settings()
