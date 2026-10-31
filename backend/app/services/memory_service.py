from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from app.core.config import settings
from app.core.mongo_storage import MongoMemoryRepository
from app.utils.profile import update_user_profile


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class MemoryService:
    def __init__(
        self,
        database_path: Path | None = None,
        max_recent_messages: int = settings.max_recent_messages,
    ):
        self.max_recent_messages = max(2, max_recent_messages)
        self.mongo: MongoMemoryRepository | None = None
        if database_path is None and settings.mongodb_uri:
            self.mongo = MongoMemoryRepository(self.max_recent_messages)
            self.database_path = None
            self._lock = threading.RLock()
            return
        self.database_path = database_path or settings.database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    context_json TEXT NOT NULL,
                    summary TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
                    role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                    content TEXT NOT NULL,
                    citations_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_messages_session
                    ON messages(session_id, id);
                """
            )

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def create_session(self, language: str = "english") -> dict[str, Any]:
        if self.mongo:
            return self.mongo.create_session(language)
        session_id = f"sess_{uuid.uuid4().hex}"
        created_at = _utcnow()
        context = {
            "current_scheme": None,
            "preferred_language": language,
            "user_profile": {},
            "previous_topics": [],
            "pending_questions": [],
        }
        with self._lock, self._connect() as connection:
            connection.execute(
                "INSERT INTO sessions(session_id, created_at, updated_at, context_json) "
                "VALUES (?, ?, ?, ?)",
                (session_id, created_at, created_at, json.dumps(context)),
            )
        return {"session_id": session_id, "created_at": created_at, "context": context}

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        if self.mongo:
            return self.mongo.get_session(session_id)
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
        if row is None:
            return None
        return {
            "session_id": row["session_id"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "context": json.loads(row["context_json"]),
            "summary": row["summary"],
        }

    def context_and_messages(self, session_id: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        if self.mongo:
            return self.mongo.context_and_messages(session_id)
        session = self.get_session(session_id)
        if session is None:
            raise KeyError(session_id)
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                "SELECT role, content, citations_json, created_at FROM messages "
                "WHERE session_id = ? ORDER BY id DESC LIMIT ?",
                (session_id, self.max_recent_messages),
            ).fetchall()
        messages = [
            {
                "role": row["role"],
                "content": row["content"],
                "citations": json.loads(row["citations_json"]),
                "created_at": row["created_at"],
            }
            for row in reversed(rows)
        ]
        return session, messages

    def record_exchange(
        self,
        session_id: str,
        user_message: str,
        answer: str,
        citations: list[dict[str, Any]],
        language: str,
        current_scheme: str | None,
    ) -> None:
        if self.mongo:
            self.mongo.record_exchange(
                session_id,
                user_message,
                answer,
                citations,
                language,
                current_scheme,
            )
            return
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT context_json, summary FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if row is None:
                raise KeyError(session_id)
            context = json.loads(row["context_json"])
            context["preferred_language"] = language
            if current_scheme:
                previous = context.get("current_scheme")
                if previous and previous != current_scheme:
                    context["previous_topics"] = (
                        context.get("previous_topics", []) + [previous]
                    )[-5:]
                context["current_scheme"] = current_scheme
            context["user_profile"] = update_user_profile(
                context.get("user_profile", {}), user_message
            )
            connection.execute(
                "INSERT INTO messages(session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                (session_id, "user", user_message, _utcnow()),
            )
            connection.execute(
                "INSERT INTO messages(session_id, role, content, citations_json, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (session_id, "assistant", answer, json.dumps(citations), _utcnow()),
            )
            recent = connection.execute(
                "SELECT role, content FROM messages WHERE session_id = ? "
                "ORDER BY id ASC LIMIT -1 OFFSET ?",
                (session_id, self.max_recent_messages),
            ).fetchall()
            summary_lines = [
                f"{item['role']}: {item['content'][:300]}" for item in recent
            ]
            summary = "\n".join(summary_lines)[-1600:]
            connection.execute(
                "UPDATE sessions SET context_json = ?, summary = ?, updated_at = ? "
                "WHERE session_id = ?",
                (json.dumps(context), summary, _utcnow(), session_id),
            )

    def history(self, session_id: str) -> dict[str, Any] | None:
        if self.mongo:
            return self.mongo.history(session_id)
        session = self.get_session(session_id)
        if session is None:
            return None
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                "SELECT role, content, citations_json, created_at FROM messages "
                "WHERE session_id = ? ORDER BY id",
                (session_id,),
            ).fetchall()
        return {
            "session_id": session_id,
            "messages": [
                {
                    "role": row["role"],
                    "content": row["content"],
                    "citations": json.loads(row["citations_json"]),
                    "created_at": row["created_at"],
                }
                for row in rows
            ],
            "conversation_context": session["context"] | {"summary": session["summary"]},
        }

    def delete_session(self, session_id: str) -> bool:
        if self.mongo:
            return self.mongo.delete_session(session_id)
        with self._lock, self._connect() as connection:
            cursor = connection.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        return cursor.rowcount > 0
