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