# Ghana Law Companion

## Evaluation

The evaluator uses the Groq judge model `qwen3.8-27b`. Ensure
`GROQ_API_KEY` is set in `.env`, then start the dashboard:

```powershell
uv run python evaluator.py
```

The Groq prompts are bounded by default to avoid exceeding the model's input
token-per-minute limit. `GROQ_CONTEXT_MAX_CHARS` controls the generation
context budget, and `GROQ_EVALUATION_MAX_CHARS` controls the combined answer
and reference text sent to the judge. Both default to `16000` characters;
lower them if the account has a smaller input-token limit.

Batch evaluation can reuse context and the local embedding model between
requests. The Ollama installation is not required for evaluation.

The application uses `openai/gpt-oss-120b` through Groq by default and falls
back to `qwen/qwen3.8-27b`. Override these model IDs with `GROQ_MODEL` and
`GROQ_FALLBACK_MODEL` in `.env` if your Groq account has different model access.
`GROQ_TIMEOUT_SECONDS` controls the provider request timeout and defaults to
`60`. `GROQ_MAX_TOKENS` controls the answer length and defaults to `900`.

The indexed source is the Constitution of the Republic of Ghana, 1992, using
the revised 1996 English edition stored in `data/raw/Ghana_1996-en.pdf`. The
application is a source-grounded research aid, not a substitute for advice
from a qualified Ghanaian lawyer and does not represent all current Ghanaian
legislation.

## Loading the constitution data

Run the data loader once after adding or changing the source PDF. It converts
the PDF to Markdown, extracts chapters, creates legal chunks, generates
embeddings, and builds the local vector store:

```powershell
uv run python data_loader.py
```

The index includes a manifest recording its embedding model, vector dimension,
chunk count, and processed-source hash. Re-run the loader after changing the
source PDF or embedding model; otherwise the application may be using an older
index. The loader creates clause-level chunks for numbered constitutional
clauses while retaining lettered paragraphs with their parent clause.

After that, run the application without repeating ingestion:

```powershell
uv run python main.py
```

## Tests

Run the local regression suite before using or deploying the application:

```powershell
uv run python -m unittest discover -s tests -v
```

The test suite covers chunk validation, vector-store integrity, citation
grounding, context budgets, and metadata-aware retrieval metrics.

The application loads the local embedding model when the app starts instead
of delaying that cost until the first question. It also caches answers for
repeated questions during the current Streamlit session and displays
retrieval, generation, and total response timings. Structured JSON generation
is intentionally kept non-streaming so citations can be validated before an
answer is displayed.

## Validated project structures

All data crossing an ingestion, retrieval, vector-store, evaluation, or
generation boundary is validated with Pydantic models in
`src/schemas.py`. The main structures are:

- `LegalChunk` and `LegalChunkMetadata` for indexed constitutional content.
- `RetrievedContext` and `VectorSearchResult` for retrieval results.
- `QueryRequest` for user questions.
- `LegalAnswer` for model output (`answer` plus `citations`).
- `TestQuestion`, `RetrievalEval`, and `AnswerEval` for evaluation data.

The answer generator requests JSON mode from the OpenAI-compatible provider and
manually validates the parsed response against the legal-answer schema,
so model responses are validated before they reach the application. Context is
limited by `GROQ_CONTEXT_MAX_CHARS` (default `16000`), and returned citations
must match Articles or Chapters present in the retrieved context. To access
the complete structured response, use
`generate_legal_answer_structured`; the existing
`generate_legal_answer` wrapper returns only the validated answer text for the
Streamlit and evaluation interfaces.

## Local production infrastructure

The API currently serves the verified local vector index. PostgreSQL with
pgvector is provided as the next persistence target:

```powershell
docker compose up -d postgres
docker compose ps
```

The database schema is initialized from `infra/postgres/init.sql`. The local
database uses development-only credentials; use managed PostgreSQL and a
secret manager for staging and production. The API will not switch to this
database until migration and retrieval verification pass.

After PostgreSQL is healthy, migrate the existing local index with:

```powershell
uv run python scripts/migrate_local_index.py
```

This migration is intended for Linux containers and production environments
where the PostgreSQL driver is available. The migration records the source
hash, replaces chunks for that exact source document, and preserves the
embedding model and constitutional metadata.

To run the API against the migrated PostgreSQL index, configure:

```powershell
$env:VECTOR_STORE_BACKEND = "postgres"
$env:SOURCE_SHA256 = "<SHA-256 of the indexed source PDF>"
$env:DATABASE_URL = "postgresql+psycopg://user:password@host:5432/database"
uv run uvicorn src.api.main:app --host 127.0.0.1 --port 8000
```

The default backend remains `local` until the PostgreSQL migration has been
verified. Production deployments should use a managed database, a connection
pool, TLS, and secret-manager credentials.

## Container deployment

Build and run the API with PostgreSQL after setting the required values:

```powershell
$env:SOURCE_SHA256 = "<SHA-256 of the indexed source PDF>"
$env:GROQ_API_KEY = "<provider key>"
$env:API_KEY = "<long random API key>"
docker compose up -d --build
docker compose ps
```

The API container runs as a non-root user and exposes port `8000`. The
PostgreSQL password and provider key shown above are for local development
only; production deployments must use managed secrets and a non-default
database password.

The query endpoint requires the `X-API-Key` header when
`REQUIRE_API_KEY=true`:

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://localhost:8000/api/v1/query `
  -Headers @{ "X-API-Key" = $env:API_KEY } `
  -ContentType "application/json" `
  -Body '{"query":"What protects personal liberty?","top_k":5}'
```

Health endpoints remain public for load balancer probes. Store the API key in
a secret manager in production and rotate it instead of committing it. The
Compose deployment also enables Redis-backed fixed-window rate limiting by
default (`RATE_LIMIT_PER_MINUTE=10`). Health endpoints are exempt; requests
over the limit receive `429 Too Many Requests`, and Redis outages return
`503 Service Unavailable` rather than silently disabling protection.