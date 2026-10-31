"""Groq chat-model initialization and response generation."""

from __future__ import annotations

import logging
import os

from langchain_groq import ChatGroq

from .config import settings

logger = logging.getLogger(__name__)


def create_llm() -> ChatGroq:
    """Create the notebook's Groq model, requiring a configured API key."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key or api_key == "your_groq_api_key":
        raise RuntimeError("GROQ_API_KEY is required to generate an answer")
    return ChatGroq(
        groq_api_key=your_groq_api_key
        model=settings.groq_model,
        temperature=settings.groq_temperature,
        max_tokens=settings.max_response_tokens,
    )


def generate_response(llm: ChatGroq, prompt: str) -> str:
    """Invoke the configured chat model and return its text response."""
    try:
        response = llm.invoke(prompt)
    except Exception:
        logger.exception("Groq response generation failed")
        raise
    content = getattr(response, "content", None)
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("The LLM returned an empty or non-text response")
    return content
