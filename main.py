from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

import streamlit as st

from src.config import DEFAULT_MD_PATH, VECTOR_DB_PATH
from src.rag.generator import generate_legal_answer_structured, rerank_contexts
from src.vectorstore.retriever import (
    retrieve_relevant_context,
    warm_up_embedding_model,
)
from src.vectorstore.store import LocalVectorStore

# Page Configuration
st.set_page_config(
    page_title="Ghana Law Companion",
    page_icon="⚖",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# Custom Styling (Theme Colors & Cards)
st.markdown(
    """
    <style>
    :root {
        --law-navy: #12304a;
        --law-blue: #1f5f7a;
        --law-gold: #d6a84f;
        --law-cream: #fbfaf6;
        --law-ink: #20313d;
        --law-green: #5f8368;
    }

    .stApp {
        background-color: var(--law-cream);
        color: var(--law-ink);
    }

    .app-header {
        margin: 0.5rem 0 1.5rem;
        padding: 2rem 2.25rem;
        border-radius: 18px;
        color: white;
        background: linear-gradient(115deg, rgba(18, 48, 74, .98), rgba(31, 95, 122, .94)),
                    repeating-linear-gradient(45deg, transparent 0 16px, rgba(214, 168, 79, .12) 17px 18px);
        border-bottom: 5px solid var(--law-gold);
        box-shadow: 0 10px 24px rgba(18, 48, 74, .12);
    }

    .app-header h1 {
        margin: 0 0 0.35rem;
        font-size: 2.5rem;
        letter-spacing: -0.03em;
        color: white !important;
    }

    .app-header p {
        margin: 0;
        color: #e8f0f2;
        font-size: 1.05rem;
    }

    .eyebrow {
        margin-bottom: 0.7rem;
        color: #f4d58b;
        font-size: 0.78rem;
        font-weight: 700;
        letter-spacing: 0.12em;
        text-transform: uppercase;
    }

    .source-footer {
        margin-top: 2rem;
        padding: 0.85rem 1rem;
        border-left: 4px solid var(--law-green);
        background: #f1f6f1;
        color: #466052;
        font-size: 0.88rem;
        border-radius: 4px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def load_vector_store() -> LocalVectorStore:
    """Load the local Qdrant vector store cached for performance."""
    if not os.path.exists(os.path.join(VECTOR_DB_PATH, "vectors.npy")):
        st.error(
            "The local vector store has not been created yet. "
            "Run 'uv run python data_loader.py' first."
        )
        st.stop()

    if not os.getenv("GROQ_API_KEY"):
        st.error("GROQ_API_KEY is not set. Add it to your .env file.")
        st.stop()

    store = LocalVectorStore(VECTOR_DB_PATH)
    warm_up_embedding_model()
    return store


def format_sources(contexts: list[dict[str, Any]]) -> str:
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
            f"**Similarity Score:** {score_text}\n\n"
            f"{context.get('text', '')}"
        )
    return "\n\n---\n\n".join(source_sections)


def main():
    vector_store = load_vector_store()
    if "answer_cache" not in st.session_state:
        st.session_state.answer_cache = {}

    # Header Section
    st.markdown(
        """
        <div class="app-header">
            <div class="eyebrow">Constitutional Research Assistant</div>
            <h1>⚖ Ghana Law Companion</h1>
            <p>Explore the 1992 Constitution of Ghana with clear, source-grounded answers for everyday legal queries.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Input Form
    with st.form("question_form"):
        st.subheader("Ask a Constitutional Question")
        question = st.text_area(
            "Question",
            placeholder="For example: What rights protect personal liberty under the 1992 Constitution?",
            label_visibility="collapsed",
            height=100,
        )
        
        col1, col2 = st.columns([1, 5])
        with col1:
            submit_button = st.form_submit_button("Search 🏛️", use_container_width=True)
        with col2:
            pass

    # Example Prompt Buttons
    st.markdown("**Or try a common topic:**")
    ex_col1, ex_col2, ex_col3 = st.columns(3)
    
    selected_example = None
    if ex_col1.button("Personal Liberty Rights"):
        selected_example = "What are the fundamental human rights regarding personal liberty?"
    if ex_col2.button("Freedom of Speech"):
        selected_example = "What protections does the Constitution provide for freedom of speech?"
    if ex_col3.button("Property Acquisition"):
        selected_example = "When may a person's property be compulsorily acquired?"

    # Determine active query
    active_query = question
    if selected_example:
        active_query = selected_example

    # Handle Search Submission:

    if submit_button or selected_example:
        if not active_query.strip():
            st.warning("Please enter a valid legal question.")
        else:
            # 1. Retrieve and rerank context upfront
            try:
                normalized_query = " ".join(active_query.split()).casefold()
                cached_result = st.session_state.answer_cache.get(normalized_query)
                total_started = time.perf_counter()
                with st.spinner("Searching constitutional provisions..."):
                    if cached_result is None:
                        retrieval_started = time.perf_counter()
                        contexts = retrieve_relevant_context(
                            query=active_query,
                            vector_store=vector_store,
                            top_k=6,
                        )
                        contexts = rerank_contexts(active_query, contexts)
                        retrieval_seconds = time.perf_counter() - retrieval_started
                        generation_started = time.perf_counter()
                        legal_answer = generate_legal_answer_structured(
                            query=active_query,
                            contexts=contexts,
                        )
                        generation_seconds = time.perf_counter() - generation_started
                        st.session_state.answer_cache[normalized_query] = (
                            legal_answer,
                            contexts,
                        )
                    else:
                        legal_answer, contexts = cached_result
                        retrieval_seconds = 0.0
                        generation_seconds = 0.0
                    sources_markdown = format_sources(contexts)
                total_seconds = time.perf_counter() - total_started
            except (RuntimeError, ValueError) as error:
                st.error(f"Unable to produce a grounded answer: {error}")
            else:
                st.markdown("---")
                st.subheader("📜 Legal Answer")
                st.markdown(legal_answer.answer)
                st.markdown("**Citations:** " + ", ".join(legal_answer.citations))
                cache_label = "cached result" if cached_result is not None else "new answer"
                st.caption(
                    f"{cache_label.capitalize()} | retrieval: {retrieval_seconds:.2f}s | "
                    f"generation: {generation_seconds:.2f}s | total: {total_seconds:.2f}s"
                )

                with st.expander(
                    "🔍 View Retrieved Constitutional Sources", expanded=False
                ):
                    st.markdown(sources_markdown)
    # Footer Notice
    md_name = Path(DEFAULT_MD_PATH).name
    st.markdown(
        f"""
        <div class="source-footer">
            <strong>Indexed Source:</strong> Constitution of Ghana, 1992
            (revised 1996 English edition) — <code>{md_name}</code><br>
            <em>Answers are informational and grounded strictly in the indexed text; they are not a substitute for advice from a qualified lawyer.</em>
        </div>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()