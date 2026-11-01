from __future__ import annotations

import re
from typing import Any, Iterator

from openai import OpenAI
from openai import OpenAIError

from src.config import (
    GROQ_API_KEY,
    GROQ_CONTEXT_MAX_CHARS,
    GROQ_FALLBACK_MODEL,
    GROQ_MODEL,
)
from src.schemas import LegalAnswer, QueryRequest, RetrievedContext

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
    request = QueryRequest(query=query)
    validated_contexts = [RetrievedContext.model_validate(context) for context in contexts]
    if len(contexts) < 2:
        return [context.model_dump(mode="json") for context in validated_contexts]

    query_terms = _query_terms(request.query)
    article_matches = set(re.findall(r"\barticles?\s+\d+[a-z]?\b", request.query.lower()))
    chapter_matches = set(re.findall(r"\bchapters?\s+\d+[a-z]?\b", request.query.lower()))

    ranked_contexts = []
    for index, context in enumerate(validated_contexts):
        text = context.text.lower()
        text_terms = set(re.findall(r"[a-z0-9]+", text))
        overlap = len(query_terms & text_terms) / max(len(query_terms), 1)
        references = (
            f"article {context.article_number or ''} "
            f"chapter {context.chapter_number or ''}"
        ).lower()
        reference_bonus = 0.0
        if article_matches and any(match in references for match in article_matches):
            reference_bonus += 0.35
        if chapter_matches and any(match in references for match in chapter_matches):
            reference_bonus += 0.2

        semantic_score = context.score
        rerank_score = semantic_score + (0.35 * overlap) + reference_bonus
        ranked_contexts.append((rerank_score, -index, context))

    ranked_contexts.sort(reverse=True, key=lambda item: (item[0], item[1]))
    return [context.model_dump(mode="json") for _, _, context in ranked_contexts]


def build_rag_prompt(query: str, contexts: list[dict[str, Any]]) -> str:
    request = QueryRequest(query=query)
    validated_contexts = [RetrievedContext.model_validate(context) for context in contexts]
    context_str = "\n\n".join(
        [
            f"--- Context Chunk {idx + 1} ---\n{ctx.text}"
            for idx, ctx in enumerate(validated_contexts)
        ]
    )

    return f"""You are "Ghana Law Companion", an expert legal assistant specializing in the 1992 Constitution of the Republic of Ghana.

Instructions:
1. Answer the user's question completely and thoroughly using ONLY the provided constitutional context below.
2. List ALL valid grounds, conditions, or exceptions explicitly stated in the context without truncating or leaving out items.
3. Cite specific Articles and Chapters directly in your response.

Context:
{context_str}

User Question:
{request.query}

Return the answer and cited Article/Chapter references as a structured response.
"""


def trim_contexts_to_budget(
    contexts: list[dict[str, Any]],
    max_chars: int = GROQ_CONTEXT_MAX_CHARS,
) -> list[dict[str, Any]]:
    """Keep complete retrieved chunks within the generation context budget."""
    if max_chars < 1:
        raise ValueError("max_chars must be at least 1")

    trimmed: list[dict[str, Any]] = []
    characters_used = 0
    for context in contexts:
        validated = RetrievedContext.model_validate(context)
        remaining = max_chars - characters_used
        if remaining <= 0:
            break
        text = validated.text
        if len(text) > remaining:
            marker = "\n[context truncated]"
            text = f"{text[:max(remaining - len(marker), 0)]}{marker}"
        trimmed_context = validated.model_copy(update={"text": text})
        trimmed.append(trimmed_context.model_dump(mode="json"))
        characters_used += len(text)
        if len(text) < len(validated.text):
            break
    return trimmed


def validate_answer_citations(
    answer: LegalAnswer,
    contexts: list[dict[str, Any]],
) -> LegalAnswer:
    """Reject model citations that cannot be supported by retrieved context."""
    validated_contexts = [
        RetrievedContext.model_validate(context) for context in contexts
    ]
    if not answer.citations:
        raise ValueError("The generated answer did not include any citations.")

    supported_articles = {
        f"article {context.article_number}".lower()
        for context in validated_contexts
        if context.article_number
    }
    supported_chapters = {
        f"chapter {context.chapter_number}".lower()
        for context in validated_contexts
        if context.chapter_number
    }
    unsupported = [
        citation
        for citation in answer.citations
        if not any(
            reference in citation.lower()
            for reference in (*supported_articles, *supported_chapters)
        )
    ]
    if unsupported:
        raise ValueError(
            "The generated answer contains unsupported citations: "
            + ", ".join(unsupported)
        )
    return answer


def generate_legal_answer_structured(
    query: str,
    contexts: list[dict[str, Any]],
    model_name: str = GROQ_MODEL,
) -> LegalAnswer:
    """Generate and validate the complete structured legal answer."""
    request = QueryRequest(query=query)
    validated_contexts = [
        RetrievedContext.model_validate(context)
        for context in trim_contexts_to_budget(contexts)
    ]
    if not validated_contexts:
        return LegalAnswer(
            answer="No relevant constitutional provisions were found for your query."
        )
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not set. Add it to your .env file.")

    client = OpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=GROQ_API_KEY,
    )
    messages = [
        {
            "role": "system",
            "content": "Answer only from the supplied Ghana Constitution context.",
        },
        {
            "role": "user",
            "content": build_rag_prompt(
                request.query,
                [context.model_dump(mode="json") for context in validated_contexts],
            ),
        },
    ]
    last_error: OpenAIError | None = None
    for candidate_model in (model_name, GROQ_FALLBACK_MODEL):
        try:
            response = client.chat.completions.parse(
                model=candidate_model,
                messages=messages,
                temperature=0.2,
                max_tokens=1200,
                response_format=LegalAnswer,
            )
            parsed = response.choices[0].message.parsed
            if parsed is None:
                raise RuntimeError("The generation model returned an empty structured response.")
            return validate_answer_citations(
                parsed,
                [context.model_dump(mode="json") for context in validated_contexts],
            )
        except OpenAIError as error:
            last_error = error
    raise RuntimeError(f"All generation models failed: {last_error}")


def generate_legal_answer(
    query: str,
    contexts: list[dict[str, Any]],
    model_name: str = GROQ_MODEL,
) -> str:
    """Return the validated answer text for existing UI and evaluation callers."""
    return generate_legal_answer_structured(query, contexts, model_name).answer


def generate_legal_answer_stream(
    query: str,
    contexts: list[dict[str, Any]],
    model_name: str = GROQ_MODEL,
) -> Iterator[str]:
    """Yield the validated structured answer as one UI-compatible chunk."""
    yield generate_legal_answer(query, contexts, model_name)