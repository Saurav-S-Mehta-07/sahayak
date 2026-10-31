from pathlib import Path

import fitz

from app.rag.chunker import split_pages
from app.rag.pdf_processor import PDFProcessor


def create_pdf(path: Path):
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "Eligibility criteria\nApplicants must meet the requirements.")
    document.save(path)
    document.close()


def test_pdf_page_number_is_one_based(tmp_path):
    pdf = tmp_path / "scheme.pdf"
    create_pdf(pdf)
    pages = PDFProcessor(tmp_path).extract(pdf)
    assert pages
    assert pages[0].metadata["page_number"] == 1
    assert pages[0].metadata["document_name"] == "scheme.pdf"
    assert pages[0].metadata["document_title"] == "Eligibility criteria"


def test_chunk_metadata_preserves_page_and_stable_id(tmp_path):
    pdf = tmp_path / "scheme.pdf"
    create_pdf(pdf)
    pages = PDFProcessor(tmp_path).extract(pdf)
    first = split_pages(pages, "doc-1", pdf.name)
    second = split_pages(pages, "doc-1", pdf.name)
    assert first[0].metadata["page_number"] == 1
    assert first[0].metadata["chunk_id"] == second[0].metadata["chunk_id"]
    assert first[0].metadata["content_hash"]
