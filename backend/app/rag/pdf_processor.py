from __future__ import annotations

import logging
from pathlib import Path

from langchain_community.document_loaders.pdf import PyPDFLoader
from langchain_core.documents import Document

from app.core.config import settings
from app.core.exceptions import DocumentIngestionError
from app.rag.text_cleaner import clean_page
from app.utils.language import DEVANAGARI

logger = logging.getLogger(__name__)


def _extract_document_title(pages: list[Document]) -> str:
    for page in pages[:2]:
        for line in page.page_content.splitlines():
            title = line.strip()
            if 8 <= len(title) <= 140 and not title.isdigit():
                return title
    return ""


class PDFProcessor:
    def __init__(self, pdf_root: Path = settings.pdf_dir):
        self.pdf_root = pdf_root.resolve()

    def extract(self, path: Path) -> list[Document]:
        resolved = path.resolve()
        if not resolved.is_relative_to(self.pdf_root) or resolved.suffix.lower() != ".pdf":
            raise DocumentIngestionError("PDF path must be inside the configured PDF directory")
        try:
            pages = PyPDFLoader(str(resolved)).load()
        except Exception as exc:
            logger.warning("PDF extraction failed for %s: %s", resolved.name, exc)
            raise DocumentIngestionError(f"Unable to read PDF: {resolved.name}") from exc

        if not pages:
            raise DocumentIngestionError(f"PDF has no pages: {resolved.name}")

        document_title = _extract_document_title(pages)

        try:
            relative = resolved.relative_to(settings.pdf_dir.resolve()).as_posix()
            source_path = f"backend/data/pdfs/{relative}"
        except ValueError:
            source_path = resolved.name
        output: list[Document] = []
        for index, page in enumerate(pages, start=1):
            text = clean_page(page.page_content)
            if not text:
                logger.info("Skipping text-empty page %s in %s", index, resolved.name)
                continue
            metadata = dict(page.metadata)
            metadata.update(
                {
                    "source_path": source_path,
                    "document_name": resolved.name,
                    "document_title": document_title or resolved.stem,
                    "page_number": index,
                    "language": "hi" if DEVANAGARI.search(text) else "en",
                }
            )
            output.append(Document(page_content=text, metadata=metadata))

        if not output:
            raise DocumentIngestionError(
                f"No extractable text found in {resolved.name}; scanned PDFs need OCR."
            )
        return output
