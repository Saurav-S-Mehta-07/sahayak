import asyncio

from app.models.schemas import ChatRequest
from app.services.chat_service import ChatService
from app.services.memory_service import MemoryService


class NoResultsRetriever:
    def retrieve(self, *args, **kwargs):
        return []


class UnusedLLM:
    async def answer(self, *args, **kwargs):
        raise AssertionError("LLM must not run when retrieval has no evidence")


def test_sessions_are_isolated(tmp_path):
    memory = MemoryService(tmp_path / "sessions.sqlite3")
    first = memory.create_session()
    second = memory.create_session()
    memory.record_exchange(first["session_id"], "Hello", "Hi", [], "english", None)
    first_history = memory.history(first["session_id"])
    second_history = memory.history(second["session_id"])
    assert len(first_history["messages"]) == 2
    assert second_history["messages"] == []


def test_volunteered_profile_is_structured_and_retained(tmp_path):
    memory = MemoryService(tmp_path / "sessions.sqlite3")
    session = memory.create_session()
    memory.record_exchange(
        session["session_id"],
        "I am 24 years old, a farmer. My state is Uttarakhand.",
        "Thanks.",
        [],
        "english",
        "PM-KISAN",
    )
    profile = memory.history(session["session_id"])["conversation_context"]["user_profile"]
    assert profile["age"] == 24
    assert profile["occupation"] == "farmer"
    assert profile["farmer"] is True
    assert profile["state"] == "Uttarakhand"


def test_chat_returns_explicit_missing_evidence_and_creates_session(tmp_path):
    memory = MemoryService(tmp_path / "sessions.sqlite3")
    service = ChatService(NoResultsRetriever(), memory, UnusedLLM())
    response = asyncio.run(service.chat(ChatRequest(message="PM Kisan eligibility?")))
    assert response.session_id.startswith("sess_")
    assert response.grounding.verification_status == "insufficient_evidence"
    assert response.citations == []
