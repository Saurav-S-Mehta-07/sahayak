from __future__ import annotations

import uuid

from backend.app.database import connect
from backend.app.services import rag_service


def test_citations_only_include_verified_document_source_links(monkeypatch) -> None:
    source_path = f"C:\\verified\\{uuid.uuid4().hex}.pdf"
    digest = uuid.uuid4().hex + ("0" * 32)

    class FakePipeline:
        def query(self, query, conversation_id, **kwargs):
            return {
                "answer": "A supported answer.",
                "conversation_id": conversation_id,
                "retrieved_documents": [{
                    "page_content": "Evidence text.",
                    "metadata": {
                        "source": source_path,
                        "page": 0,
                        "scheme_name": "Untrusted metadata name",
                        "source_url": "https://untrusted.example/",
                    },
                    "similarity_score": 0.9,
                }],
            }

    monkeypatch.setattr(rag_service, "get_rag_pipeline", lambda: FakePipeline())
    without_review = rag_service.answer_question("Question", "citation-test")
    assert without_review["sources"][0]["scheme_name"] is None
    assert without_review["sources"][0]["source_url"] is None

    try:
        with connect() as connection:
            connection.execute(
                """
                INSERT INTO scheme_documents
                    (scheme_id, filename, storage_path, source_url, language,
                     retrieval_date, sha256, verification_status, extraction_status,
                     indexing_status)
                VALUES (
                    'pm-kisan', ?, ?, 'https://pmkisan.gov.in/official.pdf',
                    'English', '2026-10-31', ?, 'verified', 'extracted', 'indexed'
                )
                """,
                ("verified.pdf", source_path, digest),
            )

        cited = rag_service.answer_question("Question", "citation-test")
        assert cited["sources"][0]["scheme_name"] == "PM-KISAN"
        assert cited["sources"][0]["source_url"] == "https://pmkisan.gov.in/official.pdf"
    finally:
        with connect() as connection:
            connection.execute(
                "DELETE FROM scheme_documents WHERE sha256 = ?", (digest,)
            )


def test_rag_filters_managed_documents_until_they_are_verified_and_indexed(
    monkeypatch,
) -> None:
    statuses = {
        "pending.pdf": ("verified", "processing"),
        "ready.pdf": ("verified", "indexed"),
        "unverified.pdf": ("pending_verification", "pending"),
    }

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, _query, paths):
            class Result:
                def fetchall(self):
                    return [
                        {
                            "storage_path": path,
                            "verification_status": verification,
                            "indexing_status": indexing,
                        }
                        for path, (verification, indexing) in statuses.items()
                        if path in paths
                    ]

            return Result()

    monkeypatch.setattr(rag_service, "connect", FakeConnection)
    candidates = [
        {"document": "pending", "metadata": {"source": "pending.pdf"}},
        {"document": "ready", "metadata": {"source": "ready.pdf"}},
        {"document": "unverified", "metadata": {"source": "unverified.pdf"}},
        {"document": "legacy", "metadata": {"source": "legacy.pdf"}},
    ]

    active = rag_service._filter_inactive_managed_documents(candidates)
    assert [item["document"] for item in active] == ["ready", "legacy"]
