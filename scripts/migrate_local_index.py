from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import psycopg


ROOT = Path(__file__).resolve().parents[1]
VECTOR_DIR = ROOT / "data" / "qdrant_db"
DATABASE_URL = "postgresql://ghana_law:local-development-only@localhost:5432/ghana_law"
EMBEDDING_MODEL = "BAAI/bge-base-en-v1.5"


def migrate() -> None:
    """Copy the validated local vector index into PostgreSQL."""
    payloads = json.loads((VECTOR_DIR / "payloads.json").read_text(encoding="utf-8"))
    vectors = np.load(VECTOR_DIR / "vectors.npy", allow_pickle=False)
    if len(payloads) != vectors.shape[0] or vectors.shape[1] != 768:
        raise ValueError("Local vector index has invalid payload or dimension counts.")

    source_path = Path(payloads[0]["source"])
    source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
    with psycopg.connect(DATABASE_URL) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO documents (source_name, source_sha256, source_version)
                VALUES (%s, %s, %s)
                ON CONFLICT (source_sha256) DO UPDATE
                SET source_version = EXCLUDED.source_version
                RETURNING id
                """,
                (source_path.name, source_hash, "constitution-1996"),
            )
            document_id = cursor.fetchone()[0]
            cursor.execute(
                "DELETE FROM document_chunks WHERE document_id = %s",
                (document_id,),
            )
            for index, (payload, vector) in enumerate(zip(payloads, vectors)):
                cursor.execute(
                    """
                    INSERT INTO document_chunks (
                        document_id, chunk_index, text, chapter_number,
                        chapter_title, article_number, article_title,
                        clause_number, page, cross_references, embedding_model,
                        embedding
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb,
                        %s, %s
                    )
                    """,
                    (
                        document_id,
                        index,
                        payload["text"],
                        payload["chapter_number"],
                        payload["chapter_title"],
                        payload["article_number"],
                        payload["article_title"],
                        payload.get("clause_number"),
                        payload["page"],
                        json.dumps(payload.get("cross_references", [])),
                        EMBEDDING_MODEL,
                        vector.tolist(),
                    ),
                )
        connection.commit()


if __name__ == "__main__":
    migrate()
