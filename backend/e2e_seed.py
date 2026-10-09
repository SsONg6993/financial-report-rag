"""Small deterministic synthetic/browser fixtures, never used by production."""

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from src.companyfacts import CONCEPTS
from src.local_store import LocalStore
from src.models import AnnualFinancials, MarketSnapshot
from src.portfolios import BY_ID, Holding, PortfolioSnapshot

COMPANIES = {
    "AAPL": (320193, "Apple Inc.", "Q3", "2026-06-27", "2026-03-29", "2025-06-28", "2025-03-30", "2025-09-28", "2024-09-29"),
    "META": (1326801, "Meta Platforms, Inc.", "Q2", "2026-06-30", "2026-04-01", "2025-06-30", "2025-04-01", "2026-01-01", "2025-01-01"),
    "RKLB": (1819994, "Rocket Lab USA, Inc.", "Q2", "2026-06-30", "2026-04-01", "2025-06-30", "2025-04-01", "2026-01-01", "2025-01-01"),
    "NVDA": (1045810, "NVIDIA Corporation", "Q2", "2026-06-30", "2026-04-01", "2025-06-30", "2025-04-01", "2026-01-01", "2025-01-01"),
    "TSLA": (1318605, "Tesla, Inc.", "Q2", "2026-06-30", "2026-04-01", "2025-06-30", "2025-04-01", "2026-01-01", "2025-01-01"),
    "KEYS": (1601046, "Keysight Technologies, Inc.", "Q3", "2026-07-31", "2026-05-01", "2025-07-31", "2025-05-01", "2025-11-01", "2024-11-01"),
}


def _facts(cik, fiscal, end, start, prior_end, prior_start, ytd_start, prior_ytd):
    accession = f"e2e-{cik}-2026"
    facts = {}
    values = {
        "revenue": (120_000_000_000, 100_000_000_000),
        "gross_profit": (60_000_000_000, 49_000_000_000),
        "operating_income": (31_000_000_000, 25_000_000_000),
        "net_income": (26_000_000_000, 20_000_000_000),
        "eps": (2.6, 2.0),
        "operating_cash_flow": (70_000_000_000, 58_000_000_000),
        "capital_expenditure": (14_000_000_000, 11_000_000_000),
    }
    for metric, (current, previous) in values.items():
        cash = metric in {"operating_cash_flow", "capital_expenditure"}
        unit = "USD/shares" if metric == "eps" else "USD"
        entries = []
        for value, period_start, period_end, year in (
            (current, ytd_start if cash else start, end, 2026),
            (previous, prior_ytd if cash else prior_start, prior_end, 2025),
        ):
            entries.append({"start": period_start, "end": period_end, "val": value,
                            "form": "10-Q", "fy": year, "fp": fiscal,
                            "filed": "2026-08-14" if year == 2026 else "2025-08-14",
                            "accn": accession if year == 2026 else f"e2e-{cik}-2025"})
        facts[CONCEPTS[metric][0]] = {"units": {unit: entries}}
    return {"cik": cik, "facts": {"us-gaap": facts}}


def _company(store, cache, ticker, details):
    cik, name, fiscal, end, start, prior_end, prior_start, ytd_start, prior_ytd = details
    source = f"https://www.sec.gov/edgar/browse/?CIK={cik}&owner=exclude"
    filing = {"accession_number": f"e2e-{cik}-2026", "form": "10-Q",
              "report_date": end, "filing_date": "2026-08-14", "source_url": source,
              "company": name, "cik": cik}
    annual = AnnualFinancials(2025, revenue=400_000_000_000, gross_profit=190_000_000_000,
                              net_income=80_000_000_000, operating_income=110_000_000_000,
                              operating_cash_flow=120_000_000_000,
                              capital_expenditure=25_000_000_000,
                              free_cash_flow=95_000_000_000,
                              gross_margin=0.475, revenue_growth=0.1, debt=45_000_000_000,
                              source_url=source)
    store.save_snapshot("company", ticker, "current", {
        "ticker": ticker, "filings": [filing], "financials": [asdict(annual)],
        "market": {"company_name": name}, "provider_warnings": ["Synthetic E2E fixture"],
    })
    market = MarketSnapshot(ticker, price=100.0, previous_close=98.5,
                            quote_as_of="2026-10-01T20:00:00+00:00",
                            fetched_at="2026-10-01T20:05:00+00:00", provider="E2E fixture",
                            source_url=source, status="delayed", company_name=name)
    store.save_snapshot("market", ticker, "current", asdict(market))
    risk = {"text": "The company faces competitive risks that could adversely affect demand and margins.",
            "section": "Risk Factors", "period": end, "source_url": source,
            "source_type": "Synthetic E2E filing excerpt"}
    store.save_snapshot("filing_chunks", ticker, filing["accession_number"],
                        {"filing": filing, "chunks": [risk]})
    folder = cache / ticker
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "companyfacts.json").write_text(json.dumps(_facts(cik, fiscal, end, start,
             prior_end, prior_start, ytd_start, prior_ytd)), encoding="utf-8")


