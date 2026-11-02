from __future__ import annotations

from typing import Protocol

from src.schemas import LegalChunkMetadata, VectorSearchResult


class VectorStore(Protocol):
    payloads: list[LegalChunkMetadata]

    def query(self, vector: list[float], limit: int) -> list[VectorSearchResult]:
        ...
