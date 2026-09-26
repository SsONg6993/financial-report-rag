"""Optional local CrossEncoder reranker."""


class CrossEncoderReranker:
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        from sentence_transformers import CrossEncoder

        self.model_name = model_name
        self.model = CrossEncoder(model_name)

    def rerank(self, query: str, hits: list[dict], top_k: int) -> list[dict]:
        if not hits:
            return []
        scores = self.model.predict([(query, hit["text"]) for hit in hits])
        ranked = []
        for hit, score in zip(hits, scores):
            ranked.append({**hit, "reranker_score": float(score)})
        ranked.sort(key=lambda item: item["reranker_score"], reverse=True)
        for rank, hit in enumerate(ranked, 1):
            hit["final_rank"] = rank
        return ranked[:top_k]
