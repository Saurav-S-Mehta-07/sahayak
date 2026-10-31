"""Administrator-only scheme document management."""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from langchain_community.document_loaders import PyPDFLoader
from pydantic import BaseModel, ConfigDict, Field

from ..auth import require_admin, require_admin_csrf
from ..database import connect
from ..services.eligibility_service import (
    normalize_field_key,
    validate_criterion_excerpt,
)
from ..services.discovery_service import discover_configured_feeds
if __package__ and __package__.startswith("backend."):
    from backend.src.config import settings
else:
    from src.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin")
MAX_PDF_BYTES = 40 * 1024 * 1024


class SchemeMetadataUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=2, max_length=160)
    ministry: str | None = Field(default=None, min_length=2, max_length=160)
    official_source_url: str | None = Field(default=None, max_length=1000)
    language: str | None = Field(default=None, min_length=2, max_length=40)
    version_date: str | None = Field(default=None, max_length=40)


class EligibilityCriterionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field_key: str = Field(min_length=1, max_length=64)
    operator: str = Field(pattern=r"^(eq|ne|gte|lte|in|contains)$")
    expected_value: str | int | float | bool | list[str | int | float | bool]
    description: str = Field(min_length=3, max_length=300)
    source_document_id: int = Field(gt=0)
    source_page: int = Field(ge=1)
    source_excerpt: str = Field(min_length=12, max_length=2000)


class DiscoveryReviewUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = Field(
        pattern=r"^(under_review|needs_more_information|rejected)$"
    )
    review_notes: str = Field(default="", max_length=2000)


def _official_host(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise HTTPException(422, "Source URL must use HTTPS.")
    return parsed.hostname.lower().rstrip(".")


def _document_response(row) -> dict:
    data = dict(row)
    data.pop("storage_path", None)
    return data


@router.get("/schemes")
def admin_schemes(_: dict = Depends(require_admin)) -> dict[str, list[dict]]:
    with connect() as connection:
        rows = connection.execute("SELECT * FROM schemes ORDER BY name").fetchall()
    return {"schemes": [dict(row) for row in rows]}


@router.post("/schemes/discover")
def discover_schemes(_: dict = Depends(require_admin_csrf)) -> dict:
    """Fetch configured official feeds; results are not authoritative scheme records."""
    try:
        return discover_configured_feeds()
    except ValueError as exc:
        raise HTTPException(503, str(exc)) from exc


@router.get("/schemes/discovered")
def discovered_schemes(
    _: dict = Depends(require_admin),
) -> dict[str, list[dict]]:
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT id, title, source_url, feed_url, source_organization,
                   published_at, excerpt, discovered_at, status, review_notes
            FROM scheme_discoveries
            ORDER BY
                CASE status
                    WHEN 'pending_verification' THEN 0
                    WHEN 'under_review' THEN 1
                    WHEN 'needs_more_information' THEN 2
                    ELSE 3
                END,
                discovered_at DESC
            """
        ).fetchall()
    return {"discoveries": [dict(row) for row in rows]}


@router.patch("/schemes/discovered/{discovery_id}")
def review_discovery(
    discovery_id: int,
    payload: DiscoveryReviewUpdate,
    admin_user: dict = Depends(require_admin_csrf),
) -> dict:
    allowed_transitions = {
        "pending_verification": {
            "under_review",
            "needs_more_information",
            "rejected",
        },
        "under_review": {"needs_more_information", "rejected"},
        "needs_more_information": {"under_review", "rejected"},
        "rejected": set(),
    }
    with connect() as connection:
        row = connection.execute(
            "SELECT * FROM scheme_discoveries WHERE id = ?", (discovery_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(404, "Discovery record not found.")
        if payload.status not in allowed_transitions[row["status"]]:
            raise HTTPException(
                409,
                f"Discovery cannot move from {row['status']} to {payload.status}.",
            )
        connection.execute(
            """
            UPDATE scheme_discoveries
            SET status = ?, review_notes = ?, reviewer_id = ?, reviewed_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                payload.status,
                payload.review_notes.strip(),
                admin_user["id"],
                discovery_id,
            ),
        )
        connection.execute(
            """
            INSERT INTO scheme_discovery_events
                (discovery_id, admin_id, action, previous_status, new_status, notes)
            VALUES (?, ?, 'reviewed', ?, ?, ?)
            """,
            (
                discovery_id,
                admin_user["id"],
                row["status"],
                payload.status,
                payload.review_notes.strip(),
            ),
        )
        updated = connection.execute(
            """
            SELECT id, title, source_url, feed_url, source_organization,
                   published_at, excerpt, discovered_at, status, review_notes,
                   reviewed_at
            FROM scheme_discoveries WHERE id = ?
            """,
            (discovery_id,),
        ).fetchone()
    return dict(updated)


