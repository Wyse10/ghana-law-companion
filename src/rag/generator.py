from __future__ import annotations

import re
from typing import Any, Iterator

from openai import OpenAI
from openai import OpenAIError

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


def generate_legal_answer_stream(
    query: str,
    contexts: list[dict[str, Any]],
    model_name: str = "openai/gpt-oss-120b",
) -> Iterator[str]:
    """Stream legal response tokens with an explicit Groq model fallback."""
    if not contexts:
        yield "No relevant constitutional provisions were found for your query."
        return

    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not set. Add it to your .env file.")

    prompt = build_rag_prompt(query, contexts)
    client = OpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=GROQ_API_KEY,
    )
    messages = [
        {
            "role": "system",
            "content": "You are a knowledgeable and precise legal assistant specializing in Ghanaian law.",
        },
        {"role": "user", "content": prompt},
    ]

    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=0.2,
            max_tokens=1200,
            stream=True,
        )
        for chunk in response:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
        return
    except OpenAIError as primary_error:
        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=messages,
                temperature=0.2,
                max_tokens=1200,
                stream=True,
            )
            for chunk in response:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
        except OpenAIError as fallback_error:
            yield (
                "Error: All generation models failed. "
                f"Primary: {primary_error}; Fallback: {fallback_error}"
            )