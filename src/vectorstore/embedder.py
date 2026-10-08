import json
from fastembed import TextEmbedding

MODEL_NAME = "BAAI/bge-base-en-v1.5"
from .store import LocalVectorStore


def index_chunks(
    json_path: str, db_path: str = "./data/qdrant_db"
) -> LocalVectorStore:
    with open(json_path, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    documents = [c["text"] for c in chunks]
    payloads = [
        {**chunk["metadata"], "text": chunk["text"]}
        for chunk in chunks
    ]

    print(f"Embedding and indexing {len(chunks)} chunks locally (FREE)...")
    model = TextEmbedding(model_name=MODEL_NAME)
    vectors = [vector.tolist() for vector in model.embed(documents)]
    store = LocalVectorStore(db_path)
    store.reset()
    store.add(vectors, payloads)

    print("Indexing complete!")
    return store
