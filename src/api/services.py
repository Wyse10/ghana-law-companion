from time import perf_counter
from typing import Any
from uuid import uuid4

from src.api.schemas import QueryAPIRequest, QueryAPIResponse, QuerySource, QueryTiming
from src.rag.generator import generate_legal_answer_structured, rerank_contexts
from src.vectorstore.retriever import retrieve_relevant_context
from src.vectorstore.store import LocalVectorStore


class RAGService:
    """Application service for grounded constitutional questions."""

    def __init__(self, vector_store: LocalVectorStore) -> None:
        self.vector_store = vector_store

    def answer(self, request: QueryAPIRequest) -> QueryAPIResponse:
        """Retrieve sources and generate a citation-validated answer."""
        started = perf_counter()
        retrieval_started = perf_counter()
        contexts = retrieve_relevant_context(
            query=request.query,
            vector_store=self.vector_store,
            top_k=request.top_k,
            chapter_filter=request.chapter,
        )
        contexts = rerank_contexts(request.query, contexts)
        retrieval_ms = (perf_counter() - retrieval_started) * 1000

        generation_started = perf_counter()
        answer = generate_legal_answer_structured(
            query=request.query,
            contexts=contexts,
        )
        generation_ms = (perf_counter() - generation_started) * 1000

        sources = [
            QuerySource(
                text=context["text"],
                chapter_number=context.get("chapter_number"),
                article_number=context.get("article_number"),
                score=float(context.get("score", 0.0)),
            )
            for context in contexts
        ]
        return QueryAPIResponse(
            request_id=str(uuid4()),
            answer=answer,
            sources=sources,
            timing=QueryTiming(
                retrieval_ms=round(retrieval_ms, 2),
                generation_ms=round(generation_ms, 2),
                total_ms=round((perf_counter() - started) * 1000, 2),
            ),
        )

    def close(self) -> None:
        """Release resources owned by the vector store."""
        self.vector_store.close()
