from __future__ import annotations

import os

from src.config import DEFAULT_MD_PATH, VECTOR_DB_PATH
from src.rag.generator import generate_legal_answer
from src.vectorstore.retriever import retrieve_relevant_context
from src.vectorstore.store import LocalVectorStore


def main() -> None:
    if not os.path.exists(os.path.join(VECTOR_DB_PATH, "vectors.npy")):
        raise FileNotFoundError(
            "The local vector store has not been created yet. "
            "Run 'uv run python data_loader.py' first."
        )

    vector_store = LocalVectorStore(VECTOR_DB_PATH)
    test_query = (
        "What are the fundamental human rights regarding personal liberty "
        "under the 1992 Constitution?"
    )

    print(f"Using indexed data from '{DEFAULT_MD_PATH}'.")
    print(f"Test Query: '{test_query}'\n")

    retrieved_contexts = retrieve_relevant_context(
        query=test_query,
        qdrant_client=vector_store,
        top_k=6,
    )

    print(f"Retrieved {len(retrieved_contexts)} relevant context chunks:")
    for idx, context in enumerate(retrieved_contexts, 1):
        print(f"\n--- [Chunk {idx}] Score: {context['score']:.4f} ---")
        print(
            f"Source: Chapter {context.get('chapter_number')}, "
            f"Article {context.get('article_number')}"
        )
        print(f"Text Snippet: {context['text'][:150]}...")

    print("\nGenerating LLM response using retrieved legal context...")
    answer = generate_legal_answer(
        query=test_query,
        contexts=retrieved_contexts,
    )

    print("\n" + "=" * 60)
    print("GENERATED LEGAL ANSWER")
    print("=" * 60)
    print(answer)
    print("=" * 60)


if __name__ == "__main__":
    main()
