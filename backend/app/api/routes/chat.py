from fastapi import APIRouter, HTTPException

from app.api.dependencies import get_runtime
from app.models.schemas import ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    try:
        return await get_runtime().chat.chat(request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Conversation session not found") from exc
