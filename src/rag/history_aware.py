from __future__ import annotations

import logging
from typing import Any, Literal

from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.messages import BaseMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.retrievers import BaseRetriever
from langchain_core.runnables import Runnable, RunnableLambda
from openai import OpenAI
from pydantic import Field

from src.api.memory import ChatMessage, to_langchain_messages, trim_conversation_messages
from src.config import (
    GROQ_API_KEY,
    GROQ_FALLBACK_MODEL,
    GROQ_MODEL,
    GROQ_TIMEOUT_SECONDS,
)
from src.vectorstore.protocol import VectorStore
from src.vectorstore.retriever import retrieve_relevant_context

logger = logging.getLogger(__name__)

RETRIEVER_SYSTEM_PROMPT = (
    "Given a chat history and the latest user question which might reference context in the chat history, "
    "formulate a standalone question which can be understood without the chat history. "
    "Do NOT answer the question, just reformulate it if needed and otherwise return it as is."
)


def get_history_aware_prompt() -> ChatPromptTemplate:
    """Return the standard LangChain ChatPromptTemplate for history-aware retrieval."""
    return ChatPromptTemplate.from_messages(
        [
            ("system", RETRIEVER_SYSTEM_PROMPT),
            MessagesPlaceholder("chat_history"),
            ("human", "{input}"),
        ]
    )


def reformulate_question_history_aware(
    query: str,
    history: list[ChatMessage] | list[BaseMessage] | list[dict[str, Any]] | None = None,
    max_tokens: int = 50,
    strategy: Literal["first", "last"] = "last",
    model_name: str = GROQ_MODEL,
    client: OpenAI | None = None,
) -> str:
    """Reformulate a user follow-up question into a standalone question using LangChain trimming and LLM.

    Uses the retriever system prompt:
    "Given a chat history and the latest user question which might reference context in the chat history,
    formulate a standalone question which can be understood without the chat history.
    Do NOT answer the question, just reformulate it if needed and otherwise return it as is."
    """
    if not history:
        return query

    # 1. Trim history using LangChain trim_messages with strategy="last" and max_tokens=50
    trimmed_history = trim_conversation_messages(
        history,
        max_tokens=max_tokens,
        strategy=strategy,
    )
    if not trimmed_history:
        return query

    # If GROQ API key is not configured and no mock client provided, return raw query
    if not GROQ_API_KEY and client is None:
        return query

    try:
        llm_client = client or OpenAI(
            base_url="https://api.groq.com/openai/v1",
            api_key=GROQ_API_KEY,
            timeout=GROQ_TIMEOUT_SECONDS,
        )

        prompt_template = get_history_aware_prompt()
        formatted_messages = prompt_template.format_messages(
            chat_history=trimmed_history,
            input=query,
        )

        openai_messages = []
        for msg in formatted_messages:
            if msg.type == "human":
                role = "user"
            elif msg.type == "ai":
                role = "assistant"
            elif msg.type == "system":
                role = "system"
            else:
                role = "user"
            openai_messages.append({"role": role, "content": msg.content})

        for candidate_model in (model_name, GROQ_FALLBACK_MODEL):
            try:
                response = llm_client.chat.completions.create(
                    model=candidate_model,
                    messages=openai_messages,
                    temperature=0.0,
                    max_tokens=512,
                )
                content = response.choices[0].message.content or ""
                reformulated = content.strip().strip('"').strip("'").strip()
                if reformulated:
                    return reformulated
            except Exception as model_err:
                logger.warning(
                    "History-aware reformulation failed on model %s: %s",
                    candidate_model,
                    model_err,
                )
    except Exception as error:
        logger.warning("History-aware query reformulation encountered error: %s", error)

    return query


def retrieve_relevant_context_history_aware(
    query: str,
    vector_store: VectorStore,
    history: list[ChatMessage] | list[BaseMessage] | list[dict[str, Any]] | None = None,
    top_k: int = 5,
    chapter_filter: str | None = None,
    max_tokens: int = 50,
    strategy: Literal["first", "last"] = "last",
    model_name: str = GROQ_MODEL,
    client: OpenAI | None = None,
) -> tuple[list[dict[str, Any]], str]:
    """Retrieve relevant legal contexts using the history-aware retriever.

    First reformulates follow-up queries using chat history (trimmed with strategy="last" and max_tokens=50),
    then retrieves matching constitutional chunks.
    Returns (contexts, effective_query).
    """
    effective_query = query
    if history:
        effective_query = reformulate_question_history_aware(
            query=query,
            history=history,
            max_tokens=max_tokens,
            strategy=strategy,
            model_name=model_name,
            client=client,
        )

    contexts = retrieve_relevant_context(
        query=effective_query,
        vector_store=vector_store,
        top_k=top_k,
        chapter_filter=chapter_filter,
    )

    # If contextual query was used and differed from raw query, supplement with raw query
    if effective_query != query:
        raw_contexts = retrieve_relevant_context(
            query=query,
            vector_store=vector_store,
            top_k=top_k,
            chapter_filter=chapter_filter,
        )
        seen = set()
        merged = []
        for ctx in contexts + raw_contexts:
            key = (
                str(ctx.get("chapter_number", "")),
                str(ctx.get("article_number", "")),
                str(ctx.get("metadata", {}).get("clause_number", "")),
                ctx.get("text", "")[:80],
            )
            if key not in seen:
                seen.add(key)
                merged.append(ctx)
        contexts = merged

    return contexts, effective_query


class HistoryAwareRetriever(BaseRetriever):
    """LangChain-compatible history-aware retriever for the 1992 Constitution of Ghana."""

    vector_store: Any
    top_k: int = 5
    chapter_filter: str | None = None
    chat_history: list[BaseMessage] = Field(default_factory=list)
    max_tokens: int = 50
    strategy: Literal["first", "last"] = "last"
    model_name: str = GROQ_MODEL
    client: Any = None

    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun | None = None
    ) -> list[Document]:
        contexts, _ = retrieve_relevant_context_history_aware(
            query=query,
            vector_store=self.vector_store,
            history=self.chat_history,
            top_k=self.top_k,
            chapter_filter=self.chapter_filter,
            max_tokens=self.max_tokens,
            strategy=self.strategy,
            model_name=self.model_name,
            client=self.client,
        )
        return [
            Document(
                page_content=ctx["text"],
                metadata=ctx.get("metadata", {}),
            )
            for ctx in contexts
        ]


def create_history_aware_retriever(
    llm: Any,
    retriever: Any,
    prompt: Any = None,
    max_tokens: int = 50,
    strategy: Literal["first", "last"] = "last",
) -> Runnable:
    """Create a LangChain LCEL history-aware retriever chain.

    Uses LangChain trim_messages with strategy='last' and max_tokens=50,
    and reformulates follow-up queries using the standard retriever system prompt.
    """
    prompt_template = prompt or get_history_aware_prompt()

    def _reformulate_and_retrieve(inputs: dict[str, Any]) -> list[Document]:
        user_input = inputs.get("input", "")
        raw_history = inputs.get("chat_history", [])
        trimmed = trim_conversation_messages(
            raw_history, max_tokens=max_tokens, strategy=strategy
        )

        if not trimmed:
            return retriever.invoke(user_input)

        formatted_prompt = prompt_template.format_messages(
            chat_history=trimmed, input=user_input
        )
        llm_response = llm.invoke(formatted_prompt)
        reformulated = getattr(llm_response, "content", str(llm_response)).strip()
        reformulated = reformulated.strip('"').strip("'").strip() or user_input
        return retriever.invoke(reformulated)

    return RunnableLambda(_reformulate_and_retrieve)

