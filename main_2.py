import json
import os
import sys

# Ensure project root is in the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config import (
    DEFAULT_MD_PATH,
    DEFAULT_PDF_PATH,
    KNOWLEDGE_BASE_DIR,
)
from src.ingestion.legal_chunker import fetch_documents, process_constitution_rag
from src.ingestion.pdf_converter import (
    convert_pdf_to_markdown,
    extract_markdown_chapters,
)

# Vector Store, Retrieval, and RAG Generation Imports
from src.vectorstore.store import init_vector_store
from src.vectorstore.embedder import index_chunks
from src.vectorstore.retriever import retrieve_relevant_context
from src.rag.generator import generate_legal_answer


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

    # 2. Extract Constitution chapters into standalone files
    print("\n2. Extracting Constitution chapters...")
    chapters = extract_markdown_chapters(md_text)
    chapters_dir = os.path.join(
        os.path.dirname(DEFAULT_MD_PATH), "chapters"
    )import json
import os
import sys

# Ensure project root is in the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config import (
    DEFAULT_MD_PATH,
    DEFAULT_PDF_PATH,
    KNOWLEDGE_BASE_DIR,
)
from src.ingestion.legal_chunker import fetch_documents, process_constitution_rag
from src.ingestion.pdf_converter import (
    convert_pdf_to_markdown,
    extract_markdown_chapters,
)

# New imports for Vector Store, Retrieval, and Generation
from src.vectorstore.store import init_vector_store
from src.vectorstore.embedder import index_chunks
from src.vectorstore.retriever import retrieve_relevant_context
from src.rag.generator import generate_legal_answer


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

    # 2. Extract every chapter into standalone Markdown files
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

    # 3. Load generated Markdown chunks as LangChain Documents
    print("\n3. Loading Markdown chunks for retrieval...")
    documents = fetch_documents(KNOWLEDGE_BASE_DIR)
    print(f"Loaded {len(documents)} documents from '{KNOWLEDGE_BASE_DIR}'.")

    # 4. Structural Legal Chunker (Primary Strategy: Article/Clause level + Context Headers + Metadata)
    print(
        "\n4. Executing Structural Legal Chunker (Articles, Context Headers & Metadata)..."
    )
    legal_chunks = process_constitution_rag(DEFAULT_PDF_PATH)
    print(f"Total Structural Chunks Generated: {len(legal_chunks)}")

    # 5. Save processed structural chunks to JSON for Vector DB Ingestion
    print(
        f"\n5. Saving processed chunks to '{processed_chunks_path}'..."
    )
    with open(
        processed_chunks_path, "w", encoding="utf-8"
    ) as json_file:
        json.dump(legal_chunks, json_file, indent=2, ensure_ascii=False)
    print("Chunks successfully saved to disk.")

    # ------------------------------------------------------------------
    # PHASE 2: Vector DB Ingestion & Indexing
    # ------------------------------------------------------------------
    print("\n6. Initializing Qdrant Vector Database Store...")
    db_path = "./data/qdrant_db"
    vector_store = init_vector_store(db_path=db_path)

    print("\n7. Embedding and Indexing Chunks into Qdrant (using BAAI/bge-base-en-v1.5)...")
    vector_store = index_chunks(
        json_path=processed_chunks_path,
        db_path=db_path,
    )

    # ------------------------------------------------------------------
    # PHASE 3: Testing End-to-End Retrieval & RAG Generation
    # ------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("RUNNING END-TO-END RAG TEST QUERY")
    print("=" * 60)

    test_query = "What are the fundamental human rights regarding personal liberty under the 1992 Constitution?"
    print(f"Test Query: '{test_query}'\n")

    # Retrieve context using local BAAI/bge-base-en-v1.5 embeddings
    retrieved_contexts = retrieve_relevant_context(
        query=test_query,
        qdrant_client=vector_store,
        top_k=3
    )

    print(f"Retrieved {len(retrieved_contexts)} relevant legal context chunks:")
    for idx, ctx in enumerate(retrieved_contexts, 1):
        print(f"\n--- [Chunk {idx}] Score: {ctx['score']:.4f} ---")
        print(f"Source: Chapter {ctx.get('chapter_number')}, Article {ctx.get('article_number')}")
        print(f"Text Snippet: {ctx['text'][:150]}...")

    # Generate answer with LLM
    print("\nGenerating LLM response using retrieved legal context...")
    answer = generate_legal_answer(query=test_query, contexts=retrieved_contexts)

    print("\n" + "=" * 60)
    print("GENERATED LEGAL ANSWER")
    print("=" * 60)
    print(answer)
    print("=" * 60)


