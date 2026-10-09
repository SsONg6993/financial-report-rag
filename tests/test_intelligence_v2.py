"""Offline V2 contracts: no live SEC, X, or paid provider calls."""

import sqlite3
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from backend import main
from backend.e2e_seed import seed as seed_e2e
from backend.e2e_server import isolated_paths
from backend.entity_registry import TrackedEntityRegistry
from backend.intelligence import IntelligenceEvent, adjacent_quarters
from backend.notifications import NotificationDispatcher
from backend.public_updates import WebsiteFeedProvider
from backend.service import ResearchService
from src.local_store import LocalStore
from src.portfolios import Holding, PortfolioSnapshot


def _snapshot(period, filing, shares, accession):
    return PortfolioSnapshot(
        "berkshire", period, filing, "https://www.sec.gov/fixture", accession,
        holdings=[Holding("APPLE INC", "COM", "037833100", shares, shares * 10,
                          ticker="AAPL", weight=1.0)] if shares else [],
    )


def test_additive_migration_preserves_existing_data(tmp_path):
    path = tmp_path / "research.sqlite3"
    store = LocalStore(path)
    store.watch("AAPL")
    store.follow("berkshire")
    again = LocalStore(path)
    assert again.watchlist() == ["AAPL"]
    assert again.follows() == ["berkshire"]
    with again.connect() as db:
        assert db.execute("SELECT version FROM schema_migrations").fetchall() == [(2,)]


def test_v1_upgrade_preserves_theses_and_history_and_is_idempotent(tmp_path):
    path = tmp_path / "v1.sqlite3"
    with sqlite3.connect(path) as db:
        db.executescript("""
            CREATE TABLE watchlist (ticker TEXT PRIMARY KEY, created_at TEXT NOT NULL);
            CREATE TABLE follows (entity_id TEXT PRIMARY KEY, created_at TEXT NOT NULL);
            CREATE TABLE theses (id TEXT PRIMARY KEY, ticker TEXT NOT NULL, payload TEXT NOT NULL);
            CREATE TABLE evaluations (id TEXT PRIMARY KEY, thesis_id TEXT NOT NULL, evaluated_at TEXT NOT NULL, payload TEXT NOT NULL);
            CREATE TABLE snapshots (kind TEXT NOT NULL, entity_id TEXT NOT NULL, snapshot_id TEXT NOT NULL,
                saved_at TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(kind, entity_id, snapshot_id));
            INSERT INTO watchlist VALUES ('AAPL','2025-01-01');
            INSERT INTO follows VALUES ('berkshire','2025-01-01');
            INSERT INTO theses VALUES ('thesis-1','AAPL','{"id":"thesis-1","ticker":"AAPL","text":"Test","rule":null}');
            INSERT INTO evaluations VALUES ('eval-1','thesis-1','2025-01-02','{"status":"STABLE"}');
        """)
    LocalStore(path)
    LocalStore(path)
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT ticker FROM watchlist").fetchall() == [("AAPL",)]
        assert db.execute("SELECT entity_id FROM follows").fetchall() == [("berkshire",)]
        assert db.execute("SELECT id FROM theses").fetchall() == [("thesis-1",)]
        assert db.execute("SELECT id FROM evaluations").fetchall() == [("eval-1",)]
        assert db.execute("SELECT version FROM schema_migrations").fetchall() == [(2,)]


def test_failed_migration_rolls_back_new_schema_without_touching_v1(tmp_path):
    path = tmp_path / "conflict.sqlite3"
    with sqlite3.connect(path) as db:
        db.executescript("""
            CREATE TABLE watchlist (ticker TEXT PRIMARY KEY, created_at TEXT NOT NULL);
            INSERT INTO watchlist VALUES ('AAPL','2025-01-01');
            CREATE TABLE intelligence_events (id TEXT PRIMARY KEY);
        """)
    with pytest.raises(sqlite3.OperationalError):
        LocalStore(path)
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT ticker FROM watchlist").fetchall() == [("AAPL",)]
        assert db.execute("SELECT name FROM sqlite_master WHERE name='tracked_entities'").fetchall() == []
        assert db.execute("SELECT name FROM sqlite_master WHERE name='schema_migrations'").fetchall() == []


