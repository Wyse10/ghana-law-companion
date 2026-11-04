from __future__ import annotations

from src.schemas import LegalChunkMetadata, VectorSearchResult


class PostgresVectorStore:
    """PostgreSQL/pgvector implementation of the vector-store protocol."""

    def __init__(
        self,
        database_url: str,
        source_sha256: str,
        min_size: int = 1,
        max_size: int = 10,
    ) -> None:
        from psycopg.rows import dict_row
        from psycopg_pool import ConnectionPool

        self._database_url = database_url.replace(
            "postgresql+psycopg://", "postgresql://"
        )
        self._source_sha256 = source_sha256
        self._pool = ConnectionPool(
            conninfo=self._database_url,
            kwargs={"row_factory": dict_row},
            min_size=min_size,
            max_size=max_size,
        )
        self.payloads = self._load_payloads()

    def _document_id(self) -> int:
        with self._pool.connection() as connection:
            row = connection.execute(
                "SELECT id FROM documents WHERE source_sha256 = %s",
                (self._source_sha256,),
            ).fetchone()
        if row is None:
            raise ValueError("No PostgreSQL document matches the configured source.")
        return int(row["id"])

    def _load_payloads(self) -> list[LegalChunkMetadata]:
        document_id = self._document_id()
        with self._pool.connection() as connection:
            rows = connection.execute(
                """
                SELECT chapter_number, chapter_title, article_number,
                       article_title, clause_number, page, cross_references,
                       text, documents.source_name
                FROM document_chunks
                JOIN documents ON documents.id = document_chunks.document_id
                WHERE document_id = %s
                ORDER BY chunk_index
                """,
                (document_id,),
            ).fetchall()
        return [
            LegalChunkMetadata.model_validate(
                {
                    **row,
                    "source": row["source_name"],
                }
            )
            for row in rows
        ]

    def query(self, vector: list[float], limit: int) -> list[VectorSearchResult]:
        if limit < 1:
            raise ValueError("limit must be at least 1")
        document_id = self._document_id()
        vector_literal = "[" + ",".join(str(value) for value in vector) + "]"
        with self._pool.connection() as connection:
            rows = connection.execute(
                """
                SELECT chapter_number, chapter_title, article_number,
                       article_title, clause_number, page, cross_references,
                       text, documents.source_name,
                       1 - (embedding <=> %s::vector) AS score
                FROM document_chunks
                JOIN documents ON documents.id = document_chunks.document_id
                WHERE document_id = %s
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                (vector_literal, document_id, vector_literal, limit),
            ).fetchall()
        return [
            VectorSearchResult(
                score=float(row["score"]),
                metadata=LegalChunkMetadata.model_validate(
                    {
                        **row,
                        "source": row["source_name"],
                    }
                ),
            )
            for row in rows
        ]

    def close(self) -> None:
        """Close all pooled database connections."""
        self._pool.close()
