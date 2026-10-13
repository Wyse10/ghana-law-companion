from __future__ import annotations

import os
import re
from typing import Any

from openai import OpenAI

from src.config import GROQ_API_KEY

_STOP_WORDS = {
    "a", "about", "an", "and", "are", "as", "at", "be", "by", "can", "does",
    "for", "from", "how", "in", "is", "it", "may", "of", "on", "or", "the",
    "this", "to", "under", "was", "what", "when", "which", "who", "with",
}


def _query_terms(query: str) -> set[str]:
    return {
        term
        for term in re.findall(r"[a-z0-9]+", query.lower())
        if len(term) > 2 and term not in _STOP_WORDS
    }


def rerank_contexts(
    query: str,
    contexts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Rerank semantic results using lexical and constitutional reference matches."""
    if len(contexts) < 2:
        return contexts[:]

    query_terms = _query_terms(query)
    article_matches = set(re.findall(r"\barticles?\s+\d+[a-z]?\b", query.lower()))
    chapter_matches = set(re.findall(r"\bchapters?\s+\d+[a-z]?\b", query.lower()))

    ranked_contexts = []
    for index, context in enumerate(contexts):
        text = str(context.get("text", "")).lower()
        text_terms = set(re.findall(r"[a-z0-9]+", text))
        overlap = len(query_terms & text_terms) / max(len(query_terms), 1)
        references = (
            f"article {context.get('article_number', '')} "
            f"chapter {context.get('chapter_number', '')}"
        ).lower()
        reference_bonus = 0.0
        if article_matches and any(match in references for match in article_matches):
            reference_bonus += 0.35
        if chapter_matches and any(match in references for match in chapter_matches):
            reference_bonus += 0.2

        semantic_score = float(context.get("score", 0.0))
        rerank_score = semantic_score + (0.35 * overlap) + reference_bonus
        ranked_contexts.append((rerank_score, -index, context))

    ranked_contexts.sort(reverse=True, key=lambda item: (item[0], item[1]))
    return [context for _, _, context in ranked_contexts]


def build_rag_prompt(query: str, contexts: list[dict[str, Any]]) -> str:
    max_context_chars = max(
        int(os.getenv("GROQ_CONTEXT_MAX_CHARS", "16000")),
        1,
    )
    context_chunks: list[str] = []
    context_chars = 0
    for idx, ctx in enumerate(contexts):
        chunk = (
            f"--- Context Chunk {idx + 1} "
            f"(Article {ctx.get('article_number', 'N/A')}, "
            f"Chapter {ctx.get('chapter_number', 'N/A')}) ---\n"
            f"{ctx['text']}"
        )
        remaining_chars = max_context_chars - context_chars
        if remaining_chars <= 0:
            break
        if len(chunk) > remaining_chars:
            chunk = chunk[:remaining_chars]
        context_chunks.append(chunk)
        context_chars += len(chunk)

    context_str = "\n\n".join(context_chunks)

    return f"""You are "Ghana Law Companion", an expert legal assistant specializing in the 1992 Constitution of the Republic of Ghana.

Instructions:
1. Answer the user's question completely and thoroughly using ONLY the provided constitutional context below.
2. List ALL valid grounds, conditions, or exceptions explicitly stated in the context without truncating or leaving out items.
3. Cite specific Articles and Chapters directly in your response.

Context:
{context_str}

User Question:
{query}

Detailed Legal Answer:"""

# In src/rag/generator.py (or generator_2.py)
def generate_legal_answer(
    query: str,
    contexts: list[dict[str, Any]],
    model_name: str | None = None,
) -> str:
    if not contexts:
        return "No relevant constitutional provisions were found for your query."

    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not set.")

    ranked_contexts = rerank_contexts(query, contexts)
    context_limit = min(int(os.getenv("RAG_CONTEXT_LIMIT", "6")), len(ranked_contexts))
    prompt = build_rag_prompt(query, ranked_contexts[:context_limit])
    
    # Upgrade default to Llama 3.3 70B for higher legal recall
    model_name = model_name or os.getenv(
        "GROQ_GENERATION_MODEL", "qwen/qwen3.8-27b"
    )

    client = OpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=GROQ_API_KEY,
    )

    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {
                "role": "system",
                "content": "You are an authoritative legal expert on the 1992 Constitution of Ghana. Provide exhaustive, structured, and fully-cited answers.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.1,
        max_tokens=min(int(os.getenv("GROQ_GENERATION_MAX_TOKENS", "800")), 900),
    )

    return response.choices[0].message.content or "Unable to generate an answer."