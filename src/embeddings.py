"""Local Sentence Transformer embeddings."""

from sentence_transformers import SentenceTransformer


class Embeddings:
    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5"):
        self.model = SentenceTransformer(model_name)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        # Filing chunks are embedded once when the index is built.
        return self.model.encode(texts, normalize_embeddings=True, show_progress_bar=True).tolist()

    def embed_query(self, query: str) -> list[float]:
        # Query embedding is generated for each search; cosine distance finds related chunks.
        return self.model.encode(query, normalize_embeddings=True).tolist()
