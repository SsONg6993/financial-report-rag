"""BM25S lexical retrieval adapter."""

import bm25s


class BM25Retriever:
    def __init__(self, chunks: list[dict]):
        self.chunks = chunks
        self.corpus_tokens = bm25s.tokenize([item["text"] for item in chunks], stopwords="en")
        self.index = bm25s.BM25(method="lucene", k1=1.2, b=0.75)
        if chunks:
            self.index.index(self.corpus_tokens, show_progress=False)

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        if not self.chunks or not query.strip():
            return []
        query_tokens = bm25s.tokenize([query], stopwords="en")
        indices, scores = self.index.retrieve(
            query_tokens, k=min(top_k, len(self.chunks)), show_progress=False
        )
        results = []
        for rank, (index, score) in enumerate(zip(indices[0], scores[0]), 1):
            if float(score) <= 0:
                continue
            results.append(
                {
                    **self.chunks[int(index)],
                    "score": float(score),
                    "backend": "bm25",
                    "backend_rank": rank,
                }
            )
        return results
