"""Dense, BM25, and RRF hybrid retrieval orchestration."""

from src.bm25 import BM25Retriever
from src.decision import DecisionUnavailable, JevDecisionProvider
from src.hybrid import reciprocal_rank_fusion


class FilingSearch:
    def __init__(self, dense_retriever, collection: str, chunks: list[dict]):
        self.dense = dense_retriever
        self.collection = collection
        self.bm25 = BM25Retriever(chunks)

    def search(
        self,
        query: str,
        top_k: int = 5,
        mode: str = "Hybrid",
        candidate_k: int = 20,
        reranker=None,
        jev: JevDecisionProvider | None = None,
    ) -> list[dict]:
        dense_hits = self.dense.search(self.collection, query, candidate_k) if mode in {"Dense", "Hybrid"} else []
        bm25_hits = self.bm25.search(query, candidate_k) if mode in {"BM25", "Hybrid"} else []
        if mode == "Dense":
            hits = dense_hits
        elif mode == "BM25":
            hits = bm25_hits
        else:
            hits = reciprocal_rank_fusion({"dense": dense_hits, "bm25": bm25_hits}, limit=candidate_k)
        if jev is not None:
            try:
                scores = jev.relevance_scores(query, hits)
                hits = [{**hit, "jev_relevance": scores.get(str(hit["chunk_id"]), 0.0)} for hit in hits]
                hits.sort(key=lambda item: item["jev_relevance"], reverse=True)
            except DecisionUnavailable:
                scores = None
        elif reranker is not None:
            try:
                reranked = reranker.rerank(query, hits, top_k)
            except Exception:  # noqa: BLE001 - optional reranking must preserve retrieval.
                reranked = None
            if reranked is not None:
                return reranked
        for rank, hit in enumerate(hits, 1):
            hit["final_rank"] = rank
        return hits[:top_k]
