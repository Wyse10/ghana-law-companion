from __future__ import annotations

import json
import os

from src.config import (
    DEFAULT_MD_PATH,
    DEFAULT_PDF_PATH,
    KNOWLEDGE_BASE_DIR,
    PROCESSED_CHUNKS_PATH,
    VECTOR_DB_PATH,
)
from src.ingestion.legal_chunker import fetch_documents, process_constitution_rag
from src.ingestion.pdf_converter import (
    convert_pdf_to_markdown,
    extract_markdown_chapters,
)
from src.vectorstore.embedder import index_chunks
from src.vectorstore.store import init_vector_store


def load_and_index_data() -> None:
    """Convert, chunk, embed, and index the constitution for later querying."""
    print("--- Starting one-time Legal RAG data loading ---")

    os.makedirs(os.path.dirname(DEFAULT_MD_PATH), exist_ok=True)
    os.makedirs(os.path.dirname(PROCESSED_CHUNKS_PATH), exist_ok=True)

    if not os.path.exists(DEFAULT_PDF_PATH):
        raise FileNotFoundError(
            f"Raw PDF file not found at '{DEFAULT_PDF_PATH}'. "
            "Place Ghana_1996-en.pdf in data/raw/ and try again."
        )

    print("\n1. Converting PDF to Markdown...")
    markdown_text = convert_pdf_to_markdown(DEFAULT_PDF_PATH, DEFAULT_MD_PATH)
    print(f"Full Markdown file generated at: '{DEFAULT_MD_PATH}'.")

    print("\n2. Extracting Constitution chapters...")
    chapters = extract_markdown_chapters(markdown_text)
    chapters_dir = os.path.join(os.path.dirname(DEFAULT_MD_PATH), "chapters")
    os.makedirs(chapters_dir, exist_ok=True)
    for chapter_number, chapter_text in chapters.items():
        chapter_path = os.path.join(
            chapters_dir, f"chapter_{chapter_number:02d}.md"
        )
        with open(chapter_path, "w", encoding="utf-8") as chapter_file:
            chapter_file.write(chapter_text + "\n")
    print(f"Extracted {len(chapters)} chapters into '{chapters_dir}'.")

    print("\n3. Loading Markdown source documents...")
    documents = fetch_documents(KNOWLEDGE_BASE_DIR)
    print(f"Loaded {len(documents)} documents from '{KNOWLEDGE_BASE_DIR}'.")

    print("\n4. Creating structural legal chunks...")
    legal_chunks = process_constitution_rag(DEFAULT_PDF_PATH)
    print(f"Total structural chunks generated: {len(legal_chunks)}")

    print(f"\n5. Saving chunks to '{PROCESSED_CHUNKS_PATH}'...")
    with open(PROCESSED_CHUNKS_PATH, "w", encoding="utf-8") as json_file:
        json.dump(legal_chunks, json_file, indent=2, ensure_ascii=False)

    print("\n6. Initializing local vector store...")
    init_vector_store(db_path=VECTOR_DB_PATH)

    print("\n7. Embedding and indexing chunks...")
    vector_store = index_chunks(
        json_path=PROCESSED_CHUNKS_PATH,
        db_path=VECTOR_DB_PATH,
    )
    print(f"Indexed point count: {len(vector_store.payloads)}")
    print("\nData loading complete. You can now run main.py.")


if __name__ == "__main__":
    load_and_index_data()
