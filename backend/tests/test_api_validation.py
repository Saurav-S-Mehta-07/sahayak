import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient

from app.models.schemas import ChatRequest, EligibilityProfile
from app.main import app


def test_blank_chat_message_is_rejected():
    with pytest.raises(ValidationError):
        ChatRequest(message="   ")


def test_invalid_profile_age_is_rejected():
    with pytest.raises(ValidationError):
        EligibilityProfile(age=150)


def test_health_and_invalid_http_request():
    with TestClient(app) as client:
        assert client.get("/health").json()["status"] == "ok"
        response = client.post("/api/v1/chat", json={"message": " "})
        assert response.status_code == 422
        assert "detail" in response.json()
        assert client.get("/api/v1/health").status_code == 200
        ingest = client.post("/api/v1/documents/ingest")
        assert ingest.status_code == 503
