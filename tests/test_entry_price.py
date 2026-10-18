from src.entry_price import estimate_entry_price
from src.portfolios import Holding, PortfolioSnapshot


def snapshot(period, holding):
    return PortfolioSnapshot(
        "manager",
        period,
        period,
        "https://www.sec.gov/fixture",
        period,
        holdings=[holding],
    )


def holding(shares=100, put_call=""):
    return Holding(
        "APPLE INC",
        "COM",
        "037833100",
        shares,
        shares * 100,
        put_call=put_call,
        ticker="AAPL",
        ticker_source="https://www.sec.gov/files/company_tickers.json",
    )


def test_insufficient_evidence_never_uses_reported_value_per_share():
    current = holding(150)
    result = estimate_entry_price(
        current,
        holding(100),
        snapshot("2026-03-31", holding(100)),
        snapshot("2026-06-30", current),
        {"history": []},
    )
    assert result["label"] == "Not reliably estimable"
    assert result["actual_purchase_price"] is None
    assert result["estimated_average"] is None


def test_complete_split_free_window_returns_low_confidence_range():
    current = holding(150)
    history = [
        {"date": "2026-04-01", "close": 100, "stock_split": 0},
        {"date": "2026-05-15", "close": 120, "stock_split": 0},
        {"date": "2026-06-26", "close": 110, "stock_split": 0},
    ]
    result = estimate_entry_price(
        current,
        holding(100),
        snapshot("2026-03-31", holding(100)),
        snapshot("2026-06-30", current),
        {"history": history, "source_url": "https://finance.yahoo.com/quote/AAPL/"},
    )
    assert result["status"] == "indicative_range"
    assert result["estimated_average"] == 110
    assert result["price_low"] == 100
    assert result["price_high"] == 120
    assert result["actual_purchase_price"] is None


def test_split_or_option_makes_estimate_unavailable():
    current = holding(150)
    previous = snapshot("2026-03-31", holding(100))
    now = snapshot("2026-06-30", current)
    history = [
        {"date": "2026-04-01", "close": 100, "stock_split": 0},
        {"date": "2026-05-01", "close": 50, "stock_split": 2},
        {"date": "2026-06-26", "close": 55, "stock_split": 0},
    ]
    assert (
        estimate_entry_price(
            current, holding(100), previous, now, {"history": history}
        )["status"]
        == "not_reliably_estimable"
    )
    assert (
        estimate_entry_price(holding(150, "CALL"), None, None, now, {})["status"]
        == "not_reliably_estimable"
    )
