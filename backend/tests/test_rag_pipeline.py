from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pytest
from langchain_core.documents import Document

from backend.src.config import settings
from backend.src.document_loader import load_all_pdfs
from backend.src.memory import ConversationMemory
from backend.src.rag_pipeline import (
    RAGPipeline,
    build_context,
    keep_cited_documents,
    validate_citation_references,
)
from backend.src.retriever import RAGRetriever, normalize_document
from backend.src.text_processor import split_docs
from backend.src.vector_database import VectorStoreManager


class FakeEmbeddingManager:
    def generate_embeddings(self, texts: Any) -> np.ndarray:
        count = 1 if isinstance(texts, str) else len(texts)
        return np.ones((count, 3), dtype=np.float32)

    def embed_query(self, query: str) -> np.ndarray:
        return np.ones(3, dtype=np.float32)


class FakeCollection:
    def count(self) -> int:
        return 1

    def query(self, **_: Any) -> dict[str, Any]:
        return {
            "ids": [["chunk-1"]],
            "documents": [["A benefit is available to eligible mothers."]],
            "metadatas": [[{"source": "scheme.pdf", "page": 2}]],
            "distances": [[0.2]],
        }


class FakeVectorStore:
    collection = FakeCollection()


class FakeLLM:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    def invoke(self, prompt: str) -> Any:
        self.prompts.append(prompt)
        return type("Response", (), {"content": "The document describes a benefit."})()


def test_split_docs_preserves_metadata() -> None:
    source = Document(page_content="abcdefghij", metadata={"source": "one.pdf"})
    chunks = split_docs([source], chunk_size=4, chunk_overlap=1)
    assert [chunk.page_content for chunk in chunks] == ["abcd", "defg", "ghij"]
    assert all(chunk.metadata["source"] == "one.pdf" for chunk in chunks)


def test_load_all_pdfs_reads_top_level_pdf() -> None:
    documents = load_all_pdfs()
    assert documents
    assert all(document.metadata.get("source", "").lower().endswith(".pdf") for document in documents)


def test_backend_paths_are_independent_of_current_directory() -> None:
    backend_root = Path(__file__).resolve().parents[1]
    assert settings.pdf_dir == backend_root / "data" / "pdfs"
    assert settings.vector_store_dir == backend_root / "vector_store"
    assert settings.sqlite_path == backend_root / "data" / "conversations.sqlite3"


def test_normalize_document_accepts_document_and_mapping() -> None:
    document = Document(page_content="text", metadata={"page": 1})
    assert normalize_document(document) == {
        "document": "text",
        "metadata": {"page": 1},
    }
    assert normalize_document({"page_content": "body", "metadata": {}})["document"] == "body"
    assert normalize_document({"document": "", "metadata": {}}) is None


def test_retriever_deduplicates_existing_store_records() -> None:
    class DuplicateCollection:
        def count(self) -> int:
            return 2

        def query(self, **_: Any) -> dict[str, Any]:
            content = "A  scheme provides cash benefits."
            return {
                "ids": [["one", "two"]],
                "documents": [[content, "A scheme provides cash benefits."]],
                "metadatas": [[
                    {"source": r"C:\docs\scheme.pdf", "page": 1},
                    {"source": "data/docs\\scheme.pdf", "page": 1},
                ]],
                "distances": [[0.2, 0.2]],
            }

    class DuplicateVectorStore:
        collection = DuplicateCollection()

    results = RAGRetriever(
        FakeEmbeddingManager(),  # type: ignore[arg-type]
        DuplicateVectorStore(),  # type: ignore[arg-type]
    ).retrieve("cash benefits")
    assert len(results) == 1
    assert results[0]["id"] == "one"


def test_retriever_converts_l2_distance_to_nonnegative_similarity() -> None:
    class L2Collection:
        configuration = {"hnsw": {"space": "l2"}}

        def count(self) -> int:
            return 1

        def query(self, **_: Any) -> dict[str, Any]:
            return {
                "ids": [["one"]],
                "documents": [["Relevant scheme evidence."]],
                "metadatas": [[{"source": "scheme.pdf", "page": 2}]],
                "distances": [[1.027]],
            }

    class L2VectorStore:
        collection = L2Collection()

    result = RAGRetriever(
        FakeEmbeddingManager(),  # type: ignore[arg-type]
        L2VectorStore(),  # type: ignore[arg-type]
    ).retrieve("scheme evidence")
    assert len(result) == 1
    assert result[0]["similarity_score"] == pytest.approx(1 / 2.027)


