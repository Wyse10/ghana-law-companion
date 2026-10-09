# Ghana Law Companion

## Evaluation

The evaluator uses the Groq judge model `qwen3.8-27b`. Ensure
`GROQ_API_KEY` is set in `.env`, then start the dashboard:

```powershell
uv run python evaluator.py
```

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