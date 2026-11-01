import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from src.eval.eval import calculate_mrr, calculate_ndcg
from src.ingestion.legal_chunker import validate_constitution_chunks
from src.rag.generator import (
    build_rag_prompt,
    parse_generated_answer,
    trim_contexts_to_budget,
    validate_answer_citations,
)
from src.schemas import LegalAnswer, LegalChunk, TestQuestion
from src.vectorstore.store import LocalVectorStore


def make_chunk(article: str = "1", text: str = "Valid constitutional text") -> LegalChunk:
    return LegalChunk.model_validate(
        {
            "text": text,
            "metadata": {
                "chapter_number": "1",
                "chapter_title": "The Constitution",
                "article_number": article,
                "article_title": "Test article",
                "page": 1,
                "cross_references": [],
                "source": "test.pdf",
            },
        }
    )


class IngestionValidationTests(unittest.TestCase):
    def test_accepts_valid_chunks(self) -> None:
        chunks = validate_constitution_chunks([make_chunk()])
        self.assertEqual(len(chunks), 1)

    def test_rejects_duplicate_articles(self) -> None:
        with self.assertRaisesRegex(ValueError, "duplicate article metadata"):
            validate_constitution_chunks([make_chunk(), make_chunk()])

    def test_rejects_extraction_artifacts(self) -> None:
        with self.assertRaisesRegex(ValueError, "replacement characters"):
            validate_constitution_chunks([make_chunk(text="Bad\ufffdtext")])


class VectorStoreIntegrityTests(unittest.TestCase):
    def test_rejects_mismatched_vector_and_payload_counts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            np.save(path / "vectors.npy", np.zeros((2, 3), dtype=np.float32))
            (path / "payloads.json").write_text(
                json.dumps([make_chunk().metadata.model_dump(mode="json")]),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "number of vectors"):
                LocalVectorStore(directory)

    def test_rejects_query_dimension_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = LocalVectorStore(directory)
            store.add([[1.0, 0.0]], [make_chunk().metadata])
            with self.assertRaisesRegex(ValueError, "dimension"):
                store.query([1.0], 1)

    def test_persists_and_queries_valid_vectors(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = LocalVectorStore(directory)
            store.add(
                [[1.0, 0.0], [0.0, 1.0]],
                [make_chunk("1").metadata, make_chunk("2").metadata],
            )
            reloaded = LocalVectorStore(directory)
            results = reloaded.query([1.0, 0.0], 1)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].metadata.article_number, "1")

    def test_validates_manifest_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = LocalVectorStore(directory)
            store.add([[1.0, 0.0]], [make_chunk().metadata])
            store.write_manifest(embedding_model="test-model")

            manifest_path = Path(directory) / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["chunk_count"] = 99
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "chunk count"):
                LocalVectorStore(directory)