@router.get("/schemes/{scheme_id}/eligibility-criteria")
def admin_eligibility_criteria(
    scheme_id: str, _: dict = Depends(require_admin)
) -> dict[str, list[dict]]:
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT criteria.*, documents.filename, documents.source_url
            FROM scheme_eligibility_criteria AS criteria
            JOIN scheme_documents AS documents
              ON documents.id = criteria.source_document_id
            WHERE criteria.scheme_id = ?
            ORDER BY criteria.id
            """,
            (scheme_id,),
        ).fetchall()
    return {
        "criteria": [
            {**dict(row), "expected_value": json.loads(row["expected_value_json"])}
            for row in rows
        ]
    }


@router.post("/schemes/{scheme_id}/eligibility-criteria", status_code=201)
def create_eligibility_criterion(
    scheme_id: str,
    payload: EligibilityCriterionCreate,
    _: dict = Depends(require_admin_csrf),
) -> dict:
    try:
        field_key = normalize_field_key(payload.field_key)
        excerpt = validate_criterion_excerpt(payload.source_excerpt)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    expected_value = payload.expected_value
    if payload.operator in {"gte", "lte"} and (
        isinstance(expected_value, bool)
        or not isinstance(expected_value, (int, float))
    ):
        raise HTTPException(422, "Numeric comparisons require a numeric expected value.")
    if payload.operator == "in" and not isinstance(expected_value, list):
        raise HTTPException(422, "The 'in' operator requires a list of expected values.")
    if payload.operator == "in" and not expected_value:
        raise HTTPException(422, "The 'in' operator requires at least one expected value.")
    if payload.operator != "in" and isinstance(expected_value, list):
        raise HTTPException(422, "Only the 'in' operator accepts a list.")
    with connect() as connection:
        document = connection.execute(
            """
            SELECT id, scheme_id, page_count, verification_status, indexing_status,
                   storage_path
            FROM scheme_documents WHERE id = ?
            """,
            (payload.source_document_id,),
        ).fetchone()
        if document is None:
            raise HTTPException(404, "Source document not found.")
        if document["scheme_id"] != scheme_id:
            raise HTTPException(422, "The source document belongs to a different scheme.")
        if (
            document["verification_status"] != "verified"
            or document["indexing_status"] != "indexed"
        ):
            raise HTTPException(
                409, "Eligibility criteria require a verified, indexed source document."
            )
        if document["page_count"] and payload.source_page > document["page_count"]:
            raise HTTPException(422, "Source page exceeds the document page count.")
        pages = PyPDFLoader(document["storage_path"]).load()
        if payload.source_page > len(pages):
            raise HTTPException(422, "Source page is outside the uploaded PDF.")
        page_text = " ".join(pages[payload.source_page - 1].page_content.split()).casefold()
        normalized_excerpt = " ".join(excerpt.split()).casefold()
        if normalized_excerpt not in page_text:
            raise HTTPException(
                422,
                "The cited excerpt must appear on the selected page of the verified PDF.",
            )
        try:
            cursor = connection.execute(
                """
                INSERT INTO scheme_eligibility_criteria
                    (scheme_id, field_key, operator, expected_value_json,
                     description, source_document_id, source_page, source_excerpt)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    scheme_id,
                    field_key,
                    payload.operator,
                    json.dumps(expected_value, ensure_ascii=False, sort_keys=True),
                    payload.description.strip(),
                    payload.source_document_id,
                    payload.source_page,
                    excerpt,
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise HTTPException(409, "This evidence-linked criterion already exists.") from exc
        row = connection.execute(
            """
            SELECT criteria.*, documents.filename, documents.source_url
            FROM scheme_eligibility_criteria AS criteria
            JOIN scheme_documents AS documents
              ON documents.id = criteria.source_document_id
            WHERE criteria.id = ?
            """,
            (cursor.lastrowid,),
        ).fetchone()
    return {
        **dict(row),
        "expected_value": json.loads(row["expected_value_json"]),
    }


