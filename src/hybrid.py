"""Rank-based reciprocal-rank fusion for heterogeneous retrievers."""


def reciprocal_rank_fusion(
    results: dict[str, list[dict]], rrf_k: int = 60, limit: int | None = None
) -> list[dict]:
    if rrf_k <= 0:
        raise ValueError("rrf_k must be positive")
    fused: dict[str, dict] = {}
    for backend, hits in results.items():
        for rank, hit in enumerate(hits, 1):
            chunk_id = str(hit["chunk_id"])
            item = fused.setdefault(
                chunk_id,
                {**hit, "backend_scores": {}, "backend_ranks": {}, "fusion_score": 0.0},
            )
            item["backend_scores"][backend] = float(hit.get("score", 0.0))
            item["backend_ranks"][backend] = rank
            item["fusion_score"] += 1 / (rrf_k + rank)
    ranked = sorted(fused.values(), key=lambda item: (-item["fusion_score"], item["chunk_id"]))
    for rank, item in enumerate(ranked, 1):
        item["final_rank"] = rank
    return ranked[:limit] if limit is not None else ranked
