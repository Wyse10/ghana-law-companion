import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from pydantic import SecretStr
from redis.exceptions import RedisError

from src.api.config import Settings
from src.api.main import app
from src.api.schemas import QueryAPIResponse
from src.api.rate_limit import RateLimitMiddleware


class FakeRAGService:
    def answer(self, request):
        return QueryAPIResponse.model_validate(
            {
                "request_id": "test-request",
                "answer": {
                    "answer": f"Grounded answer for: {request.query}",
                    "citations": ["Article 14"],
                },
                "sources": [
                    {
                        "text": "Personal liberty text.",
                        "chapter_number": "5",
                        "article_number": "14",
                        "score": 0.91,
                    }
                ],
                "timing": {
                    "retrieval_ms": 1.0,
                    "generation_ms": 2.0,
                    "total_ms": 3.0,
                },
            }
        )


class FastAPITests(unittest.TestCase):
    def setUp(self) -> None:
        self.auth_settings_patcher = patch(
            "src.api.auth.get_settings",
            return_value=Settings(require_api_key=False, api_key=None),
        )
        self.auth_settings_patcher.start()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.auth_settings_patcher.stop()

    def test_liveness(self) -> None:
        response = self.client.get("/health/live")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertRegex(response.headers["X-Request-ID"], r"^[0-9a-f-]{36}$")

    def test_security_headers_are_present(self) -> None:
        response = self.client.get("/health/live")

        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response.headers["X-Frame-Options"], "DENY")
        self.assertEqual(response.headers["Referrer-Policy"], "no-referrer")
        self.assertEqual(
            response.headers["Permissions-Policy"],
            "geolocation=(), microphone=(), camera=()",
        )
        self.assertNotIn("Strict-Transport-Security", response.headers)

    def test_metrics_endpoint_returns_prometheus_text(self) -> None:
        response = self.client.get("/metrics")

        self.assertEqual(response.status_code, 200)
        self.assertIn("ghana_law_http_requests_total", response.text)

    def test_api_documentation_is_available_in_development(self) -> None:
        response = self.client.get("/docs")

        self.assertEqual(response.status_code, 200)

    def test_readiness_reports_available_index(self) -> None:
        response = self.client.get("/health/ready")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_readiness_reports_postgres_failure(self) -> None:
        with patch(
            "src.api.main.get_settings",
            return_value=Settings(
                vector_store_backend="postgres",
                source_sha256="a" * 64,
                database_url="postgresql+psycopg://invalid",
            ),
        ):
            response = self.client.get("/health/ready")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"], "PostgreSQL is unavailable.")

    def test_readiness_reports_redis_failure(self) -> None:
        with (
            patch(
                "src.api.main.get_settings",
                return_value=Settings(
                    rate_limit_enabled=True,
                    redis_url="redis://127.0.0.1:1/0",
                ),
            ),
            patch("src.api.main.Redis.ping", side_effect=RedisError("unavailable")),
        ):
            response = self.client.get("/health/ready")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"], "Redis is unavailable.")

    def test_browser_origins_are_not_allowed_by_default(self) -> None:
        response = self.client.options(
            "/api/v1/query",
            headers={
                "Origin": "https://untrusted.example",
                "Access-Control-Request-Method": "POST",
            },
        )

        self.assertNotIn("access-control-allow-origin", response.headers)

    def test_query_returns_validated_answer(self) -> None:
        with patch("src.api.main._get_rag_service", return_value=FakeRAGService()):
            response = self.client.post(
                "/api/v1/query",
                json={"query": "What protects personal liberty?", "top_k": 5},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["answer"]["citations"], ["Article 14"])
        self.assertEqual(payload["sources"][0]["article_number"], "14")
        self.assertEqual(payload["request_id"], "test-request")

    def test_multi_turn_conversation_flow(self) -> None:
        from unittest.mock import MagicMock
        from src.api.memory import ConversationMemory
        from src.api.services import RAGService
        from src.schemas import LegalAnswer

        memory = ConversationMemory()
        fake_store = MagicMock()
        fake_store.query.return_value = []
        fake_store.payloads = []

        service = RAGService(vector_store=fake_store, memory=memory)

        with (
            patch("src.api.services.retrieve_relevant_context", return_value=[
                {"text": "Article 8 text", "article_number": "8", "chapter_number": "3", "score": 0.9}
            ]),
            patch("src.api.services.generate_legal_answer_structured") as mock_gen,
            patch("src.api.main._get_rag_service", return_value=service),
        ):
            mock_gen.return_value = LegalAnswer(
                answer="Under Article 8(1), dual citizenship is permitted.",
                citations=["Article 8(1)"],
            )

            # Turn 1: Initial query
            res1 = self.client.post(
                "/api/v1/query",
                json={"query": "Can a Ghanaian citizen hold dual citizenship?"},
            )
            self.assertEqual(res1.status_code, 200)
            data1 = res1.json()
            session_id = data1["session_id"]
            self.assertTrue(bool(session_id))
            self.assertEqual(len(data1["history"]), 2)

            # Turn 2: Follow-up query using session_id
            mock_gen.return_value = LegalAnswer(
                answer="Under Article 8(2), the restriction applies to citizens holding another citizenship.",
                citations=["Article 8(2)"],
            )
            res2 = self.client.post(
                "/api/v1/query",
                json={
                    "query": "Does that exception apply to non-citizens?",
                    "session_id": session_id,
                },
            )
            self.assertEqual(res2.status_code, 200)
            data2 = res2.json()
            self.assertEqual(data2["session_id"], session_id)
            self.assertEqual(len(data2["history"]), 4)
            self.assertEqual(
                data2["history"][2]["content"],
                "Does that exception apply to non-citizens?",
            )

            # Test GET conversation history endpoint
            history_res = self.client.get(f"/api/v1/conversations/{session_id}")
            self.assertEqual(history_res.status_code, 200)
            self.assertEqual(len(history_res.json()["messages"]), 4)

            # Test DELETE conversation endpoint
            del_res = self.client.delete(f"/api/v1/conversations/{session_id}")
            self.assertEqual(del_res.status_code, 200)
            self.assertEqual(del_res.json()["cleared"], "true")

            # Verify history is now empty
            history_res2 = self.client.get(f"/api/v1/conversations/{session_id}")
            self.assertEqual(history_res2.status_code, 200)
            self.assertEqual(len(history_res2.json()["messages"]), 0)

    def test_health_endpoints_remain_public_when_authentication_enabled(self) -> None:
        with patch(
            "src.api.auth.get_settings",
            return_value=Settings(
                require_api_key=True,
                api_key=SecretStr("test-key"),
            ),
        ):
            response = self.client.get("/health/live")

        self.assertEqual(response.status_code, 200)

    def test_query_rejects_missing_api_key(self) -> None:
        with patch(
            "src.api.auth.get_settings",
            return_value=Settings(
                require_api_key=True,
                api_key=SecretStr("test-key"),
            ),
        ):
            response = self.client.post(
                "/api/v1/query",
                json={"query": "What protects personal liberty?"},
            )

        self.assertEqual(response.status_code, 401)

    def test_query_rejects_invalid_api_key(self) -> None:
        with patch(
            "src.api.auth.get_settings",
            return_value=Settings(
                require_api_key=True,
                api_key=SecretStr("test-key"),
            ),
        ):
            response = self.client.post(
                "/api/v1/query",
                headers={"X-API-Key": "wrong-key"},
                json={"query": "What protects personal liberty?"},
            )

        self.assertEqual(response.status_code, 401)

    def test_query_accepts_valid_api_key(self) -> None:
        with (
            patch(
                "src.api.auth.get_settings",
                return_value=Settings(
                    require_api_key=True,
                    api_key=SecretStr("test-key"),
                ),
            ),
            patch("src.api.main._get_rag_service", return_value=FakeRAGService()),
        ):
            response = self.client.post(
                "/api/v1/query",
                headers={"X-API-Key": "test-key"},
                json={"query": "What protects personal liberty?"},
            )

        self.assertEqual(response.status_code, 200)

    def test_query_accepts_any_rotating_api_key(self) -> None:
        with (
            patch(
                "src.api.auth.get_settings",
                return_value=Settings(
                    require_api_key=True,
                    api_keys="old-key, next-key",
                ),
            ),
            patch("src.api.main._get_rag_service", return_value=FakeRAGService()),
        ):
            response = self.client.post(
                "/api/v1/query",
                headers={"X-API-Key": "next-key"},
                json={"query": "What protects personal liberty?"},
            )

        self.assertEqual(response.status_code, 200)

    def test_query_rejects_empty_query(self) -> None:
        response = self.client.post("/api/v1/query", json={"query": "   "})

        self.assertEqual(response.status_code, 422)
        self.assertIn("query must not be empty", response.text)

    def test_query_rejects_invalid_top_k(self) -> None:
        response = self.client.post(
            "/api/v1/query",
            json={"query": "What protects personal liberty?", "top_k": 11},
        )

        self.assertEqual(response.status_code, 422)

    def test_query_reports_missing_vector_store(self) -> None:
        from fastapi import HTTPException

        with patch(
            "src.api.main._get_rag_service",
            side_effect=HTTPException(status_code=503, detail="index unavailable"),
        ):
            response = self.client.post(
                "/api/v1/query",
                json={"query": "What protects personal liberty?"},
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"], "index unavailable")

    def test_query_reports_provider_failure(self) -> None:
        with patch(
            "src.api.main._get_rag_service",
            side_effect=RuntimeError("provider unavailable"),
        ):
            response = self.client.post(
                "/api/v1/query",
                json={"query": "What protects personal liberty?"},
            )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["detail"], "provider unavailable")


