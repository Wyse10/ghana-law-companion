from __future__ import annotations

from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue

MODEL_NAME = "BAAI/bge-base-en-v1.5"
COLLECTION_NAME = "ghana_constitution"


def retrieve_relevant_context(
    query: str,
    qdrant_client: QdrantClient,
    top_k: int = 4,
    chapter_filter: str | None = None,
) -> list[dict[str, Any]]:
    """Embed the user query locally via FastEmbed and retrieve matching legal

    chunks from Qdrant.
    """
    # Build metadata filter if specified (e.g., Chapter "5")
    query_filter = None
    if chapter_filter:
        query_filter = Filter(
            must=[
                FieldCondition(
                    key="chapter_number",
                    match=MatchValue(value=str(chapter_filter)),
                )
            ]
        )

    # Perform query using qdrant-client fastembed integration
    # Qdrant embeds the search query on CPU automatically using BAAI/bge-base-en-v1.5
    results = qdrant_client.query(
        collection_name=COLLECTION_NAME,
        query_text=query,
        using=MODEL_NAME,
        query_filter=query_filter,
        limit=top_k,
    )

    retrieved_chunks = []
    for point in results:
        payload = point.metadata or {}
        retrieved_chunks.append(
            {
                "text": payload.get("document", payload.get("text", "")),
                "chapter_number": payload.get("chapter_number"),
                "chapter_title": payload.get("chapter_title"),
                "article_number": payload.get("article_number"),
                "article_title": payload.get("article_title"),
                "page": payload.get("page"),
                "score": point.score,
                "metadata": payload,
            }
        )

    return retrieved_chunks