from dataclasses import asdict
from pathlib import Path

from streamlit.testing.v1 import AppTest

from src.local_store import LocalStore
from src.models import AnnualFinancials
from src.portfolios import Holding, PortfolioSnapshot


def test_four_pages_render_with_local_theses_and_portfolio(tmp_path, monkeypatch):
    path = tmp_path / "ui.sqlite3"
    monkeypatch.setenv("THESISLENS_DB", str(path))
    monkeypatch.setenv("ENABLE_JEV", "false")
    store = LocalStore(path)
    store.watch("AAPL")
    store.follow("berkshire")
    store.save_thesis("AAPL", "Gross margin remains above 45%", {"metric": "gross_margin", "operator": ">", "threshold": 0.45})
    store.save_thesis("AAPL", "Services remains a growth driver")
    store.save_thesis("AAPL", "China weakness stabilizes")
    store.save_thesis("AAPL", "FCF remains strong", {"metric": "free_cash_flow", "operator": ">", "threshold": 90e9})
    store.save_snapshot("company", "AAPL", "current", {"ticker": "AAPL", "filings": [],
                        "financials": [asdict(AnnualFinancials(2024, revenue=100, gross_margin=0.44)),
                                       asdict(AnnualFinancials(2025, revenue=120, gross_margin=0.47))],
                        "market": {"company_name": "Apple"}})
    snapshot = PortfolioSnapshot("berkshire", "2026-06-30", "2026-08-14", "https://www.sec.gov/example", "2",
                                 holdings=[Holding("APPLE INC", "COM", "037833100", 10, 100, ticker="AAPL", weight=1)])
    store.save_snapshot("portfolio", "berkshire", "2026-06-30:2", snapshot.to_dict())
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py", default_timeout=30).run()
    assert not app.exception
    assert app.radio(key="navigation").options == ["Home", "Research", "Public Portfolios", "Ask"]
    assert not app.tabs
    app.radio(key="navigation").set_value("Research").run()
    assert not app.exception
    assert any(item.label == "Evaluate thesis evidence" for item in app.button)
    next(item for item in app.button if item.label == "Evaluate thesis evidence").click().run()
    assert not app.exception
    assert store.theses("AAPL")[0]["status"] == "STRENGTHENED"
    assert len(store.theses("AAPL")) == 4
    assert store.theses("AAPL")[1]["status"] == "UNCERTAIN"
    app.radio(key="navigation").set_value("Public Portfolios").run()
    assert not app.exception
    assert any(item.value == "Public Financial Disclosures" for item in app.subheader)
    assert app.dataframe
    monkeypatch.setattr("src.thesis_research.load_company", lambda ticker, store, refresh: (None, []))
    next(item for item in app.button if item.label == "Research this company").click().run()
    assert not app.exception
    assert app.radio(key="navigation").value == "Research"
    assert app.session_state["selected_ticker"] == "AAPL"
    app.radio(key="navigation").set_value("Ask").run()
    assert not app.exception
