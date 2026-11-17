import unittest
from unittest.mock import MagicMock, patch

from langchain_core.documents import Document
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.api.memory import (
    ChatMessage,
    ConversationMemory,
    ConversationSession,
    from_langchain_messages,
    to_langchain_messages,
    trim_conversation_messages,
)
from src.rag.history_aware import (
    RETRIEVER_SYSTEM_PROMPT,
    HistoryAwareRetriever,
    create_history_aware_retriever,
    get_history_aware_prompt,
    reformulate_question_history_aware,
    retrieve_relevant_context_history_aware,
)


class TestHistoryAwareRetriever(unittest.TestCase):
    """Test suite for section memory and history-aware retrieval."""

    def test_retriever_system_prompt_content(self) -> None:
        """Verify the retriever system prompt matches the exact required formulation."""
        self.assertIn("Given a chat history", RETRIEVER_SYSTEM_PROMPT)
        self.assertIn("formulate a standalone question", RETRIEVER_SYSTEM_PROMPT)
        self.assertIn("Do NOT answer the question", RETRIEVER_SYSTEM_PROMPT)
        self.assertIn("just reformulate it if needed and otherwise return it as is", RETRIEVER_SYSTEM_PROMPT)

    def test_trim_messages_max_tokens_and_strategy(self) -> None:
        """Verify trim_conversation_messages trims with strategy='last' and max_tokens=50."""
        # Create a series of messages that exceeds 50 tokens
        messages = [
            HumanMessage(content="What is the Supreme Court of Ghana? " * 5),
            AIMessage(content="The Supreme Court is the highest judicial body in Ghana. " * 5),
            HumanMessage(content="Can a citizen hold dual citizenship?"),
            AIMessage(content="Yes, Article 8(1) permits dual citizenship."),
        ]

        trimmed = trim_conversation_messages(messages, max_tokens=50, strategy="last")

        self.assertIsInstance(trimmed, list)
        self.assertGreater(len(trimmed), 0)
        self.assertLessEqual(len(trimmed), len(messages))
        # The last messages must be preserved due to strategy="last"
        self.assertEqual(trimmed[-1].content, "Yes, Article 8(1) permits dual citizenship.")

    def test_conversation_session_token_trimming(self) -> None:
        """Verify ConversationSession trim_by_tokens trims to max_tokens=50."""
        session = ConversationSession(session_id="test-session")
        session.add_user_message("What is Article 1? " * 8)
        session.add_assistant_message("Article 1 states the sovereignty of Ghana. " * 8)
        session.add_user_message("Does it apply to foreign treaties?")

        self.assertEqual(len(session.messages), 3)
        session.trim_by_tokens(max_tokens=50, strategy="last")

        # After token trimming, older long messages are pruned, preserving recent turns
        self.assertLess(len(session.messages), 3)
        self.assertEqual(session.messages[-1].content, "Does it apply to foreign treaties?")

    def test_reformulate_empty_history_returns_raw_query(self) -> None:
        """When history is empty, reformulate_question_history_aware returns the raw query."""
        raw_query = "What is Article 1 of the Constitution?"
        reformulated = reformulate_question_history_aware(query=raw_query, history=[])
        self.assertEqual(reformulated, raw_query)

    def test_reformulate_with_mock_llm_reformulation(self) -> None:
        """Verify LLM receives system prompt and trimmed history, returning reformulated question."""
        history = [
            ChatMessage(role="user", content="Can a Ghanaian citizen hold dual citizenship?"),
            ChatMessage(
                role="assistant",
                content="Yes. Under Article 8(1) a citizen may hold dual citizenship, but Article 8(2) specifies exceptions.",
                citations=["Article 8(1)", "Article 8(2)"],
            ),
        ]
        user_follow_up = "Does that exception apply to non-citizens?"

        mock_client = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = (
            "Does the dual citizenship public office exception in Article 8(2) apply to non-citizens?"
        )
        mock_response = MagicMock(choices=[mock_choice])
        mock_client.chat.completions.create.return_value = mock_response

        reformulated = reformulate_question_history_aware(
            query=user_follow_up,
            history=history,
            max_tokens=50,
            strategy="last",
            client=mock_client,
        )

        self.assertEqual(
            reformulated,
            "Does the dual citizenship public office exception in Article 8(2) apply to non-citizens?",
        )
        # Verify the prompt passed to the LLM has the retriever system prompt
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        messages_sent = call_kwargs["messages"]
        self.assertEqual(messages_sent[0]["role"], "system")
        self.assertEqual(messages_sent[0]["content"], RETRIEVER_SYSTEM_PROMPT)

    def test_retrieve_relevant_context_history_aware(self) -> None:
        """Verify retrieve_relevant_context_history_aware retrieves contexts using reformulated query."""
        fake_store = MagicMock()
        mock_context = {
            "text": "Article 8(2) bars dual citizens from certain public offices.",
            "article_number": "8",
            "chapter_number": "3",
            "score": 0.95,
            "metadata": {
                "chapter_number": "3",
                "chapter_title": "Citizenship",
                "article_number": "8",
                "article_title": "Citizenship",
                "page": 1,
                "source": "pdf",
            },
        }

        mock_client = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = (
            "Does the dual citizenship exception in Article 8(2) apply to non-citizens?"
        )
        mock_client.chat.completions.create.return_value = MagicMock(choices=[mock_choice])

        history = [
            ChatMessage(role="user", content="Can a Ghanaian citizen hold dual citizenship?"),
            ChatMessage(role="assistant", content="Yes, Article 8(1) allows it with Article 8(2) exceptions."),
        ]

        with patch("src.rag.history_aware.retrieve_relevant_context", return_value=[mock_context]):
            contexts, effective_query = retrieve_relevant_context_history_aware(
                query="Does that exception apply to non-citizens?",
                vector_store=fake_store,
                history=history,
                client=mock_client,
            )

        self.assertEqual(len(contexts), 1)
        self.assertEqual(
            effective_query,
            "Does the dual citizenship exception in Article 8(2) apply to non-citizens?",
        )

    def test_create_history_aware_retriever_chain(self) -> None:
        """Verify create_history_aware_retriever produces a Runnable chain."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(
            content="Standalone question regarding judicial power in Article 125."
        )

        mock_retriever = MagicMock()
        mock_retriever.invoke.return_value = [
            Document(page_content="Article 125: Judicial power", metadata={"article": "125"})
        ]

        chain = create_history_aware_retriever(
            llm=mock_llm,
            retriever=mock_retriever,
            max_tokens=50,
            strategy="last",
        )

        history = [
            HumanMessage(content="Who exercises judicial power?"),
            AIMessage(content="Judicial power resides in the Judiciary under Article 125."),
        ]

        docs = chain.invoke({
            "input": "Can Parliament interfere with it?",
            "chat_history": history,
        })

        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0].metadata["article"], "125")
        mock_retriever.invoke.assert_called_with(
            "Standalone question regarding judicial power in Article 125."
        )


if __name__ == "__main__":
    unittest.main()

