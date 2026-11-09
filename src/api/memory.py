from __future__ import annotations

import re
import time
from threading import Lock
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """A message in a conversational session."""

    role: str = Field(description="Role of the sender: 'user' or 'assistant'.")
    content: str = Field(min_length=1, description="Text content of the message.")
    citations: list[str] = Field(
        default_factory=list,
        description="Constitutional citations associated with this turn (for assistant).",
    )
    timestamp: float = Field(
        default_factory=time.time,
        description="Unix timestamp when the message was recorded.",
    )


class ConversationSession:
    """In-memory storage for a single user conversation session."""

    def __init__(self, session_id: str) -> None:
        self.session_id: str = session_id
        self.created_at: float = time.time()
        self.updated_at: float = time.time()
        self.messages: list[ChatMessage] = []

    def add_user_message(self, content: str) -> ChatMessage:
        msg = ChatMessage(role="user", content=content, timestamp=time.time())
        self.messages.append(msg)
        self.updated_at = time.time()
        return msg

    def add_assistant_message(
        self, content: str, citations: list[str] | None = None
    ) -> ChatMessage:
        msg = ChatMessage(
            role="assistant",
            content=content,
            citations=citations or [],
            timestamp=time.time(),
        )
        self.messages.append(msg)
        self.updated_at = time.time()
        return msg

    def trim(self, max_turns: int) -> None:
        """Keep only the most recent max_turns * 2 messages."""
        max_messages = max_turns * 2
        if len(self.messages) > max_messages:
            self.messages = self.messages[-max_messages:]

    def get_citations(self) -> set[str]:
        """Collect all citations mentioned across assistant turns."""
        citations: set[str] = set()
        for msg in self.messages:
            if msg.role == "assistant":
                for cit in msg.citations:
                    citations.add(cit)
        return citations

    def get_recent_user_queries(self, count: int = 2) -> list[str]:
        """Return the most recent user queries."""
        user_msgs = [m.content for m in self.messages if m.role == "user"]
        return user_msgs[-count:]


class ConversationMemory:
    """Thread-safe conversation memory manager for multi-turn legal Q&A."""

    def __init__(self, max_turns: int = 10, ttl_seconds: int = 86400) -> None:
        self.max_turns = max_turns
        self.ttl_seconds = ttl_seconds
        self._sessions: dict[str, ConversationSession] = {}
        self._lock = Lock()

    def get_or_create_session(self, session_id: str | None = None) -> str:
        """Get an existing session or generate a new unique session ID."""
        with self._lock:
            if session_id and session_id.strip():
                clean_id = session_id.strip()
                if clean_id not in self._sessions:
                    self._sessions[clean_id] = ConversationSession(clean_id)
                else:
                    self._sessions[clean_id].updated_at = time.time()
                return clean_id

            new_id = str(uuid4())
            self._sessions[new_id] = ConversationSession(new_id)
            return new_id

    def get_history(self, session_id: str) -> list[ChatMessage]:
        """Return the list of ChatMessage instances for a session."""
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return []
            return list(session.messages)

    def get_history_dicts(self, session_id: str) -> list[dict[str, Any]]:
        """Return history as dictionaries suitable for prompt construction."""
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return []
            return [
                {
                    "role": m.role,
                    "content": m.content,
                    "citations": m.citations,
                }
                for m in session.messages
            ]

    def add_turn(
        self,
        session_id: str,
        user_query: str,
        assistant_answer: str,
        citations: list[str] | None = None,
    ) -> list[ChatMessage]:
        """Record a completed user question and assistant answer turn."""
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                session = ConversationSession(session_id)
                self._sessions[session_id] = session

            session.add_user_message(user_query)
            session.add_assistant_message(assistant_answer, citations)
            session.trim(self.max_turns)
            return list(session.messages)

    def set_history(self, session_id: str, messages: list[ChatMessage]) -> None:
        """Explicitly set or overwrite the history of a session."""
        with self._lock:
            session = ConversationSession(session_id)
            session.messages = list(messages)
            session.trim(self.max_turns)
            self._sessions[session_id] = session

    def clear_session(self, session_id: str) -> bool:
        """Clear and remove a conversation session."""
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                return True
            return False

    def get_session_citations(self, session_id: str) -> set[str]:
        """Collect all citations previously recorded in the session."""
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return set()
            return session.get_citations()

    def build_contextual_query(self, session_id: str, current_query: str) -> str:
        """Enrich a follow-up query with conversational context for vector retrieval.

        If the current query has pronouns or contextual references like 'that exception',
        'those offices', 'does it apply', enrich the query with prior topics and citations.
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if not session or not session.messages:
                return current_query

            recent_queries = session.get_recent_user_queries(count=2)
            citations = session.get_citations()

        # Check if the query is anaphoric or brief (needs context)
        is_contextual = bool(
            re.search(
                r"\b(that|this|those|these|it|they|them|the same|such|above|exception|restriction|office|apply|applicable)\b",
                current_query,
                re.IGNORECASE,
            )
            or len(current_query.split()) < 6
        )

        if not is_contextual and not citations:
            return current_query

        # Combine prior query keywords and known citations with current query
        context_parts = []
        if recent_queries:
            # Clean last user query
            last_q = recent_queries[-1]
            context_parts.append(last_q)

        if citations:
            context_parts.append(" ".join(citations))

        if context_parts:
            return f"{current_query} (Context: {' '.join(context_parts)})"

        return current_query

    def cleanup_expired(self) -> int:
        """Remove sessions that have been inactive longer than ttl_seconds."""
        now = time.time()
        removed = 0
        with self._lock:
            expired_keys = [
                sid
                for sid, s in self._sessions.items()
                if now - s.updated_at > self.ttl_seconds
            ]
            for sid in expired_keys:
                del self._sessions[sid]
                removed += 1
        return removed


# Global default instance
_default_memory: ConversationMemory | None = None
_memory_lock = Lock()


def get_conversation_memory() -> ConversationMemory:
    """Retrieve the singleton ConversationMemory instance."""
    global _default_memory
    if _default_memory is None:
        with _memory_lock:
            if _default_memory is None:
                _default_memory = ConversationMemory()
    return _default_memory

