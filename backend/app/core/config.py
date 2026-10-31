from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPOSITORY_DIR = BACKEND_DIR.parent
load_dotenv(REPOSITORY_DIR / ".env", override=False)


def _integer(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


def _floating(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc


def _boolean(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    backend_dir: Path = BACKEND_DIR
    pdf_dir: Path = BACKEND_DIR / "data" / "pdfs"
    processed_dir: Path = BACKEND_DIR / "data" / "processed"
    vector_dir: Path = BACKEND_DIR / "data" / "vector_store"
    database_path: Path = BACKEND_DIR / "data" / "processed" / "sahayak.sqlite3"
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    groq_api_key: str | None = os.getenv("GROQ_API_KEY")
    groq_model: str = os.getenv("GROQ_MODEL", "qwen/qwen3-32b")
    groq_temperature: float = _floating("GROQ_TEMPERATURE", 0.1)
    groq_max_tokens: int = _integer("GROQ_MAX_TOKENS", 1024)
    groq_timeout_seconds: float = _floating("GROQ_TIMEOUT_SECONDS", 30.0)
    groq_retries: int = _integer("GROQ_RETRIES", 2)
    mongodb_uri: str | None = os.getenv("MONGODB_URI")
    mongodb_username: str | None = os.getenv("MONGODB_USERNAME")
    mongodb_password: str | None = os.getenv("MONGODB_PASSWORD")
    mongodb_database: str | None = os.getenv("MONGODB_DATABASE")
    retrieval_top_k: int = _integer("RETRIEVAL_TOP_K", 5)
    retrieval_min_similarity: float = _floating("RETRIEVAL_MIN_SIMILARITY", 0.5)
    max_request_characters: int = _integer("MAX_REQUEST_CHARACTERS", 4000)
    max_context_characters: int = _integer("MAX_CONTEXT_CHARACTERS", 14000)
    max_recent_messages: int = _integer("MAX_RECENT_MESSAGES", 12)
    ingestion_api_key: str | None = os.getenv("INGESTION_API_KEY")
    cors_origins: tuple[str, ...] = tuple(
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
        if origin.strip()
    )
    log_level: str = os.getenv("LOG_LEVEL", "INFO")


settings = Settings()
