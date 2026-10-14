from __future__ import annotations

import re
from typing import Any

from litellm import completion

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
    context_str = "\n\n".join(
        [f"--- Context Chunk {idx+1} ---\n{ctx['text']}" for idx, ctx in enumerate(contexts)]
    )

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


def generate_legal_answer(
    query: str,
    contexts: list[dict[str, Any]],
    model_name: str = "groq/openai/gpt-oss-120b",
) -> str:
    """Generate a legal response using LiteLLM with built-in automatic failover/fallback."""
    if not contexts:
        return "No relevant constitutional provisions were found for your query."

    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not set. Add it to your .env file.")

    prompt = build_rag_prompt(query, contexts)

    try:
        # LiteLLM automatically tries the primary model, and if it fails or hits rate limits,
        # it instantly falls back to the models listed in the fallbacks array.
        response = completion(
            model=model_name,  # Primary model
            messages=[
                {
                    "role": "system",
                    "content": "You are a knowledgeable and precise legal assistant specializing in Ghanaian law.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=1200,
            fallbacks=["groq/openai/gpt-oss-20b"],
            api_key=GROQ_API_KEY,
        )

        return (
            response.choices[0].message.content
            or "Unable to generate an answer."
        )

    except Exception as e:
        return f"Error: All generation models and fallbacks failed. Details: {e}"