from __future__ import annotations

from functools import lru_cache
import re
from typing import Any

from fastembed import TextEmbedding

MODEL_NAME = "BAAI/bge-base-en-v1.5"
from .store import LocalVectorStore

_STOP_WORDS = {
    "a", "about", "an", "and", "are", "as", "at", "be", "by", "can", "does",
    "for", "from", "how", "in", "is", "it", "may", "of", "on", "or", "the",
    "this", "to", "under", "was", "what", "when", "which", "who", "with",
}


def _terms(text: str) -> set[str]:
    return {
        term
        for term in re.findall(r"[a-z0-9]+", text.lower())
        if len(term) > 2 and term not in _STOP_WORDS
    }


def _build_chunk(result: dict[str, Any]) -> dict[str, Any] | None:
    payload = result["metadata"]
    text_content = payload.get("text", "")
    if not text_content:
        return None
    return {
        "text": text_content,
        "chapter_number": payload.get("chapter_number"),
        "article_number": payload.get("article_number"),
        "score": result["score"],
        "metadata": payload,
    }


@lru_cache(maxsize=1)
def _get_embedding_model() -> TextEmbedding:
    return TextEmbedding(model_name=MODEL_NAME)


def retrieve_relevant_context(
    query: str,
    qdrant_client: LocalVectorStore,
    top_k: int = 5,
    chapter_filter: str | None = None,
) -> list[dict[str, Any]]:
    """Embed the user query locally via FastEmbed and retrieve matching legal

    chunks from Qdrant.
    """
    model = _get_embedding_model()
    query_vector = next(model.embed([query])).tolist()
    candidate_limit = max(top_k * 5, 50)
    semantic_results = qdrant_client.query(vector=query_vector, limit=candidate_limit)
    query_terms = _terms(query)
    candidates: dict[tuple[str, str, str], tuple[dict[str, Any], float]] = {}
    semantic_scores: dict[tuple[str, str], float] = {}
    top_semantic_key: tuple[str, str, str] | None = None
    top_semantic_score = 0.0

    for result_index, result in enumerate(semantic_results):
        chunk = _build_chunk(result)
        if chunk is None:
            continue
        payload = chunk["metadata"]
        if chapter_filter is not None and payload.get("chapter_number") != chapter_filter:
            continue
        article_key = (
            str(payload.get("chapter_number", "")),
            str(payload.get("article_number", "")),
        )
        semantic_scores[article_key] = max(
            semantic_scores.get(article_key, 0.0), float(chunk["score"])
        )
        key = (*article_key, str(payload.get("text", "")))
        if result_index == 0:
            top_semantic_key = key
            top_semantic_score = float(chunk["score"])
        candidates[key] = (chunk, float(chunk["score"]))

    for payload in qdrant_client.payloads:
        if chapter_filter is not None and payload.get("chapter_number") != chapter_filter:
            continue
        text = str(payload.get("text", ""))
        searchable_text = f"{payload.get('article_title', '')} {text}"
        matching_terms = len(query_terms & _terms(searchable_text))
        if not matching_terms:
            continue
        chunk = _build_chunk({"metadata": payload, "score": 0.0})
        if chunk is None:
            continue
        article_key = (
            str(payload.get("chapter_number", "")),
            str(payload.get("article_number", "")),
        )
        key = (*article_key, text)
        semantic_score = semantic_scores.get(article_key, 0.0)
        candidates[key] = (chunk, semantic_score)

    ranked: list[tuple[float, int, dict[str, Any]]] = []
    for index, (chunk, semantic_score) in enumerate(candidates.values()):
        searchable_text = (
            f"{chunk['metadata'].get('article_title', '')} {chunk['text']}"
        ).lower()
        title_terms = _terms(str(chunk["metadata"].get("article_title", "")))
        matching_terms = len(query_terms & _terms(searchable_text))
        coverage = matching_terms / max(len(query_terms), 1)
        title_coverage = len(query_terms & title_terms) / max(len(query_terms), 1)
        phrase_bonus = 0.15 if "supreme court" in query.lower() and "supreme court" in searchable_text else 0.0
        hybrid_score = (
            semantic_score
            + (0.3 * coverage)
            + (0.25 * title_coverage)
            + phrase_bonus
        )
        ranked.append((hybrid_score, -index, chunk))

    ranked.sort(reverse=True, key=lambda item: (item[0], item[1]))
    if (
        top_semantic_score < 0.74
        or top_semantic_key is None
        or top_semantic_key not in candidates
    ):
        return [chunk for _, _, chunk in ranked[:top_k]]

    top_semantic_chunk = candidates[top_semantic_key][0]
    ranked = [
        item
        for item in ranked
        if (
            str(item[2]["metadata"].get("chapter_number", "")),
            str(item[2]["metadata"].get("article_number", "")),
            str(item[2].get("text", "")),
        )
        != top_semantic_key
    ]
    return [top_semantic_chunk] + [chunk for _, _, chunk in ranked[: top_k - 1]]