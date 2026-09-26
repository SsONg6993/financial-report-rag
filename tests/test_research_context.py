from dataclasses import replace

from backend.research_context import comparisons, risk_cards, structured_answer
from backend.service import ResearchService
from src.config import AppConfig
from src.local_store import LocalStore
from src.market import ResilientMarketProvider
from src.models import MarketSnapshot


def test_comparison_missing_year_and_negative_fcf():
    rows = [{"fiscal_year": 2024, "free_cash_flow": -20, "revenue_growth": .1},
            {"fiscal_year": 2025, "free_cash_flow": -10, "revenue_growth": .2}]
    result = comparisons(rows)
    assert result[0]["delta"] == .1
    assert result[1]["relative_change"] == .5
    assert result[1]["status"] == "Improving"
    rows[0]["fiscal_year"] = 2023
    assert comparisons(rows)[1]["previous"] is None


def test_quote_fallback_rejects_empty_snapshot():
    class Empty:
        def snapshot(self, ticker):
            return MarketSnapshot(ticker=ticker)

    class Working:
        def snapshot(self, ticker):
            return MarketSnapshot(ticker=ticker, price=50, provider="fallback")

    assert ResilientMarketProvider([Empty(), Working()]).snapshot("META").provider == "fallback"
    assert ResilientMarketProvider([Empty()]).snapshot("META").error


def test_market_cache_survives_failure_without_sec_data(tmp_path, monkeypatch):
    store = LocalStore(tmp_path / "test.sqlite3")
    service = ResearchService(store)
    store.save_snapshot("market", "RKLB", "current", {"price": 50, "quote_as_of": "2026-09-25"})
    monkeypatch.setattr(ResilientMarketProvider, "snapshot", lambda self, key: MarketSnapshot(ticker=key, error="failed"))
    service.refresh("market", "RKLB")
    company = service.company("RKLB")
    assert company["available"] is False
    assert company["market"]["price"] == 50
    assert company["market"]["status"] == "cached"
    assert company["market"]["quote_as_of"] == "2026-09-25"


def test_risks_deduplicate_and_preserve_full_evidence():
    chunk = {"text": "We face regulatory restrictions in several markets. These restrictions may limit our operations.", "period": "2026-06-30", "source_url": "https://sec.gov/example"}
    result = risk_cards([chunk, chunk])
    assert len(result) == 1
    assert result[0]["title"] == "Regulatory pressure"
    assert result[0]["summary"] in chunk["text"]
    assert result[0]["evidence"] == chunk


def test_fallback_is_structured_without_raw_chunks(monkeypatch):
    monkeypatch.setenv("THESISLENS_OFFLINE", "true")
    evidence = [{"text": "RAW EVIDENCE", "source_url": "https://sec.gov/example"}]
    result = structured_answer("Question?", {}, evidence, "Evidence is limited.", AppConfig.from_env())
    assert set(result["sections"]) == {"short_answer", "why", "numbers", "watch", "annual_context"}
    assert "RAW EVIDENCE" not in result["answer"]


def test_model_cannot_replace_investor_motive_guard(monkeypatch):
    monkeypatch.setattr("backend.research_context.synthesis", lambda *_: {"short_answer": "Investor sold because of valuation", "why": ["Review company context."], "watch": ["Next filing."]})
    config = replace(AppConfig.from_env(), ollama_model="qwen3:4b")
    result = structured_answer("Why sell?", {}, [], "The filing does not provide the reason.", config, protected=True)
    assert result["sections"]["short_answer"] == "The filing does not provide the reason."