class GroundingTests(unittest.TestCase):
    def test_builds_personal_liberty_prompt_with_json_example(self) -> None:
        context = {
            "text": "Personal liberty may be restricted under Article 14.",
            "chapter_number": "5",
            "article_number": "14",
            "score": 1.0,
            "metadata": make_chunk("14").metadata.model_copy(
                update={"chapter_number": "5"}
            ).model_dump(mode="json"),
        }

        prompt = build_rag_prompt(
            "What are the personal liberty rights?",
            [context],
        )

        self.assertIn(
            '{"answer": "grounded answer text", "citations": ["Article 20(1)", "Chapter 5"]}',
            prompt,
        )

    def test_parses_json_generation(self) -> None:
        answer = parse_generated_answer(
            '{"answer": "Grounded answer.", "citations": ["Article 20(1)"]}'
        )
        self.assertEqual(answer.answer, "Grounded answer.")
        self.assertEqual(answer.citations, ["Article 20(1)"])

    def test_parses_fenced_json_generation(self) -> None:
        answer = parse_generated_answer(
            '```json\n{"answer": "Grounded answer.", "citations": ["Article 20"]}\n```'
        )
        self.assertEqual(answer.citations, ["Article 20"])

    def test_rejects_non_json_generation(self) -> None:
        with self.assertRaisesRegex(ValueError, "invalid JSON"):
            parse_generated_answer("依据")

    def test_context_budget_keeps_retrieved_context_bounded(self) -> None:
        context = {
            "text": "a" * 100,
            "chapter_number": "1",
            "article_number": "1",
            "score": 1.0,
            "metadata": make_chunk().metadata.model_dump(mode="json"),
        }
        trimmed = trim_contexts_to_budget([context], max_chars=20)
        self.assertEqual(len(trimmed), 1)
        self.assertIn("[context truncated]", trimmed[0]["text"])
        self.assertLessEqual(len(trimmed[0]["text"]), 40)

    def test_rejects_citation_outside_retrieved_context(self) -> None:
        answer = LegalAnswer(answer="Answer", citations=["Article 99"])
        context = {
            "text": "Source",
            "chapter_number": "1",
            "article_number": "1",
            "score": 1.0,
            "metadata": make_chunk().metadata.model_dump(mode="json"),
        }
        with self.assertRaisesRegex(ValueError, "unsupported citations"):
            validate_answer_citations(answer, [context])

    def test_accepts_citation_from_retrieved_context(self) -> None:
        answer = LegalAnswer(answer="Answer", citations=["Article 1"])
        context = {
            "text": "Source",
            "chapter_number": "1",
            "article_number": "1",
            "score": 1.0,
            "metadata": make_chunk().metadata.model_dump(mode="json"),
        }
        validated = validate_answer_citations(answer, [context])
        self.assertEqual(validated.citations, ["Article 1"])

    def test_accepts_abbreviated_clause_citations(self) -> None:
        answer = LegalAnswer(
            answer="Property may be compulsorily acquired subject to constitutional conditions.",
            citations=[f"Art. 20({clause})" for clause in range(1, 7)],
        )
        property_chunk = make_chunk("20").metadata.model_copy(
            update={"chapter_number": "5"}
        )
        context = {
            "text": "Compulsory acquisition of property",
            "chapter_number": "5",
            "article_number": "20",
            "score": 1.0,
            "metadata": property_chunk.model_dump(mode="json"),
        }

        validated = validate_answer_citations(answer, [context])

        self.assertEqual(len(validated.citations), 6)

    def test_accepts_chapter_citation(self) -> None:
        answer = LegalAnswer(answer="Answer", citations=["Chapter 5"])
        context = {
            "text": "Source",
            "chapter_number": "5",
            "article_number": "20",
            "score": 1.0,
            "metadata": make_chunk("20").metadata.model_copy(
                update={"chapter_number": "5"}
            ).model_dump(mode="json"),
        }

        validated = validate_answer_citations(answer, [context])

        self.assertEqual(validated.citations, ["Chapter 5"])


class EvaluationMetricTests(unittest.TestCase):
    def test_retrieval_metrics_use_article_and_chapter_metadata(self) -> None:
        test = TestQuestion(
            id="property",
            query="property",
            expected_chapter="5",
            expected_articles=["20"],
            ground_truth_answer="answer",
            category="rights",
        )
        matching_context = {
            "text": "This text does not contain the article label.",
            "chapter_number": "5",
            "article_number": "20",
            "score": 1.0,
            "metadata": make_chunk("20").metadata.model_copy(
                update={"chapter_number": "5"}
            ).model_dump(mode="json"),
        }
        wrong_chapter_context = {
            "text": "Article 20 appears in this text.",
            "chapter_number": "26",
            "article_number": "20",
            "score": 0.9,
            "metadata": make_chunk("20").metadata.model_dump(mode="json"),
        }

        documents = [wrong_chapter_context, matching_context]

        self.assertEqual(calculate_mrr(test, "20", documents), 0.5)
        self.assertAlmostEqual(
            calculate_ndcg(test, "20", documents),
            1 / 1.584962500721156,
        )


if __name__ == "__main__":
    unittest.main()
