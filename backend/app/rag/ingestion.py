from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from app.core.config import settings
from app.core.exceptions import DocumentIngestionError
from app.core.mongo_storage import MongoDocumentRepository
from app.rag.chunker import split_pages
from app.rag.embeddings import EmbeddingManager
from app.rag.loader import discover_pdfs
from app.rag.pdf_processor import PDFProcessor
from app.rag.vector_store import VectorStore

logger = logging.getLogger(__name__)


class IngestionService:
    def __init__(
        self,
        embeddings: EmbeddingManager,
        vector_store: VectorStore,
        pdf_dir: Path = settings.pdf_dir,
        database_path: Path | None = None,
    ):
        self.embeddings = embeddings
        self.vector_store = vector_store
        self.pdf_dir = pdf_dir.resolve()
        self.processor = PDFProcessor(self.pdf_dir)
        self.mongo_metadata: MongoDocumentRepository | None = None
        if database_path is None and settings.mongodb_uri:
            self.mongo_metadata = MongoDocumentRepository()
            self.database_path = None
        else:
            self.database_path = database_path or settings.database_path
            self.database_path.parent.mkdir(parents=True, exist_ok=True)
            with self._connect() as connection:
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS indexed_documents (
                        document_id TEXT PRIMARY KEY,
                        source_path TEXT NOT NULL UNIQUE,
                        document_name TEXT NOT NULL,
                        document_title TEXT NOT NULL DEFAULT '',
                        scheme_name TEXT NOT NULL,
                        checksum TEXT NOT NULL,
                        page_count INTEGER NOT NULL,
                        chunk_count INTEGER NOT NULL,
                        indexed_at TEXT NOT NULL
                    )
                    """
                )
                columns = {
                    row["name"]
                    for row in connection.execute("PRAGMA table_info(indexed_documents)")
                }
                if "document_title" not in columns:
                    connection.execute(
                        "ALTER TABLE indexed_documents ADD COLUMN document_title TEXT NOT NULL DEFAULT ''"
                    )

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        if self.database_path is None:
            raise RuntimeError("SQLite is not active for this ingestion service")
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    @staticmethod
    def _digest(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as file:
            for block in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    def _document_id(self, path: Path) -> str:
        relative = path.relative_to(self.pdf_dir).as_posix()
        return hashlib.sha256(relative.encode("utf-8")).hexdigest()[:24]

    def _index_one(self, path: Path, checksum: str) -> tuple[int, int, bool, int]:
        document_id = self._document_id(path)
        pages = self.processor.extract(path)
        full_page_count = int(pages[0].metadata.get("total_pages", len(pages)))
        chunks = split_pages(pages, document_id, path.name)

        old_ids = set(self.vector_store.ids_for_document(document_id))
        existing_ids = old_ids
        new_chunks = [
            chunk for chunk in chunks if str(chunk.metadata["chunk_id"]) not in existing_ids
        ]
        vectors = self.embeddings.embed([chunk.page_content for chunk in new_chunks])
        self.vector_store.upsert(new_chunks, vectors)

        current_ids = {str(chunk.metadata["chunk_id"]) for chunk in chunks}
        self.vector_store.delete_ids(sorted(old_ids - current_ids))

        relative = path.relative_to(self.pdf_dir).as_posix()
        scheme_name = str(chunks[0].metadata["scheme_name"]) if chunks else path.stem
        document_title = str(chunks[0].metadata.get("document_title", path.stem)) if chunks else path.stem
        record = {
            "document_id": document_id,
            "source_path": relative,
            "document_name": path.name,
            "document_title": document_title,
            "scheme_name": scheme_name,
            "checksum": checksum,
            "page_count": full_page_count,
            "chunk_count": len(chunks),
            "indexed_at": datetime.now(timezone.utc).isoformat(),
        }
        if self.mongo_metadata:
            self.mongo_metadata.upsert(record)
        else:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO indexed_documents
                        (document_id, source_path, document_name, document_title, scheme_name, checksum,
                         page_count, chunk_count, indexed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(document_id) DO UPDATE SET
                        source_path=excluded.source_path,
                        document_name=excluded.document_name,
                        document_title=excluded.document_title,
                        scheme_name=excluded.scheme_name,
                        checksum=excluded.checksum,
                        page_count=excluded.page_count,
                        chunk_count=excluded.chunk_count,
                        indexed_at=excluded.indexed_at
                    """,
                    (
                        document_id,
                        relative,
                        path.name,
                        document_title,
                        scheme_name,
                        checksum,
                        full_page_count,
                        len(chunks),
                        record["indexed_at"],
                    ),
                )
        logger.info(
            "Indexed %s: pages=%s chunks=%s new_embeddings=%s",
            path.name,
            full_page_count,
            len(chunks),
            len(new_chunks),
        )
        return full_page_count, len(chunks), bool(old_ids), len(new_chunks)

    def ingest(self) -> dict[str, Any]:
        paths = discover_pdfs(self.pdf_dir)
        processed = 0
        pages_total = 0
        chunks_total = 0
        generated = 0
        updated = 0
        skipped = 0
        duplicates = 0
        failures: list[dict[str, str]] = []
        seen_hashes: dict[str, str] = {}
        live_paths = {path.relative_to(self.pdf_dir).as_posix() for path in paths}
        if self.mongo_metadata:
            stored = self.mongo_metadata.all()
        else:
            with self._connect() as connection:
                rows = connection.execute(
                    "SELECT source_path, checksum, page_count, chunk_count FROM indexed_documents"
                ).fetchall()
                stored = {str(row["source_path"]): dict(row) for row in rows}

        for path in paths:
            relative = path.relative_to(self.pdf_dir).as_posix()
            checksum: str | None = None
            try:
                checksum = self._digest(path)
                if checksum in seen_hashes and seen_hashes[checksum] != relative:
                    duplicates += 1
                    logger.info("Skipping duplicate PDF %s", path.name)
                    duplicate_record = stored.get(relative)
                    if duplicate_record:
                        self.vector_store.delete_document(self._document_id(path))
                        if self.mongo_metadata:
                            self.mongo_metadata.delete_source(relative)
                        else:
                            with self._connect() as connection:
                                connection.execute(
                                    "DELETE FROM indexed_documents WHERE source_path = ?",
                                    (relative,),
                                )
                        stored.pop(relative, None)
                    continue
                seen_hashes[checksum] = relative
                row = stored.get(relative)
                if (
                    row
                    and row["checksum"] == checksum
                    and len(self.vector_store.ids_for_document(self._document_id(path)))
                    == int(row["chunk_count"])
                ):
                    skipped += 1
                    processed += 1
                    pages_total += int(row["page_count"])
                    chunks_total += int(row["chunk_count"])
                    continue

                page_count, chunk_count, was_update, new_embedding_count = self._index_one(
                    path, checksum
                )
                processed += 1
                pages_total += page_count
                chunks_total += chunk_count
                generated += new_embedding_count
                if was_update or row:
                    updated += 1
            except (OSError, DocumentIngestionError, ValueError) as exc:
                previous = stored.get(relative)
                if previous and checksum and previous["checksum"] != checksum:
                    self.vector_store.delete_document(self._document_id(path))
                    if self.mongo_metadata:
                        self.mongo_metadata.delete_source(relative)
                    else:
                        with self._connect() as connection:
                            connection.execute(
                                "DELETE FROM indexed_documents WHERE source_path = ?",
                                (relative,),
                            )
                failures.append({"document": path.name, "error": str(exc)})
                logger.exception("Failed to ingest %s", path.name)
            except Exception:
                failures.append({"document": path.name, "error": "Unexpected ingestion error"})
                logger.exception("Unexpected error while ingesting %s", path.name)

        deleted = 0
        for relative, row in stored.items():
            if relative in live_paths:
                continue
            document_id = self._document_id(self.pdf_dir / Path(relative))
            self.vector_store.delete_document(document_id)
            if self.mongo_metadata:
                self.mongo_metadata.delete_source(relative)
            else:
                with self._connect() as connection:
                    connection.execute(
                        "DELETE FROM indexed_documents WHERE source_path = ?", (relative,)
                    )
            deleted += 1

        summary = {
            "total_pdfs_discovered": len(paths),
            "successfully_processed": processed,
            "failed_pdfs": failures,
            "total_pages": pages_total,
            "total_chunks": chunks_total,
            "new_embeddings_generated": generated,
            "updated_documents": updated,
            "skipped_unchanged_documents": skipped,
            "duplicate_documents": duplicates,
            "deleted_documents": deleted,
        }
        logger.info("Ingestion complete: %s", json.dumps(summary, ensure_ascii=False))
        return summary

    def clear_metadata(self) -> None:
        if self.mongo_metadata:
            self.mongo_metadata.clear_all()
            return
        with self._connect() as connection:
            connection.execute("DELETE FROM indexed_documents")

    def documents(self) -> list[dict[str, Any]]:
        if self.mongo_metadata:
            rows = self.mongo_metadata.list_documents()
        else:
            with self._connect() as connection:
                rows = [
                    dict(row)
                    for row in connection.execute(
                        """
                        SELECT document_id, document_name, document_title, scheme_name, page_count,
                               chunk_count, checksum, indexed_at
                        FROM indexed_documents ORDER BY document_name COLLATE NOCASE
                        """
                    ).fetchall()
                ]
        return [
            {
                key: row[key]
                for key in (
                    "document_id",
                    "document_name",
                    "document_title",
                    "scheme_name",
                    "page_count",
                    "chunk_count",
                    "checksum",
                    "indexed_at",
                )
            }
            | {"status": "indexed", "pdf_url": f"/api/v1/documents/{row['document_id']}/file"}
            for row in rows
        ]

    def document(self, document_id: str) -> dict[str, Any] | None:
        if self.mongo_metadata:
            row = self.mongo_metadata.get_document(document_id)
        else:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT * FROM indexed_documents WHERE document_id = ?",
                    (document_id,),
                ).fetchone()
        if row is None:
            return None
        return dict(row) | {"status": "indexed"}

    def pdf_path(self, document_id: str) -> Path | None:
        document = self.document(document_id)
        if document is None:
            return None
        path = (self.pdf_dir / document["source_path"]).resolve()
        if not path.is_relative_to(self.pdf_dir) or not path.is_file():
            return None
        return path
