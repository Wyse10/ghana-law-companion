from pydantic import BaseModel, Field, field_validator

from src.schemas import LegalAnswer


class QueryAPIRequest(BaseModel):
    """Request body for a grounded legal question."""

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
    answer: LegalAnswer
    sources: list[QuerySource]
    timing: QueryTiming
    disclaimer: str = (
        "This is legal information, not legal advice. Consult a qualified "
        "Ghanaian lawyer for advice about your situation."
    )
