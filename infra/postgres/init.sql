CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documents (
    id BIGSERIAL PRIMARY KEY,
    source_name TEXT NOT NULL,
    source_sha256 CHAR(64) NOT NULL UNIQUE,
    source_version TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS document_chunks (
    id BIGSERIAL PRIMARY KEY,
    document_id BIGINT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    text TEXT NOT NULL,
    chapter_number TEXT NOT NULL,
    chapter_title TEXT NOT NULL,
    article_number TEXT NOT NULL,
    article_title TEXT NOT NULL,
    clause_number TEXT,
    page INTEGER NOT NULL CHECK (page >= 1),
    cross_references JSONB NOT NULL DEFAULT '[]'::jsonb,
    embedding_model TEXT NOT NULL,
    embedding vector(768) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (document_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS document_chunks_embedding_idx
    ON document_chunks
    USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS document_chunks_article_idx
    ON document_chunks (chapter_number, article_number);
