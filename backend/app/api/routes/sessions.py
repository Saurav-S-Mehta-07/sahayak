from fastapi import APIRouter, HTTPException, Query, Response, status

from app.api.dependencies import get_runtime
from app.models.schemas import SessionCreateResponse, SessionHistoryResponse

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", response_model=SessionCreateResponse, status_code=status.HTTP_201_CREATED)
def create_session(
    language: str = Query(default="english", pattern="^(english|hindi|hinglish)$"),
) -> dict:
    return get_runtime().memory.create_session(language)


@router.get("/{session_id}/history", response_model=SessionHistoryResponse)
def get_session_history(session_id: str) -> dict:
    history = get_runtime().memory.history(session_id)
    if history is None:
        raise HTTPException(status_code=404, detail="Conversation session not found")
    return history


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(session_id: str) -> Response:
    if not get_runtime().memory.delete_session(session_id):
        raise HTTPException(status_code=404, detail="Conversation session not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
