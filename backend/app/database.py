"""SQLite persistence for accounts and document-management metadata."""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

if __package__ and __package__.startswith("backend."):
    from backend.src.config import settings
else:
    from src.config import settings

_initialized = False
_initialization_lock = threading.Lock()


def _connect() -> sqlite3.Connection:
    settings.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(settings.sqlite_path, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database() -> None:
    """Create additive application tables, preserving existing chat memory."""
    global _initialized
    if _initialized:
        return
    with _initialization_lock:
        if _initialized:
            return
        with _connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('citizen', 'admin')),
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    csrf_hash TEXT NOT NULL,
                    expires_at REAL NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_sessions_expiry ON sessions(expires_at);
                CREATE TABLE IF NOT EXISTS conversation_owners (
                    conversation_id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    title TEXT NOT NULL DEFAULT 'New conversation',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS conversation_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                    content TEXT NOT NULL,
                    language TEXT NOT NULL DEFAULT 'en',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_conversation_messages
                    ON conversation_messages (conversation_id, id);
                CREATE TABLE IF NOT EXISTS conversation_citations (
                    assistant_message_id INTEGER PRIMARY KEY
                        REFERENCES conversation_messages(id) ON DELETE CASCADE,
                    sources_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS conversation_context (
                    conversation_id TEXT PRIMARY KEY
                        REFERENCES conversation_owners(conversation_id) ON DELETE CASCADE,
                    preferred_language TEXT NOT NULL DEFAULT 'en',
                    preferred_script TEXT NOT NULL DEFAULT 'Latin',
                    active_scheme_id TEXT,
                    rolling_summary TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS schemes (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    ministry TEXT NOT NULL,
                    official_source_url TEXT NOT NULL,
                    language TEXT NOT NULL DEFAULT 'English',
                    version_date TEXT,
                    source_status TEXT NOT NULL DEFAULT 'source_listed'
                );
                CREATE TABLE IF NOT EXISTS scheme_discoveries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    source_url TEXT NOT NULL UNIQUE,
                    feed_url TEXT NOT NULL,
                    source_organization TEXT NOT NULL,
                    published_at TEXT,
                    excerpt TEXT NOT NULL DEFAULT '',
                    discovered_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    status TEXT NOT NULL DEFAULT 'pending_verification'
                        CHECK (status IN (
                            'pending_verification', 'under_review',
                            'needs_more_information', 'rejected'
                        )),
                    reviewer_id INTEGER REFERENCES users(id),
                    reviewed_at TEXT,
                    review_notes TEXT NOT NULL DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS idx_scheme_discoveries_status
                    ON scheme_discoveries (status, discovered_at DESC);
                CREATE TABLE IF NOT EXISTS scheme_discovery_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    discovery_id INTEGER NOT NULL
                        REFERENCES scheme_discoveries(id) ON DELETE CASCADE,
                    admin_id INTEGER NOT NULL REFERENCES users(id),
                    action TEXT NOT NULL,
                    previous_status TEXT NOT NULL,
                    new_status TEXT NOT NULL,
                    notes TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS scheme_documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scheme_id TEXT NOT NULL REFERENCES schemes(id),
                    filename TEXT NOT NULL,
                    storage_path TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    language TEXT NOT NULL,
                    version_date TEXT,
                    retrieval_date TEXT NOT NULL,
                    sha256 TEXT NOT NULL UNIQUE,
                    page_count INTEGER,
                    chunk_count INTEGER NOT NULL DEFAULT 0,
                    verification_status TEXT NOT NULL DEFAULT 'pending_verification',
                    extraction_status TEXT NOT NULL DEFAULT 'pending',
                    indexing_status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS scheme_eligibility_criteria (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scheme_id TEXT NOT NULL REFERENCES schemes(id) ON DELETE CASCADE,
                    field_key TEXT NOT NULL,
                    operator TEXT NOT NULL CHECK (
                        operator IN ('eq', 'ne', 'gte', 'lte', 'in', 'contains')
                    ),
                    expected_value_json TEXT NOT NULL,
                    description TEXT NOT NULL,
                    source_document_id INTEGER NOT NULL
                        REFERENCES scheme_documents(id) ON DELETE RESTRICT,
                    source_page INTEGER NOT NULL CHECK (source_page >= 1),
                    source_excerpt TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (scheme_id, field_key, operator, expected_value_json, source_document_id)
                );
                CREATE INDEX IF NOT EXISTS idx_scheme_eligibility
                    ON scheme_eligibility_criteria (scheme_id, field_key);
                CREATE TABLE IF NOT EXISTS document_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_id INTEGER NOT NULL REFERENCES scheme_documents(id),
                    event TEXT NOT NULL,
                    detail TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            message_columns = {
                row["name"]
                for row in connection.execute(
                    "PRAGMA table_info(conversation_messages)"
                ).fetchall()
            }
            if "language" not in message_columns:
                connection.execute(
                    "ALTER TABLE conversation_messages ADD COLUMN language TEXT NOT NULL DEFAULT 'en'"
                )
            context_columns = {
                row["name"]
                for row in connection.execute(
                    "PRAGMA table_info(conversation_context)"
                ).fetchall()
            }
            if "rolling_summary" not in context_columns:
                connection.execute(
                    "ALTER TABLE conversation_context ADD COLUMN rolling_summary TEXT NOT NULL DEFAULT ''"
                )
            owner_columns = {
                row["name"]
                for row in connection.execute(
                    "PRAGMA table_info(conversation_owners)"
                ).fetchall()
            }
            if "title" not in owner_columns:
                connection.execute(
                    "ALTER TABLE conversation_owners ADD COLUMN title TEXT NOT NULL DEFAULT 'New conversation'"
                )
            seed_path = Path(__file__).parent / "data" / "schemes.json"
            if seed_path.exists():
                schemes: list[dict[str, Any]] = json.loads(
                    seed_path.read_text(encoding="utf-8")
                )
                connection.executemany(
                    """
                    INSERT OR IGNORE INTO schemes
                        (id, name, ministry, official_source_url, language, version_date)
                    VALUES (:id, :name, :ministry, :official_source_url, :language, :version_date)
                    """,
                    schemes,
                )
        _initialized = True


def connect() -> sqlite3.Connection:
    initialize_database()
    return _connect()


def user_view(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "email": row["email"],
        "role": row["role"],
        "created_at": row["created_at"],
    }
