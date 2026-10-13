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