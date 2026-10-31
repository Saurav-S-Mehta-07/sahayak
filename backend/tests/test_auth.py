from dataclasses import replace
from io import BytesIO
import uuid

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter

from backend.app import database
from backend.app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    original_initialized = database._initialized
    monkeypatch.setattr(database, "_initialized", False)
    monkeypatch.setattr(
        database,
        "settings",
        replace(database.settings, sqlite_path=tmp_path / "auth-test.sqlite3"),
    )
    test_client = TestClient(app)
    yield test_client
    test_client.close()
    database._initialized = original_initialized


def register(client: TestClient, email: str | None = None) -> str:
    response = client.post(
        "/api/auth/register",
        json={
            "email": email or f"{uuid.uuid4().hex}@example.test",
            "password": "a-strong-password-123",
        },
    )
    assert response.status_code == 201
    csrf_token = response.json()["csrf_token"]
    client.headers["X-CSRF-Token"] = csrf_token
    return csrf_token


def test_registration_login_logout_and_session_csrf(client) -> None:
    email = f"{uuid.uuid4().hex}@example.test"
    csrf_token = register(client, email)
    current = client.get("/api/auth/me")
    assert current.json()["user"]["role"] == "citizen"
    client.headers["X-CSRF-Token"] = current.json()["csrf_token"]
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/auth/me").json()["user"] is None
    login = client.post(
        "/api/auth/login",
        json={"email": email, "password": "a-strong-password-123"},
    )
    assert login.status_code == 200
    assert login.json()["csrf_token"] != csrf_token
    client.headers["X-CSRF-Token"] = login.json()["csrf_token"]
    assert client.get("/api/auth/me").status_code == 200


