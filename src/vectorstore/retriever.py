from __future__ import annotations

from typing import Any

from fastembed import TextEmbedding

MODEL_NAME = "BAAI/bge-base-en-v1.5"
from .store import LocalVectorStore


def retrieve_relevant_context(
    query: str,
    qdrant_client: LocalVectorStore,
    top_k: int = 5,
    chapter_filter: str | None = None,
) -> list[dict[str, Any]]:
    """Embed the user query locally via FastEmbed and retrieve matching legal

    chunks from Qdrant.
    """
    model = TextEmbedding(model_name=MODEL_NAME)
    query_vector = next(model.embed([query])).tolist()
    results = qdrant_client.query(
        collection_name="ghana_constitution",
        query_text=query,
        using="BAAI/bge-base-en-v1.5",  # MUST match the exact model name used during add()
        limit=top_k,
    )

    # Inside src/vectorstore/retriever.py
    retrieved_chunks = []
    for point in results:
        payload = point.metadata or {}
        # Check both 'document' (FastEmbed default) and 'text'
        text_content = payload.get("document") or payload.get("text") or ""

        if text_content:
            retrieved_chunks.append({
                "text": text_content,
                "chapter_number": payload.get("chapter_number"),
                "article_number": payload.get("article_number"),
                "score": point.score,
                "metadata": payload,
            })

    return retrieved_chunks