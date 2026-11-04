# Ghana Law Companion

## Evaluation

The evaluator uses the Groq judge model `qwen3.8-27b`. Ensure
`GROQ_API_KEY` is set in `.env`, then run the evaluator:

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

After ingestion, run the FastAPI API with Docker Compose as described below.

## Tests

Run the local regression suite before using or deploying the application:

```powershell
uv run python -m unittest discover -s tests -v
```

The test suite covers chunk validation, vector-store integrity, citation
grounding, context budgets, and metadata-aware retrieval metrics.

The FastAPI service loads the embedding model when the first query arrives and
returns retrieval, generation, and total response timings. Structured JSON
generation is intentionally kept non-streaming so citations can be validated
before an answer is returned.

## Continuous integration

Every push to `main` and every pull request runs the regression suite, checks
the development and production Compose configurations, validates the Caddy
edge configuration, builds the API image, and runs a Compose smoke test
against live PostgreSQL, Redis, and API containers. CI does not deploy or
access production secrets. Production deployment should be a separate approved
workflow that promotes the exact image digest built by CI.

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
`generate_legal_answer` wrapper returns only the validated answer text for
evaluation and internal library callers.

## NestJS BFF

Streamlit has been removed. The production web-facing server is now the
NestJS BFF in `nestjs/`. It exposes `POST /api/query`, forwards validated
requests to FastAPI at `/api/v1/query`, and keeps `API_KEY` server-side.
NestJS does not provide a browser UI; a separate frontend can consume this
gateway later.

Build and run the BFF locally:

```powershell
Set-Location nestjs
npm ci
npm run build
npm start
```

In Compose, the BFF is available internally on port `3000` and uses
`FASTAPI_URL=http://api:8000`. The public Caddy profile routes `/api/query`
through NestJS and never exposes the FastAPI credential to clients.

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
$env:POSTGRES_PASSWORD = "<unique database password>"
docker compose up -d --build
docker compose ps
```

The API container runs as a non-root user and exposes port `8000`. The
Compose default database password is only for local development; staging and
production must inject `POSTGRES_PASSWORD` from a secret manager. Do not put
production secrets in `.env.example`, source control, or image layers.
Interactive API documentation is enabled by default for development and
disabled in the production Compose configuration (`API_DOCS_ENABLED=false`).
The API also emits browser security headers, including content-type,
clickjacking, referrer, and permissions protections. HSTS is emitted when
requests arrive over HTTPS; the Caddy edge proxy provides HTTPS in production.
PostgreSQL retrieval uses a bounded connection pool
(`DATABASE_POOL_MIN_SIZE=1`, `DATABASE_POOL_MAX_SIZE=10`) that is closed during
API shutdown.

For zero-downtime API-key rotation, set `API_KEYS` to a comma-separated list
containing the current and replacement keys. Deploy with both keys, update
clients to the replacement, then remove the old key in a second deployment:

```powershell
$env:API_KEYS = "<current-key>,<replacement-key>"
docker compose up -d
# After all clients migrate:
$env:API_KEYS = "<replacement-key>"
docker compose up -d
```

`API_KEY` remains supported as the single-key fallback. Store these values in
the platform secret manager and never commit them.

Use the production override to fail fast when required secrets are missing:

```powershell
$env:POSTGRES_DB = "ghana_law"
$env:POSTGRES_USER = "ghana_law"
$env:POSTGRES_PASSWORD = "<managed database password>"
$env:DATABASE_URL = "postgresql+psycopg://<user>:<password>@<managed-host>:5432/<database>"
docker compose -f docker-compose.yml -f docker-compose.production.yml config --quiet
docker compose -f docker-compose.yml -f docker-compose.production.yml up -d --build
```

For managed PostgreSQL, point `DATABASE_URL` at the managed service and omit
the local PostgreSQL service from the deployment. Never paste secret values
into shell history or CI logs; inject them through the hosting platform's
secret store.

For a TLS edge proxy, set a DNS record for the API host, then start the
optional Caddy profile:

```powershell
$env:API_DOMAIN = "api.example.com"
docker compose --profile edge up -d
```

Caddy obtains and renews the certificate through Let's Encrypt for a public
domain, forwards only `/health/*` and `/api/*`, and returns `404` for
`/metrics`. Keep the API
container bound to localhost as configured here so clients cannot bypass the
TLS proxy. Caddy emits HSTS for HTTPS clients, and requests larger than 64 KiB
are rejected at the edge before they reach FastAPI. In production, also keep
PostgreSQL private and replace the development database password with a
managed secret.

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
`503 Service Unavailable` rather than silently disabling protection. CORS is
disabled by default (`CORS_ORIGINS=""`); set it to a comma-separated list of
trusted frontend origins before enabling browser access.
Prometheus-compatible metrics are available at `/metrics`; keep that endpoint
private to your monitoring network or protect it at the reverse proxy.

## PostgreSQL backup and restore verification

Back up the PostgreSQL database to a local, ignored `backups` directory:

```powershell
.\scripts\backup_postgres.ps1
```

The script creates a compressed custom-format dump and a SHA-256 checksum.
Store both files in durable, encrypted object storage in production; do not
rely on the Docker volume or the application host as the only copy.

Verify a dump by restoring it into a temporary database and checking that the
document and chunk tables can be read:

```powershell
.\scripts\verify_postgres_backup.ps1 `
  -BackupPath .\backups\ghana-law-YYYYMMDD-HHMMSS.dump
```

Run backup and restore verification on a schedule, retain multiple recovery
points, and record the last successful restore test. A production restore
should be performed against a new managed database, followed by application
readiness and retrieval checks before traffic is switched.