@router.patch("/schemes/{scheme_id}")
def update_scheme(
    scheme_id: str,
    payload: SchemeMetadataUpdate,
    _: dict = Depends(require_admin_csrf),
) -> dict:
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(422, "Provide at least one scheme field to update.")
    if any(
        key != "version_date" and value is None
        for key, value in updates.items()
    ):
        raise HTTPException(422, "Scheme fields cannot be cleared.")
    if "official_source_url" in updates and updates["official_source_url"]:
        _official_host(updates["official_source_url"])
        updates["source_status"] = "source_listed"
    if "version_date" in updates:
        if not updates["version_date"]:
            updates["version_date"] = None
        else:
            try:
                date.fromisoformat(updates["version_date"])
            except ValueError as exc:
                raise HTTPException(422, "Version date must use YYYY-MM-DD.") from exc
    assignments = ", ".join(f"{key} = ?" for key in updates)
    with connect() as connection:
        cursor = connection.execute(
            f"UPDATE schemes SET {assignments} WHERE id = ?",
            (*updates.values(), scheme_id),
        )
        if cursor.rowcount == 0:
            raise HTTPException(404, "Scheme not found.")
        row = connection.execute(
            "SELECT * FROM schemes WHERE id = ?", (scheme_id,)
        ).fetchone()
    return dict(row)


