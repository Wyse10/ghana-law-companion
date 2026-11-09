from __future__ import annotations

import json
import re
from typing import Any, Iterator

from openai import OpenAI
from openai import OpenAIError

from src.config import (
    GROQ_API_KEY,
    GROQ_CONTEXT_MAX_CHARS,
    GROQ_FALLBACK_MODEL,
    GROQ_MAX_TOKENS,
    GROQ_MODEL,
    GROQ_TIMEOUT_SECONDS,
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


def build_rag_prompt(
    query: str,
    contexts: list[dict[str, Any]],
    history: list[dict[str, Any]] | None = None,
) -> str:
    request = QueryRequest(query=query)
    validated_contexts = [RetrievedContext.model_validate(context) for context in contexts]
    context_str = "\n\n".join(
        [
            f"--- Context Chunk {idx + 1} ---\n{ctx.text}"
            for idx, ctx in enumerate(validated_contexts)
        ]
    )

    history_str = ""
    if history:
        history_lines = []
        for msg in history[-6:]:  # last 3 turns
            role = "User" if msg.get("role") == "user" else "Assistant"
            content = msg.get("content", "").strip()
            history_lines.append(f"{role}: {content}")
        if history_lines:
            history_str = "\nConversation History:\n" + "\n".join(history_lines) + "\n"

    return f"""You are "Ghana Law Companion", an expert legal assistant specializing in the 1992 Constitution of the Republic of Ghana.

Instructions:
1. Answer the user's question completely, accurately, and thoroughly using ONLY the provided constitutional context and conversation history below.
2. Structure the answer for high readability and clarity:
   - If the query is a yes/no question, begin directly with "Yes." or "No." followed by the core constitutional finding.
   - When listing grounds, exceptions, conditions, public offices, rights, or procedures, format them as clean markdown bullet points (- Item) rather than a continuous run-on sentence with semicolons.
   - Use clear paragraph breaks between distinct legal rules, general provisions, and subsequent restrictions/exceptions.
3. If the user asks a contextual follow-up question (e.g. referencing "that exception", "those offices", "they", or prior provisions), use the conversation history to resolve the reference accurately.
4. List ALL valid grounds, conditions, or exceptions explicitly stated in the context without truncating or leaving out items.
5. Cite specific Articles and Chapters directly in your response (e.g. Article 8(1), Article 8(2), Chapter 3).
{history_str}
Context from the 1992 Constitution of Ghana:
{context_str}

User Question:
{request.query}

Return ONLY a valid JSON object with exactly this shape:
{{"answer": "grounded answer text", "citations": ["Article 20(1)", "Chapter 5"]}}
The answer must be in English. Do not return commentary or any text before or after the JSON object.
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
    history: list[dict[str, Any]] | None = None,
) -> LegalAnswer:
    """Reject model citations that cannot be supported by retrieved context or conversation history."""
    validated_contexts = [
        RetrievedContext.model_validate(context) for context in contexts
    ]
    if not answer.citations:
        raise ValueError("The generated answer did not include any citations.")

    supported_articles = {
        str(context.article_number).lower()
        for context in validated_contexts
        if context.article_number
    }
    supported_chapters = {
        str(context.chapter_number).lower()
        for context in validated_contexts
        if context.chapter_number
    }

    # If conversation history exists, also allow citations previously established in history
    if history:
        for msg in history:
            for cit in msg.get("citations", []):
                cit_art = re.search(r"\b(?:article|art\.?)\s+(\d+[a-z]?)\b", cit.lower())
                if cit_art:
                    supported_articles.add(cit_art.group(1))
                cit_ch = re.search(r"\bchapter\s+(\d+[a-z]?)\b", cit.lower())
                if cit_ch:
                    supported_chapters.add(cit_ch.group(1))
            for art_match in re.findall(r"\b(?:article|art\.?)\s+(\d+[a-z]?)\b", msg.get("content", "").lower()):
                supported_articles.add(art_match)
            for ch_match in re.findall(r"\bchapter\s+(\d+[a-z]?)\b", msg.get("content", "").lower()):
                supported_chapters.add(ch_match)

    unsupported = []
    for citation in answer.citations:
        citation_lower = citation.lower()
        article_match = re.search(
            r"\b(?:article|art\.?)\s+(\d+[a-z]?)\b",
            citation_lower,
        )
        if article_match:
            if article_match.group(1) not in supported_articles:
                unsupported.append(citation)
            continue

        chapter_supported = any(
            re.search(
                rf"\bchapter\s+{re.escape(chapter)}\b",
                citation_lower,
            )
            for chapter in supported_chapters
        )
        if not chapter_supported:
            unsupported.append(citation)

    if unsupported:
        raise ValueError(
            "The generated answer contains unsupported citations: "
            + ", ".join(unsupported)
        )
    return answer


def parse_generated_answer(content: str) -> LegalAnswer:
    """Parse provider JSON mode output into the validated answer schema."""
    if not content or not content.strip():
        raise ValueError("The generation model returned empty content.")

    normalized = content.strip()
    if normalized.startswith("```"):
        normalized = re.sub(r"^```(?:json)?\s*", "", normalized, flags=re.IGNORECASE)
        normalized = re.sub(r"\s*```$", "", normalized)

    try:
        payload = json.loads(normalized)
    except json.JSONDecodeError as error:
        raise ValueError(
            "The generation model returned invalid JSON."
        ) from error
    if not isinstance(payload, dict):
        raise ValueError("The generation model returned a JSON value, not an object.")
    return LegalAnswer.model_validate(payload)


def generate_legal_answer_structured(
    query: str,
    contexts: list[dict[str, Any]],
    model_name: str = GROQ_MODEL,
    history: list[dict[str, Any]] | None = None,
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
        timeout=GROQ_TIMEOUT_SECONDS,
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
                history=history,
            ),
        },
    ]
    last_error: Exception | None = None
    for candidate_model in (model_name, GROQ_FALLBACK_MODEL):
        try:
            response = client.chat.completions.create(
                model=candidate_model,
                messages=messages,
                temperature=0.2,
                max_tokens=GROQ_MAX_TOKENS,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content
            parsed = parse_generated_answer(content or "")
            return validate_answer_citations(
                parsed,
                [context.model_dump(mode="json") for context in validated_contexts],
                history=history,
            )
        except (OpenAIError, RuntimeError, ValueError) as error:
            last_error = error
    raise RuntimeError(f"All generation models failed: {last_error}")


def generate_legal_answer(
    query: str,
    contexts: list[dict[str, Any]],
    model_name: str = GROQ_MODEL,
    history: list[dict[str, Any]] | None = None,
) -> str:
    """Return the validated answer text for existing UI and evaluation callers."""
    return generate_legal_answer_structured(
        query, contexts, model_name, history=history
    ).answer


def generate_legal_answer_stream(
    query: str,
    contexts: list[dict[str, Any]],
    model_name: str = GROQ_MODEL,
    history: list[dict[str, Any]] | None = None,
) -> Iterator[str]:
    """Yield the validated structured answer as one UI-compatible chunk."""
    yield generate_legal_answer(query, contexts, model_name, history=history)