def _portfolio(store, manager, before, after, ticker="AAPL", issuer="APPLE INC"):
    source = f"https://www.sec.gov/edgar/browse/?CIK={BY_ID[manager].cik}&owner=exclude"
    for period, shares, accession in (("2026-03-31", before, "prior"),
                                      ("2026-06-30", after, "current")):
        holdings = [Holding(issuer, "COM", "037833100", shares, shares * 100,
                            ticker=ticker, weight=1.0)] if shares else []
        snapshot = PortfolioSnapshot(manager, period, "2026-05-15" if accession == "prior" else "2026-08-14",
                                     source, f"e2e-{manager}-{accession}", holdings=holdings)
        store.save_snapshot("portfolio", manager, period, snapshot.to_dict())


def seed(database: Path, cache: Path):
    """Initialize V2 tables and only the records required by browser scenarios."""
    store = LocalStore(database)
    store.watch("AAPL")
    for ticker, details in COMPANIES.items():
        _company(store, cache, ticker, details)
    cache.mkdir(parents=True, exist_ok=True)
    (cache / "company_directory.json").write_text(json.dumps({
        "checked_at": datetime.now(UTC).isoformat(),
        "directory": {
            "fields": ["cik", "name", "ticker", "exchange"],
            "data": [[details[0], details[1], ticker, "NYSE" if ticker == "KEYS" else "Nasdaq"]
                     for ticker, details in COMPANIES.items()]
                    + [[1067983, "BERKSHIRE HATHAWAY INC", "BRK-B", "NYSE"]],
        },
    }), encoding="utf-8")
    _portfolio(store, "berkshire", 200, 150)
    _portfolio(store, "coatue", 60, 80, "NVDA", "NVIDIA CORP")
    _portfolio(store, "pershing", 40, 45)
    ark = PortfolioSnapshot("ark", "2026-10-01", "2026-10-01",
                            "https://www.ark-funds.com/funds/arkk", "e2e-ark-2026-10-01",
                            source_type="Official ARKK daily fund holdings",
                            holdings=[Holding("TESLA INC", "COM", "88160R101", 100, 10000,
                                              ticker="TSLA", weight=1.0)])
    store.save_snapshot("portfolio", "ark", ark.reporting_period, ark.to_dict())
    store.save_snapshot("insiders", "AAPL", "current", {
        "records": [{"id": "e2e-form4-aapl", "source_type": "SEC Form 4", "ticker": "AAPL",
                     "insider": "Newstead Jennifer", "role": "SVP", "issuer": "Apple Inc.",
                     "security": "Common Stock", "transaction_date": "2026-09-22",
                     "reporting_period": "2026-09-22", "filing_date": "2026-09-24",
                     "activity": "SELL", "shares": 2399.0, "price": 340.06,
                     "transaction_code": "S", "derivative": False,
                     "context": "Transaction code S. Synthetic E2E fixture, not a trade signal.",
                     "footnotes": [],
                     "source_url": "https://www.sec.gov/Archives/edgar/data/320193/000114036126037584/xslF345X06/form4.xml"}],
        "warnings": [], "coverage": "Synthetic E2E fixture"})