def test_e2e_seed_is_synthetic_and_default_db_is_rejected(tmp_path, monkeypatch):
    database = tmp_path / "synthetic.sqlite3"
    seed_e2e(database, tmp_path / "cache")
    store = LocalStore(database)
    assert store.watchlist() == ["AAPL"]
    assert len(store.snapshots("portfolio", "berkshire")) == 2
    with store.connect() as db:
        assert db.execute("SELECT version FROM schema_migrations").fetchall() == [(2,)]
        assert db.execute("SELECT COUNT(*) FROM theses").fetchone()[0] == 0
    monkeypatch.setenv("THESISLENS_E2E_DB", "data/local/thesislens.sqlite3")
    monkeypatch.setenv("THESISLENS_DB", "data/local/thesislens.sqlite3")
    monkeypatch.setenv("THESISLENS_CACHE_DIR", "data/cache")
    monkeypatch.setenv("THESISLENS_OFFLINE", "true")
    with pytest.raises(SystemExit, match="E2E refused"):
        isolated_paths()


def test_dated_event_dedup_and_reported_exit(tmp_path, monkeypatch):
    monkeypatch.setenv("THESISLENS_OFFLINE", "true")
    store = LocalStore(tmp_path / "events.sqlite3")
    store.watch("AAPL")
    store.follow("berkshire")
    store.save_snapshot("portfolio", "berkshire", "2026-03-31",
                        _snapshot("2026-03-31", "2026-05-15", 100, "old").to_dict())
    store.save_snapshot("portfolio", "berkshire", "2026-06-30",
                        _snapshot("2026-06-30", "2026-08-14", 0, "new").to_dict())
    service = ResearchService(store)
    first = service.intelligence.feed("my_watchlist")
    second = service.intelligence.feed("my_watchlist")
    assert len(first["events"]) == len(second["events"]) == 1
    assert first["events"][0]["event_type"] == "portfolio_exit"
    assert first["events"][0]["reporting_period"] == "2026-06-30"
    assert first["events"][0]["published_at"] == "2026-08-14"
    activity = service.intelligence.company_activity("AAPL")
    assert activity["counts"]["EXITED"] == 1
    assert activity["tracked_managers"][0]["reported_shares"] == 0


def test_nonadjacent_quarters_not_compared(tmp_path, monkeypatch):
    monkeypatch.setenv("THESISLENS_OFFLINE", "true")
    store = LocalStore(tmp_path / "gap.sqlite3")
    store.save_snapshot("portfolio", "berkshire", "2025-12-31",
                        _snapshot("2025-12-31", "2026-02-14", 100, "old").to_dict())
    store.save_snapshot("portfolio", "berkshire", "2026-06-30",
                        _snapshot("2026-06-30", "2026-08-14", 0, "new").to_dict())
    service = ResearchService(store)
    assert adjacent_quarters("2025-12-31", "2026-06-30") is False
    assert all(e["event_type"] != "portfolio_exit" for e in service.intelligence.feed()["events"])


def test_ark_daily_changes_are_not_13f_convergence(tmp_path, monkeypatch):
    monkeypatch.setenv("THESISLENS_OFFLINE", "true")
    store = LocalStore(tmp_path / "ark.sqlite3")
    for period, shares in (("2026-10-01", 100), ("2026-10-02", 120)):
        snapshot = PortfolioSnapshot(
            "ark", period, period, "https://www.ark-funds.com/arkk", period,
            source_type="Official ARKK daily fund holdings",
            holdings=[Holding("EXAMPLE INC", "COM", "123456789", shares, shares * 10,
                              ticker="EXM", weight=1.0)],
        )
        store.save_snapshot("portfolio", "ark", period, snapshot.to_dict())
    service = ResearchService(store)
    investor_events = service.intelligence.feed("investors")["events"]
    assert any(e["event_type"] == "portfolio_increase" and e["reporting_period"] == "2026-10-02"
               for e in investor_events)
    assert not service.intelligence.feed("institutions")["events"]
    assert not service.intelligence.company_activity("EXM")["tracked_managers"]


