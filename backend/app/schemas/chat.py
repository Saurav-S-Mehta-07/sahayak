"""Chat API request and response models."""

from pydantic import BaseModel, ConfigDict, Field

_RESPONSE_LANGUAGE_PATTERN = (
    r"^(auto|en|hi|ur|bn|ta|te|mr|gu|kn|ml|pa|hinglish|roman_hindi|roman_urdu)$"
)


class ChatRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    query: str = Field(min_length=1, max_length=1500)
    conversation_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        pattern=r"^[A-Za-z0-9._:-]+$",
    )
    response_language: str = Field(default="auto", pattern=_RESPONSE_LANGUAGE_PATTERN)
    conversation_title: str | None = Field(default=None, min_length=1, max_length=80)


class ConversationTitleRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    title: str = Field(min_length=1, max_length=80)


class ChatSource(BaseModel):
    filename: str
    source: str
    page: int | str | None = None
    content: str
    score: float | None = None
    scheme_name: str | None = None
    source_url: str | None = None


class ChatResponse(BaseModel):
    answer: str
    sources: list[ChatSource]
    conversation_id: str
    language: str = "en"
    direction: str = "ltr"
