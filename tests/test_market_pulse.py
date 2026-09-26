from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
import requests
from fastapi.testclient import TestClient

from backend import main
from backend.market_pulse.engine import build_impact, cluster, empty_reaction, freshness
from backend.market_pulse.models import MarketEvent
from backend.market_pulse.providers import (
    FetchResult,
    RSSProvider,
    canonical_url,
    timestamp,
)
from backend.market_pulse.service import MarketPulseService, summarize
from src.config import AppConfig
from src.local_store import LocalStore

NOW = datetime(2026, 9, 26, 12, tzinfo=UTC)


def event(**kwargs):
    return MarketEvent(
        id="0123456789abcdefabcd",
        headline="Oil prices rose on supply concerns",
        summary="Oil prices rose on supply concerns.",
        category="Energy",
        source="Official source",
        source_url="https://example.org/event",
        published_at=(NOW - timedelta(hours=2)).isoformat(),
        cached_at=NOW.isoformat(),
        provider_id="test",
        **kwargs,
    )


class Provider:
    id, name, ttl_seconds = "test", "Test primary source", 1800

    def __init__(self):
        self.count, self.fail, self.not_modified = 0, False, False

    def fetch(self, _state):
        self.count += 1
        if self.fail:
            raise requests.ConnectionError("offline")
        return FetchResult(None if self.not_modified else [event()], "etag", "date")


@pytest.fixture
def pulse(tmp_path, monkeypatch):
    monkeypatch.setenv("THESISLENS_OFFLINE", "true")
    store = LocalStore(tmp_path / "pulse.sqlite3")
    research = SimpleNamespace(
        store=store,
        config=AppConfig.from_env(),
        portfolios=lambda _: [],
        cached_company=lambda _: {},
        chunks=lambda _: [],
    )
    return MarketPulseService(research, [Provider()], lambda: NOW)


def test_rss_normalizes_sanitizes_and_keeps_unknown_event_time():
    provider = RSSProvider("test", "Official", "https://example.org/feed", "Technology")
    xml = b"<rss><channel><item><title>AI infrastructure expands</title><link>https://example.org/story?utm_source=rss</link><description>&lt;p&gt;A new AI product was announced.&lt;/p&gt;</description><pubDate>Sat, 26 Sep 2026 10:00:00 GMT</pubDate></item></channel></rss>"
    result = provider.parse(xml, NOW)[0]
    assert result.category == "Artificial Intelligence"
    assert "<p>" not in result.summary
    assert result.event_time is None
    assert result.source_url == "https://example.org/story"
    assert result.published_at == "2026-09-26T10:00:00+00:00"


def test_atom_and_missing_dates():
    provider = RSSProvider("test", "Official", "https://example.org/feed", "Technology")
    xml = b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Event</title><link href="https://example.org/1"/><published>2026-09-26T10:00:00Z</published><summary>Short text</summary></entry><entry><title>Undated</title><link href="https://example.org/2"/></entry></feed>'
    assert len(provider.parse(xml, NOW)) == 1
    assert timestamp("2026-09-26T10:00:00") is None


def test_invalid_dates_future_events_and_entities_rejected():
    provider = RSSProvider("test", "Official", "https://example.org/feed", "Energy")
    assert timestamp("not a date") is None
    with pytest.raises(ValueError, match="entities"):
        provider.parse(b"<!DOCTYPE rss><rss/>", NOW)
    xml = b"<rss><channel><item><title>Future</title><link>https://example.org/future</link><pubDate>Sat, 26 Sep 2026 20:00:00 GMT</pubDate></item></channel></rss>"
    assert not provider.parse(xml, NOW)


def test_clustering_keeps_sources_and_ids_but_not_different_dates():
    first = event()
    second = first.model_copy(
        update={
            "id": "second",
            "source_url": "https://other.org/news",
            "source": "Second source",
        }
    )
    result = cluster([first, second])
    assert len(result) == 1
    assert len(result[0].related_sources) == 1
    assert len(result[0].aliases) == 1
    later = second.model_copy(
        update={"published_at": (NOW - timedelta(days=3)).isoformat()}
    )
    assert len(cluster([first, later])) == 2
    assert (
        canonical_url("https://www.eia.gov/detail.php?id=123&utm_source=rss")
        == "https://www.eia.gov/detail.php?id=123"
    )


