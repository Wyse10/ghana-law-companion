from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _require_text(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("value must not be empty")
    return value


class LegalChunkMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")

    chapter_number: str
    chapter_title: str
    article_number: str
    article_title: str
    page: int = Field(ge=1)
    cross_references: list[str] = Field(default_factory=list)
    source: str


class LegalChunk(BaseModel):
    text: str = Field(min_length=1)
    metadata: LegalChunkMetadata

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return _require_text(value)


class RetrievedContext(BaseModel):
    text: str = Field(min_length=1)
    chapter_number: str | None = None
    article_number: str | None = None
    score: float = 0.0
    metadata: LegalChunkMetadata

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return _require_text(value)


class VectorSearchResult(BaseModel):
    score: float
    metadata: LegalChunkMetadata


class QueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=10_000)

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        return _require_text(value)


class LegalAnswer(BaseModel):
    answer: str = Field(min_length=1)
    citations: list[str] = Field(default_factory=list)

    @field_validator("answer")
    @classmethod
    def validate_answer(cls, value: str) -> str:
        return _require_text(value)


class TestQuestion(BaseModel):
    id: str = Field(min_length=1)
    query: str = Field(min_length=1)
    expected_chapter: str = Field(min_length=1)
    expected_articles: list[str] = Field(min_length=1)
    ground_truth_answer: str = Field(min_length=1)
    category: str = Field(min_length=1)

    @property
    def keywords(self) -> list[str]:
        return [f"Article {article}" for article in self.expected_articles]


class RetrievalEval(BaseModel):
    mrr: float = Field(ge=0.0, le=1.0, description="Mean Reciprocal Rank")
    ndcg: float = Field(ge=0.0, le=1.0, description="Normalized Discounted Cumulative Gain")
    keywords_found: int = Field(ge=0)
    total_keywords: int = Field(ge=0)
    keyword_coverage: float = Field(ge=0.0, le=100.0)


class AnswerEval(BaseModel):
    feedback: str = Field(min_length=1)
    accuracy: float = Field(ge=1.0, le=5.0)
    completeness: float = Field(ge=1.0, le=5.0)
    relevance: float = Field(ge=1.0, le=5.0)


class EvaluationResult(BaseModel):
    retrieval: RetrievalEval
    answer: AnswerEval
    generated_answer: str = Field(min_length=1)
    retrieved_documents: list[RetrievedContext]


def validate_chunks(values: list[dict[str, Any] | LegalChunk]) -> list[LegalChunk]:
    return [
        value if isinstance(value, LegalChunk) else LegalChunk.model_validate(value)
        for value in values
    ]