if __name__ == "__main__":
    main()
    os.makedirs(chapters_dir, exist_ok=True)

    for chapter_number, chapter_text in chapters.items():
        chapter_path = os.path.join(
            chapters_dir, f"chapter_{chapter_number:02d}.md"
        )
        with open(chapter_path, "w", encoding="utf-8") as chapter_file:
            chapter_file.write(chapter_text + "\n")
    print(f"Extracted {len(chapters)} chapters into '{chapters_dir}'.")

    # 3. Load generated Markdown chunks as LangChain Documents
    print("\n3. Loading Markdown chunks for retrieval...")
    documents = fetch_documents(KNOWLEDGE_BASE_DIR)
    print(f"Loaded {len(documents)} documents from '{KNOWLEDGE_BASE_DIR}'.")

    # 4. Execute Legal Chunker (Article/Clause level + Context Headers + Metadata)
    print(
        "\n4. Executing Structural Legal Chunker (Articles, Context Headers & Metadata)..."
    )
    legal_chunks = process_constitution_rag(DEFAULT_PDF_PATH)
    print(f"Total Structural Chunks Generated: {len(legal_chunks)}")

    # 5. Save processed structural chunks to JSON for Vector DB Ingestion
    print(
        f"\n5. Saving processed chunks to '{processed_chunks_path}'..."
    )
    with open(
        processed_chunks_path, "w", encoding="utf-8"
    ) as json_file:
        json.dump(legal_chunks, json_file, indent=2, ensure_ascii=False)
    print("Chunks successfully saved to disk.")

    # ------------------------------------------------------------------
    # PHASE 2: Vector DB Ingestion & Indexing
    # ------------------------------------------------------------------
    print("\n6. Initializing Qdrant Vector Database Store...")
    db_path = "./data/qdrant_db"
    qdrant_client = init_vector_store(db_path=db_path)

    print("\n7. Embedding and Indexing Chunks into Qdrant (using BAAI/bge-base-en-v1.5)...")
    index_chunks(
        json_path=processed_chunks_path,
        db_path=db_path,
    )

    # Verify Qdrant points count
    if qdrant_client.collection_exists("ghana_constitution"):
        info = qdrant_client.get_collection("ghana_constitution")
        print(f"Indexed Point Count in Qdrant: {info.points_count}")

    # ------------------------------------------------------------------
    # PHASE 3: Testing End-to-End Retrieval & RAG Generation
    # ------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("RUNNING END-TO-END RAG TEST QUERY")
    print("=" * 60)

    test_query = "What are the fundamental human rights regarding personal liberty under the 1992 Constitution?"
    print(f"Test Query: '{test_query}'\n")

    # Retrieve context using local BAAI/bge-base-en-v1.5 embeddings
    retrieved_contexts = retrieve_relevant_context(
        query=test_query,
        qdrant_client=qdrant_client,
        top_k=3
    )

    print(f"Retrieved {len(retrieved_contexts)} relevant legal context chunks:")
    for idx, ctx in enumerate(retrieved_contexts, 1):
        print(f"\n--- [Chunk {idx}] Score: {ctx['score']:.4f} ---")
        print(f"Source: Chapter {ctx.get('chapter_number')}, Article {ctx.get('article_number')}")
        print(f"Text Snippet: {ctx['text'][:150]}...")

    # Generate answer with LLM via Groq API
    print("\nGenerating LLM response using retrieved legal context...")
    answer = generate_legal_answer(query=test_query, contexts=retrieved_contexts)

    print("\n" + "=" * 60)
    print("GENERATED LEGAL ANSWER")
    print("=" * 60)
    print(answer)
    print("=" * 60)


if __name__ == "__main__":
    main()