from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams


def init_vector_store(db_path: str = "./data/qdrant_db") -> QdrantClient:
    """Initialize local Qdrant vector database store."""
    client = QdrantClient(path=db_path)
    collection_name = "ghana_constitution"

    # Recreate collection safely using modern qdrant-client syntax
    if client.collection_exists(collection_name):
        client.delete_collection(collection_name)

    client.create_collection(
        collection_name=collection_name
        vectors_config=VectorParams(
            size=768,  # Beijing Academy of AI-embedding-base dimension
            distance=Distance.COSINE,
        ),
    )
    return client