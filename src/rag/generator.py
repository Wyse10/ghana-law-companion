from __future__ import annotations

import os
from typing import Any

from openai import OpenAI

from src.config import GROQ_API_KEY


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
    model_name: str | None = None,
) -> str:
    """Generate a legal response using open-source models via Groq's free cloud API."""
    if not contexts:
        return "No relevant constitutional provisions were found for your query."

    if not GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Add it to a .env file or your environment."
        )

    prompt = build_rag_prompt(query, contexts)
    model_name = model_name or os.getenv(
        "GROQ_GENERATION_MODEL", "openai/gpt-oss-20b"
    )

    # Groq provides an OpenAI-compatible endpoint
    client = OpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=GROQ_API_KEY,
    )

    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {
                "role": "system",
                "content": "You are a knowledgeable and precise legal assistant specializing in Ghanaian law.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_tokens=int(os.getenv("GROQ_GENERATION_MAX_TOKENS", "1200")),
    )

    return (
        response.choices[0].message.content
        or "Unable to generate an answer."
    )