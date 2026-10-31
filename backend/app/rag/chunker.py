from __future__ import annotations

import hashlib
import re

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.utils.language import DEVANAGARI
from app.utils.text_utils import scheme_name_from_filename, slugify

CHUNK_SIZE = 500
CHUNK_OVERLAP = 50


def split_pages(
    pages: list[Document],
    document_id: str,
    document_name: str,
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
        add_start_index=True,
    )
    chunks = splitter.split_documents(pages)
    scheme_name = scheme_name_from_filename(document_name)
    scheme_id = slugify(scheme_name)
    for index, chunk in enumerate(chunks):
        content_hash = hashlib.sha256(chunk.page_content.encode("utf-8")).hexdigest()
        page_number = int(chunk.metadata.get("page_number", 1))
        chunk_id = hashlib.sha256(
            f"{document_id}:{page_number}:{content_hash}".encode("utf-8")
        ).hexdigest()
        chunk.metadata.update(
            {
                "document_id": document_id,
                "document_name": document_name,
                "scheme_name": scheme_name,
                "scheme_id": scheme_id,
                "page_number": page_number,
                "chunk_id": chunk_id,
                "content_hash": content_hash,
                "chunk_index": index,
                "language": "hi" if DEVANAGARI.search(chunk.page_content) else "en",
            }
        )
    return chunks