def test_freshness_uses_publication_not_cache_time():
    assert freshness((NOW - timedelta(hours=2)).isoformat(), NOW) == "2 HOURS AGO"
    assert (
        freshness((NOW - timedelta(days=10)).isoformat(), NOW, True)
        == "10 DAYS AGO · STALE CACHE"
    )
    assert freshness(None, NOW) == "DATE UNAVAILABLE"


def test_failure_retains_cache_and_cooldown(pulse):
    pulse.refresh()
    provider = pulse.providers[0]
    pulse.refresh()
    assert provider.count == 1
    pulse.clock = lambda: NOW + timedelta(hours=1)
    provider.fail = True
    pulse.refresh()
    assert len(pulse.events()) == 1
    assert pulse.feed()["events"][0]["stale"]
    assert pulse.state(provider)["successful_at"] == NOW.isoformat()
    assert pulse.state(provider)["etag"] == "etag"


def test_304_reuses_saved_snapshot(pulse):
    pulse.refresh()
    pulse.providers[0].not_modified = True
    pulse.clock = lambda: NOW + timedelta(hours=1)
    pulse.refresh()
    assert len(pulse.events()) == 1
    assert not pulse.state(pulse.providers[0])["error"]


def test_empty_304_does_not_create_fake_success(pulse):
    pulse.providers[0].not_modified = True
    pulse.refresh()
    assert pulse.state(pulse.providers[0])["error"]
    assert not pulse.events()


def test_supported_fuel_cost_mechanism_not_price_prediction():
    chunks = [
        {
            "text": "Jet fuel is a material operating cost.",
            "source_url": "https://sec.gov/filing",
            "period": "2026-06-30",
        }
    ]
    result = build_impact(event(), "DAL", "Delta", chunks)
    assert result.impact_type == "POTENTIAL_HEADWIND"
    assert result.evidence_strength == "STRONG"
    assert result.evidence_refs[0].date == "2026-06-30"
    assert (
        "not price direction" not in result.explanation
    )  # Explicit uncertainty, not a forecast.
    assert "may" in result.explanation


def test_insufficient_exposure_is_unclear():
    assert build_impact(event(), "AAPL", "Apple", []).impact_type == "UNCLEAR"
    assert (
        build_impact(
            event(),
            "AAPL",
            "Apple",
            [
                {
                    "text": "Oil is mentioned.",
                    "source_url": "https://sec.gov/filing",
                    "period": "2026-06-30",
                }
            ],
        ).impact_type
        == "UNCLEAR"
    )


def test_natural_gas_is_not_jet_fuel():
    gas = event().model_copy(
        update={
            "headline": "Natural gas prices fell",
            "summary": "Natural gas spot prices declined.",
        }
    )
    chunk = {
        "text": "Jet fuel is a material operating cost.",
        "source_url": "https://sec.gov/filing",
        "period": "2026-06-30",
    }
    assert build_impact(gas, "DAL", "Delta", [chunk]).impact_type == "UNCLEAR"


def test_historical_energy_data_not_new_shock():
    historical = event().model_copy(
        update={
            "headline": "Oil prices were higher last year",
            "summary": "Historical data.",
        }
    )
    chunk = {
        "text": "Fuel is a material operating cost.",
        "source_url": "https://sec.gov/filing",
        "period": "2026-06-30",
    }
    assert build_impact(historical, "DAL", "Delta", [chunk]).impact_type == "INDIRECT"


def test_watchlist_requires_supported_evidence(pulse):
    pulse.store.watch("AAPL")
    pulse.refresh()
    assert pulse.feed()["watchlist_event_count"] == 0
    pulse.research.chunks = lambda _: [
        {
            "text": "Fuel is a material operating cost.",
            "source_url": "https://sec.gov/filing",
            "period": "2026-06-30",
        }
    ]
    assert pulse.feed()["watchlist_event_count"] == 1


