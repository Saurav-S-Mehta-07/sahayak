from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any
from urllib.parse import urlsplit

from pymongo import ASCENDING, MongoClient
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import PyMongoError

from app.core.config import settings
from app.core.exceptions import ServiceUnavailableError
from app.utils.profile import update_user_profile

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def mongo_database() -> Database:
    if not settings.mongodb_uri:
        raise ServiceUnavailableError("MONGODB_URI is not configured")
    parsed = urlsplit(settings.mongodb_uri)
    options: dict[str, Any] = {
        "serverSelectionTimeoutMS": 5000,
        "connectTimeoutMS": 5000,
        "appname": "yojana-sahayak",
    }
    if not parsed.username and settings.mongodb_username:
        options["username"] = settings.mongodb_username
        if settings.mongodb_password:
            options["password"] = settings.mongodb_password
    try:
        client = MongoClient(settings.mongodb_uri, **options)
        database_name = (
            settings.mongodb_database
            or parsed.path.strip("/").split("/", 1)[0]
            or "yojana_sahayak"
        )
        return client[database_name]
    except PyMongoError as exc:
        logger.error("Could not initialize MongoDB client (%s)", type(exc).__name__)
        raise ServiceUnavailableError("MongoDB storage is unavailable") from exc


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class MongoMemoryRepository:
    def __init__(
        self,
        max_recent_messages: int,
        database: Database | None = None,
    ):
        self.max_recent_messages = max_recent_messages
        self.database = database or mongo_database()
        self.sessions: Collection = self.database["yojana_sahayak_sessions"]
        self.messages: Collection = self.database["yojana_sahayak_messages"]
        self._indexes_ready = False

    def _ensure_indexes(self) -> None:
        if self._indexes_ready:
            return
        try:
            self.messages.create_index([("session_id", ASCENDING), ("sequence", ASCENDING)])
        except PyMongoError as exc:
            raise ServiceUnavailableError("MongoDB session storage is unavailable") from exc
        self._indexes_ready = True

    def create_session(self, language: str) -> dict[str, Any]:
        self._ensure_indexes()
        session_id = f"sess_{uuid.uuid4().hex}"
        created_at = _now()
        context = {
            "current_scheme": None,
            "preferred_language": language,
            "user_profile": {},
            "previous_topics": [],
            "pending_questions": [],
        }
        try:
            self.sessions.insert_one(
                {
                    "_id": session_id,
                    "created_at": created_at,
                    "updated_at": created_at,
                    "context": context,
                    "summary": "",
                    "message_sequence": 0,
                }
            )
        except PyMongoError as exc:
            raise ServiceUnavailableError("Could not create conversation session") from exc
        return {"session_id": session_id, "created_at": created_at, "context": context}

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        self._ensure_indexes()
        try:
            row = self.sessions.find_one({"_id": session_id})
        except PyMongoError as exc:
            raise ServiceUnavailableError("Could not read conversation session") from exc
        if row is None:
            return None
        return {
            "session_id": row["_id"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "context": row["context"],
            "summary": row.get("summary", ""),
        }

    def context_and_messages(self, session_id: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        session = self.get_session(session_id)
        if session is None:
            raise KeyError(session_id)
        try:
            rows = list(
                self.messages.find({"session_id": session_id})
                .sort("sequence", -1)
                .limit(self.max_recent_messages)
            )
        except PyMongoError as exc:
            raise ServiceUnavailableError("Could not read conversation history") from exc
        rows.reverse()
        return session, [
            {
                "role": row["role"],
                "content": row["content"],
                "citations": row.get("citations", []),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def record_exchange(
        self,
        session_id: str,
        user_message: str,
        answer: str,
        citations: list[dict[str, Any]],
        language: str,
        current_scheme: str | None,
    ) -> None:
        self._ensure_indexes()
        session = self.get_session(session_id)
        if session is None:
            raise KeyError(session_id)
        context = session["context"]
        context["preferred_language"] = language
        if current_scheme:
            previous = context.get("current_scheme")
            if previous and previous != current_scheme:
                context["previous_topics"] = (context.get("previous_topics", []) + [previous])[-5:]
            context["current_scheme"] = current_scheme

        context["user_profile"] = update_user_profile(
            context.get("user_profile", {}), user_message
        )

        try:
            latest = self.sessions.find_one_and_update(
                {"_id": session_id},
                {"$inc": {"message_sequence": 2}},
                return_document=True,
            )
            if latest is None:
                raise KeyError(session_id)
            previous_count = int(latest["message_sequence"]) - 2
            recent_messages = list(
                self.messages.find({"session_id": session_id})
                .sort("sequence", -1)
                .limit(self.max_recent_messages)
            )
        except PyMongoError as exc:
            raise ServiceUnavailableError("Could not save conversation messages") from exc
        recent_messages.reverse()
        message_docs = [
            {
                "session_id": session_id,
                "sequence": previous_count + offset + 1,
                "role": role,
                "content": content,
                "citations": citations if role == "assistant" else [],
                "created_at": _now(),
            }
            for offset, (role, content) in enumerate(
                (("user", user_message), ("assistant", answer))
            )
        ]
        summary_lines = [
            f"{item['role']}: {item['content'][:300]}"
            for item in recent_messages
            if item.get("content")
        ]
        summary = "\n".join(summary_lines)[-1600:]
        try:
            self.messages.insert_many(message_docs)
            self.sessions.update_one(
                {"_id": session_id},
                {
                    "$set": {
                        "context": context,
                        "summary": summary,
                        "updated_at": _now(),
                    }
                },
            )
        except PyMongoError as exc:
            raise ServiceUnavailableError("Could not save conversation messages") from exc

    def history(self, session_id: str) -> dict[str, Any] | None:
        self._ensure_indexes()
        session = self.get_session(session_id)
        if session is None:
            return None
        try:
            rows = self.messages.find({"session_id": session_id}).sort("sequence", ASCENDING)
            messages = [
                {
                    "role": row["role"],
                    "content": row["content"],
                    "citations": row.get("citations", []),
                    "created_at": row["created_at"],
                }
                for row in rows
            ]
        except PyMongoError as exc:
            raise ServiceUnavailableError("Could not read conversation history") from exc
        return {
            "session_id": session_id,
            "messages": messages,
            "conversation_context": session["context"] | {"summary": session["summary"]},
        }

    def delete_session(self, session_id: str) -> bool:
        self._ensure_indexes()
        try:
            result = self.sessions.delete_one({"_id": session_id})
            self.messages.delete_many({"session_id": session_id})
        except PyMongoError as exc:
            raise ServiceUnavailableError("Could not delete conversation session") from exc
        return result.deleted_count > 0


class MongoDocumentRepository:
    def __init__(self, database: Database | None = None):
        self.collection: Collection = (database or mongo_database())[
            "yojana_sahayak_indexed_documents"
        ]
        self._indexes_ready = False

    def _ensure_indexes(self) -> None:
        if self._indexes_ready:
            return
        try:
            self.collection.create_index("document_id", unique=True)
            self.collection.create_index("source_path", unique=True)
            self.collection.create_index("checksum")
        except PyMongoError as exc:
            raise ServiceUnavailableError("MongoDB document metadata is unavailable") from exc
        self._indexes_ready = True

    def all(self) -> dict[str, dict[str, Any]]:
        self._ensure_indexes()
        try:
            return {
                str(row["source_path"]): row
                for row in self.collection.find({}, {"_id": 0})
            }
        except PyMongoError as exc:
            raise ServiceUnavailableError("Could not read document metadata") from exc

    def upsert(self, document: dict[str, Any]) -> None:
        self._ensure_indexes()
        try:
            self.collection.replace_one(
                {"document_id": document["document_id"]},
                document,
                upsert=True,
            )
        except PyMongoError as exc:
            raise ServiceUnavailableError("Could not save document metadata") from exc

    def delete_source(self, source_path: str) -> None:
        self._ensure_indexes()
        try:
            self.collection.delete_one({"source_path": source_path})
        except PyMongoError as exc:
            raise ServiceUnavailableError("Could not remove document metadata") from exc

    def list_documents(self) -> list[dict[str, Any]]:
        self._ensure_indexes()
        try:
            return list(self.collection.find({}, {"_id": 0}).sort("document_name", ASCENDING))
        except PyMongoError as exc:
            raise ServiceUnavailableError("Could not list document metadata") from exc

    def get_document(self, document_id: str) -> dict[str, Any] | None:
        self._ensure_indexes()
        try:
            return self.collection.find_one({"document_id": document_id}, {"_id": 0})
        except PyMongoError as exc:
            raise ServiceUnavailableError("Could not read document metadata") from exc

    def clear_all(self) -> None:
        self._ensure_indexes()
        try:
            self.collection.delete_many({})
        except PyMongoError as exc:
            raise ServiceUnavailableError("Could not clear document metadata") from exc