class FakeRedis:
    def __init__(self, count: int) -> None:
        self.count = count

    async def incr(self, key: str) -> int:
        return self.count

    async def expire(self, key: str, seconds: int) -> bool:
        return True


class RateLimitTests(unittest.IsolatedAsyncioTestCase):
    async def test_health_endpoint_is_exempt(self) -> None:
        middleware = RateLimitMiddleware(
            app,
            redis=FakeRedis(99),
            limit=1,
        )
        request = unittest.mock.Mock()
        request.url.path = "/health/live"
        request.client.host = "127.0.0.1"
        async def next_handler(_):
            return None

        response = await middleware.dispatch(request, next_handler)

        self.assertIsNone(response)

    async def test_limit_returns_429(self) -> None:
        middleware = RateLimitMiddleware(
            app,
            redis=FakeRedis(2),
            limit=1,
        )
        request = unittest.mock.Mock()
        request.url.path = "/api/v1/query"
        request.client.host = "127.0.0.1"
        async def next_handler(_):
            return None

        response = await middleware.dispatch(request, next_handler)

        self.assertEqual(response.status_code, 429)


class ConversationMemoryTests(unittest.TestCase):
    def test_memory_session_lifecycle(self) -> None:
        from src.api.memory import ConversationMemory

        memory = ConversationMemory(max_turns=3)
        session_id = memory.get_or_create_session()
        self.assertTrue(bool(session_id))

        # Add 4 turns (should trim to max_turns=3, i.e. 6 messages)
        for i in range(1, 5):
            memory.add_turn(
                session_id=session_id,
                user_query=f"Question {i}",
                assistant_answer=f"Answer {i}",
                citations=[f"Article {i}"],
            )

        history = memory.get_history(session_id)
        self.assertEqual(len(history), 6)  # 3 turns * 2 messages
        self.assertEqual(history[0].content, "Question 2")
        self.assertEqual(history[-1].content, "Answer 4")

        # Test contextual query builder
        enriched = memory.build_contextual_query(session_id, "Does that exception apply?")
        self.assertIn("Question 4", enriched)
        self.assertIn("Article 4", enriched)

        # Test clearing
        cleared = memory.clear_session(session_id)
        self.assertTrue(cleared)
        self.assertEqual(len(memory.get_history(session_id)), 0)

    def test_multi_turn_prompt_includes_history(self) -> None:
        from src.rag.generator import build_rag_prompt

        history = [
            {"role": "user", "content": "Can dual citizens hold public office?"},
            {
                "role": "assistant",
                "content": "Article 8(2) restricts them from certain offices.",
                "citations": ["Article 8(2)"],
            },
        ]
        context = [{
            "text": "Article 8(2) text...",
            "article_number": "8",
            "chapter_number": "3",
            "score": 0.9,
            "metadata": {
                "chapter_number": "3",
                "chapter_title": "Citizenship",
                "article_number": "8",
                "article_title": "Citizenship",
                "page": 1,
                "source": "pdf",
            },
        }]

        prompt = build_rag_prompt(
            query="Does that exception apply to non-citizens?",
            contexts=context,
            history=history,
        )
        self.assertIn("Conversation History:", prompt)
        self.assertIn("Can dual citizens hold public office?", prompt)
        self.assertIn("Does that exception apply to non-citizens?", prompt)
        self.assertIn("use the conversation history to resolve the reference accurately", prompt)
