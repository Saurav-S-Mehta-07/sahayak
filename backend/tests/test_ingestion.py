from pathlib import Path

import fitz

from app.rag.ingestion import IngestionService


class FakeEmbeddings:
    def __init__(self):
        self.calls = 0

    def embed(self, texts):
        self.calls += len(texts)
        return [[float(len(text)), 1.0] for text in texts]


class FakeVectorStore:
    def __init__(self):
        self.chunks = {}

    def ids_for_document(self, document_id):
        return [
            chunk_id
            for chunk_id, chunk in self.chunks.items()
            if chunk.metadata["document_id"] == document_id
        ]

    def upsert(self, chunks, vectors):
        for chunk in chunks:
            self.chunks[chunk.metadata["chunk_id"]] = chunk

    def delete_ids(self, ids):
        for chunk_id in ids:
            self.chunks.pop(chunk_id, None)

    def delete_document(self, document_id):
        self.delete_ids(self.ids_for_document(document_id))


def write_pdf(path: Path, text: str):
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    document.save(path)
    document.close()


def test_ingestion_is_incremental_and_removes_deleted_documents(tmp_path):
    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    pdf = pdf_dir / "scheme.pdf"
    write_pdf(pdf, "Eligibility\nApplicants must meet the criteria.")
    embeddings = FakeEmbeddings()
    vectors = FakeVectorStore()
    service = IngestionService(
        embeddings,
        vectors,
        pdf_dir=pdf_dir,
        database_path=tmp_path / "metadata.sqlite3",
    )

    first = service.ingest()
    assert first["successfully_processed"] == 1
    assert first["new_embeddings_generated"] > 0

    second = service.ingest()
    assert second["skipped_unchanged_documents"] == 1
    assert second["new_embeddings_generated"] == 0

    write_pdf(pdf, "Eligibility\nApplicants must meet the updated documented criteria.")
    updated = service.ingest()
    assert updated["updated_documents"] == 1

    pdf.unlink()
    deleted = service.ingest()
    assert deleted["deleted_documents"] == 1
    assert vectors.chunks == {}
