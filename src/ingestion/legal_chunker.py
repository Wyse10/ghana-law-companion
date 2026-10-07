from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .pdf_converter import (
    convert_pdf_to_markdown,
    convert_pdf_to_page_chunks,
)


def process_constitution_rag(pdf_path: str) -> list[dict[str, Any]]:
    """Convert the Constitution and create article/clause-oriented chunks

    with context headers, page tracking, and structured metadata.
    """
    # 1. Convert and save the full Markdown document for reference/chapter extraction
    md_out_path = str(Path(pdf_path).with_suffix(".md"))
    convert_pdf_to_markdown(pdf_path, md_out_path)

    # 2. Extract layout-aware page chunks to preserve exact page numbers
    page_data = convert_pdf_to_page_chunks(pdf_path)

    chunks: list[dict[str, Any]] = []
    current_chapter_num = "Unknown"
    current_chapter_title = "General Provisions"

    # Regex patterns for Ghana Constitution structural elements
    chapter_pattern = re.compile(
        r"#\s*CHAPTER\s+(\d+)[\.\s]*\n+(.+)", re.IGNORECASE
    )
    article_pattern = re.compile(
        r"(?:##\s*)?(\d+)\.\s+([^\n]+)", re.IGNORECASE
    )
    cross_ref_pattern = re.compile(
        r"(?:article|articles|clause|clauses)\s+(\d+)", re.IGNORECASE
    )

    for page_info in page_data:
        # PyMuPDF4LLM page index is 0-based; add 1 for 1-based page numbering
        page_num = page_info["metadata"].get("page", 0) + 1
        page_text = page_info.get("text", "")

        lines = page_text.split("\n")

        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue

            # Detect Chapter transition
            chap_match = chapter_pattern.search(line_str)
            if chap_match:
                current_chapter_num = chap_match.group(1)
                current_chapter_title = chap_match.group(2).strip()
                continue

            # Detect Article transition
            art_match = article_pattern.search(line_str)
            if art_match:
                art_num = art_match.group(1)
                art_title = art_match.group(2).strip()

                # Extract legal cross-references inside the line
                refs = list(set(cross_ref_pattern.findall(line_str)))

                # Context Header injected to ensure optimal vector embeddings
                context_header = (
                    f"Chapter {current_chapter_num}: {current_chapter_title}\n"
                    f"Article {art_num}: {art_title}\n\n"
                )

                chunks.append(
                    {
                        "text": context_header + line_str,
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
                )

    return chunks