def test_portfolio_overlap_preserves_disclosure_dates(pulse):
    pulse.store.follow("berkshire")
    pulse.research.portfolios = lambda _: [
        SimpleNamespace(
            reporting_period="2026-06-30",
            filing_date="2026-08-14",
            source_url="https://sec.gov/13f",
            source_type="SEC Form 13F",
            holdings=[SimpleNamespace(ticker="CVX", put_call="")],
        )
    ]
    context = pulse.portfolio_map()["CVX"][0]
    assert context["reporting_period"] == "2026-06-30"
    assert "not confirmation" in context["note"]


def test_reaction_missing_is_not_invented():
    reaction = empty_reaction(event(), "DAL")
    assert reaction["reference_price"] is None
    assert reaction["day_1_return"] is None
    assert reaction["day_5_return"] is None
    assert "Observed after" in reaction["label"]
    assert "not proof of causation" in reaction["label"]


def test_model_cannot_inject_raw_article_or_new_facts(monkeypatch):
    monkeypatch.delenv("THESISLENS_OFFLINE", raising=False)

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"response": '{"what": "Buy now", "why": 99, "watch": 0}'}

    monkeypatch.setattr(
        "backend.market_pulse.service.requests.post", lambda *_a, **_kw: Response()
    )
    result = summarize(event(), AppConfig.from_env())
    assert result["what_happened"] == event().summary
    assert "Buy now" not in str(result)
    assert "Ollama" not in result["generator"]


def test_api_detail_watchlist_and_ask_use_pulse(pulse, monkeypatch):
    pulse.refresh()
    monkeypatch.setattr(main.service, "market_pulse", pulse)
    with TestClient(main.app) as client:
        feed = client.get("/api/market-pulse").json()
        assert len(feed["events"]) == 1
        assert client.get("/api/market-pulse/watchlist").json()["events"] == []
        detail = client.get("/api/market-pulse/" + event().id).json()
        assert "Timestamp-aligned" in detail["reaction_note"]
        assert client.get("/api/market-pulse/not-found").status_code == 404
        answer = client.post(
            "/api/ask",
            json={
                "question": "Which recent news may affect my watchlist?",
                "ticker": "AAPL",
            },
        ).json()
        assert "Market Pulse" in answer["source"]
        assert "No recent event" in answer["answer"]


def test_jev_optional_failure_keeps_deterministic_impact(pulse, monkeypatch):
    from src.decision import DecisionUnavailable

    monkeypatch.delenv("THESISLENS_OFFLINE", raising=False)
    pulse.research.config = replace(
        pulse.research.config, enable_jev=True, typesafe_api_key="synthetic-test-key"
    )
    pulse.store.save_snapshot(
        "pulse_provider",
        "test",
        "current",
        {"events": [event().model_dump()], "successful_at": NOW.isoformat()},
    )
    pulse.research.chunks = lambda _: [
        {
            "text": "Fuel is a material operating cost.",
            "source_url": "https://sec.gov/filing",
            "period": "2026-06-30",
        }
    ]

    def unavailable(*_):
        raise DecisionUnavailable("offline")

    monkeypatch.setattr(
        "backend.market_pulse.service.JevDecisionProvider.evidence_sufficiency",
        unavailable,
    )
    result = pulse.detail(event().id)
    assert result["impacts"][0]["impact_type"] == "POTENTIAL_HEADWIND"
    assert result["impacts"][0]["judgment"]["sufficiency"] == "UNAVAILABLE"


