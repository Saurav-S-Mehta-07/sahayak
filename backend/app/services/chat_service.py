from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.core.config import settings
from app.core.exceptions import LLMServiceError
from app.models.schemas import (
    ChatRequest,
    ChatResponse,
    ConversationContext,
    GroundingResult,
)
from app.rag.citation_manager import CitationManager
from app.rag.context_builder import ContextBuilder
from app.rag.query_processor import QueryProcessor
from app.rag.retriever import Retriever
from app.services.hallucination_checker import HallucinationChecker
from app.services.llm_service import LLMService
from app.services.memory_service import MemoryService
from app.utils.language import detect_language, language_fallback
from app.utils.text_utils import slugify

logger = logging.getLogger(__name__)


class ChatService:
    def __init__(
        self,
        retriever: Retriever,
        memory: MemoryService,
        llm: LLMService,
        query_processor: QueryProcessor | None = None,
        context_builder: ContextBuilder | None = None,
        citation_manager: CitationManager | None = None,
        checker: HallucinationChecker | None = None,
    ):
        self.retriever = retriever
        self.memory = memory
        self.llm = llm
        self.query_processor = query_processor or QueryProcessor()
        self.context_builder = context_builder or ContextBuilder(
            max_characters=max(1000, settings.max_context_characters - 3500)
        )
        self.citation_manager = citation_manager or CitationManager()
        self.checker = checker or HallucinationChecker()

    async def chat(self, request: ChatRequest) -> ChatResponse:
        if request.session_id is None:
            session = self.memory.create_session()
            session_id = session["session_id"]
            session_context = session["context"]
            recent_messages: list[dict[str, Any]] = []
            summary = ""
        else:
            stored = self.memory.get_session(request.session_id)
            if stored is None:
                raise KeyError(request.session_id)
            session_id = request.session_id
            session_context, recent_messages = self.memory.context_and_messages(session_id)
            summary = session_context["summary"]
            session_context = session_context["context"]

        language = self._language(request.message, request.language, session_context)
        current_scheme = request.scheme_id or session_context.get("current_scheme")
        query = self.query_processor.process(
            request.message,
            requested_language=language,
            current_scheme=current_scheme,
        )
        results = self.retriever.retrieve(
            query.variants,
            scheme_id=request.scheme_id
            or (slugify(current_scheme) if current_scheme else None),
        )
        evidence = self.context_builder.build(results)
        resolved_scheme = (
            str(results[0]["metadata"].get("scheme_name"))
            if results and results[0]["metadata"].get("scheme_name")
            else current_scheme
        )

        if not evidence:
            answer = language_fallback(language)
            grounding = GroundingResult(
                grounded=False,
                verification_status="insufficient_evidence",
                unsupported_claims=[],
                citation_valid=False,
            )
            citations = []
        else:
            prompt = self._conversation_prompt(
                request.message,
                summary,
                recent_messages,
                resolved_scheme,
                session_context.get("user_profile", {}),
            )
            try:
                answer = await self.llm.answer(
                    prompt,
                    self.context_builder.format(evidence),
                    language,
                )
            except LLMServiceError:
                logger.exception("Language model unavailable for session %s", session_id)
                raise
            citations = self.citation_manager.citations(evidence, answer)
            verification = self.checker.verify(
                answer,
                citations,
                evidence,
                user_message=request.message,
            )
            grounding = verification.grounding
            if not verification.safe:
                logger.warning(
                    "Grounding verification failed for session %s (%s)",
                    session_id,
                    grounding.verification_status,
                )
                answer = language_fallback(language)
                citations = []
                grounding = GroundingResult(
                    grounded=False,
                    verification_status="verification_failed",
                    unsupported_claims=verification.grounding.unsupported_claims,
                    citation_valid=verification.grounding.citation_valid,
                )

        self.memory.record_exchange(
            session_id=session_id,
            user_message=request.message,
            answer=answer,
            citations=[citation.model_dump() for citation in citations],
            language=language,
            current_scheme=resolved_scheme,
        )
        return ChatResponse(
            session_id=session_id,
            answer=answer,
            language=language,
            citations=citations,
            grounding=grounding,
            suggested_questions=self._suggestions(language, bool(resolved_scheme)),
            conversation_context=ConversationContext(
                current_scheme=resolved_scheme,
                preferred_language=language,
            ),
        )

    @staticmethod
    def _language(message: str, requested: str, context: dict[str, Any]) -> str:
        if requested != "auto":
            return requested
        detected = detect_language(message, "auto")
        words = re.findall(r"\w+", message)
        if (
            len(words) <= 4
            and not re.search(r"[\u0900-\u097f]", message)
            and detected == "english"
            and context.get("preferred_language") in {"hindi", "hinglish"}
        ):
            return str(context["preferred_language"])
        return detected

    @staticmethod
    def _conversation_prompt(
        message: str,
        summary: str,
        recent_messages: list[dict[str, Any]],
        current_scheme: str | None,
        user_profile: dict[str, Any],
    ) -> str:
        history = "\n".join(
            f"{item['role']}: {item['content'][:900]}" for item in recent_messages
        )
        summary = summary[-1600:]
        return (
            f"Current scheme: {current_scheme or 'not yet identified'}\n"
            f"Known volunteered eligibility details: "
            f"{json.dumps(user_profile, ensure_ascii=False) or '{}'}\n"
            f"Older conversation summary:\n{summary or '(none)'}\n"
            f"Recent messages:\n{history or '(none)'}\n"
            f"Current user question:\n{message}"
        )[-settings.max_context_characters :]

    @staticmethod
    def _suggestions(language: str, has_scheme: bool) -> list[str]:
        if language == "hindi":
            return (
                ["इस योजना के लिए कौन से दस्तावेज़ चाहिए?", "आवेदन कैसे करें?"]
                if has_scheme
                else ["किस योजना के बारे में जानना चाहते हैं?", "मैं योजनाएँ कैसे खोज सकता हूँ?"]
            )
        if language == "hinglish":
            return (
                ["Is scheme ke liye kaun se documents chahiye?", "Apply kaise karein?"]
                if has_scheme
                else ["Aap kis scheme ke baare mein jaana chahte hain?", "Schemes kaise search karun?"]
            )
        return (
            ["Which documents are required for this scheme?", "How do I apply?"]
            if has_scheme
            else ["Which scheme would you like to learn about?", "How can I search schemes?"]
        )
