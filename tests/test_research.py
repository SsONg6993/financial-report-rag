from requests import ConnectionError

from src.decision import (
    DecisionEngine,
    DecisionSource,
    JevDecisionProvider,
    OllamaDecisionProvider,
)
from src.hybrid import reciprocal_rank_fusion
from src.llm import GenerationResult, generate_answer
from src.router import QueryIntent, route_query


def test_rrf_uses_ranks_and_preserves_backend_scores():
    dense = [
        {"chunk_id": "a", "score": 0.91, "text": "revenue"},
        {"chunk_id": "b", "score": 0.89, "text": "margin"},
    ]
    lexical = [
        {"chunk_id": "b", "score": 8.2, "text": "margin"},
        {"chunk_id": "c", "score": 7.4, "text": "risk"},
    ]

    hits = reciprocal_rank_fusion({"dense": dense, "bm25": lexical}, rrf_k=60)

    assert hits[0]["chunk_id"] == "b"
    assert hits[0]["backend_scores"] == {"dense": 0.89, "bm25": 8.2}
    assert hits[0]["backend_ranks"] == {"dense": 2, "bm25": 1}
    assert hits[0]["fusion_score"] > hits[1]["fusion_score"]


def test_query_router_prefers_deterministic_tools():
    assert route_query("What was revenue in 2025?") is QueryIntent.METRIC_LOOKUP
    assert route_query("What was revenue CAGR from 2022 to 2025?") is QueryIntent.CALCULATION
    assert route_query("Why did Services revenue grow?") is QueryIntent.FILING_RAG
    assert route_query("Compare Apple and Microsoft margins") is QueryIntent.PEER_COMPARISON
    assert route_query("Estimate a DCF value") is QueryIntent.VALUATION
    assert route_query("Classify the cybersecurity risks") is QueryIntent.RISK_ANALYSIS


def test_jev_route_is_typed_and_uses_documented_choice_response():
    class Response:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "model": "jev-1.13.0",
                "answers": {
                    "route": {
                        "type": "choice",
                        "choice": "VALUATION",
                        "confidence": 0.91,
                        "probabilities": {"VALUATION": 0.91},
                    }
                },
            }

    class Session:
        def post(self, *args, **kwargs):
            assert kwargs["timeout"] == 8.0
            assert kwargs["json"]["questions"]["route"]["type"] == "choice"
            return Response()

    provider = JevDecisionProvider("secret", session=Session(), timeout=8.0)
    decision = provider.route("Estimate the intrinsic value")

    assert decision.value is QueryIntent.VALUATION
    assert decision.confidence == 0.91
    assert decision.source is DecisionSource.JEV


def test_decision_engine_falls_back_when_jev_confidence_is_low():
    class LowConfidenceProvider:
        def route(self, query):
            from src.decision import Decision

            return Decision(QueryIntent.GENERAL_RESEARCH, 0.42, DecisionSource.JEV)

    decision = DecisionEngine(LowConfidenceProvider(), confidence_threshold=0.7).route(
        "What was revenue in 2025?"
    )

    assert decision.value is QueryIntent.METRIC_LOOKUP
    assert decision.source is DecisionSource.DETERMINISTIC
    assert decision.fallback_reason == "Decision confidence below threshold."


def test_ollama_decision_provider_parses_bounded_route():
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"response": '{"route":"FILING_RAG","confidence":0.82}'}

    class Session:
        def post(self, *args, **kwargs):
            assert kwargs["json"]["format"] == "json"
            return Response()

    decision = OllamaDecisionProvider(session=Session()).route("Why did revenue grow?")
    assert decision.value is QueryIntent.FILING_RAG
    assert decision.confidence == 0.82
    assert decision.source is DecisionSource.LOCAL_LLM


def test_malformed_jev_json_shape_falls_back_deterministically():
    class Response:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return []

    class Session:
        def post(self, *args, **kwargs):
            return Response()

    provider = JevDecisionProvider("secret", session=Session(), transient_retries=0)
    decision = DecisionEngine(provider).route("What was revenue in 2025?")

    assert decision.value is QueryIntent.METRIC_LOOKUP
    assert decision.source is DecisionSource.DETERMINISTIC


def test_reranker_failure_retains_fused_or_backend_results():
    from src.search import FilingSearch

    class Dense:
        def search(self, collection, query, top_k):
            return []

    class BrokenReranker:
        def rerank(self, query, hits, top_k):
            raise RuntimeError("device failure")

    search = FilingSearch(Dense(), "collection", [{"chunk_id": "a", "text": "revenue grew"}])
    hits = search.search("revenue", mode="BM25", reranker=BrokenReranker(), top_k=1)

    assert hits[0]["chunk_id"] == "a"


def test_ollama_connection_failure_returns_retrieval_only_result(monkeypatch):
    def fail(*args, **kwargs):
        raise ConnectionError("offline")

    monkeypatch.setattr("src.llm.requests.post", fail)
    result = generate_answer(
        "What changed?",
        [{"chunk_id": "A-1", "section": "Item 7", "score": 1.0, "text": "Revenue grew."}],
        "llama3.2",
    )

    assert result == GenerationResult(answer=None, available=False, error="Ollama is unavailable.")
