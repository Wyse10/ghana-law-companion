from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import gradio as gr

from src.config import DEFAULT_MD_PATH, VECTOR_DB_PATH
from src.rag.generator import generate_legal_answer, rerank_contexts
from src.vectorstore.retriever import retrieve_relevant_context
from src.vectorstore.store import LocalVectorStore


def _format_sources(contexts: list[dict[str, Any]]) -> str:
    if not contexts:
        return "No relevant constitutional provisions were found."

    source_sections = []
    for index, context in enumerate(contexts, start=1):
        article = context.get("article_number") or "N/A"
        chapter = context.get("chapter_number") or "N/A"
        score = context.get("score")
        score_text = f"{float(score):.4f}" if score is not None else "N/A"
        source_sections.append(
            f"### Chunk {index} — Article {article}, Chapter {chapter}\n"
            f"**Similarity:** {score_text}\n\n"
            f"{context.get('text', '')}"
        )
    return "\n\n---\n\n".join(source_sections)


def answer_question(
    question: str,
    vector_store: LocalVectorStore,
) -> tuple[str, str]:
    """Retrieve constitutional context and generate an answer for one question."""
    question = question.strip()
    if not question:
        raise gr.Error("Enter a question about the 1992 Constitution of Ghana.")

    contexts = retrieve_relevant_context(
        query=question,
        qdrant_client=vector_store,
        top_k=6,
    )
    contexts = rerank_contexts(question, contexts)
    answer = generate_legal_answer(query=question, contexts=contexts)
    return answer, _format_sources(contexts)


def build_app(vector_store: LocalVectorStore) -> gr.Blocks:
    with gr.Blocks(
        title="Ghana Law Companion",
    ) as app:
        gr.Markdown(
            "# 🏛️ Ghana Law Companion\n"
            "Ask questions about the 1992 Constitution of Ghana. "
            "Answers are grounded in the indexed constitutional text."
        )

        with gr.Row():
            with gr.Column(scale=3):
                question = gr.Textbox(
                    label="Your question",
                    placeholder=(
                        "For example: What rights protect personal liberty "
                        "under the 1992 Constitution?"
                    ),
                    lines=3,
                )
                with gr.Row():
                    ask_button = gr.Button("Ask Ghana Law Companion", variant="primary")
                    clear_button = gr.ClearButton([question], value="Clear")

            with gr.Column(scale=4):
                answer = gr.Markdown(
                    label="Answer",
                    value="Your answer will appear here.",
                )

        gr.Examples(
            examples=[
                "What are the fundamental human rights regarding personal liberty?",
                "What protections does the Constitution provide for freedom of speech?",
                "When may a person's property be compulsorily acquired?",
            ],
            inputs=question,
            label="Example questions",
        )

        with gr.Accordion("Retrieved constitutional sources", open=False):
            sources = gr.Markdown()

        gr.Markdown(
            f"Indexed source: `{Path(DEFAULT_MD_PATH).name}`"
        )

        ask_button.click(
            fn=lambda query: answer_question(query, vector_store),
            inputs=question,
            outputs=[answer, sources],
        )
        question.submit(
            fn=lambda query: answer_question(query, vector_store),
            inputs=question,
            outputs=[answer, sources],
        )
        clear_button.click(
            fn=lambda: ("Your answer will appear here.", ""),
            outputs=[answer, sources],
        )

    return app


def main() -> None:
    if not os.path.exists(os.path.join(VECTOR_DB_PATH, "vectors.npy")):
        raise FileNotFoundError(
            "The local vector store has not been created yet. "
            "Run 'uv run python data_loader.py' first."
        )

    if not os.getenv("GROQ_API_KEY"):
        raise RuntimeError(
            "GROQ_API_KEY is not set. Add it to the .env file before starting the app."
        )

    vector_store = LocalVectorStore(VECTOR_DB_PATH)
    app = build_app(vector_store)
    app.launch(theme=gr.themes.Soft())


if __name__ == "__main__":
    main()
