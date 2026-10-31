from __future__ import annotations

from dataclasses import replace

from backend.app import database
from backend.app.services.eligibility_service import (
    evaluate_scheme,
    recommend_schemes,
)


def test_eligibility_states_require_verified_indexed_evidence(
    tmp_path, monkeypatch
) -> None:
    original_initialized = database._initialized
    monkeypatch.setattr(database, "_initialized", False)
    monkeypatch.setattr(
        database,
        "settings",
        replace(database.settings, sqlite_path=tmp_path / "eligibility.sqlite3"),
    )
    try:
        with database.connect() as connection:
            connection.execute(
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
                    "unused.pdf",
                    "https://pmkisan.gov.in/",
                    "English",
                    "2026-10-31",
                    "a" * 64,
                    5,
                    "verified",
                    "extracted",
                    "indexed",
                ),
            )
            document_id = connection.execute(
                "SELECT id FROM scheme_documents WHERE sha256 = ?", ("a" * 64,)
            ).fetchone()["id"]
            connection.execute(
                """
                INSERT INTO scheme_eligibility_criteria
                    (scheme_id, field_key, operator, expected_value_json,
                     description, source_document_id, source_page, source_excerpt)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "pm-kisan",
                    "age",
                    "gte",
                    "18",
                    "Applicant age is at least 18",
                    document_id,
                    2,
                    "The applicant must be at least 18 years old.",
                ),
            )

        assert evaluate_scheme("pm-kisan", {"age": 20})["status"] == "potentially_eligible"
        assert (
            evaluate_scheme("pm-kisan", {"age": 16})["status"]
            == "not_eligible_based_on_provided_information"
        )
        assert evaluate_scheme("pm-kisan", {})["status"] == "more_information_required"
        assert recommend_schemes({"age": 20})["recommendations"][0]["scheme_id"] == "pm-kisan"
    finally:
        database._initialized = original_initialized
