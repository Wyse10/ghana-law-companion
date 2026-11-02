from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from langchain_core.documents import Document

from src.config import KNOWLEDGE_BASE_DIR
from .pdf_converter import (
    convert_pdf_to_markdown,
    convert_pdf_to_page_chunks,
)
from src.schemas import LegalChunk


def fetch_documents(
    knowledge_base: str | Path = KNOWLEDGE_BASE_DIR,
) -> list[Document]:
    """Load Markdown documents from categorized knowledge-base folders.

    Each immediate subfolder is treated as a document type. Markdown files
    are loaded recursively and returned as LangChain ``Document`` objects.
    """
    base_path = Path(knowledge_base)
    if not base_path.exists():
        raise FileNotFoundError(f"Knowledge base directory not found: {base_path}")
    if not base_path.is_dir():
        raise NotADirectoryError(f"Knowledge base is not a directory: {base_path}")

    documents: list[Document] = []
    folders = sorted(path for path in base_path.iterdir() if path.is_dir())

    for folder in folders:
        doc_type = folder.name
        for file_path in sorted(folder.rglob("*.md")):
            documents.append(
                Document(
                    page_content=file_path.read_text(encoding="utf-8"),
                    metadata={
                        "doc_type": doc_type,
                        "source": str(file_path),
                        "file_name": file_path.name,
                    },
                )
            )

    return documents


def validate_constitution_chunks(chunks: list[LegalChunk]) -> list[LegalChunk]:
    """Validate extracted constitutional chunks before they are indexed."""
    if not chunks:
        raise ValueError("Constitution extraction produced no legal chunks.")

    seen_articles: set[tuple[str, str]] = set()
    errors: list[str] = []
    for index, chunk in enumerate(chunks, start=1):
        metadata = chunk.metadata
        article_key = (
            metadata.chapter_number,
            metadata.article_number,
            metadata.clause_number or "",
        )
        if metadata.chapter_number == "Unknown":
            errors.append(f"chunk {index} has no recognized chapter")
        if article_key in seen_articles:
            errors.append(
                f"duplicate article metadata: chapter {metadata.chapter_number}, "
                f"article {metadata.article_number}, clause "
                f"{metadata.clause_number or 'none'}"
            )
        seen_articles.add(article_key)
        if "\ufffd" in chunk.text:
            errors.append(f"chunk {index} contains replacement characters")
        if len(chunk.text) > 30_000:
            errors.append(
                f"chunk {index} is {len(chunk.text)} characters; "
                "split oversized articles before indexing"
            )

    if errors:
        details = "\n".join(f"- {error}" for error in errors[:20])
        suffix = "" if len(errors) <= 20 else f"\n- ...and {len(errors) - 20} more"
        raise ValueError(f"Invalid constitutional chunks:\n{details}{suffix}")
    return chunks


def split_article_body(
    body_lines: list[str],
) -> list[tuple[str | None, str]]:
    """Split an article into numbered clauses while retaining clause content."""
    clause_pattern = re.compile(
        r"^\s*(?:\*\*(\d+)\.\*\*\s+|(\d+)\.\s+(?![a-z]\.))",
        re.IGNORECASE,
    )
    sections: list[tuple[str | None, list[str]]] = []
    current_clause: str | None = None
    current_lines: list[str] = []

    for line in body_lines:
        match = clause_pattern.match(line)
        if match:
            if current_lines:
                sections.append((current_clause, current_lines))
            current_clause = match.group(1) or match.group(2)
            current_lines = [line]
        else:
            current_lines.append(line)

    if current_lines:
        sections.append((current_clause, current_lines))
    return [
        (clause_number, "\n".join(lines).strip())
        for clause_number, lines in sections
        if "\n".join(lines).strip()
    ]


def process_constitution_rag(pdf_path: str) -> list[LegalChunk]:
    """Convert the Constitution and create article/clause-oriented chunks

    with context headers, page tracking, and structured metadata.
    """
    # 1. Convert and save the full Markdown document for reference/chapter extraction
    md_out_path = str(Path(pdf_path).with_suffix(".md"))
    convert_pdf_to_markdown(pdf_path, md_out_path)

    # 2. Extract layout-aware page chunks to preserve exact page numbers
    page_data = convert_pdf_to_page_chunks(pdf_path)

    chunks: list[LegalChunk] = []
    current_chapter_num = "Unknown"
    current_chapter_title = "General Provisions"
    current_article: dict[str, Any] | None = None

    chapter_pattern = re.compile(
        r"^\s*#{1,6}\s+\*{0,2}CHAPTER\s+(\d+)\.\s+(.+?)\*{0,2}\s*$",
        re.IGNORECASE,
    )
    article_pattern = re.compile(
        r"^\s*#{1,6}\s+\*{0,2}(\d+)\.\s+(.+?)\*{0,2}\s*$",
        re.IGNORECASE,
    )
    cross_ref_pattern = re.compile(
        r"(?:article|articles|clause|clauses)\s+(\d+)", re.IGNORECASE
    )

    def flush_article() -> None:
        nonlocal current_article
        if current_article is None:
            return

        body_lines = current_article.pop("_body_lines")
        header = current_article.pop("_header")
        metadata = current_article["metadata"]
        body = "\n".join(body_lines).strip()
        if body:
            metadata["cross_references"] = sorted(
                set(cross_ref_pattern.findall(body))
            )
            for clause_number, clause_text in split_article_body(body_lines):
                chunk_metadata = {
                    **metadata,
                    "clause_number": clause_number,
                }
                chunks.append(
                    LegalChunk.model_validate(
                        {
                            "text": header + clause_text,
                            "metadata": chunk_metadata,
                        }
                    )
                )
        current_article = None

    for page_info in page_data:
        page_num = page_info["metadata"].get("page_number", 1)
        page_text = page_info.get("text", "")

        for line in page_text.split("\n"):
            line_str = line.strip()
            if not line_str:
                continue

            chap_match = chapter_pattern.match(line_str)
            if chap_match:
                flush_article()
                current_chapter_num = chap_match.group(1)
                current_chapter_title = chap_match.group(2).strip()
                continue

            art_match = article_pattern.match(line_str)
            if art_match:
                flush_article()
                art_num = art_match.group(1)
                art_title = art_match.group(2).strip()
                refs = list(set(cross_ref_pattern.findall(line_str)))
                context_header = (
                    f"Chapter {current_chapter_num}: {current_chapter_title}\n"
                    f"Article {art_num}: {art_title}\n\n"
                )
                current_article = {
                    "_header": context_header,
                    "_body_lines": [],
                    "metadata": {
                        "chapter_number": current_chapter_num,
                        "chapter_title": current_chapter_title,
                        "article_number": art_num,
                        "article_title": art_title,
                        "page": page_num,
                        "cross_references": refs,
                        "source": pdf_path,
                    },
                }
                continue

            if current_article is not None:
                current_article["_body_lines"].append(line_str)

    flush_article()
    return chunks