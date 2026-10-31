"""RAG chat endpoint."""

import logging
import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ..auth import get_current_user, require_user_csrf
from ..database import connect
from ..schemas.chat import ChatRequest, ChatResponse, ConversationTitleRequest
from ..services.conversation_orchestrator import process_message

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest, user: dict[str, Any] = Depends(require_user_csrf)
) -> dict[str, Any]:
    """Answer a question using retrieved passages from the existing RAG system."""
    conversation_id = request.conversation_id or str(uuid.uuid4())
    with connect() as connection:
        owner = connection.execute(
            "SELECT user_id FROM conversation_owners WHERE conversation_id = ?",
            (conversation_id,),
        ).fetchone()
        if owner is None:
            legacy_turn = connection.execute(
                "SELECT 1 FROM conversation_messages WHERE conversation_id = ? LIMIT 1",
                (conversation_id,),
            ).fetchone()
            if legacy_turn:
                raise HTTPException(
                    status_code=403,
                    detail="This conversation is not available to this account.",
                )
            connection.execute(
                "INSERT INTO conversation_owners (conversation_id, user_id, title) VALUES (?, ?, ?)",
                (
                    conversation_id,
                    user["id"],
                    request.conversation_title or "New conversation",
                ),
            )
        elif owner["user_id"] != user["id"]:
            raise HTTPException(
                status_code=404, detail="Conversation not found."
            )
    try:
        result = process_message(
            request.query,
            conversation_id,
            response_language=request.response_language,
        )
        with connect() as connection:
            assistant_message = connection.execute(
                """
                SELECT id FROM conversation_messages
                WHERE conversation_id = ? AND role = 'assistant'
                ORDER BY id DESC LIMIT 1
                """,
                (conversation_id,),
            ).fetchone()
            if assistant_message:
                connection.execute(
                    """
                    INSERT OR REPLACE INTO conversation_citations
                        (assistant_message_id, sources_json)
                    VALUES (?, ?)
                    """,
                    (
                        assistant_message["id"],
                        json.dumps(result.get("sources", []), ensure_ascii=False),
                    ),
                )
        return result
    except ValueError as exc:
        with connect() as connection:
            connection.execute(
                """
                DELETE FROM conversation_owners WHERE conversation_id = ?
                AND NOT EXISTS (
                    SELECT 1 FROM conversation_messages WHERE conversation_id = ?
                )
                """,
                (conversation_id, conversation_id),
            )
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("RAG query failed")
        raise HTTPException(
            status_code=502,
            detail=(
                "The RAG service could not complete this query. "
                "Check the backend logs."
            ),
        ) from exc


@router.get("/conversations")
def list_conversations(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, list]:
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT owners.conversation_id, owners.title, messages.id, messages.role,
                   messages.content, messages.language, messages.created_at,
                   citations.sources_json
            FROM conversation_owners AS owners
            LEFT JOIN conversation_messages AS messages
                ON messages.conversation_id = owners.conversation_id
            LEFT JOIN conversation_citations AS citations
                ON citations.assistant_message_id = messages.id
            WHERE owners.user_id = ?
            ORDER BY owners.created_at DESC, messages.id ASC
            """,
            (user["id"],),
        ).fetchall()
    conversations: dict[str, dict[str, Any]] = {}
    for row in rows:
        conversation = conversations.setdefault(
            row["conversation_id"],
            {
                "id": row["conversation_id"],
                "title": row["title"],
                "updatedAt": row["created_at"],
                "messages": [],
            },
        )
        if row["id"] is not None:
            message = {
                "id": str(row["id"]),
                "role": row["role"],
                "content": row["content"],
                "language": row["language"],
                "createdAt": row["created_at"],
                "sources": json.loads(row["sources_json"] or "[]"),
            }
            conversation["messages"].append(message)
            conversation["updatedAt"] = row["created_at"]
            if row["role"] == "user" and conversation["title"] == "New conversation":
                conversation["title"] = row["content"][:52]
    return {"conversations": list(conversations.values())}


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(
    conversation_id: str, user: dict[str, Any] = Depends(require_user_csrf)
) -> None:
    with connect() as connection:
        cursor = connection.execute(
            "DELETE FROM conversation_owners WHERE conversation_id = ? AND user_id = ?",
            (conversation_id, user["id"]),
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Conversation not found.")
        connection.execute(
            "DELETE FROM conversation_messages WHERE conversation_id = ?",
            (conversation_id,),
        )


@router.patch("/conversations/{conversation_id}")
def rename_conversation(
    conversation_id: str,
    request: ConversationTitleRequest,
    user: dict[str, Any] = Depends(require_user_csrf),
) -> dict[str, str]:
    with connect() as connection:
        cursor = connection.execute(
            """
            UPDATE conversation_owners SET title = ?
            WHERE conversation_id = ? AND user_id = ?
            """,
            (request.title, conversation_id, user["id"]),
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Conversation not found.")
    return {"id": conversation_id, "title": request.title}


@router.delete("/conversations/{conversation_id}/messages", status_code=204)
def clear_conversation(
    conversation_id: str, user: dict[str, Any] = Depends(require_user_csrf)
) -> None:
    with connect() as connection:
        owner = connection.execute(
            "SELECT 1 FROM conversation_owners WHERE conversation_id = ? AND user_id = ?",
            (conversation_id, user["id"]),
        ).fetchone()
        if owner is None:
            raise HTTPException(status_code=404, detail="Conversation not found.")
        connection.execute(
            "DELETE FROM conversation_messages WHERE conversation_id = ?",
            (conversation_id,),
        )
        connection.execute(
            "DELETE FROM conversation_context WHERE conversation_id = ?",
            (conversation_id,),
        )
