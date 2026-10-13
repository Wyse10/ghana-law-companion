from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import gradio as gr

from src.config import DEFAULT_MD_PATH, VECTOR_DB_PATH
from src.rag.generator import generate_legal_answer, rerank_contexts
from src.vectorstore.retriever import retrieve_relevant_context
from src.vectorstore.store import LocalVectorStore


APP_CSS = """
:root {
    --law-navy: #12304a;
    --law-blue: #1f5f7a;
    --law-gold: #d6a84f;
    --law-cream: #fbfaf6;
    --law-ink: #20313d;
    --law-green: #5f8368;
}

.gradio-container {
    max-width: 1180px !important;
    background: var(--law-cream);
    color: var(--law-ink);
}

.app-header {
    margin: 1.25rem 0 1rem;
    padding: 2rem 2.25rem;
    border-radius: 18px;
    color: white;
    background:
        linear-gradient(115deg, rgba(18, 48, 74, .98), rgba(31, 95, 122, .94)),
        repeating-linear-gradient(45deg, transparent 0 16px, rgba(214, 168, 79, .12) 17px 18px);
    border-bottom: 5px solid var(--law-gold);
    box-shadow: 0 10px 24px rgba(18, 48, 74, .12);
}

.app-header h1 {
    margin: 0 0 .35rem;
    font-size: clamp(2rem, 5vw, 3.1rem);
    letter-spacing: -.03em;
}

.app-header p {
    max-width: 700px;
    margin: 0;
    color: #e8f0f2;
    font-size: 1.05rem;
}

.eyebrow {
    margin-bottom: .7rem;
    color: #f4d58b;
    font-size: .78rem;
    font-weight: 700;
    letter-spacing: .12em;
    text-transform: uppercase;
}

.section-card {
    padding: 1.15rem 1.25rem;
    border: 1px solid #dce4e1;
    border-radius: 14px;
    background: white;
    box-shadow: 0 5px 16px rgba(18, 48, 74, .06);
}

.section-title {
    margin: 0 0 .7rem;
    color: var(--law-navy);
    font-size: 1.12rem;
    font-weight: 700;
}

.answer-panel {
    min-height: 290px;
    border-top: 4px solid var(--law-gold);
}

.answer-panel .prose {
    line-height: 1.7;
}

.legal-note {
    margin: .3rem 0 0;
    color: #58706c;
    font-size: .9rem;
}

.source-footer {
    margin-top: 1.2rem;
    padding: .85rem 1rem;
    border-left: 4px solid var(--law-green);
    background: #f1f6f1;
    color: #466052;
    font-size: .88rem;
}

.source-footer code {
    color: var(--law-navy);
}
"""


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
        gr.HTML(
            "<header class='app-header'>"
            "<div class='eyebrow'>Constitutional research assistant</div>"
            "<h1>⚖ Ghana Law Companion</h1>"
            "<p>Explore the 1992 Constitution of Ghana with clear, "
            "source-grounded answers for everyday legal questions.</p>"
            "</header>"
        )

        with gr.Row():
            with gr.Column(scale=3, elem_classes=["section-card"]):
                gr.Markdown(
                    "### Ask a constitutional question\n"
                    "<p class='legal-note'>Try a topic, right, article, or legal process.</p>",
                )
                question = gr.Textbox(
                    label="Question",
                    placeholder=(
                        "For example: What rights protect personal liberty under "
                        "the 1992 Constitution?"
                    ),
                    lines=3,
                    elem_id="question-box",
                )
                with gr.Row():
                    ask_button = gr.Button("Search the Constitution", variant="primary")
                    clear_button = gr.ClearButton([question], value="Clear")

            with gr.Column(scale=4, elem_classes=["section-card", "answer-panel"]):
                gr.Markdown("### Legal answer")
                answer = gr.Markdown(
                    value="Your answer will appear here, with relevant constitutional sources.",
                )

        gr.Examples(
            examples=[
                "What are the fundamental human rights regarding personal liberty?",
                "What protections does the Constitution provide for freedom of speech?",
                "When may a person's property be compulsorily acquired?",
            ],
            inputs=question,
            label="Start with an example",
            examples_per_page=3,
        )

        with gr.Accordion("Retrieved constitutional sources", open=False):
            sources = gr.Markdown()

        gr.Markdown(
            f"**Indexed source:** `{Path(DEFAULT_MD_PATH).name}`  \n"
            "Answers are informational and grounded in the indexed text; "
            "they are not a substitute for advice from a qualified lawyer.",
            elem_classes=["source-footer"],
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
    app.launch(
        css=APP_CSS,
        theme=gr.themes.Soft(
            primary_hue=gr.themes.colors.blue,
            secondary_hue=gr.themes.colors.green,
            neutral_hue=gr.themes.colors.slate,
        )
    )


if __name__ == "__main__":
    main()
