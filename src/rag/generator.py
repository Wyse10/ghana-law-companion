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

    prompt = build_rag_prompt(query, contexts)
    
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