"""Regression coverage for bounded interactive request paths."""

from backend.intelligence import IntelligenceEvent
from backend.service import ResearchService
from src.local_store import LocalStore
from src.portfolios import Holding, PortfolioSnapshot


def _portfolio(holdings: int = 12) -> PortfolioSnapshot:
    rows = [
        Holding(
            f"ISSUER {index}",
            "COM",
            f"{index:09d}",
            100,
            1_000,
            ticker=f"T{index}",
            weight=1 / holdings,
            ticker_source="https://www.sec.gov/fixture",
        )
        for index in range(holdings)
    ]
    return PortfolioSnapshot(
        "berkshire",
        "2026-06-30",
        "2026-08-14",
        "https://www.sec.gov/fixture",
        "performance-fixture",
        holdings=rows,
    )


def test_latest_snapshots_batches_entities_and_snapshot_limit(tmp_path):
    store = LocalStore(tmp_path / "bounded.sqlite3")
    for ticker in ("A", "B"):
        store.save_snapshot("market", ticker, "2025", {"value": 1})
        store.save_snapshot("market", ticker, "2026", {"value": 2})
    assert store.snapshots("market", "A", limit=1) == [{"value": 2}]
    assert store.latest_snapshots("market", ["A", "B", "A"]) == {
        "A": {"value": 2},
        "B": {"value": 2},
    }


def test_investor_enrichment_does_not_query_market_per_holding(
    tmp_path, monkeypatch
):
    store = LocalStore(tmp_path / "investor.sqlite3")
    snapshot = _portfolio()
    store.save_snapshot(
        "portfolio", "berkshire", snapshot.reporting_period, snapshot.to_dict()
    )
    for index in range(12):
        store.save_snapshot("market", f"T{index}", "current", {"price": 10})
    original = store.snapshots
    market_calls = 0

    def counted(kind, entity_id, limit=None):
        nonlocal market_calls
        if kind == "market":
            market_calls += 1
        return original(kind, entity_id, limit)

    monkeypatch.setattr(store, "snapshots", counted)
    investor = ResearchService(store).investor("berkshire")
    assert len(investor["holdings"]) == 12
    assert market_calls == 0


def test_investor_summaries_bound_holdings_and_skip_changes(tmp_path):
    store = LocalStore(tmp_path / "summaries.sqlite3")
    snapshot = _portfolio()
    store.save_snapshot(
        "portfolio", "berkshire", snapshot.reporting_period, snapshot.to_dict()
    )
    summary = next(
        item
        for item in ResearchService(store).investor_summaries()
        if item["id"] == "berkshire"
    )
    assert len(summary["holdings"]) == 3
    assert summary["changes"] == []


def test_cached_feed_can_skip_synchronous_materialization(tmp_path, monkeypatch):
    store = LocalStore(tmp_path / "events.sqlite3")
    service = ResearchService(store)
    event = IntelligenceEvent(
        id="cached-event",
        event_type="public_update",
        entity_id="official-source",
        entity_name="Official source",
        headline="Dated official update",
        source_type="Official public feed",
        source_url="https://example.org/update",
        published_at="2026-10-10",
        detected_at="2026-10-10T12:00:00+00:00",
        importance_score=0.1,
    )
    store.save_intelligence_event(event.model_dump())
    calls = 0

    def materialize():
        nonlocal calls
        calls += 1

    monkeypatch.setattr(service.intelligence, "ingest_cached", materialize)
    result = service.intelligence.feed(materialize=False)
    assert result["events"][0]["id"] == "cached-event"
    assert calls == 0

    class Background:
        def __init__(self):
            self.tasks = []

        def add_task(self, task):
            self.tasks.append(task)

    background = Background()
    service.intelligence.schedule(background)
    service.intelligence.schedule(background)
    assert len(background.tasks) == 1
    background.tasks[0]()
    assert calls == 1
