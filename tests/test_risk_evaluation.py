from src.evaluation import (
    evaluate_rankings,
    evaluate_router,
    evaluation_dataset_compatible,
    run_retrieval_evaluation,
)
from src.risk import classify_risks


def test_risk_classification_keeps_evidence_linked():
    chunks = [
        {"chunk_id": "r1", "section": "Item 1A", "text": "Cybersecurity incidents may disrupt systems and expose customer data."},
        {"chunk_id": "r2", "section": "Item 1A", "text": "Foreign exchange volatility and inflation may affect results."},
    ]

    risks = classify_risks(chunks)

    assert risks[0].chunk_id == "r1"
    assert "CYBERSECURITY" in {item.category for item in risks}
    assert all(item.evidence for item in risks)


def test_evaluation_computes_recall_mrr_latency_without_fabricating_results():
    rankings = [
        {"question_id": "q1", "relevant": {"a"}, "retrieved": ["a", "b"], "latency_ms": 10.0},
        {"question_id": "q2", "relevant": {"c"}, "retrieved": ["x", "c"], "latency_ms": 30.0},
    ]

    metrics = evaluate_rankings(rankings, ks=(1, 2, 5))

    assert metrics["recall_at_1"] == 0.5
    assert metrics["recall_at_2"] == 1.0
    assert metrics["mrr"] == 0.75
    assert metrics["latency_ms_mean"] == 20.0


def test_section_level_recall_counts_any_relevant_chunk_as_success():
    metrics = evaluate_rankings(
        [
            {
                "question_id": "q1",
                "relevant": {"section-chunk-1", "section-chunk-2", "section-chunk-3"},
                "retrieved": ["section-chunk-2"],
                "latency_ms": 1.0,
                "granularity": "section",
            }
        ],
        ks=(1,),
    )

    assert metrics["recall_at_1"] == 1.0


def test_router_evaluation_measures_accuracy_and_failures():
    class Provider:
        def route(self, query):
            from src.decision import Decision, DecisionSource
            from src.router import QueryIntent

            if query == "broken":
                raise RuntimeError("offline")
            return Decision(QueryIntent.METRIC_LOOKUP, 1.0, DecisionSource.DETERMINISTIC)

    result = evaluate_router(
        Provider(),
        [
            {"query": "revenue", "expected": "METRIC_LOOKUP"},
            {"query": "broken", "expected": "FILING_RAG"},
        ],
    )

    assert result["accuracy"] == 0.5
    assert result["failure_rate"] == 0.5


def test_retrieval_qrels_require_keyword_support_within_expected_section():
    class Searcher:
        class Lexical:
            def __init__(self):
                self.chunks = [
                    {"chunk_id": "wrong", "section": "Item 8", "text": "Share repurchases"},
                    {"chunk_id": "right", "section": "Item 8", "text": "Net income was 10"},
                ]

        def __init__(self):
            self.bm25 = self.Lexical()

        def search(self, *args, **kwargs):
            return [self.bm25.chunks[0]]

    result = run_retrieval_evaluation(
        Searcher(),
        [{"id": "q", "question": "net income", "expected_section": "Item 8", "expected_keywords": ["net income"]}],
        "BM25",
        top_k=1,
    )

    assert result["recall_at_1"] == 0.0
    assert result["qrel_granularity"] == "keyword-derived chunk"


def test_aapl_dataset_rejects_wrong_ticker_or_year():
    assert evaluation_dataset_compatible("AAPL", {"year": 2025}, "aapl_2025_questions.jsonl")
    assert not evaluation_dataset_compatible("MSFT", {"year": 2025}, "aapl_2025_questions.jsonl")
    assert not evaluation_dataset_compatible("AAPL", {"year": 2024}, "aapl_2025_questions.jsonl")
