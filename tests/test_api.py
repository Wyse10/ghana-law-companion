import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from pydantic import SecretStr

from src.api.config import Settings
from src.api.main import app
from src.api.schemas import QueryAPIResponse


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
        self.client = TestClient(app)

    def test_liveness(self) -> None:
        response = self.client.get("/health/live")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_readiness_reports_available_index(self) -> None:
        response = self.client.get("/health/ready")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

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
