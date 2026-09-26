"""Actual retrieval and decision evaluation metrics; no placeholder scores."""

import json
import statistics
import time
from pathlib import Path


def evaluate_rankings(rankings: list[dict], ks: tuple[int, ...] = (1, 3, 5)) -> dict[str, float]:
    if not rankings:
        return {**{f"recall_at_{k}": 0.0 for k in ks}, "mrr": 0.0, "latency_ms_mean": 0.0}
    metrics: dict[str, float] = {}
    for k in ks:
        recalls = []
        for row in rankings:
            relevant = set(row["relevant"])
            retrieved = set(row["retrieved"][:k])
            if row.get("granularity") == "section":
                recalls.append(1.0 if relevant & retrieved else 0.0)
            else:
                recalls.append(len(relevant & retrieved) / len(relevant) if relevant else 0.0)
        metrics[f"recall_at_{k}"] = sum(recalls) / len(recalls)
    reciprocal_ranks = []
    for row in rankings:
        relevant = set(row["relevant"])
        rank = next((index for index, item in enumerate(row["retrieved"], 1) if item in relevant), None)
        reciprocal_ranks.append(1 / rank if rank else 0.0)
    metrics["mrr"] = sum(reciprocal_ranks) / len(reciprocal_ranks)
    metrics["latency_ms_mean"] = statistics.mean(float(row["latency_ms"]) for row in rankings)
    return metrics


def load_evaluation_dataset(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def evaluation_dataset_compatible(ticker: str, filing: dict, dataset_name: str) -> bool:
    if dataset_name == "aapl_2025_questions.jsonl":
        return ticker.upper() == "AAPL" and int(filing.get("year", 0)) == 2025
    return False


def run_retrieval_evaluation(searcher, cases: list[dict], mode: str, top_k: int = 5) -> dict:
    rankings = []
    unanswerable_count = 0
    for case in cases:
        keywords = [keyword.lower() for keyword in case.get("expected_keywords", [])]
        expected_section = str(case.get("expected_section") or "").lower()
        relevant = {
            chunk["chunk_id"]
            for chunk in searcher.bm25.chunks
            if (not expected_section or str(chunk.get("section", "")).lower() == expected_section)
            and keywords
            and any(keyword in chunk.get("text", "").lower() for keyword in keywords)
        }
        started = time.perf_counter()
        hits = searcher.search(case["question"], top_k=top_k, mode=mode)
        latency_ms = (time.perf_counter() - started) * 1000
        if not case.get("answerable", True):
            unanswerable_count += 1
            continue
        rankings.append(
            {
                "question_id": case["id"],
                "relevant": relevant,
                "retrieved": [hit["chunk_id"] for hit in hits],
                "latency_ms": latency_ms,
                "granularity": "exact_chunk",
            }
        )
    return {
        "mode": mode,
        "case_count": len(cases),
        "evaluated_answerable_count": len(rankings),
        "unanswerable_not_scored": unanswerable_count,
        "qrel_granularity": "keyword-derived chunk",
        **evaluate_rankings(rankings),
    }


def evaluate_router(provider, cases: list[dict]) -> dict[str, float]:
    if not cases:
        return {"accuracy": 0.0, "failure_rate": 0.0, "latency_ms_mean": 0.0}
    correct = 0
    failures = 0
    latencies = []
    for case in cases:
        started = time.perf_counter()
        try:
            decision = provider.route(case["query"])
            correct += decision.value.value == case["expected"]
        except Exception:  # noqa: BLE001 - provider failures are an evaluated outcome.
            failures += 1
        latencies.append((time.perf_counter() - started) * 1000)
    return {
        "accuracy": correct / len(cases),
        "failure_rate": failures / len(cases),
        "latency_ms_mean": statistics.mean(latencies),
    }