def test_free_channel_disabled_and_failure_retains_event(tmp_path, monkeypatch):
    store = LocalStore(tmp_path / "notify.sqlite3")
    store.save_intelligence_event({
        "id": "event-1", "event_type": "public_update", "entity_id": "nvidia",
        "ticker": "NVDA", "published_at": "2026-10-05", "detected_at": "2026-10-05",
        "headline": "Official update", "source_url": "https://example.org/release",
    })
    store.enqueue_notification("event-1", "local", "normal")
    monkeypatch.delenv("THESISLENS_NOTIFICATION_CHANNEL", raising=False)
    assert NotificationDispatcher(store).dispatch()["delivered"] == 0
    assert store.notifications()[0]["status"] == "pending"
    monkeypatch.setenv("THESISLENS_NOTIFICATION_CHANNEL", "ntfy")
    monkeypatch.setenv("THESISLENS_NTFY_TOPIC", "research")
    monkeypatch.setenv("THESISLENS_QUIET_START_UTC", "23:00")
    monkeypatch.setenv("THESISLENS_QUIET_END_UTC", "23:01")

    class FailingSession:
        def post(self, *args, **kwargs):
            import requests
            raise requests.ConnectionError("offline")

    dispatcher = NotificationDispatcher(store, session=FailingSession(),
                                        clock=lambda: datetime(2026, 10, 5, 12, tzinfo=UTC))
    assert dispatcher.dispatch()["delivered"] == 0
    assert any(row["status"] == "failed" for row in store.notifications())
    assert store.intelligence_events()[0]["id"] == "event-1"
    assert store.dismiss_notification("event-1")
    assert all(row["status"] == "dismissed" for row in store.notifications())


def test_notification_delivery_is_idempotent(tmp_path, monkeypatch):
    store = LocalStore(tmp_path / "delivery.sqlite3")
    store.save_intelligence_event({
        "id": "event-2", "event_type": "public_update", "entity_id": "nvidia",
        "ticker": "NVDA", "published_at": "2026-10-05", "detected_at": "2026-10-05",
        "headline": "Official update", "source_url": "https://example.org/release",
    })
    store.enqueue_notification("event-2", "local", "normal")
    monkeypatch.setenv("THESISLENS_NOTIFICATION_CHANNEL", "ntfy")
    monkeypatch.setenv("THESISLENS_NTFY_TOPIC", "research")
    monkeypatch.setenv("THESISLENS_QUIET_START_UTC", "23:00")
    monkeypatch.setenv("THESISLENS_QUIET_END_UTC", "23:01")

    class SuccessSession:
        calls = 0
        def post(self, *args, **kwargs):
            self.calls += 1
            class Response:
                def raise_for_status(self):
                    pass
            return Response()

    session = SuccessSession()
    dispatcher = NotificationDispatcher(store, session=session,
                                        clock=lambda: datetime(2026, 10, 5, 12, tzinfo=UTC))
    assert dispatcher.dispatch()["delivered"] == 1
    assert dispatcher.dispatch()["delivered"] == 0
    assert session.calls == 1


def test_dry_run_previews_all_free_consumers_without_mutation(tmp_path, monkeypatch):
    store = LocalStore(tmp_path / "preview.sqlite3")
    for event_id, priority in (("normal-event", "normal"), ("critical-event", "critical"),
                               ("digest-event", "digest")):
        store.save_intelligence_event({
            "id": event_id, "event_type": "public_update", "entity_id": "official",
            "ticker": "AAPL", "published_at": "2026-10-05", "detected_at": "2026-10-05",
            "headline": event_id, "source_url": "https://example.org/" + event_id,
        })
        if priority != "digest":
            store.enqueue_notification(event_id, "local", priority)
    monkeypatch.setenv("THESISLENS_QUIET_START_UTC", "23:00")
    monkeypatch.setenv("THESISLENS_QUIET_END_UTC", "23:01")
    before = store.notifications()

    class NoNetwork:
        def post(self, *args, **kwargs):
            raise AssertionError("dry-run attempted external delivery")

    dispatcher = NotificationDispatcher(store, session=NoNetwork(),
                                        clock=lambda: datetime(2026, 10, 5, 12, tzinfo=UTC))
    for channel in ("telegram", "ntfy", "hermes"):
        preview = dispatcher.dry_run(channel, max_items=5)
        assert preview["dry_run"] is True
        assert [item["event_id"] for item in preview["deliveries"]] == ["critical-event", "normal-event"]
        assert all("https://example.org/" in item["message"] for item in preview["deliveries"])
    assert store.notifications() == before
    assert store.mark_intelligence_read("critical-event")
    assert all(item["event_id"] != "critical-event" for item in dispatcher.dry_run("hermes", 5)["deliveries"])
    assert any(event["id"] == "digest-event" for event in store.intelligence_events())


def test_official_letter_year_not_fabricated_as_publication_date(monkeypatch):
    class Response:
        def raise_for_status(self):
            pass
        def iter_content(self, _size):
            yield b'<a href="2024ltr.pdf">2024</a>'
    monkeypatch.setattr("backend.public_updates.requests.get", lambda *a, **k: Response())
    updates = WebsiteFeedProvider().fetch_updates("berkshire-letters")
    assert len(updates) == 1
    assert updates[0].published_at is None
    assert updates[0].original_url.startswith("https://www.berkshirehathaway.com/")