def test_build_context_includes_sources_and_pages() -> None:
    context = build_context(
        [{"document": "Relevant text.", "metadata": {"source": "one.pdf", "page": 3}}]
    )
    assert "one.pdf" in context
    assert "page 3" in context
    assert "Relevant text." in context


def test_generated_citation_markers_must_exist_in_retrieved_context() -> None:
    answer = validate_citation_references(
        "Supported [1] and 【1】, unsupported [2] and .",
        "[1] Source: scheme.pdf, page 2\nEvidence.",
    )
    assert answer == "Supported [1] and 【1】, unsupported  and ."


def test_uncited_sources_are_removed_and_citation_markers_are_renumbered() -> None:
    docs = [
        {"document": "first", "metadata": {"source": "one.pdf"}},
        {"document": "second", "metadata": {"source": "two.pdf"}},
        {"document": "third", "metadata": {"source": "three.pdf"}},
    ]
    answer, sources = keep_cited_documents("Third [3], then first 【1】.", docs)
    assert answer == "Third [2], then first [1]."
    assert sources == [docs[0], docs[2]]


def test_memory_persists_and_respects_limits(tmp_path: Path) -> None:
    memory = ConversationMemory(tmp_path / "memory.sqlite3")
    memory.add_turn("chat", "first question", "first answer")
    memory.add_turn("chat", "second question", "second answer")
    assert [item["content"] for item in memory.load_history("chat")] == [
        "first question",
        "first answer",
        "second question",
        "second answer",
    ]
    assert len(memory.load_history("chat", max_messages=1)) == 1
    memory.clear("chat")
    assert memory.load_history("chat") == []


def test_query_includes_previous_turn_in_memory_context(tmp_path: Path) -> None:
    memory = ConversationMemory(tmp_path / "memory.sqlite3")
    llm = FakeLLM()
    pipeline = RAGPipeline(
        embedding_manager=FakeEmbeddingManager(),  # type: ignore[arg-type]
        vector_store=FakeVectorStore(),  # type: ignore[arg-type]
        llm=llm,
        memory=memory,
        conversation_id="chat",
    )
    first = pipeline.query("What is the benefit?")
    second = pipeline.query("Can you clarify?")
    assert first["answer"] == "The document describes a benefit."
    assert first["sources"][0]["page"] == 2
    assert "User: What is the benefit?" in llm.prompts[1]
    assert second["memory_context"][0]["content"] == "What is the benefit?"


def test_short_followups_reuse_user_stated_scheme_context(tmp_path: Path) -> None:
    class RecordingEmbeddingManager(FakeEmbeddingManager):
        def __init__(self) -> None:
            self.queries: list[str] = []

        def embed_query(self, query: str) -> np.ndarray:
            self.queries.append(query)
            return super().embed_query(query)

    embeddings = RecordingEmbeddingManager()
    pipeline = RAGPipeline(
        embedding_manager=embeddings,  # type: ignore[arg-type]
        vector_store=FakeVectorStore(),  # type: ignore[arg-type]
        llm=FakeLLM(),
        memory=ConversationMemory(tmp_path / "followups.sqlite3"),
    )
    pipeline.query("Tell me about PM-KISAN")
    pipeline.query("Who is eligible?")
    pipeline.query("What documents do I need?")
    assert "PM-KISAN" in embeddings.queries[1]
    assert "PM-KISAN" in embeddings.queries[2]
    assert "Current question: What documents do I need?" in embeddings.queries[2]


def test_prompt_requires_grounded_inline_citations_and_natural_replies(
    tmp_path: Path,
) -> None:
    pipeline = RAGPipeline(
        embedding_manager=FakeEmbeddingManager(),  # type: ignore[arg-type]
        vector_store=FakeVectorStore(),  # type: ignore[arg-type]
        llm=FakeLLM(),
        memory=ConversationMemory(tmp_path / "prompt.sqlite3"),
    )
    prompt = pipeline._prompt(
        "What services are listed?",
        [],
        "[1] Source: scheme.pdf, page 2\nMedical aid and police assistance.",
    )
    assert "sole evidence for scheme facts" in prompt
    assert "Cite each factual scheme claim inline" in prompt
    assert "do not ask the user to supply a citation" in prompt
    assert "respond naturally without forcing a scheme answer" in prompt
    assert "Rolling conversation summary (memory, not evidence)" in prompt


