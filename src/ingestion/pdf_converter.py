from pathlib import Path
import re
from typing import Any
import pymupdf4llm


def convert_pdf_to_markdown(pdf_path: str, markdown_path: str) -> str:
    """Convert a PDF to Markdown and save the result to disk."""
    source_path = Path(pdf_path)
    output_path = Path(markdown_path)

    if not source_path.is_file():
        raise FileNotFoundError(f"PDF file not found: {source_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    markdown = pymupdf4llm.to_markdown(str(source_path))
    output_path.write_text(markdown, encoding="utf-8")
    return markdown


def convert_pdf_to_page_chunks(pdf_path: str) -> list[dict[str, Any]]:
    """Convert PDF to layout-aware page dictionaries (retaining page numbers)."""
    source_path = Path(pdf_path)
    if not source_path.is_file():
        raise FileNotFoundError(f"PDF file not found: {source_path}")
    return pymupdf4llm.to_markdown(str(source_path), page_chunks=True)


def extract_markdown_section(
    markdown: str, start_header: str, end_header: str
) -> str:
    """Return the Markdown section between two headers."""
    start = markdown.find(start_header)
    if start == -1:
        return ""

    end = markdown.find(end_header, start + len(start_header))
    return markdown[start:] if end == -1 else markdown[start:end]


def extract_markdown_chapters(markdown: str) -> dict[int, str]:
    """Extract every numbered chapter from converted Constitution Markdown."""
    chapter_pattern = re.compile(r"(?m)^#{1,6}\s+\**CHAPTER\s+(\d+)\.\s+.*$")
    matches = list(chapter_pattern.finditer(markdown))
    chapters: dict[int, str] = {}

    for index, match in enumerate(matches):
        end = (
            matches[index + 1].start()
            if index + 1 < len(matches)
            else len(markdown)
        )
        chapter_text = markdown[match.start() : end].strip()
        if chapter_text:
            chapters[int(match.group(1))] = chapter_text

    return chapters

def format_documents_to_chunks(
    documents: list[Document],
) -> list[dict[str, Any]]:
    """Standardize LangChain Document objects into dictionary chunks matching

    process_constitution_rag payload format.
    """
    return [
        {
            "text": doc.page_content,
            "metadata": {
                **doc.metadata,
                "chapter_number": "KB",
                "chapter_title": doc.metadata.get("doc_type", "General"),
                "article_number": "N/A",
                "article_title": doc.metadata.get("file_name", "Untitled"),
                "page": 1,
                "cross_references": [],
            },
        }
        for doc in documents
    ]