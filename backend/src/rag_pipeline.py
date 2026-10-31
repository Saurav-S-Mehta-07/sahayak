"""Composable RAG workflow for backend applications."""

from __future__ import annotations

import logging
import re
import uuid
from collections.abc import Sequence
from typing import Any, Callable

from .config import settings
from .document_loader import load_all_pdfs
from .embeddings import EmbeddingManager
from .llm import create_llm, generate_response
from .memory import ConversationMemory, Message
from .retriever import RAGRetriever
from .text_processor import split_docs
from .vector_database import VectorStoreManager

logger = logging.getLogger(__name__)


def _estimate_tokens(text: str) -> int:
    return max(1, (len(text) + 3) // 4)


def _fit_text(text: str, token_budget: int) -> str:
    if token_budget <= 0:
        return ""
    return text if _estimate_tokens(text) <= token_budget else text[: token_budget * 4]


def build_context(
    documents: Sequence[dict[str, Any]], token_budget: int | None = None
) -> str:
    """Format retrieved documents into a context block within the token budget."""
    remaining = (
        settings.document_budget_tokens if token_budget is None else token_budget
    )
    if remaining < 0:
        raise ValueError("Context token budget cannot be negative")
    sections: list[str] = []
    for index, result in enumerate(documents, start=1):
        content = result.get("document") or result.get("page_content") or ""
        if not isinstance(content, str) or not content.strip():
            continue
        metadata = result.get("metadata")
        source = metadata.get("source", "Unknown source") if isinstance(metadata, dict) else "Unknown source"
        page = metadata.get("page")
        label = f"[{index}] Source: {source}"
        if page is not None:
            label += f", page {page}"
        section = f"{label}\n{content.strip()}"
        tokens = _estimate_tokens(section)
        if tokens > remaining:
            section = _fit_text(section, remaining)
            if section:
                sections.append(section)
            break
        sections.append(section)
        remaining -= tokens
        if remaining <= 0:
            break
    return "\n\n".join(sections)


def validate_citation_references(answer: str, context: str) -> str:
    """Remove model-generated citation markers not present in the supplied context."""
    valid = set(re.findall(r"(?m)^\[(\d+)\]\s+Source:", context))

    def replace(match: re.Match[str]) -> str:
        number = match.group(1) or match.group(2)
        if number in valid:
            return match.group(0)
        logger.warning("Removed answer citation marker without a matching context source")
        return ""

    return re.sub(r"\[(\d+)\]|【(\d+)(?:†[^】]*)?】", replace, answer)


def keep_cited_documents(
    answer: str, documents: Sequence[dict[str, Any]]
) -> tuple[str, list[dict[str, Any]]]:
    """Return only cited retrieved documents and renumber markers for the UI."""
    cited = sorted(
        {
            int(match.group(1) or match.group(2))
            for match in re.finditer(r"\[(\d+)\]|【(\d+)(?:†[^】]*)?】", answer)
        }
    )
    selected = [number for number in cited if 1 <= number <= len(documents)]
    if not selected:
        return answer, list(documents)
    renumbered = {old: new for new, old in enumerate(selected, start=1)}

    def replace(match: re.Match[str]) -> str:
        number = int(match.group(1) or match.group(2))
        return f"[{renumbered[number]}]" if number in renumbered else ""

    compact_answer = re.sub(
        r"\[(\d+)\]|【(\d+)(?:†[^】]*)?】", replace, answer
    )
    return compact_answer, [documents[number - 1] for number in selected]


class RAGPipeline:
    """Initialize reusable RAG components and query with conversation memory."""

    def __init__(
        self,
        embedding_manager: EmbeddingManager | None = None,
        vector_store: VectorStoreManager | None = None,
        llm: Any | None = None,
        memory: ConversationMemory | None = None,
        conversation_id: str | None = None,
        retrieval_filter: Callable[
            [Sequence[dict[str, Any]]], Sequence[dict[str, Any]]
        ]
        | None = None,
    ) -> None:
        self.embedding_manager = embedding_manager or EmbeddingManager()
        self.vector_store = vector_store or VectorStoreManager()
        self.retriever = RAGRetriever(self.embedding_manager, self.vector_store)
        self._llm = llm
        self.memory = memory or ConversationMemory()
        self.conversation_id = conversation_id or str(uuid.uuid4())
        self.retrieval_filter = retrieval_filter

    def ingest(self, documents: Sequence[Any] | None = None) -> int:
        """Load or accept page documents, chunk, embed, and persist them."""
        pages = list(documents) if documents is not None else load_all_pdfs()
        chunks = split_docs(pages)
        if not chunks:
            logger.warning("No document chunks were produced for ingestion")
            return 0
        texts = [document.page_content for document in chunks]
        vectors = self.embedding_manager.generate_embeddings(texts)
        return self.vector_store.add_documents(chunks, vectors)

    def _prompt(
        self,
        query: str,
        history: Sequence[Message],
        context: str,
        response_language: str = "English",
        active_topic: str | None = None,
        conversation_summary: str = "",
    ) -> str:
        history_context = "\n".join(
            f"{message['role'].capitalize()}: {message['content']}"
            for message in history
        )
        instructions = (
            "Answer the user's latest question directly in a warm, concise, "
            "natural voice. Use conversation memory only to resolve references "
            "and preferences; it is not evidence. Use retrieved document passages "
            "as the sole evidence for scheme facts. Do not add plausible details, "
            "examples, requirements, amounts, or advice that the passages do not "
            "state. Preserve important qualifications and list items from the "
            "source. Cite each factual scheme claim inline with its matching "
            "context marker, such as [1]. Never create a citation or infer a "
            "source/page. If a factual question has no supporting passage, say "
            "the available documents did not provide enough evidence and offer "
            "one useful next step; do not ask the user to supply a citation. For "
            "greetings and thanks, respond naturally without forcing a scheme answer. "
            f"Write the answer in {response_language}; do not translate source titles."
        )
        prompt = (
            f"{instructions}\n\n"
            f"Active topic for reference resolution only: {active_topic or '(none)'}\n\n"
            f"Rolling conversation summary (memory, not evidence): {conversation_summary or '(none)'}\n\n"
            f"Conversation memory:\n{history_context or '(no prior conversation)'}\n\n"
            f"Context:\n{context or '(no relevant document context found)'}\n\n"
            f"Query: {query}\nAnswer:"
        )
        reserved_tokens = settings.max_response_tokens + _estimate_tokens(query) + 256
        available_tokens = max(0, settings.context_window_tokens - reserved_tokens)
        if _estimate_tokens(prompt) <= available_tokens:
            return prompt

        history_budget = min(
            settings.history_budget_tokens,
            max(0, available_tokens - settings.document_budget_tokens),
        )
        history_text = _fit_text(history_context, history_budget)
        document_budget = min(
            settings.document_budget_tokens,
            max(0, available_tokens - _estimate_tokens(history_text)),
        )
        context = _fit_text(context, document_budget)
        return (
            f"{instructions}\n\n"
            f"Active topic for reference resolution only: {active_topic or '(none)'}\n\n"
            f"Rolling conversation summary (memory, not evidence): {conversation_summary or '(none)'}\n\n"
            f"Conversation memory:\n{history_text or '(no prior conversation)'}\n\n"
            f"Context:\n{context or '(no relevant document context found)'}\n\n"
            f"Query: {query}\nAnswer:"
        )

    @staticmethod
    def _retrieval_query(query: str, history: Sequence[Message]) -> str:
        """Carry the recent user-stated subject into short follow-up retrievals."""
        if len(query.split()) > 12 or not history:
            return query
        if not re.match(
            r"^(who|what|which|when|where|why|how|can|could|do|does|is|are|"
            r"and|also|tell me|explain|what about)\b",
            query.strip(),
            flags=re.IGNORECASE,
        ):
            return query
        common_starts = {
            "who", "what", "which", "when", "where", "why", "how", "can",
            "could", "do", "does", "is", "are", "and", "also", "tell",
            "me", "explain", "about", "the", "this", "that", "it", "i",
        }
        specific_terms = [
            word
            for word in re.findall(r"\b[A-Z][A-Za-z0-9-]*\b", query)
            if word.lower() not in common_starts
        ]
        if specific_terms:
            return query
        prior_questions = [
            message["content"].strip()[:180]
            for message in history
            if message["role"] == "user" and message["content"].strip()
        ][-3:]
        if not prior_questions:
            return query
        return "Recent user-stated scheme context: " + " ".join(
            prior_questions
        ) + f"\nCurrent question: {query}"

    def query(
        self,
        query: str,
        top_k: int | None = None,
        conversation_id: str | None = None,
        response_language: str = "English",
        active_topic: str | None = None,
        input_language: str = "en",
        conversation_summary: str = "",
    ) -> dict[str, Any]:
        """Answer a query and return the answer, documents, and memory context."""
        if not isinstance(query, str) or not query.strip():
            raise ValueError("Query must be a non-empty string")
        active_conversation = conversation_id or self.conversation_id
        history = self.memory.load_history(active_conversation)
        retrieval_query = self._retrieval_query(query.strip(), history)
        llm = self._llm if self._llm is not None else create_llm()
        if input_language not in {"en", "en-Latn"}:
            retrieval_query = generate_response(
                llm,
                "Convert this user question into a concise English search query for "
                "retrieving relevant passages from government scheme documents. "
                "Translate the question only; preserve scheme names, places, amounts, "
                "dates, and requested facts. Do not answer, add facts, or include "
                "explanation. Return only the English search query.\n\n"
                f"User question: {query.strip()}",
            )
            if not retrieval_query.strip():
                raise RuntimeError("The question could not be normalized for retrieval")
        if (
            active_topic
            and len(query.split()) <= 12
            and not re.search(rf"\b{re.escape(active_topic)}\b", query, re.I)
            and re.match(r"^(who|what|which|when|where|why|how|can|could|do|does|is|are|and|also)\b", query.strip(), re.I)
        ):
            retrieval_query = f"Active scheme: {active_topic}\n{retrieval_query}"
        results = self.retriever.retrieve(retrieval_query, top_k=top_k)
        if self.retrieval_filter is not None:
            results = list(self.retrieval_filter(results))
        context = build_context(results)
        prompt = self._prompt(
            query.strip(),
            history,
            context,
            response_language,
            active_topic,
            conversation_summary,
        )
        answer = validate_citation_references(generate_response(llm, prompt), context)
        answer, results = keep_cited_documents(answer, results)
        assistant_language = {
            "Hindi": "hi",
            "Urdu": "ur",
            "Bengali": "bn",
            "Tamil": "ta",
            "Telugu": "te",
            "Marathi": "mr",
            "Gujarati": "gu",
            "Kannada": "kn",
            "Malayalam": "ml",
            "Punjabi": "pa",
            "Hinglish (Hindi-English mix)": "hinglish",
            "Hindi written in Latin script": "roman_hindi",
            "Urdu written in Latin script": "roman_urdu",
        }.get(response_language, "en")
        self.memory.add_turn(
            active_conversation,
            query.strip(),
            answer,
            user_language=input_language,
            assistant_language=assistant_language,
        )
        sources = [
            {
                "source": result["metadata"].get("source"),
                "page": result["metadata"].get("page"),
                "metadata": result["metadata"],
            }
            for result in results
        ]
        return {
            "answer": answer,
            "sources": sources,
            "retrieved_documents": results,
            "context": context,
            "memory_context": history,
            "conversation_id": active_conversation,
        }

    def respond_without_retrieval(
        self,
        query: str,
        conversation_id: str,
        response_language: str,
        intent: str,
        previous_sources: Sequence[dict[str, Any]] = (),
        input_language: str = "en",
    ) -> dict[str, Any]:
        """Handle conversational turns without calling the vector retriever."""
        if not query.strip():
            raise ValueError("Query must be a non-empty string")
        history = self.memory.load_history(conversation_id)
        previous_answer = next(
            (
                message["content"]
                for message in reversed(history)
                if message["role"] == "assistant"
            ),
            "",
        )
        prompt = (
            "Respond to the user's conversational request as one coherent, "
            "natural answer. Do not introduce new government-scheme facts. "
            "For help, describe only this product's known capabilities: asking "
            "questions about available scheme documents and receiving citations. "
            "When simplifying, repeating, or translating, preserve the previous "
            "answer's meaning and every citation marker; do not add facts. "
            "Use the previous answer only for that transformation, not as "
            "independent evidence. Keep greetings and thanks brief. "
            f"Write in {response_language}.\n\n"
            f"Intent: {intent}\n"
            f"Previous answer:\n{previous_answer or '(no previous answer)'}\n\n"
            f"User message: {query}\nAnswer:"
        )
        llm = self._llm if self._llm is not None else create_llm()
        answer = generate_response(llm, prompt)
        assistant_language = {
            "Hindi": "hi",
            "Urdu": "ur",
            "Bengali": "bn",
            "Tamil": "ta",
            "Telugu": "te",
            "Marathi": "mr",
            "Gujarati": "gu",
            "Kannada": "kn",
            "Malayalam": "ml",
            "Punjabi": "pa",
            "Hinglish (Hindi-English mix)": "hinglish",
            "Hindi written in Latin script": "roman_hindi",
            "Urdu written in Latin script": "roman_urdu",
        }.get(response_language, "en")
        self.memory.add_turn(
            conversation_id,
            query.strip(),
            answer,
            user_language=input_language,
            assistant_language=assistant_language,
        )
        return {
            "answer": answer,
            "sources": list(previous_sources) if intent in {"simplify", "repeat", "translate"} else [],
            "retrieved_documents": [],
            "conversation_id": conversation_id,
        }

    def clear_memory(self, conversation_id: str | None = None) -> None:
        """Clear stored history for this pipeline's or a specified conversation."""
        self.memory.clear(conversation_id or self.conversation_id)
