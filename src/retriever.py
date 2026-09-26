"""One local Qdrant collection per filing and embedding model."""

import hashlib
from pathlib import Path

from qdrant_client import QdrantClient, models

INDEX_SCHEMA_VERSION = 2


def collection_name(filing: dict, model_name: str) -> str:
    key = f"v{INDEX_SCHEMA_VERSION}:{filing['ticker']}:{filing['accession_number']}:{model_name}"
    return f"filing_v{INDEX_SCHEMA_VERSION}_" + hashlib.sha256(key.encode()).hexdigest()[:20]


class Retriever:
    def __init__(self, embeddings, store_dir: Path = Path("data/vector_store"), client=None):
        store_dir.mkdir(parents=True, exist_ok=True)
        self.client = client or QdrantClient(path=str(store_dir))
        self.embeddings = embeddings

    def has_index(self, name: str) -> bool:
        return self.client.collection_exists(name)

    def build_index(self, name: str, chunks: list[dict]) -> bool:
        if self.has_index(name):
            return False
        if not chunks:
            raise ValueError("The filing did not produce any text chunks.")
        vectors = self.embeddings.embed_documents([chunk["text"] for chunk in chunks])
        self.client.create_collection(
            collection_name=name,
            vectors_config=models.VectorParams(size=len(vectors[0]), distance=models.Distance.COSINE),
        )
        for start in range(0, len(chunks), 100):
            points = [
                models.PointStruct(id=i, vector=vectors[i], payload=chunks[i])
                for i in range(start, min(start + 100, len(chunks)))
            ]
            self.client.upsert(collection_name=name, points=points, wait=True)
        return True

    def search(self, name: str, query: str, top_k: int = 5) -> list[dict]:
        vector = self.embeddings.embed_query(query)
        results = self.client.query_points(
            collection_name=name, query=vector, limit=top_k, with_payload=True
        ).points
        return [
            {"score": hit.score, "backend": "dense", "backend_rank": rank, **hit.payload}
            for rank, hit in enumerate(results, 1)
        ]

    def all_chunks(self, name: str) -> list[dict]:
        chunks: list[dict] = []
        offset = None
        while True:
            points, offset = self.client.scroll(
                collection_name=name,
                limit=256,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            chunks.extend(dict(point.payload or {}) for point in points)
            if offset is None:
                break
        return sorted(chunks, key=lambda item: item.get("chunk_ordinal", 0))
