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

## Loading the constitution data

Run the data loader once after adding or changing the source PDF. It converts
the PDF to Markdown, extracts chapters, creates legal chunks, generates
embeddings, and builds the local vector store:

```powershell
uv run python data_loader.py
```

After that, run the application without repeating ingestion:

```powershell
uv run python main.py
```

## Validated project structures

All data crossing an ingestion, retrieval, vector-store, evaluation, or
generation boundary is validated with Pydantic models in
`src/schemas.py`. The main structures are:

- `LegalChunk` and `LegalChunkMetadata` for indexed constitutional content.
- `RetrievedContext` and `VectorSearchResult` for retrieval results.
- `QueryRequest` for user questions.
- `LegalAnswer` for model output (`answer` plus `citations`).
- `TestQuestion`, `RetrievalEval`, and `AnswerEval` for evaluation data.

The answer generator uses the OpenAI-compatible structured parsing endpoint,
so model responses are validated before they reach the application. To access
the complete structured response, use
`generate_legal_answer_structured`; the existing
`generate_legal_answer` wrapper returns only the validated answer text for the
Streamlit and evaluation interfaces.