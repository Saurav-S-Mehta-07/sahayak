"""PDF loading helpers."""

from __future__ import annotations

import logging
from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document

from .config import settings

logger = logging.getLogger(__name__)


def load_all_pdfs(folder_path: str | Path | None = None) -> list[Document]:
    """Load PDF pages from files directly inside the configured PDF directory."""
    directory = Path(folder_path) if folder_path is not None else settings.pdf_dir
    if not directory.is_dir():
        raise FileNotFoundError(f"PDF directory does not exist: {directory}")

    pdf_paths = sorted(
        path for path in directory.iterdir() if path.is_file() and path.suffix.lower() == ".pdf"
    )
    documents: list[Document] = []
    for pdf_path in pdf_paths:
        documents.extend(PyPDFLoader(str(pdf_path)).load())

    logger.info("Loaded %d pages from %d PDFs in %s", len(documents), len(pdf_paths), directory)
    return documents
