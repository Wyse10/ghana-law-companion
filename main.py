import os
import sys

# Ensure project root is in the Python path
sys.path.insert(
    0, os.path.dirname(os.path.abspath(__file__))
)

# Your existing imports follow below:
from src.config import DEFAULT_MD_PATH, DEFAULT_PDF_PATH
from src.ingestion.legal_chunker import (
    process_constitution_rag,
    split_markdown_by_headers,
)
from src.ingestion.pdf_converter import (
    convert_pdf_to_markdown,
    extract_markdown_section,
)


def main():
    print("--- Starting Legal RAG Processing Pipeline ---")

    # Ensure output directory exists
    os.makedirs(os.path.dirname(DEFAULT_MD_PATH), exist_ok=True)

    if not os.path.exists(DEFAULT_PDF_PATH):
        print(f"Error: Raw PDF file not found at '{DEFAULT_PDF_PATH}'.")
        print("Please place 'Ghana_1996-en.pdf' inside the 'data/raw/' folder.")
        return

    # 1. Approach B: Convert PDF to Markdown
    print("\n1. Converting PDF to Markdown (pymupdf4llm)...")
    md_text = convert_pdf_to_markdown(DEFAULT_PDF_PATH, DEFAULT_MD_PATH)
    print(f"Markdown file successfully generated at '{DEFAULT_MD_PATH}'.")

    # 2. Strategy Option 2: Targeted Extraction Example (Chapter 5)
    print("\n2. Executing Option 2: Extracting Chapter 5 (Human Rights)...")
    chapter_5_md = extract_markdown_section(
        md_text, start_header="# CHAPTER 5", end_header="# CHAPTER 6"
    )
    print(
        f"Extracted Chapter 5 snippet length: {len(chapter_5_md)} characters."
    )

    # 3. Strategy Option 1 with Approach B: Markdown Header Splitter
    print("\n3. Executing Option 1: Header-based Chunking...")
    header_docs = split_markdown_by_headers(md_text)
    print(f"Total Header Chunks Generated: {len(header_docs)}")

    # 4. Advanced Structural Legal Chunker with Metadata & Context Headers
    print("\n4. Executing Structural Legal Chunker (Articles & Clauses)...")
    legal_chunks = process_constitution_rag(DEFAULT_PDF_PATH)
    print(
        f"Total Legal Chunks Generated with Metadata: {len(legal_chunks)}"
    )

    if legal_chunks:
        print("\n--- Sample Generated Chunk ---")
        print("Text Payload:")
        print(legal_chunks[0]["text"])
        print("Metadata Payload:")
        print(legal_chunks[0]["metadata"])


if __name__ == "__main__":
    main()