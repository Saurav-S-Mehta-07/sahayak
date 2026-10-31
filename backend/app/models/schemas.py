from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.config import settings


class Citation(BaseModel):
    citation_id: str
    document_id: str
    document_name: str
    document_title: str | None = None
    scheme_name: str
    page_number: int = Field(ge=1)
    section: str | None = None
    supporting_excerpt: str
    pdf_url: str


class GroundingResult(BaseModel):
    grounded: bool
    verification_status: Literal[
        "verified", "partially_supported", "insufficient_evidence", "verification_failed"
    ]
    unsupported_claims: list[str] = Field(default_factory=list)
    citation_valid: bool


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str = Field(min_length=1, max_length=settings.max_request_characters)
    language: Literal["auto", "english", "hindi", "hinglish"] = "auto"
    scheme_id: str | None = Field(default=None, max_length=120)

    @field_validator("message")
    @classmethod
    def reject_blank_message(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("message must not be blank")
        return value.strip()


class ConversationContext(BaseModel):
    current_scheme: str | None = None
    preferred_language: str


class ChatResponse(BaseModel):
    session_id: str
    answer: str
    language: Literal["english", "hindi", "hinglish"]
    citations: list[Citation]
    grounding: GroundingResult
    suggested_questions: list[str]
    conversation_context: ConversationContext


class EligibilityProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    age: int | None = Field(default=None, ge=0, le=120)
    state: str | None = Field(default=None, max_length=100)
    district: str | None = Field(default=None, max_length=100)
    occupation: str | None = Field(default=None, max_length=100)
    annual_income: float | None = Field(default=None, ge=0)
    student_status: bool | None = None
    education_level: str | None = Field(default=None, max_length=100)
    gender: str | None = Field(default=None, max_length=40)
    farmer: bool | None = None
    land_ownership: str | None = Field(default=None, max_length=100)
    category: str | None = Field(default=None, max_length=100)


class EligibilityRequest(BaseModel):
    session_id: str | None = None
    scheme_id: str = Field(min_length=1, max_length=120)
    profile: EligibilityProfile


class EligibilityResult(BaseModel):
    scheme_name: str
    status: Literal["LIKELY_ELIGIBLE", "LIKELY_NOT_ELIGIBLE", "INSUFFICIENT_INFORMATION"]
    matched_criteria: list[str]
    unmatched_criteria: list[str]
    missing_information: list[str]
    explanation: str
    citations: list[Citation]
    disclaimer: str


class SessionCreateResponse(BaseModel):
    session_id: str
    created_at: str


class SessionHistoryResponse(BaseModel):
    session_id: str
    messages: list[dict[str, Any]]
    conversation_context: dict[str, Any]


class DocumentSummary(BaseModel):
    document_id: str
    document_name: str
    scheme_name: str
    page_count: int
    chunk_count: int
    status: str
    checksum: str
    pdf_url: str


class IngestionSummary(BaseModel):
    total_pdfs_discovered: int
    successfully_processed: int
    failed_pdfs: list[dict[str, str]]
    total_pages: int
    total_chunks: int
    new_embeddings_generated: int
    updated_documents: int
    skipped_unchanged_documents: int
    duplicate_documents: int = 0
    deleted_documents: int = 0


class ErrorResponse(BaseModel):
    detail: str
