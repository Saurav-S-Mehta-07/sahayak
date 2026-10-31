from fastapi import APIRouter

from app.api.dependencies import get_runtime
from app.core.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
def api_health() -> dict:
    runtime = get_runtime()
    return {
        "status": "ok",
        "vector_store_initialized": runtime.vector_store._collection is not None,
        "indexed_chunks": (
            runtime.vector_store.count
            if runtime.vector_store._collection is not None
            else 0
        ),
        "groq_configured": bool(settings.groq_api_key),
    }
