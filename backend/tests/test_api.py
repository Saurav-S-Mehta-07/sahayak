import uuid

from fastapi.testclient import TestClient
from langchain_core.documents import Document

from backend.app.main import app
from backend.app.services import conversation_orchestrator


client = TestClient(app)


def authenticated_client() -> TestClient:
    test_client = TestClient(app)
    response = test_client.post(
        "/api/auth/register",
        json={
            "email": f"{uuid.uuid4().hex}@example.test",
            "password": "test-password-long-enough",
        },
    )
    assert response.status_code == 201
    test_client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    return test_client


def test_health_reports_existing_vector_store() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["document_chunks"] > 0


def test_documents_are_read_from_vector_store() -> None:
    response = client.get("/api/documents")
    assert response.status_code == 200
    documents = response.json()["documents"]
    assert any(item["filename"] == "Women Empowerment Schemes.pdf" for item in documents)
    assert all(item["chunk_count"] > 0 for item in documents)
    assert all(item["source"] == item["filename"] for item in documents)


def test_chat_rejects_empty_query() -> None:
    response = authenticated_client().post("/api/chat", json={"query": "   "})
    assert response.status_code == 422


def test_chat_adapts_document_shapes_and_sanitizes_citations(monkeypatch) -> None:
    conversation_id = f"conversation-{uuid.uuid4().hex}"

    class FakePipeline:
        class FakeMemory:
            def load_history(self, conversation_id):
                return []

        memory = FakeMemory()

        def query(self, query, conversation_id, **kwargs):
            assert query == "What is the benefit?"
            assert conversation_id == conversation_id_expected
            return {
                "answer": "A document-grounded answer.",
                "conversation_id": conversation_id,
                "retrieved_documents": [
                    Document(
                        page_content="Retrieved passage.",
                        metadata={
                            "source": r"C:\private\folder\scheme.pdf",
                            "page": 2,
                        },
                    ),
                    {
                        "page_content": "Another passage.",
                        "metadata": {"source": "other.pdf", "page": 5},
                        "similarity_score": 0.72,
                    },
                ],
            }

    conversation_id_expected = conversation_id
    def fake_answer(query, conversation_id, **kwargs):
        assert query == "What is the benefit?"
        assert conversation_id == conversation_id_expected
        assert kwargs["response_language"] == "English"
        return {
            "answer": "A document-grounded answer.",
            "sources": [
                {
                    "filename": "scheme.pdf",
                    "source": "scheme.pdf",
                    "page": 2,
                    "content": "Retrieved passage.",
                    "score": None,
                    "scheme_name": None,
                    "source_url": None,
                },
                {
                    "filename": "other.pdf",
                    "source": "other.pdf",
                    "page": 5,
                    "content": "Another passage.",
                    "score": 0.72,
                },
            ],
            "conversation_id": conversation_id,
        }

    monkeypatch.setattr(
        conversation_orchestrator.rag_service, "get_rag_pipeline", lambda: FakePipeline()
    )
    monkeypatch.setattr(
        conversation_orchestrator.rag_service, "answer_question", fake_answer
    )
    response = authenticated_client().post(
        "/api/chat",
        json={
            "query": "What is the benefit?",
            "conversation_id": conversation_id,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "A document-grounded answer."
    assert data["language"] == "en"
    assert data["direction"] == "ltr"
    assert data["sources"] == [
        {
            "filename": "scheme.pdf",
            "source": "scheme.pdf",
            "page": 2,
            "content": "Retrieved passage.",
            "score": None,
            "scheme_name": None,
            "source_url": None,
        },
        {
            "filename": "other.pdf",
            "source": "other.pdf",
            "page": 5,
            "content": "Another passage.",
            "score": 0.72,
            "scheme_name": None,
            "source_url": None,
        },
    ]


def test_chat_language_override_and_verified_source_metadata(monkeypatch) -> None:
    conversation_id = f"conversation-{uuid.uuid4().hex}"

    def fake_answer(query, conversation_id, **kwargs):
        assert kwargs["response_language"] == "Urdu"
        return {
            "answer": "جواب",
            "sources": [{
                "filename": "scheme.pdf",
                "source": "scheme.pdf",
                "page": 0,
                "content": "A verified passage.",
                "score": 0.8,
                "scheme_name": "A Scheme",
                "source_url": "https://official.example/scheme.pdf",
            }],
            "conversation_id": conversation_id,
        }

    class FakeMemory:
        def load_history(self, conversation_id):
            return []

    class FakePipeline:
        memory = FakeMemory()

    monkeypatch.setattr(
        conversation_orchestrator.rag_service, "get_rag_pipeline", lambda: FakePipeline()
    )
    monkeypatch.setattr(
        conversation_orchestrator.rag_service, "answer_question", fake_answer
    )
    response = authenticated_client().post(
        "/api/chat",
        json={
            "query": "What is this scheme?",
            "conversation_id": conversation_id,
            "response_language": "ur",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["language"] == "ur"
    assert data["direction"] == "rtl"
    assert data["sources"][0]["scheme_name"] == "A Scheme"
    assert data["sources"][0]["source_url"] == "https://official.example/scheme.pdf"


def test_conversation_rename_clear_and_owner_scope() -> None:
    owner_client = authenticated_client()
    other_client = authenticated_client()
    owner_session = owner_client.get("/api/auth/me").json()
    owner_client.headers["X-CSRF-Token"] = owner_session["csrf_token"]
    owner_id = owner_session["user"]["id"]
    conversation_id = f"conversation-{uuid.uuid4().hex}"
    with conversation_orchestrator.connect() as connection:
        connection.execute(
            "INSERT INTO conversation_owners (conversation_id, user_id, title) VALUES (?, ?, ?)",
            (conversation_id, owner_id, "Before"),
        )
        connection.execute(
            """
            INSERT INTO conversation_messages (conversation_id, role, content)
            VALUES (?, 'user', 'Old message'), (?, 'assistant', 'Old answer')
            """,
            (conversation_id, conversation_id),
        )
        connection.execute(
            """
            INSERT INTO conversation_context
                (conversation_id, preferred_language, active_scheme_id)
            VALUES (?, 'hi', 'pm-kisan')
            """,
            (conversation_id,),
        )

    renamed = owner_client.patch(
        f"/api/conversations/{conversation_id}", json={"title": "PM-KISAN"}
    )
    assert renamed.status_code == 200
    assert renamed.json()["title"] == "PM-KISAN"
    assert other_client.patch(
        f"/api/conversations/{conversation_id}", json={"title": "Not yours"}
    ).status_code == 404

    cleared = owner_client.delete(f"/api/conversations/{conversation_id}/messages")
    assert cleared.status_code == 204
    listing = owner_client.get("/api/conversations").json()["conversations"]
    current = next(item for item in listing if item["id"] == conversation_id)
    assert current["title"] == "PM-KISAN"
    assert current["messages"] == []
    with conversation_orchestrator.connect() as connection:
        context = connection.execute(
            "SELECT 1 FROM conversation_context WHERE conversation_id = ?",
            (conversation_id,),
        ).fetchone()
    assert context is None


def test_chat_rejects_unsupported_response_language() -> None:
    response = authenticated_client().post(
        "/api/chat", json={"query": "Hello", "response_language": "fr"}
    )
    assert response.status_code == 422


def test_chat_greeting_uses_orchestrator_without_rag_retrieval(monkeypatch) -> None:
    class FakeMemory:
        def load_history(self, conversation_id):
            return []

    class FakePipeline:
        memory = FakeMemory()

        def respond_without_retrieval(
            self, query, conversation_id, response_language, intent,
            previous_sources, input_language,
        ):
            assert query == "Hi"
            assert response_language == "English"
            assert intent == "greeting"
            return {
                "answer": "Hello! I can help with questions about scheme documents.",
                "sources": [],
                "conversation_id": conversation_id,
            }

    def unexpected_retrieval(*_args, **_kwargs):
        raise AssertionError("greetings must not invoke document retrieval")

    monkeypatch.setattr(
        conversation_orchestrator.rag_service,
        "get_rag_pipeline",
        lambda: FakePipeline(),
    )
    monkeypatch.setattr(
        conversation_orchestrator.rag_service,
        "answer_question",
        unexpected_retrieval,
    )
    test_client = authenticated_client()
    response = test_client.post("/api/chat", json={"query": "Hi"})
    assert response.status_code == 200
    assert response.json()["answer"].startswith("Hello!")
    assert response.json()["sources"] == []
    with conversation_orchestrator.connect() as connection:
        context = connection.execute(
            "SELECT preferred_language, active_scheme_id, rolling_summary FROM conversation_context WHERE conversation_id = ?",
            (response.json()["conversation_id"],),
        ).fetchone()
    assert context["preferred_language"] == "en"
    assert context["active_scheme_id"] is None
    assert "Latest intent: greeting" in context["rolling_summary"]


def test_eligibility_requires_authentication_and_reports_missing_evidence() -> None:
    unauthenticated = TestClient(app)
    assert unauthenticated.post(
        "/api/eligibility/evaluate",
        json={"scheme_id": "pm-kisan", "answers": {"age": 30}},
    ).status_code == 401

    client = authenticated_client()
    result = client.post(
        "/api/eligibility/evaluate",
        json={"scheme_id": "pm-kisan", "answers": {"age": 30}},
    )
    assert result.status_code == 200
    data = result.json()
    assert data["status"] == "more_information_required"
    assert data["criteria"] == []
    assert "No administrator-reviewed" in data["message"]


def test_recommendations_only_consider_documented_criteria() -> None:
    client = authenticated_client()
    result = client.post(
        "/api/eligibility/recommendations",
        json={"answers": {"age": 30}},
    )
    assert result.status_code == 200
    assert result.json()["recommendations"] == []