def test_hermes_rest_feed_brief_and_source_follow(tmp_path, monkeypatch):
    monkeypatch.setenv("THESISLENS_OFFLINE", "true")
    store = LocalStore(tmp_path / "api.sqlite3")
    monkeypatch.setattr(main, "service", ResearchService(store))
    client = TestClient(main.app)
    assert client.get("/api/intelligence/feed").status_code == 200
    assert client.get("/api/intelligence/daily-brief").status_code == 200
    assert client.put("/api/intelligence/sources/nvidia/follow", json={"enabled": True}).json()["followed"]
    assert "nvidia" in store.source_follows()
    assert client.put("/api/intelligence/sources/x/follow", json={"enabled": True}).status_code == 404


def test_hermes_contracts_are_source_cited_and_mark_read_only(tmp_path, monkeypatch):
    monkeypatch.setenv("THESISLENS_OFFLINE", "true")
    store = LocalStore(tmp_path / "hermes.sqlite3")
    store.watch("AAPL")
    store.follow("berkshire")
    store.save_snapshot("portfolio", "berkshire", "2026-03-31",
                        _snapshot("2026-03-31", "2026-05-15", 100, "old").to_dict())
    store.save_snapshot("portfolio", "berkshire", "2026-06-30",
                        _snapshot("2026-06-30", "2026-08-14", 90, "new").to_dict())
    now = datetime.now(UTC).date().isoformat()
    public = IntelligenceEvent(
        id="official-release", event_type="public_update", entity_id="nvidia",
        entity_name="NVIDIA Newsroom", ticker="AAPL", headline="Official public update",
        source_type="Official RSS/Atom", source_url="https://example.org/official",
        published_at=now, detected_at=now, importance_score=0.2,
    )
    store.save_intelligence_event(public.model_dump())
    monkeypatch.setattr(main, "service", ResearchService(store))
    client = TestClient(main.app)
    latest = client.get("/api/intelligence/feed", params={"category": "all"}).json()
    watched = client.get("/api/intelligence/feed", params={"category": "my_watchlist"}).json()
    updates = client.get("/api/intelligence/feed", params={"category": "public_updates"}).json()
    assert all({"id", "source_url", "published_at", "reporting_period", "detected_at"} <= row.keys()
               for row in latest["events"])
    assert all(row["ticker"] == "AAPL" for row in watched["events"])
    assert any(row["id"] == "official-release" for row in updates["events"])
    investor = client.get("/api/investors/berkshire").json()
    changes = client.get("/api/investors/berkshire/changes").json()
    activity = client.get("/api/intelligence/company/AAPL").json()
    brief = client.get("/api/intelligence/daily-brief").json()
    assert investor["source_url"].startswith("https://www.sec.gov/")
    assert changes[0]["reporting_period"] == "2026-06-30"
    assert changes[0]["filing_date"] == "2026-08-14"
    assert activity["tracked_managers"][0]["manager_id"] == "berkshire"
    assert any(row["id"] == "official-release" for row in brief["public_updates"])
    assert client.put("/api/intelligence/events/official-release/read").json() == {
        "event_id": "official-release", "read": True}
    assert next(row for row in store.intelligence_events() if row["id"] == "official-release")["read_at"]


def test_cik_resolution_requires_matching_original_13f(tmp_path):
    store = LocalStore(tmp_path / "registry.sqlite3")
    registry = TrackedEntityRegistry(store)

    class Response:
        def __init__(self, payload):
            self.payload = payload
        def raise_for_status(self):
            pass
        def json(self):
            return self.payload

    class Session:
        def __init__(self, payload):
            self.payload = payload
        def get(self, url, timeout):
            assert url.endswith("CIK0001234567.json")
            return Response(self.payload)

    base = {"cik": 1234567, "name": "Example Verified Manager", "filings": {"recent": {"form": ["13F-HR"]}}}
    with pytest.raises(ValueError):
        registry.resolve_cik(1234567, Session({**base, "cik": 7654321}))
    with pytest.raises(ValueError):
        registry.resolve_cik(1234567, Session({**base, "filings": {"recent": {"form": ["13F-NT"]}}}))
    assert registry.search("Example") == []
    item = registry.resolve_cik(1234567, Session(base))
    assert item.id == "sec-1234567"
    assert registry.get(item.id).cik_source_url.endswith("CIK=1234567&owner=exclude")
