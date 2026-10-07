import json
import os
import sys

# Ensure project root is in the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config import DEFAULT_MD_PATH, DEFAULT_PDF_PATH
from src.ingestion.legal_chunker import process_constitution_rag
from src.ingestion.pdf_converter import (
    convert_pdf_to_markdown,
    extract_markdown_chapters,
)


def main():
    print("--- Starting Legal RAG Processing Pipeline ---")

    # Define processed chunks output path (data/processed/constitution_chunks.json)
    processed_dir = os.path.join(
        os.path.dirname(DEFAULT_MD_PATH), "..", "processed"
    )
    processed_chunks_path = os.path.join(
        processed_dir, "constitution_chunks.json"
    )

    # Ensure output directories exist
    os.makedirs(os.path.dirname(DEFAULT_MD_PATH), exist_ok=True)
    os.makedirs(processed_dir, exist_ok=True)

    if not os.path.exists(DEFAULT_PDF_PATH):
        print(f"Error: Raw PDF file not found at '{DEFAULT_PDF_PATH}'.")
        print(
            "Please ensure 'Ghana_1996-en.pdf' is inside the 'data/raw/' folder."
        )
        return

    # 1. Convert raw PDF into layout-aware Markdown (pymupdf4llm)
    print("\n1. Converting PDF to Markdown (pymupdf4llm)...")
    md_text = convert_pdf_to_markdown(DEFAULT_PDF_PATH, DEFAULT_MD_PATH)
    print(f"Full Markdown file generated at: '{DEFAULT_MD_PATH}'.")

    # 2. Extract every chapter into standalone Markdown files (supports targeted retrieval)
    print("\n2. Extracting Constitution chapters...")
    chapters = extract_markdown_chapters(md_text)
    chapters_dir = os.path.join(
        os.path.dirname(DEFAULT_MD_PATH), "chapters"
    )
    os.makedirs(chapters_dir, exist_ok=True)

    for chapter_number, chapter_text in chapters.items():
        chapter_path = os.path.join(
            chapters_dir, f"chapter_{chapter_number:02d}.md"
        )
        with open(chapter_path, "w", encoding="utf-8") as chapter_file:
            chapter_file.write(chapter_text + "\n")
    print(f"Extracted {len(chapters)} chapters into '{chapters_dir}'.")

    # 3. Structural Legal Chunker (Primary Strategy: Article/Clause level + Context Headers + Metadata)
    print(
        "\n3. Executing Structural Legal Chunker (Articles, Context Headers & Metadata)..."
    )
    legal_chunks = process_constitution_rag(DEFAULT_PDF_PATH)
    print(f"Total Structural Chunks Generated: {len(legal_chunks)}")

    # 4. Save processed structural chunks to JSON for Vector DB Ingestion
    print(
        f"\n4. Saving processed chunks to '{processed_chunks_path}'..."
    )
    with open(
        processed_chunks_path, "w", encoding="utf-8"
    ) as json_file:
        json.dump(legal_chunks, json_file, indent=2, ensure_ascii=False)
    print("Chunks successfully saved to disk.")

    # Display sample output for verification
    if legal_chunks:
        print("\n" + "=" * 50)
        print("SAMPLE STRUCTURAL CHUNK PAYLOAD")
        print("=" * 50)
        print("TEXT (Payload sent to Embeddings Model):")
        print(legal_chunks[0]["text"])
        print("-" * 50)
        print("METADATA (Payload indexed in Vector Database):")
        print(json.dumps(legal_chunks[0]["metadata"], indent=2))
        print("=" * 50)


if __name__ == "__main__":
    main()