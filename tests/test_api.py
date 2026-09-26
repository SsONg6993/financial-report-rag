"""Offline adapter tests. Synthetic fixtures are never served in the real app."""

import pytest
from fastapi.testclient import TestClient

from backend import main
from backend.disclosures import parse_form4, parse_ownership
from backend.quarterly import quarter_facts, quarterly_changes
from backend.service import ResearchService
from backend.tickers import cover_class_tickers
from src.local_store import LocalStore
from src.models import AnnualFinancials
from src.portfolios import Holding, PortfolioSnapshot
from src.thesis import serialize_financials


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("THESISLENS_OFFLINE", "true")
    store = LocalStore(tmp_path / "api.sqlite3")
    service = ResearchService(store)
    for period, shares in [("2025-03-31", 100), ("2025-06-30", 90)]:
        snapshot = PortfolioSnapshot(
            "berkshire",
            period,
            "2025-08-14",
            "https://www.sec.gov/fixture",
            period,
            holdings=[
                Holding(
                    "APPLE INC",
                    "COM",
                    "037833100",
                    shares,
                    shares * 10,
                    ticker="AAPL",
                    weight=1,
                )
            ],
        )
        store.save_snapshot("portfolio", "berkshire", period, snapshot.to_dict())
    rows = [
        AnnualFinancials(
            2024,
            revenue=100,
            gross_margin=0.45,
            revenue_growth=0.1,
            free_cash_flow=10,
            debt=20,
            source_url="https://data.sec.gov/fixture",
        ),
        AnnualFinancials(
            2025,
            revenue=120,
            gross_margin=0.46,
            revenue_growth=0.2,
            free_cash_flow=12,
            debt=21,
            source_url="https://data.sec.gov/fixture",
        ),
    ]
    store.save_snapshot(
        "company",
        "AAPL",
        "current",
        {
            "ticker": "AAPL",
            "financials": serialize_financials(rows),
            "filings": [],
            "market": {},
            "provider_warnings": [],
        },
    )
    monkeypatch.setattr(main, "service", service)
    return TestClient(main.app)


def test_feed_source_dates_and_valid_share_change(client):
    data = client.get("/api/home/feed").json()
    assert data["activity"][0]["pct_change"] == -0.1
    assert data["activity"][0]["reporting_period"] == "2025-06-30"
    assert data["activity"][0]["filing_date"] == "2025-08-14"
    assert len(data["investors"]) == 10


def test_missing_sources_are_not_filled(client):
    assert client.get("/api/investors/ark").json()["available"] is False
    company = client.get("/api/company/NVDA").json()
    assert company["available"] is False
    assert company["suggestions"] == []
    assert client.get("/api/insiders/AAPL").json()["available"] is False


def test_track_edit_evaluate_history(client):
    suggestions = client.get("/api/company/AAPL/suggested-theses").json()
    assert len(suggestions) == 4
    suggestion = suggestions[0]
    response = client.post(
        "/api/theses",
        json={"ticker": "aapl", "text": suggestion["text"], "rule": suggestion["rule"]},
    )
    assert response.status_code == 201
    thesis = response.json()
    evaluation = client.post(f"/api/theses/{thesis['id']}/evaluate").json()
    assert evaluation["status"] == "STABLE"
    assert evaluation["supporting_evidence"]
    assert len(evaluation["history"]) == 1
    edit = client.put(
        f"/api/theses/{thesis['id']}",
        json={"ticker": "AAPL", "text": "A different hypothesis", "rule": None},
    ).json()
    assert edit["status"] == "NOT_EVALUATED"
    evaluation = client.post(f"/api/theses/{thesis['id']}/evaluate").json()
    assert evaluation["status"] == "UNCERTAIN"
    assert len(evaluation["history"]) == 2


