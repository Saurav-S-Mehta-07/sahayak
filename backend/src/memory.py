"""SQLite-backed conversation memory with a bounded prompt context."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import TypedDict

from .config import settings

logger = logging.getLogger(__name__)


class Message(TypedDict):
    role: str
    content: str


def _token_estimate(text: str) -> int:
    return max(1, (len(text) + 3) // 4)


class ConversationMemory:
    """Persist conversation turns and return recent history within a token budget."""

    def __init__(self, database_path: str | Path | None = None) -> None:
        self.database_path = Path(database_path or settings.sqlite_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS conversation_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                    content TEXT NOT NULL,
                    language TEXT NOT NULL DEFAULT 'en',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            columns = {
                row[1]
                for row in connection.execute(
                    "PRAGMA table_info(conversation_messages)"
                ).fetchall()
            }
            if "language" not in columns:
                connection.execute(
                    "ALTER TABLE conversation_messages ADD COLUMN language TEXT NOT NULL DEFAULT 'en'"
                )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_conversation_messages
                ON conversation_messages (conversation_id, id)
                """
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database_path, timeout=30)

    def load_history(
        self,
        conversation_id: str,
        max_messages: int | None = None,
        token_budget: int | None = None,
    ) -> list[Message]:
        """Load the newest messages that fit within the configured context limits."""
        if not conversation_id.strip():
            raise ValueError("conversation_id must not be empty")
        message_limit = (
            settings.max_recent_messages if max_messages is None else max_messages
        )
        budget = settings.history_budget_tokens if token_budget is None else token_budget
        if message_limit < 0 or budget < 0:
            raise ValueError("Memory limits cannot be negative")
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT role, content FROM conversation_messages
                WHERE conversation_id = ?
                ORDER BY id DESC LIMIT ?
                """,
                (conversation_id, message_limit),
            ).fetchall()

        selected: list[Message] = []
        used_tokens = 0
        for role, content in rows:
            message_tokens = _token_estimate(content)
            if used_tokens + message_tokens <= budget:
                selected.append({"role": role, "content": content})
                used_tokens += message_tokens
                continue
            if not selected and budget > 0:
                selected.append(
                    {"role": role, "content": content[: budget * 4]}
                )
            break
        selected.reverse()
        return selected

    def add_turn(
        self,
        conversation_id: str,
        query: str,
        answer: str,
        user_language: str = "en",
        assistant_language: str = "en",
    ) -> None:
        """Persist a successful user/assistant exchange atomically."""
        if not conversation_id.strip():
            raise ValueError("conversation_id must not be empty")
        if not query.strip() or not answer.strip():
            raise ValueError("Conversation messages must not be empty")
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO conversation_messages
                    (conversation_id, role, content, language)
                VALUES (?, ?, ?, ?)
                """,
                (
                    (conversation_id, "user", query, user_language),
                    (conversation_id, "assistant", answer, assistant_language),
                ),
            )

    def clear(self, conversation_id: str) -> None:
        """Delete all stored messages for one conversation."""
        if not conversation_id.strip():
            raise ValueError("conversation_id must not be empty")
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM conversation_messages WHERE conversation_id = ?",
                (conversation_id,),
            )
        logger.info("Cleared memory for conversation %s", conversation_id)
