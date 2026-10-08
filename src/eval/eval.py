from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from litellm import completion
from pydantic import BaseModel, Field

from src.config import GROQ_API_KEY
from src.rag.generator import generate_legal_answer
from src.vectorstore.retriever import retrieve_relevant_context
from src.vectorstore.store import LocalVectorStore

load_dotenv(override=True)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = PROJECT_ROOT / "data" / "evals" / "golden_dataset.json"
DB_PATH = str(PROJECT_ROOT / "data" / "qdrant_db")
# Keep this in sync with the models currently exposed by the Groq account.
MODEL = "groq/qwen/qwen3.8-27b"


@dataclass(frozen=True)
class TestQuestion:
    id: str
    query: str
    expected_chapter: str
    expected_articles: list[str]
    ground_truth_answer: str
    category: str

    @property
    def keywords(self) -> list[str]:
        return [f"Article {article}" for article in self.expected_articles]


def load_tests(path: str | Path = DATASET_PATH) -> list[TestQuestion]:
    """Load the golden evaluation dataset used by the Gradio dashboard."""
    dataset_path = Path(path)
    if not dataset_path.is_absolute():
        dataset_path = PROJECT_ROOT / dataset_path
    records = json.loads(dataset_path.read_text(encoding="utf-8"))
    return [TestQuestion(**record) for record in records]


class RetrievalEval(BaseModel):
    mrr: float = Field(description="Mean Reciprocal Rank")
    ndcg: float = Field(description="Normalized Discounted Cumulative Gain")
    keywords_found: int
    total_keywords: int
    keyword_coverage: float


class AnswerEval(BaseModel):
    feedback: str
    accuracy: float
    completeness: float
    relevance: float


def _document_text(document: dict[str, Any]) -> str:
    return str(document.get("text", ""))


def calculate_mrr(keyword: str, retrieved_docs: list[dict[str, Any]]) -> float:
    keyword_lower = keyword.lower()
    for rank, document in enumerate(retrieved_docs, start=1):
        if keyword_lower in _document_text(document).lower():
            return 1.0 / rank
    return 0.0


def calculate_dcg(relevances: list[int], k: int) -> float:
    return sum(
        relevances[index] / math.log2(index + 2)
        for index in range(min(k, len(relevances)))
    )


def calculate_ndcg(
    keyword: str, retrieved_docs: list[dict[str, Any]], k: int = 10
) -> float:
    keyword_lower = keyword.lower()
    relevances = [
        int(keyword_lower in _document_text(document).lower())
        for document in retrieved_docs[:k]
    ]
    dcg = calculate_dcg(relevances, k)
    idcg = calculate_dcg(sorted(relevances, reverse=True), k)
    return dcg / idcg if idcg else 0.0


def fetch_context(
    query: str, vector_store: LocalVectorStore | None = None
) -> list[dict[str, Any]]:
    """Retrieve current local vector-store context for an evaluation query."""
    store = vector_store or LocalVectorStore(DB_PATH)
    return retrieve_relevant_context(query=query, qdrant_client=store, top_k=10)


def answer_question(
    query: str, vector_store: LocalVectorStore | None = None
) -> tuple[str, list[dict[str, Any]]]:
    """Generate an answer using the same RAG path as the application."""
    contexts = fetch_context(query, vector_store)
    return generate_legal_answer(query=query, contexts=contexts), contexts


def evaluate_retrieval(
    test: TestQuestion,
    vector_store: LocalVectorStore | None = None,
    k: int = 10,
) -> RetrievalEval:
    retrieved_docs = fetch_context(test.query, vector_store)
    mrr_scores = [calculate_mrr(keyword, retrieved_docs) for keyword in test.keywords]
    ndcg_scores = [
        calculate_ndcg(keyword, retrieved_docs, k) for keyword in test.keywords
    ]
    keywords_found = sum(score > 0 for score in mrr_scores)
    total_keywords = len(test.keywords)
    return RetrievalEval(
        mrr=sum(mrr_scores) / total_keywords if total_keywords else 0.0,
        ndcg=sum(ndcg_scores) / total_keywords if total_keywords else 0.0,
        keywords_found=keywords_found,
        total_keywords=total_keywords,
        keyword_coverage=(
            keywords_found / total_keywords * 100 if total_keywords else 0.0
        ),
    )


def evaluate_answer(
    test: TestQuestion,
    vector_store: LocalVectorStore | None = None,
) -> tuple[AnswerEval, str, list[dict[str, Any]]]:
    if not GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Add it to the .env file before running answer evaluation."
        )

    generated_answer, retrieved_docs = answer_question(test.query, vector_store)
    judge_messages = [
        {
            "role": "system",
            "content": (
                "Evaluate the generated legal answer against the reference answer. "
                "Only give 5 for a perfect answer. If it is factually wrong, accuracy must be 1."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Question:\n{test.query}\n\nGenerated Answer:\n{generated_answer}\n\n"
                f"Reference Answer:\n{test.ground_truth_answer}\n\n"
                "Return feedback plus accuracy, completeness, and relevance scores from 1 to 5."
            ),
        },
    ]
    response = completion(
        model=MODEL,
        messages=judge_messages,
        response_format=AnswerEval,
        api_key=GROQ_API_KEY,
    )
    content = response.choices[0].message.content
    if not content:
        raise RuntimeError("The evaluation judge returned an empty response.")
    return AnswerEval.model_validate_json(content), generated_answer, retrieved_docs


def main() -> None:
    import sys

    if len(sys.argv) != 2:
        raise SystemExit("Usage: python -m src.eval.eval <test_number>")
    tests = load_tests()
    test_number = int(sys.argv[1])
    if not 0 <= test_number < len(tests):
        raise SystemExit(f"Test number must be between 0 and {len(tests) - 1}.")
    test = tests[test_number]
    result = evaluate_retrieval(test)
    print(f"Test: {test.id}")
    print(f"MRR: {result.mrr:.4f}")
    print(f"nDCG: {result.ndcg:.4f}")
    print(f"Keyword coverage: {result.keyword_coverage:.1f}%")


if __name__ == "__main__":
    main()
