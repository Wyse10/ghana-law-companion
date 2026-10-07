import json
from pathlib import Path
from typing import Any

import numpy as np


class LocalVectorStore:
    """Small local vector store that does not require Qdrant's gRPC DLL."""

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.mkdir(parents=True, exist_ok=True)
        self.vectors: np.ndarray = np.empty((0, 0), dtype=np.float32)
        self.payloads: list[dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        vectors_path = self.db_path / "vectors.npy"
        payloads_path = self.db_path / "payloads.json"
        if vectors_path.exists() and payloads_path.exists():
            self.vectors = np.load(vectors_path)
            self.payloads = json.loads(
                payloads_path.read_text(encoding="utf-8")
            )

    def reset(self) -> None:
        self.vectors = np.empty((0, 0), dtype=np.float32)
        self.payloads = []

    def add(self, vectors: list[list[float]], payloads: list[dict[str, Any]]) -> None:
        new_vectors = np.asarray(vectors, dtype=np.float32)
        self.vectors = (
            new_vectors
            if self.vectors.size == 0
            else np.vstack((self.vectors, new_vectors))
        )
        self.payloads.extend(payloads)
        np.save(self.db_path / "vectors.npy", self.vectors)
        (self.db_path / "payloads.json").write_text(
            json.dumps(self.payloads, ensure_ascii=False),
            encoding="utf-8",
        )

    def query(self, vector: list[float], limit: int) -> list[dict[str, Any]]:
        if not self.payloads:
            return []
        query_vector = np.asarray(vector, dtype=np.float32)
        scores = self.vectors @ query_vector
        indices = np.argsort(scores)[::-1][:limit]
        return [
            {
                "score": float(scores[index]),
                "metadata": self.payloads[index],
            }
            for index in indices
        ]


def init_vector_store(db_path: str = "./data/qdrant_db") -> LocalVectorStore:
    """Initialize the local store used by the RAG pipeline."""
    store = LocalVectorStore(db_path)
    store.reset()
    return store
