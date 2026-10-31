"""Document text splitting."""

from __future__ import annotations

from collections.abc import Sequence

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from .config import settings


def split_docs(
    documents: Sequence[Document],
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[Document]:
    """Split page documents into overlapping chunks while retaining metadata."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size if chunk_size is None else chunk_size,
        chunk_overlap=(
            settings.chunk_overlap if chunk_overlap is None else chunk_overlap
        ),
    )
    return splitter.split_documents(list(documents))
