from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams

def create_qdrant_collection(client, collection_name, vector_size):
    client.recreate_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=vector_size, distance="Cosine")
    )

def upload_embeddings(client, collection_name, embeddings):
    points = [PointStruct(id=str(i), vector=embedding) for i, embedding in enumerate(embeddings)]
    client.upsert(collection_name=collection_name, points=points)