from __future__ import annotations

from typing import Any

from openai import OpenAI

from src.config import GROQ_API_KEY


def build_rag_prompt(query: str, contexts: list[dict[str, Any]]) -> str:
    """Format retrieved legal context chunks into a structured system prompt."""
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
    model_name: str = "openai/gpt-oss-20b",
) -> str:
    """Generate a legal response using open-source models via Groq's free cloud API."""
    if not contexts:
        return "No relevant constitutional provisions were found for your query."

    if not GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Add it to a .env file or your environment."
        )

    prompt = build_rag_prompt(query, contexts)

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
    )

    return (
        response.choices[0].message.content
        or "Unable to generate an answer."
    )