def test_watch_follow_and_sourced_ask(client):
    assert (
        client.put("/api/company/AAPL/watch", json={"enabled": True}).status_code == 200
    )
    assert (
        client.put(
            "/api/investors/berkshire/follow", json={"enabled": True}
        ).status_code
        == 200
    )
    answer = client.post(
        "/api/ask", json={"question": "Which investors I follow disclose AAPL?"}
    ).json()
    assert "Berkshire" in answer["answer"]
    assert answer["evidence"][0]["source_url"].startswith("https://www.sec.gov/")
    no_motive = client.post(
        "/api/ask", json={"question": "Why did Berkshire reduce AAPL?"}
    ).json()
    assert "no sourced" in no_motive["answer"]
    assert not no_motive["evidence"]


@pytest.mark.parametrize(
    "payload",
    [
        {"ticker": "AAPL", "text": " "},
        {"ticker": "../../x", "text": "test"},
        {
            "ticker": "AAPL",
            "text": "test",
            "rule": {"metric": "fake", "operator": ">", "threshold": 1},
        },
    ],
)
def test_invalid_thesis_input(client, payload):
    assert client.post("/api/theses", json=payload).status_code == 422


def test_unknown_entities(client):
    assert client.get("/api/investors/not-real").status_code == 404
    assert client.post("/api/theses/missing/evaluate").status_code == 404


def test_form4_codes_roles_and_footnotes():
    filing = {
        "ticker": "AAPL",
        "accession_number": "abc",
        "filing_date": "2026-09-01",
        "source_url": "https://www.sec.gov/fixture.xml",
    }
    xml = b"<ownershipDocument><issuerName>Apple</issuerName><reportingOwner><rptOwnerName>Example Person</rptOwnerName><isDirector>1</isDirector></reportingOwner><nonDerivativeTransaction><transactionCode>S</transactionCode><transactionDate><value>2026-08-30</value></transactionDate><transactionShares><value>10</value></transactionShares><transactionPricePerShare><value>200</value></transactionPricePerShare></nonDerivativeTransaction><footnotes><footnote>Plan transaction</footnote></footnotes></ownershipDocument>"
    rows = parse_form4(xml, filing)
    assert rows[0]["activity"] == "SELL"
    assert rows[0]["role"] == "Director"
    assert rows[0]["shares"] == 10
    assert rows[0]["price"] == 200
    assert rows[0]["transaction_date"] == "2026-08-30"


def test_schedule_unknown_does_not_invent_percentage():
    filing = {
        "ticker": "AAPL",
        "accession_number": "a",
        "form": "SC 13G",
        "filing_date": "2026-09-01",
        "source_url": "https://www.sec.gov/x",
    }
    rows = parse_ownership(b"<edgarSubmission/>", filing)
    assert rows[0]["ownership_percentage"] is None


def test_modern_schedule_actual_field_names():
    filing = {
        "ticker": "AAPL",
        "accession_number": "a",
        "form": "SCHEDULE 13G",
        "filing_date": "2026-09-01",
        "source_url": "https://www.sec.gov/x",
    }
    xml = b"<edgarSubmission><issuerName>Apple</issuerName><coverPageHeaderReportingPersonDetails><reportingPersonName>Example institution</reportingPersonName><classPercent>7.48</classPercent></coverPageHeaderReportingPersonDetails></edgarSubmission>"
    row = parse_ownership(xml, filing)[0]
    assert row["filer"] == "Example institution"
    assert row["ownership_percentage"] == 7.48


def test_ignore_suggestions_persists(client):
    first = client.get("/api/company/AAPL/suggested-theses").json()[0]
    assert (
        client.put(
            "/api/company/AAPL/suggestions/" + first["id"] + "/ignore",
            json={"enabled": True},
        ).status_code
        == 200
    )
    assert first["id"] not in [
        s["id"] for s in client.get("/api/company/AAPL/suggested-theses").json()
    ]


