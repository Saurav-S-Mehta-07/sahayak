import asyncio

import pytest

from app.core.exceptions import LLMServiceError
from app.services.llm_service import LLMService


class TemporaryFailure(Exception):
    status_code = 503


class BrokenClient:
    async def ainvoke(self, _messages):
        raise TemporaryFailure("temporary failure")


def test_transient_groq_failure_is_retried_then_reported(monkeypatch):
    async def no_wait(_seconds):
        return None

    monkeypatch.setattr("app.services.llm_service.asyncio.sleep", no_wait)
    service = LLMService()
    service._client = BrokenClient()
    with pytest.raises(LLMServiceError, match="temporarily unavailable"):
        asyncio.run(service.answer("question", "evidence", "english"))
