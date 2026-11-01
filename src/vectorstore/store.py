import json
from pathlib import Path
from typing import Any

import numpy as np

from src.schemas import LegalChunkMetadata, VectorSearchResult


class LocalVectorStore:
    """Small local vector store that does not require Qdrant's gRPC DLL."""

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.mkdir(parents=True, exist_ok=True)
        self.vectors: np.ndarray = np.empty((0, 0), dtype=np.float32)
        self.payloads: list[LegalChunkMetadata] = []
        self._load()

    def _load(self) -> None:
        vectors_path = self.db_path / "vectors.npy"
        payloads_path = self.db_path / "payloads.json"
        manifest_path = self.db_path / "manifest.json"
        if vectors_path.exists() != payloads_path.exists():
            raise ValueError(
                f"Vector store at '{self.db_path}' is incomplete; "
                "vectors.npy and payloads.json must be present together."
            )
        if not vectors_path.exists():
            return

        self.vectors = np.load(vectors_path, allow_pickle=False)
        raw_payloads = json.loads(payloads_path.read_text(encoding="utf-8"))
        if not isinstance(raw_payloads, list):
            raise ValueError("Vector-store payloads must be a JSON list.")
        self.payloads = [
            LegalChunkMetadata.model_validate(payload) for payload in raw_payloads
        ]
        self._validate_integrity()
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self._validate_manifest(manifest)

    def _validate_integrity(self) -> None:
        if self.vectors.ndim != 2:
            raise ValueError(
                f"Vector store vectors must be two-dimensional; got {self.vectors.ndim}."
            )
        if len(self.payloads) != self.vectors.shape[0]:
            raise ValueError(
                "Vector store is inconsistent: the number of vectors does not "
                "match the number of payloads."
            )
        if self.vectors.shape[0] and self.vectors.shape[1] < 1:
            raise ValueError("Vector store vectors must have at least one dimension.")
        if not np.isfinite(self.vectors).all():
            raise ValueError("Vector store contains non-finite vector values.")

    def _validate_manifest(self, manifest: Any) -> None:
        if not isinstance(manifest, dict):
            raise ValueError("Vector-store manifest must be a JSON object.")
        required_fields = {
            "schema_version",
            "embedding_model",
            "embedding_dimension",
            "chunk_count",
        }
        missing_fields = required_fields - manifest.keys()
        if missing_fields:
            raise ValueError(
                "Vector-store manifest is missing fields: "
                + ", ".join(sorted(missing_fields))
            )
        if manifest["schema_version"] != 1:
            raise ValueError("Unsupported vector-store manifest schema version.")
        if manifest["embedding_dimension"] != self.vectors.shape[1]:
            raise ValueError("Manifest embedding dimension does not match vectors.")
        if manifest["chunk_count"] != len(self.payloads):
            raise ValueError("Manifest chunk count does not match payloads.")

    def reset(self) -> None:
        self.vectors = np.empty((0, 0), dtype=np.float32)
        self.payloads = []
        manifest_path = self.db_path / "manifest.json"
        if manifest_path.exists():
            manifest_path.unlink()

    def write_manifest(
        self,
        *,
        embedding_model: str,
        source_sha256: str | None = None,
    ) -> None:
        """Persist metadata describing the current index build."""
        self._validate_integrity()
        manifest = {
            "schema_version": 1,
            "embedding_model": embedding_model,
            "embedding_dimension": int(self.vectors.shape[1])
            if self.vectors.ndim == 2 and self.vectors.shape[0]
            else 0,
            "chunk_count": len(self.payloads),
        }
        if source_sha256:
            manifest["source_sha256"] = source_sha256
        (self.db_path / "manifest.json").write_text(
            json.dumps(manifest, indent=2),
            encoding="utf-8",
        )

    def add(
        self,
        vectors: list[list[float]],
        payloads: list[dict[str, Any] | LegalChunkMetadata],
    ) -> None:
        validated_payloads = [
            payload
            if isinstance(payload, LegalChunkMetadata)
            else LegalChunkMetadata.model_validate(payload)
            for payload in payloads
        ]
        new_vectors = np.asarray(vectors, dtype=np.float32)
        if new_vectors.ndim != 2:
            raise ValueError("Vectors must be a two-dimensional array.")
        if len(validated_payloads) != new_vectors.shape[0]:
            raise ValueError("Each vector must have a matching payload.")
        if new_vectors.shape[0] and new_vectors.shape[1] < 1:
            raise ValueError("Vectors must have at least one dimension.")
        if not np.isfinite(new_vectors).all():
            raise ValueError("Vectors must contain only finite values.")
        if self.vectors.size and self.vectors.shape[1] != new_vectors.shape[1]:
            raise ValueError("New vectors must match the existing vector dimension.")
        self.vectors = (
            new_vectors
            if self.vectors.size == 0
            else np.vstack((self.vectors, new_vectors))
        )
        self.payloads.extend(validated_payloads)
        self._validate_integrity()
        np.save(self.db_path / "vectors.npy", self.vectors)
        (self.db_path / "payloads.json").write_text(
            json.dumps(
                [payload.model_dump(mode="json") for payload in self.payloads],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def query(self, vector: list[float], limit: int) -> list[VectorSearchResult]:
        if limit < 1:
            raise ValueError("limit must be at least 1")
        if not self.payloads:
            return []
        query_vector = np.asarray(vector, dtype=np.float32)
        if query_vector.ndim != 1:
            raise ValueError("Query vector must be one-dimensional.")
        if query_vector.shape[0] != self.vectors.shape[1]:
            raise ValueError(
                "Query vector dimension does not match the indexed vectors."
            )
        if not np.isfinite(query_vector).all():
            raise ValueError("Query vector must contain only finite values.")
        scores = self.vectors @ query_vector
        indices = np.argsort(scores)[::-1][:limit]
        return [
            VectorSearchResult(
                score=float(scores[index]),
                metadata=self.payloads[index].model_dump(mode="python"),
            )
            for index in indices
        ]


def init_vector_store(db_path: str = "./data/qdrant_db") -> LocalVectorStore:
    """Initialize the local store used by the RAG pipeline."""
    store = LocalVectorStore(db_path)
    store.reset()
    return store