def test_non_english_query_is_normalized_only_for_retrieval(tmp_path: Path) -> None:
    class RecordingEmbeddingManager(FakeEmbeddingManager):
        def __init__(self) -> None:
            self.queries: list[str] = []

        def embed_query(self, query: str) -> np.ndarray:
            self.queries.append(query)
            return super().embed_query(query)

    class TranslationLLM:
        def __init__(self) -> None:
            self.prompts: list[str] = []

        def invoke(self, prompt: str) -> Any:
            self.prompts.append(prompt)
            content = (
                "What is the PM-KISAN benefit?"
                if prompt.startswith("Convert this user question")
                else "PM-KISAN benefit answer. [1]"
            )
            return type("Response", (), {"content": content})()

    embeddings = RecordingEmbeddingManager()
    llm = TranslationLLM()
    memory = ConversationMemory(tmp_path / "multilingual.sqlite3")
    pipeline = RAGPipeline(
        embedding_manager=embeddings,  # type: ignore[arg-type]
        vector_store=FakeVectorStore(),  # type: ignore[arg-type]
        llm=llm,
        memory=memory,
    )
    original_query = "پی ایم کسان کا فائدہ کیا ہے؟"
    result = pipeline.query(
        original_query,
        conversation_id="urdu-chat",
        input_language="ur",
        response_language="Urdu",
    )

    assert embeddings.queries == ["What is the PM-KISAN benefit?"]
    assert original_query in llm.prompts[1]
    assert "Write the answer in Urdu" in llm.prompts[1]
    assert result["answer"] == "PM-KISAN benefit answer. [1]"
    with memory._connect() as connection:
        languages = connection.execute(
            "SELECT role, language FROM conversation_messages "
            "WHERE conversation_id = ? ORDER BY id",
            ("urdu-chat",),
        ).fetchall()
    assert [(row[0], row[1]) for row in languages] == [
        ("user", "ur"),
        ("assistant", "ur"),
    ]


def test_persisted_active_scheme_augments_a_short_followup_retrieval(
    tmp_path: Path,
) -> None:
    class RecordingEmbeddingManager(FakeEmbeddingManager):
        def __init__(self) -> None:
            self.queries: list[str] = []

        def embed_query(self, query: str) -> np.ndarray:
            self.queries.append(query)
            return super().embed_query(query)

    embeddings = RecordingEmbeddingManager()
    pipeline = RAGPipeline(
        embedding_manager=embeddings,  # type: ignore[arg-type]
        vector_store=FakeVectorStore(),  # type: ignore[arg-type]
        llm=FakeLLM(),
        memory=ConversationMemory(tmp_path / "active-scheme.sqlite3"),
    )
    pipeline.query(
        "Who is eligible?",
        conversation_id="returning-chat",
        active_topic="PM-KISAN",
    )
    assert "Active scheme: PM-KISAN" in embeddings.queries[0]


def test_empty_query_is_rejected(tmp_path: Path) -> None:
    pipeline = RAGPipeline(
        embedding_manager=FakeEmbeddingManager(),  # type: ignore[arg-type]
        vector_store=FakeVectorStore(),  # type: ignore[arg-type]
        llm=FakeLLM(),
        memory=ConversationMemory(tmp_path / "memory.sqlite3"),
    )
    with pytest.raises(ValueError, match="non-empty"):
        pipeline.query("  ")


def test_vector_store_can_remove_chunks_for_a_failed_managed_source() -> None:
    class Collection:
        def __init__(self) -> None:
            self.deleted: list[str] = []

        def get(self, *, where, include):
            assert where == {"source": "managed.pdf"}
            assert include == ["metadatas"]
            return {"ids": ["chunk-a", "chunk-b"]}

        def delete(self, *, ids):
            self.deleted.extend(ids)

    manager = object.__new__(VectorStoreManager)
    manager.collection = Collection()
    assert manager.remove_documents_for_source("managed.pdf") == 2
    assert manager.collection.deleted == ["chunk-a", "chunk-b"]