def test_chat_is_authenticated_csrf_protected_and_conversation_owned(
    client, monkeypatch
) -> None:
    from backend.app.services import rag_service

    def answer(_query, conversation_id, **_kwargs):
        return {
            "answer": "Grounded test reply",
            "sources": [],
            "conversation_id": conversation_id,
        }

    monkeypatch.setattr(rag_service, "answer_question", answer)
    csrf = register(client)
    unauthenticated = TestClient(app)
    assert unauthenticated.post("/api/chat", json={"query": "Hello"}).status_code == 401
    missing_csrf = client.post(
        "/api/chat",
        json={"query": "Hello"},
        headers={"X-CSRF-Token": ""},
    )
    assert missing_csrf.status_code == 403

    conversation_id = f"test-{uuid.uuid4().hex}"
    response = client.post(
        "/api/chat",
        json={"query": "Tell me about this scheme", "conversation_id": conversation_id},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 200
    assert response.json()["conversation_id"] == conversation_id
    assert any(
        item["id"] == conversation_id
        for item in client.get("/api/conversations").json()["conversations"]
    )

    other_user = TestClient(app)
    register(other_user)
    forbidden = other_user.post(
        "/api/chat",
        json={"query": "Continue", "conversation_id": conversation_id},
    )
    assert forbidden.status_code == 404
    assert client.delete(f"/api/conversations/{conversation_id}").status_code == 204
    assert client.get("/api/conversations").json()["conversations"] == []


def test_citizen_cannot_access_administration(client) -> None:
    register(client)
    assert client.get("/api/admin/documents").status_code == 403
    assert client.get("/api/admin/schemes/discovered").status_code == 403
    assert client.post("/api/admin/documents/1/verify").status_code == 403
    assert client.post("/api/admin/schemes/pm-kisan/verify-source").status_code == 403


def test_discovery_creates_a_review_only_signal_and_records_admin_actions(
    client, monkeypatch
) -> None:
    from backend.app.services import discovery_service

    register(client)
    with database.connect() as connection:
        connection.execute("UPDATE users SET role = 'admin'")

    monkeypatch.setattr(
        discovery_service,
        "settings",
        replace(
            discovery_service.settings,
            scheme_discovery_feed_urls=("https://pib.gov.in/scheme-updates.xml",),
        ),
    )
    monkeypatch.setattr(
        discovery_service,
        "_fetch_feed",
        lambda _url: b"""<?xml version="1.0"?>
            <rss><channel>
              <item>
                <title>New government programme announced</title>
                <link>https://pib.gov.in/example-release</link>
                <pubDate>Sat, 31 Oct 2026 10:00:00 +0000</pubDate>
                <description><![CDATA[Official <b>announcement</b>.]]></description>
              </item>
              <item>
                <title>Third-party claim</title>
                <link>https://example.com/unverified</link>
              </item>
            </channel></rss>""",
    )

    first_scan = client.post("/api/admin/schemes/discover")
    assert first_scan.status_code == 200
    assert first_scan.json()["new_discoveries"] == 1
    assert first_scan.json()["errors"] == []

    second_scan = client.post("/api/admin/schemes/discover")
    assert second_scan.status_code == 200
    assert second_scan.json()["new_discoveries"] == 0

    discoveries = client.get("/api/admin/schemes/discovered").json()["discoveries"]
    assert len(discoveries) == 1
    discovery = discoveries[0]
    assert discovery["status"] == "pending_verification"
    assert discovery["source_url"] == "https://pib.gov.in/example-release"
    assert discovery["excerpt"] == "Official announcement."
    assert "scheme_id" not in discovery
    with database.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM scheme_documents").fetchone()[0] == 0

    reviewed = client.patch(
        f"/api/admin/schemes/discovered/{discovery['id']}",
        json={"status": "under_review", "review_notes": "Check ministry guideline."},
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["status"] == "under_review"
    assert client.patch(
        f"/api/admin/schemes/discovered/{discovery['id']}",
        json={"status": "verified"},
    ).status_code == 422

    with database.connect() as connection:
        event = connection.execute(
            "SELECT action, previous_status, new_status, notes FROM scheme_discovery_events"
        ).fetchone()
    assert tuple(event) == (
        "reviewed",
        "pending_verification",
        "under_review",
        "Check ministry guideline.",
    )


def test_upload_requires_a_pdf_and_persists_metadata(client) -> None:
    register(client)
    response = client.post(
        "/api/admin/documents",
        data={
            "scheme_id": "pm-kisan",
            "source_url": "https://pmkisan.gov.in/",
            "language": "English",
        },
        files={"upload": ("not-a-pdf.pdf", b"not a pdf", "application/pdf")},
    )
    assert response.status_code == 403

    with database.connect() as connection:
        connection.execute("UPDATE users SET role = 'admin'")
    approved_source = client.post("/api/admin/schemes/pm-kisan/verify-source")
    assert approved_source.status_code == 200
    assert approved_source.json()["source_status"] == "verified"
    bad_file = client.post(
        "/api/admin/documents",
        data={
            "scheme_id": "pm-kisan",
            "source_url": "https://pmkisan.gov.in/",
            "language": "English",
        },
        files={"upload": ("not-a-pdf.pdf", b"not a pdf", "application/pdf")},
    )
    assert bad_file.status_code == 415

    output = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.write(output)
    uploaded = client.post(
        "/api/admin/documents",
        data={
            "scheme_id": "pm-kisan",
            "source_url": "https://pmkisan.gov.in/",
            "language": "English",
            "version_date": "2025-01-02",
        },
        files={"upload": ("guidelines.pdf", output.getvalue(), "application/pdf")},
    )
    assert uploaded.status_code == 201
    record = uploaded.json()
    assert record["verification_status"] == "pending_verification"
    assert record["extraction_status"] == "empty"
    assert record["page_count"] == 1
    assert len(record["sha256"]) == 64
    assert "storage_path" not in record
    assert client.post(f"/api/admin/documents/{record['id']}/verify").status_code == 409
    assert client.post(f"/api/admin/documents/{record['id']}/ingest").status_code == 409


def test_admin_eligibility_criteria_must_match_verified_pdf_page(
    client, monkeypatch
) -> None:
    from backend.app.routes import admin

    csrf = register(client)
    with database.connect() as connection:
        connection.execute("UPDATE users SET role = 'admin'")
        cursor = connection.execute(
            """
            INSERT INTO scheme_documents
                (scheme_id, filename, storage_path, source_url, language,
                 retrieval_date, sha256, page_count, verification_status,
                 extraction_status, indexing_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "pm-kisan",
                "pm-kisan.pdf",
                "verified.pdf",
                "https://pmkisan.gov.in/",
                "English",
                "2026-10-31",
                "c" * 64,
                1,
                "verified",
                "extracted",
                "indexed",
            ),
        )
        document_id = cursor.lastrowid

    class FakeLoader:
        def __init__(self, _path):
            pass

        def load(self):
            return [
                type(
                    "Page",
                    (),
                    {"page_content": "The applicant must be at least 18 years old."},
                )()
            ]

    monkeypatch.setattr(admin, "PyPDFLoader", FakeLoader)
    payload = {
        "field_key": "age",
        "operator": "gte",
        "expected_value": 18,
        "description": "Applicant must be at least 18",
        "source_document_id": document_id,
        "source_page": 1,
        "source_excerpt": "The applicant must be at least 18 years old.",
    }
    saved = client.post(
        "/api/admin/schemes/pm-kisan/eligibility-criteria",
        json=payload,
        headers={"X-CSRF-Token": csrf},
    )
    assert saved.status_code == 201
    result = client.post(
        "/api/eligibility/evaluate",
        json={"scheme_id": "pm-kisan", "answers": {"age": 20}},
        headers={"X-CSRF-Token": csrf},
    )
    assert result.status_code == 200
    assert result.json()["status"] == "potentially_eligible"
    assert result.json()["criteria"][0]["source"]["filename"] == "pm-kisan.pdf"

    payload["field_key"] = "student"
    payload["source_excerpt"] = "This criterion is not in the source page."
    rejected = client.post(
        "/api/admin/schemes/pm-kisan/eligibility-criteria",
        json=payload,
        headers={"X-CSRF-Token": csrf},
    )
    assert rejected.status_code == 422
