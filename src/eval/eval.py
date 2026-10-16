from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI
from src.config import GROQ_API_KEY
from src.schemas import AnswerEval, RetrievedContext, RetrievalEval, TestQuestion
from src.rag.generator import generate_legal_answer
from src.vectorstore.retriever import retrieve_relevant_context
from src.vectorstore.store import LocalVectorStore

load_dotenv(override=True)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = PROJECT_ROOT / "data" / "evals" / "golden_dataset.json"
DB_PATH = str(PROJECT_ROOT / "data" / "qdrant_db")

# Keep this in sync with the model exposed by the Groq account.
MODEL = "qwen/qwen3.8-27b"
EVAL_CONTEXT_LIMIT = int(os.getenv("EVAL_CONTEXT_LIMIT", "10"))


def load_tests(path: str | Path = DATASET_PATH) -> list[TestQuestion]:
    """Load the golden evaluation dataset used by the Gradio dashboard."""
    dataset_path = Path(path)
    if not dataset_path.is_absolute():
        dataset_path = PROJECT_ROOT / dataset_path
    records = json.loads(dataset_path.read_text(encoding="utf-8"))
    return [TestQuestion.model_validate(record) for record in records]


def _limit_text(text: str, max_chars: int) -> str:
    """Keep model evaluation prompts below the provider's input-token limit."""
    if len(text) <= max_chars:
        return text
    return f"{text[:max_chars]}\n[content truncated]"


def _document_text(document: dict[str, Any]) -> str:
    return RetrievedContext.model_validate(document).text


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
    """Retrieve local vector-store context for an evaluation query."""
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


# In eval_4.py
def evaluate_answer(
    test: TestQuestion,
    vector_store: LocalVectorStore | None = None,
    generated_answer: str | None = None,
    retrieved_docs: list[dict[str, Any]] | None = None,
) -> tuple[AnswerEval, str, list[dict[str, Any]]]:
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not set.")

    if generated_answer is None or retrieved_docs is None:
        generated_answer, retrieved_docs = answer_question(test.query, vector_store)

    evaluation_max_chars = max(
        int(os.getenv("GROQ_EVALUATION_MAX_CHARS", "16000")),
        1,
    )
    judge_messages = [
        {
            "role": "system",
            "content": (
                "You are an expert legal evaluator for the 1992 Constitution of Ghana. "
                "Compare the Generated Answer with the Reference Answer and evaluate it "
                "only against the user's question.\n\n"
                "Please evaluate the generated answer on three dimensions:\n"
                "1. Accuracy: How factually correct is it compared to the reference answer? "
                "Only give 5/5 for a perfect answer. If the answer is factually wrong, "
                "the accuracy score must be 1/5.\n"
                "2. Completeness: How thoroughly does it address every aspect of the "
                "question, covering all information and legal grounds in the reference answer?\n"
                "3. Relevance: How directly does it answer the specific question asked, "
                "without unnecessary or unrelated information?\n\n"
                "Use integer scores from 1 (very poor) to 5 (ideal) for each dimension. "
                "Give detailed feedback that explains the scores, identifies missing or "
                "incorrect legal points, and distinguishes factual errors from omissions. "
                "Do not penalize harmless differences in wording, formatting, or organization "
                "when the legal meaning is correct. Return only the requested feedback and "
                "the three scores in the specified structured response format."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Question:\n{_limit_text(test.query, 2000)}\n\n"
                f"Generated Answer:\n{_limit_text(generated_answer, evaluation_max_chars // 2)}\n\n"
                f"Reference Answer:\n{_limit_text(test.ground_truth_answer, evaluation_max_chars // 2)}"
            ),
        },
    ]

    client = OpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=GROQ_API_KEY,
    )

    response = client.chat.completions.parse(
        model=MODEL,
        messages=judge_messages,
        response_format=AnswerEval,
        max_tokens=min(int(os.getenv("GROQ_EVALUATION_MAX_TOKENS", "200")), 300),
    )

    parsed_answer = response.choices[0].message.parsed
    if parsed_answer is None:
        raise RuntimeError("The evaluation judge returned an empty structured response.")
    return parsed_answer, generated_answer, retrieved_docs

def evaluate_test_case(
    test: TestQuestion,
    vector_store: LocalVectorStore | None = None,
) -> tuple[RetrievalEval, AnswerEval, str, list[dict[str, Any]]]:
    """Evaluate one test case while retrieving its context only once."""
    retrieved_docs = fetch_context(test.query, vector_store)
    mrr_scores = [calculate_mrr(keyword, retrieved_docs) for keyword in test.keywords]
    ndcg_scores = [
        calculate_ndcg(keyword, retrieved_docs) for keyword in test.keywords
    ]
    total_keywords = len(test.keywords)
    keywords_found = sum(score > 0 for score in mrr_scores)
    retrieval_result = RetrievalEval(
        mrr=sum(mrr_scores) / total_keywords if total_keywords else 0.0,
        ndcg=sum(ndcg_scores) / total_keywords if total_keywords else 0.0,
        keywords_found=keywords_found,
        total_keywords=total_keywords,
        keyword_coverage=(
            keywords_found / total_keywords * 100 if total_keywords else 0.0
        ),
    )
    generated_answer = generate_legal_answer(
        test.query, retrieved_docs[:EVAL_CONTEXT_LIMIT]
    )
    answer_result, _, _ = evaluate_answer(
        test,
        vector_store,
        generated_answer=generated_answer,
        retrieved_docs=retrieved_docs,
    )
    return retrieval_result, answer_result, generated_answer, retrieved_docs


def main() -> None:
    import sys

    if len(sys.argv) != 2:
        raise SystemExit("Usage: python -m src.eval.eval <test_number>")
    tests = load_tests()
    test_number = int(sys.argv[1])
    if not 0 <= test_number < len(tests):
        raise SystemExit(f"Test number must be between 0 and {len(tests) - 1}.")
    test = tests[test_number]
    ret_eval, ans_eval, gen_ans, _ = evaluate_test_case(test)

    print(f"\n{'=' * 60}")
    print(f"Test ID: {test.id}")
    print(f"{'=' * 60}")
    print(f"MRR: {ret_eval.mrr:.4f}")
    print(f"nDCG: {ret_eval.ndcg:.4f}")
    print(f"Keyword Coverage: {ret_eval.keyword_coverage:.1f}%")
    print(f"\nAccuracy: {ans_eval.accuracy:.2f}/5.0")
    print(f"Completeness: {ans_eval.completeness:.2f}/5.0")
    print(f"Relevance: {ans_eval.relevance:.2f}/5.0")
    print(f"Feedback: {ans_eval.feedback}")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()