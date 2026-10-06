from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from langchain_core.documents import Document

from .pdf_converter import convert_pdf_to_markdown


def split_markdown_by_headers(markdown: str) -> list[Document]:
    """Split Markdown into documents, starting a new document at each header."""
    matches = list(re.finditer(r"(?m)^#{1,6}\s+.+$", markdown))
    if not matches:
        return [Document(page_content=markdown)] if markdown.strip() else []

    documents: list[Document] = []
    if markdown[: matches[0].start()].strip():
        documents.append(Document(page_content=markdown[: matches[0].start()].strip()))

    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown)
        content = markdown[match.start() : end].strip()
        if content:
            documents.append(
                Document(
                    page_content=content,
                    metadata={"header": match.group(0).strip()},
                )
            )
    return documents


def process_constitution_rag(pdf_path: str) -> list[dict[str, Any]]:
    """Convert the Constitution and create article/clause-oriented chunks."""
    markdown = convert_pdf_to_markdown(
        pdf_path,
        str(Path(pdf_path).with_suffix(".md")),
    )
    documents = split_markdown_by_headers(markdown)
    return [
        {
            "text": document.page_content,
            "metadata": {
                **document.metadata,
                "source": pdf_path,
            },
        }
        for document in documents
    ]