@router.post("/schemes/{scheme_id}/verify-source")
def verify_scheme_source(
    scheme_id: str, _: dict = Depends(require_admin_csrf)
) -> dict:
    with connect() as connection:
        row = connection.execute(
            "SELECT * FROM schemes WHERE id = ?", (scheme_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(404, "Scheme not found.")
        _official_host(row["official_source_url"])
        connection.execute(
            "UPDATE schemes SET source_status = 'verified' WHERE id = ?",
            (scheme_id,),
        )
        updated = connection.execute(
            "SELECT * FROM schemes WHERE id = ?", (scheme_id,)
        ).fetchone()
    return dict(updated)


@router.get("/documents")
def admin_documents(_: dict = Depends(require_admin)) -> dict[str, list[dict]]:
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT d.*, s.name AS scheme_name FROM scheme_documents AS d
            JOIN schemes AS s ON s.id = d.scheme_id ORDER BY d.created_at DESC
            """
        ).fetchall()
    return {"documents": [_document_response(row) for row in rows]}


@router.post("/documents", status_code=201)
async def upload_document(
    scheme_id: str = Form(...),
    source_url: str = Form(...),
    language: str = Form(..., min_length=2, max_length=40),
    version_date: str | None = Form(default=None, max_length=40),
    upload: UploadFile = File(...),
    _: dict = Depends(require_admin_csrf),
) -> dict:
    if Path(upload.filename or "").suffix.lower() != ".pdf":
        raise HTTPException(415, "Only PDF documents can be uploaded.")
    if version_date:
        try:
            date.fromisoformat(version_date)
        except ValueError as exc:
            raise HTTPException(422, "Version date must use YYYY-MM-DD.") from exc
    content = await upload.read(MAX_PDF_BYTES + 1)
    if len(content) > MAX_PDF_BYTES:
        raise HTTPException(413, "PDF exceeds the 40 MB upload limit.")
    if not content.startswith(b"%PDF-"):
        raise HTTPException(415, "The uploaded file is not a valid PDF.")
    source_host = _official_host(source_url)
    digest = hashlib.sha256(content).hexdigest()

    with connect() as connection:
        scheme = connection.execute(
            "SELECT * FROM schemes WHERE id = ?", (scheme_id,)
        ).fetchone()
        if scheme is None:
            raise HTTPException(404, "Scheme not found.")
        if scheme["source_status"] != "verified":
            raise HTTPException(
                409, "Review and verify the scheme source before uploading a document."
            )
        registered_host = _official_host(scheme["official_source_url"])
        if source_host != registered_host:
            raise HTTPException(
                422,
                "Source host must match the scheme's registered official source. "
                "Unverified submissions require an administrator to correct the catalog first.",
            )
        existing = connection.execute(
            "SELECT * FROM scheme_documents WHERE sha256 = ?", (digest,)
        ).fetchone()
        if existing:
            return _document_response(existing)

        target_dir = settings.pdf_dir / "managed"
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"{digest}.pdf"
        target.write_bytes(content)
        try:
            pages = PyPDFLoader(str(target)).load()
            page_count = len(pages)
            extraction_status = "extracted" if any(
                page.page_content.strip() for page in pages
            ) else "empty"
        except Exception as exc:
            target.unlink(missing_ok=True)
            logger.exception("Could not extract uploaded PDF")
            raise HTTPException(422, "The PDF could not be read.") from exc

        cursor = connection.execute(
            """
            INSERT INTO scheme_documents
                (scheme_id, filename, storage_path, source_url, language,
                 version_date, retrieval_date, sha256, page_count, extraction_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                scheme_id,
                Path(upload.filename).name,
                str(target),
                source_url,
                language,
                version_date,
                date.today().isoformat(),
                digest,
                page_count,
                extraction_status,
            ),
        )
        document_id = cursor.lastrowid
        connection.execute(
            """
            INSERT INTO document_events (document_id, event, detail)
            VALUES (?, 'uploaded', ?)
            """,
            (document_id, "Stored with pending official-source verification."),
        )
        row = connection.execute(
            "SELECT * FROM scheme_documents WHERE id = ?", (document_id,)
        ).fetchone()
    return _document_response(row)


@router.post("/documents/{document_id}/verify")
def verify_document(
    document_id: int, _: dict = Depends(require_admin_csrf)
) -> dict:
    with connect() as connection:
        row = connection.execute(
            """
            SELECT d.*, s.official_source_url, s.source_status
            FROM scheme_documents d
            JOIN schemes s ON s.id = d.scheme_id WHERE d.id = ?
            """,
            (document_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(404, "Document not found.")
        if row["source_status"] != "verified":
            raise HTTPException(409, "Verify the scheme source before approving this document.")
        if _official_host(row["source_url"]) != _official_host(row["official_source_url"]):
            raise HTTPException(422, "The document source does not match the official scheme source.")
        if row["extraction_status"] != "extracted":
            raise HTTPException(409, "The PDF has no extractable text and cannot be approved.")
        connection.execute(
            "UPDATE scheme_documents SET verification_status = 'verified' WHERE id = ?",
            (document_id,),
        )
        connection.execute(
            """
            INSERT INTO document_events (document_id, event, detail)
            VALUES (?, 'verified', 'Administrator confirmed the official source.')
            """,
            (document_id,),
        )
        updated = connection.execute(
            "SELECT * FROM scheme_documents WHERE id = ?", (document_id,)
        ).fetchone()
    return _document_response(updated)


@router.post("/documents/{document_id}/ingest")
def ingest_document(document_id: int, _: dict = Depends(require_admin_csrf)) -> dict:
    with connect() as connection:
        row = connection.execute(
            "SELECT * FROM scheme_documents WHERE id = ?", (document_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(404, "Document not found.")
        if row["verification_status"] != "verified":
            raise HTTPException(409, "Verify the official source before indexing.")
        if row["indexing_status"] == "indexed":
            return _document_response(row)
        connection.execute(
            "UPDATE scheme_documents SET indexing_status = 'processing' WHERE id = ?",
            (document_id,),
        )

    try:
        pages = PyPDFLoader(row["storage_path"]).load()
        if not pages or not any(page.page_content.strip() for page in pages):
            raise ValueError("The PDF contains no extractable text.")
        with connect() as connection:
            scheme = connection.execute(
                "SELECT name, ministry FROM schemes WHERE id = ?", (row["scheme_id"],)
            ).fetchone()
        for page in pages:
            page.metadata.update(
                {
                    "source": row["storage_path"],
                    "filename": row["filename"],
                    "scheme_id": row["scheme_id"],
                    "scheme_name": scheme["name"],
                    "ministry": scheme["ministry"],
                    "source_url": row["source_url"],
                    "sha256": row["sha256"],
                    "language": row["language"],
                    "version_date": row["version_date"] or "",
                }
            )
        from ..services.rag_service import get_rag_pipeline

        chunk_count = get_rag_pipeline().ingest(pages)
        if chunk_count <= 0:
            raise ValueError("The existing RAG pipeline produced no chunks.")
        with connect() as connection:
            connection.execute(
                """
                UPDATE scheme_documents SET indexing_status = 'indexed',
                    extraction_status = 'extracted', page_count = ?, chunk_count = ?
                WHERE id = ?
                """,
                (len(pages), chunk_count, document_id),
            )
            connection.execute(
                """
                INSERT INTO document_events (document_id, event, detail)
                VALUES (?, 'indexed', ?)
                """,
                (document_id, f"Indexed {chunk_count} chunks across {len(pages)} pages."),
            )
            updated = connection.execute(
                "SELECT * FROM scheme_documents WHERE id = ?", (document_id,)
            ).fetchone()
        return _document_response(updated)
    except Exception as exc:
        rollback_error = None
        try:
            from ..services.rag_service import get_rag_pipeline

            get_rag_pipeline().vector_store.remove_documents_for_source(
                row["storage_path"]
            )
        except Exception as cleanup_exc:
            rollback_error = cleanup_exc
            logger.exception(
                "Could not roll back partial vectors for document %s",
                document_id,
            )
        with connect() as connection:
            connection.execute(
                "UPDATE scheme_documents SET indexing_status = 'failed' WHERE id = ?",
                (document_id,),
            )
            connection.execute(
                "INSERT INTO document_events (document_id, event, detail) VALUES (?, 'failed', ?)",
                (
                    document_id,
                    (
                        f"{exc}; vector cleanup also failed: {rollback_error}"
                        if rollback_error
                        else str(exc)
                    )[:1000],
                ),
            )
        logger.exception("Document ingestion failed for document %s", document_id)
        raise HTTPException(502, "Document ingestion failed. Review the admin event log.") from exc


@router.get("/documents/{document_id}/events")
def document_events(
    document_id: int, _: dict = Depends(require_admin)
) -> dict[str, list[dict]]:
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT event, detail, created_at FROM document_events
            WHERE document_id = ? ORDER BY id DESC
            """,
            (document_id,),
        ).fetchall()
        exists = connection.execute(
            "SELECT 1 FROM scheme_documents WHERE id = ?", (document_id,)
        ).fetchone()
    if exists is None:
        raise HTTPException(404, "Document not found.")
    return {"events": [dict(row) for row in rows]}
