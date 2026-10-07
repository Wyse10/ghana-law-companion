from __future__ import annotations

import os
from typing import Any

from openai import OpenAI


def build_rag_prompt(query: str, contexts: list[dict[str, Any]]) -> str:
    """Format retrieved legal context chunks and query into a structured system

    prompt.
    """
    context_str = ""
    for idx, ctx in enumerate(contexts, 1):
        context_str += (
            f"--- Document Context {idx} ---\n"
            f"{ctx['text']}\n"
            f"(Source: Chapter {ctx.get('chapter_number', 'N/A')}, "
            f"Article {ctx.get('article_number', 'N/A')}, Page {ctx.get('page', 'N/A')})\n\n"
        )

    prompt = f"""You are "Ghana Law Companion", an expert legal assistant specializing in the 1992 Constitution of the Republic of Ghana.

Instructions:
1. Answer the user's question accurately using ONLY the provided constitutional context below.
2. Cite specific Articles and Chapters directly in your response when applicable.
3. If the context does not contain enough information to answer, state clearly that the provision is not found in the retrieved sections.

Context:
{context_str}

User Question:
{query}

Answer:"""
    return prompt


def generate_legal_answer(
    query: str,
    contexts: list[dict[str, Any]],
    model_name: str = "gpt-4o-mini",
) -> str:
    """Generate a legal response synthesized from retrieved context chunks."""
    if not contexts:
        return "No relevant constitutional provisions were found for your query."

    prompt = build_rag_prompt(query, contexts)

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

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
    )

    return (
        response.choices[0].message.content
        or "Unable to generate an answer."
    )