from pydantic import BaseModel, Field, field_validator

from src.api.memory import ChatMessage
from src.schemas import LegalAnswer


class QueryAPIRequest(BaseModel):
    """Request body for a grounded legal question with multi-turn support."""

    query: str = Field(
        min_length=1,
        max_length=10_000,
        examples=["What rights protect personal liberty under the Constitution?"],
    )
    top_k: int = Field(default=5, ge=1, le=10, examples=[5])
    chapter: str | None = Field(
        default=None,
        max_length=20,
        examples=[None],
        description="Optional chapter number, for example '5'.",
    )
    session_id: str | None = Field(
        default=None,
        max_length=128,
        description="Optional conversation session ID for multi-turn follow-ups.",
    )
    messages: list[ChatMessage] | None = Field(
        default=None,
        description="Optional explicit conversation history for this session.",
    )

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("query must not be empty")
        return value


class QuerySource(BaseModel):
    """A constitutional source returned with an answer."""

    text: str
    chapter_number: str | None = None
    article_number: str | None = None
    score: float


class QueryTiming(BaseModel):
    """Timing measurements for one query."""

    retrieval_ms: float
    generation_ms: float
    total_ms: float


class QueryAPIResponse(BaseModel):
    """Validated response from the legal question endpoint."""

    request_id: str
    session_id: str = Field(default="", description="Conversation session ID for follow-ups")
    answer: LegalAnswer
    sources: list[QuerySource]
    timing: QueryTiming
    history: list[ChatMessage] = Field(default_factory=list, description="Conversation history for this session")
    disclaimer: str = (
        "This is legal information, not legal advice. Consult a qualified "
        "Ghanaian lawyer for advice about your situation."
    )


class ConversationHistoryResponse(BaseModel):
    """Conversation history payload for a session."""

    session_id: str
    messages: list[ChatMessage]