@pytest.mark.parametrize(
    "category,text",
    [
        (
            "Energy",
            "Leveraging Windows to fuel our cloud business and product revenue.",
        ),
        ("GDP / Growth", "Other Business and Macroeconomic Conditions"),
        ("Interest Rates / Central Banks", "Debt | liabilities | total cost | 12345"),
        (
            "Interest Rates / Central Banks",
            "We have debt liabilities and other operating costs.",
        ),
    ],
)
def test_metaphors_headings_and_tables_are_not_exposure(category, text):
    row = event().model_copy(update={"category": category})
    chunk = {
        "text": text,
        "source_url": "https://sec.gov/filing",
        "period": "2026-06-30",
    }
    assert build_impact(row, "MSFT", "Microsoft", [chunk]).impact_type == "UNCLEAR"


def test_source_abbreviations_do_not_create_fragment_summaries(monkeypatch):
    monkeypatch.setenv("THESISLENS_OFFLINE", "true")
    row = event().model_copy(
        update={
            "summary": "The U.S. current-account balance narrowed during the second quarter. production."
        }
    )
    result = summarize(row, AppConfig.from_env())
    assert (
        result["what_happened"]
        == "The U.S. current-account balance narrowed during the second quarter."
    )


def test_incidental_gdp_in_description_does_not_reclassify_release():
    provider = RSSProvider("bea", "BEA", "https://example.org/feed", "Macroeconomics")
    xml = b"<rss><channel><item><title>International Transactions, Second Quarter</title><link>https://example.org/current-account</link><description>The current account was 3% of GDP.</description><pubDate>Sat, 26 Sep 2026 10:00:00 GMT</pubDate></item></channel></rss>"
    assert provider.parse(xml, NOW)[0].category == "Macroeconomics"


def test_issuer_project_not_automatically_industry_wide_exposure():
    row = event().model_copy(
        update={
            "provider_id": "nvidia",
            "headline": "NVIDIA expands AI capacity in Australia",
            "category": "Artificial Intelligence",
        }
    )
    chunk = {
        "text": "We invest in artificial intelligence products and services.",
        "source_url": "https://sec.gov/filing",
        "period": "2026-06-30",
    }
    assert build_impact(row, "MSFT", "Microsoft", [chunk]).impact_type == "UNCLEAR"
    assert build_impact(row, "NVDA", "NVIDIA", [chunk]).impact_type == "MIXED"


def test_corporate_category_uses_valid_event_contract():
    provider = RSSProvider("test", "Official", "https://example.org/feed", "Technology")
    xml = b"<rss><channel><item><title>Company announces financial results</title><link>https://example.org/results</link><pubDate>Sat, 26 Sep 2026 10:00:00 GMT</pubDate></item></channel></rss>"
    assert provider.parse(xml, NOW)[0].category == "Corporate / Industry Events"


def test_ask_resolves_company_name_without_fabricating_relevance(pulse):
    pulse.refresh()
    pulse.store.watch("NVDA")
    row = event().model_copy(
        update={
            "provider_id": "test",
            "category": "Artificial Intelligence",
            "headline": "AI infrastructure capacity expands",
        }
    )
    pulse.store.save_snapshot(
        "pulse_provider",
        "test",
        "current",
        {"events": [row.model_dump()], "successful_at": NOW.isoformat()},
    )
    pulse.research.chunks = lambda ticker: (
        [
            {
                "text": "We invest in artificial intelligence products and services.",
                "source_url": "https://sec.gov/filing",
                "period": "2026-06-30",
            }
        ]
        if ticker == "NVDA"
        else []
    )
    result = pulse.answer("How might recent AI news affect NVIDIA?", "AAPL")
    assert "NVDA" in str(result["sections"]["numbers"])
    assert "AAPL" not in str(result["sections"]["numbers"])


def test_model_cannot_replace_main_event_with_revised_prior_period(monkeypatch):
    monkeypatch.delenv("THESISLENS_OFFLINE", raising=False)

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"response": '{"what": 1, "why": 0, "watch": 0}'}

    monkeypatch.setattr(
        "backend.market_pulse.service.requests.post", lambda *_a, **_kw: Response()
    )
    row = event().model_copy(
        update={
            "summary": "The U.S. current-account deficit widened during the second quarter. The revised first-quarter deficit was lower than previously reported."
        }
    )
    assert "second quarter" in summarize(row, AppConfig.from_env())["what_happened"]