def test_quarter_duration_and_comparison():
    entries = [
        {
            "start": "2025-04-01",
            "end": "2025-06-30",
            "val": 100,
            "form": "10-Q",
            "filed": "2025-08-01",
        },
        {
            "start": "2026-04-01",
            "end": "2026-06-30",
            "val": 120,
            "form": "10-Q",
            "filed": "2026-08-01",
        },
        {
            "start": "2026-01-01",
            "end": "2026-06-30",
            "val": 220,
            "form": "10-Q",
            "filed": "2026-08-01",
        },
    ]
    payload = {
        "cik": 1,
        "facts": {"us-gaap": {"Revenues": {"units": {"USD": entries}}}},
    }
    rows = quarter_facts(payload)
    assert rows[-1]["revenue"] == 120
    assert quarterly_changes(rows)[0]["category"] == "Improved"
    assert len(quarterly_changes(rows)[0]["evidence"]) == 2


def test_refresh_failure_is_cached_and_retains_data(client, monkeypatch):
    monkeypatch.setattr(
        "backend.service.fetch_disclosures",
        lambda *a: (_ for _ in ()).throw(RuntimeError("unavailable")),
    )
    main.service.refresh("insiders", "AAPL")
    state = main.service.cache_state("insiders", "AAPL")
    assert state["error"] and not state["stale"]
    assert main.service.company("AAPL")["available"]


def test_ark_snapshots_persist_compare_and_remain_stale_on_refresh_failure(
    client, monkeypatch
):
    snapshots = iter(
        [
            PortfolioSnapshot(
                "ark",
                period,
                period,
                f"https://assets.ark-funds.com/{period}.csv",
                period,
                "Official ARKK daily fund holdings",
                [
                    Holding(
                        "TESLA INC",
                        "ARKK fund holding",
                        "88160R101",
                        shares,
                        shares * 100,
                        ticker="TSLA",
                        weight=1,
                    )
                ],
            )
            for period, shares in [("2026-09-24", 100), ("2026-09-25", 110)]
        ]
    )
    monkeypatch.setattr("backend.service.fetch_ark_holdings", lambda: next(snapshots))

    main.service.refresh("ark", "ark")
    first = main.service.investor("ark")
    assert first["available"]
    assert first["changes"] == []

    main.service.refresh("ark", "ark")
    current = main.service.investor("ark")
    assert current["latest_period"] == "2026-09-25"
    assert current["changes"][0]["activity"] == "INCREASED"
    assert len(main.service.portfolios("ark")) == 2

    def fail():
        raise RuntimeError("official source unavailable")

    monkeypatch.setattr("backend.service.fetch_ark_holdings", fail)
    main.service.refresh("ark", "ark")
    stale = main.service.investor("ark")
    assert stale["available"]
    assert stale["holdings"][0]["ticker"] == "TSLA"
    assert stale["refresh"]["stale"] is True
    assert stale["refresh"]["error"]
    assert stale["freshness"] == "Stale cached snapshot · holdings date 2026-09-25"


def test_cover_class_mapping_requires_explicit_common_stock_row():
    html = '<table><tr><td>Class A Common Stock, par $0.001</td><td><ix:nonNumeric name="dei:TradingSymbol">GOOGL</ix:nonNumeric></td></tr><tr><td>Class C Capital Stock</td><td><ix:nonNumeric name="dei:TradingSymbol">GOOG</ix:nonNumeric></td></tr><tr><td>Series A Preferred Stock</td><td><ix:nonNumeric name="dei:TradingSymbol">GOOGM</ix:nonNumeric></td></tr></table>'
    assert cover_class_tickers(html) == {"A": "GOOGL", "C": "GOOG"}


def test_legacy_duplicate_cache_keys_are_not_comparison_periods(client):
    snapshot = main.service.store.snapshots("portfolio", "berkshire")[0]
    main.service.store.save_snapshot(
        "portfolio", "berkshire", "legacy-accession-key", snapshot
    )
    assert len(main.service.portfolios("berkshire")) == 2
    assert client.get("/api/home/feed").status_code == 200


def test_tracking_same_claim_is_idempotent(client):
    claim = {"ticker": "AAPL", "text": "Cash generation stays positive", "rule": None}
    first = client.post("/api/theses", json=claim).json()
    second = client.post("/api/theses", json=claim).json()
    assert first["id"] == second["id"]
