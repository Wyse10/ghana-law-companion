from time import perf_counter
from typing import Any
from uuid import uuid4

from src.api.memory import ConversationMemory, get_conversation_memory
from src.api.schemas import QueryAPIRequest, QueryAPIResponse, QuerySource, QueryTiming
from src.rag.generator import generate_legal_answer_structured, rerank_contexts
from src.rag.history_aware import retrieve_relevant_context_history_aware
from src.vectorstore.retriever import retrieve_relevant_context
from src.vectorstore.store import LocalVectorStore


class RAGService:
    """Application service for grounded constitutional questions with conversational memory."""

    def __init__(
        self,
        vector_store: LocalVectorStore,
        memory: ConversationMemory | None = None,
    ) -> None:
        self.vector_store = vector_store
        self.memory = memory or get_conversation_memory()

    def answer(self, request: QueryAPIRequest) -> QueryAPIResponse:
        """Retrieve sources and generate a citation-validated answer with conversational memory."""
        started = perf_counter()

        # 1. Manage multi-turn session ID and history
        session_id = self.memory.get_or_create_session(request.session_id)
        if request.messages is not None:
            self.memory.set_history(session_id, request.messages)

        history_dicts = self.memory.get_history_dicts(session_id)
        session_messages = self.memory.get_history(session_id)

        # 2. History-Aware Retrieval for multi-turn sessions
        retrieval_started = perf_counter()
        contexts, effective_query = retrieve_relevant_context_history_aware(
            query=request.query,
            vector_store=self.vector_store,
            history=session_messages,
            top_k=request.top_k,
            chapter_filter=request.chapter,
            max_tokens=50,
            strategy="last",
        )

        contexts = rerank_contexts(effective_query, contexts)
        retrieval_ms = (perf_counter() - retrieval_started) * 1000

        # 3. Structured generation with conversation history
        generation_started = perf_counter()
        answer = generate_legal_answer_structured(
            query=request.query,
            contexts=contexts,
            history=history_dicts,
        )
        generation_ms = (perf_counter() - generation_started) * 1000

        # 4. Save new turn to conversation memory
        updated_history = self.memory.add_turn(
            session_id=session_id,
            user_query=request.query,
            assistant_answer=answer.answer,
            citations=answer.citations,
        )

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
            session_id=session_id,
            answer=answer,
            sources=sources,
            history=updated_history,
            timing=QueryTiming(
                retrieval_ms=round(retrieval_ms, 2),
                generation_ms=round(generation_ms, 2),
                total_ms=round((perf_counter() - started) * 1000, 2),
            ),
        )

    def close(self) -> None:
        """Release resources owned by the vector store."""
        self.vector_store.close()
