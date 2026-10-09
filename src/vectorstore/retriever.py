from __future__ import annotations

from functools import lru_cache
from typing import Any

from fastembed import TextEmbedding

MODEL_NAME = "BAAI/bge-base-en-v1.5"
from .store import LocalVectorStore


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
    results = qdrant_client.query(vector=query_vector, limit=top_k)

    retrieved_chunks = []
    for result in results:
        payload = result["metadata"]
        if chapter_filter is not None and payload.get("chapter_number") != chapter_filter:
            continue

        text_content = payload.get("text", "")

        if text_content:
            retrieved_chunks.append({
                "text": text_content,
                "chapter_number": payload.get("chapter_number"),
                "article_number": payload.get("article_number"),
                "score": result["score"],
                "metadata": payload,
            })

    return retrieved_chunks