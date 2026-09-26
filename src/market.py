"""Optional market-data providers; failures return an explicit partial snapshot."""

from typing import Protocol

from src.models import MarketSnapshot
from src.sec import normalize_ticker


class MarketDataProvider(Protocol):
    def snapshot(self, ticker: str) -> MarketSnapshot: ...


class YahooFinanceProvider:
    def snapshot(self, ticker: str) -> MarketSnapshot:
        ticker = normalize_ticker(ticker)
        try:
            import yfinance as yf

            security = yf.Ticker(ticker)
            info = security.info or {}
            history_frame = security.history(period="1y", auto_adjust=False)
            history = []
            if not history_frame.empty:
                history = [
                    {"date": str(index.date()), "close": float(row["Close"])}
                    for index, row in history_frame.iterrows()
                    if row.get("Close") is not None
                ]
            return MarketSnapshot(
                ticker=ticker,
                price=info.get("currentPrice") or info.get("regularMarketPrice"),
                market_cap=info.get("marketCap"),
                high_52_week=info.get("fiftyTwoWeekHigh"),
                low_52_week=info.get("fiftyTwoWeekLow"),
                volume=info.get("volume"),
                enterprise_value=info.get("enterpriseValue"),
                trailing_pe=info.get("trailingPE"),
                price_to_sales=info.get("priceToSalesTrailing12Months"),
                price_to_book=info.get("priceToBook"),
                ev_to_revenue=info.get("enterpriseToRevenue"),
                ev_to_ebitda=info.get("enterpriseToEbitda"),
                company_name=info.get("longName", ticker),
                description=info.get("longBusinessSummary", ""),
                currency=info.get("currency", "USD"),
                history=history,
            )
        except Exception as exc:  # noqa: BLE001 - optional provider must fail closed.
            return MarketSnapshot(ticker=ticker, error=f"Market data unavailable: {type(exc).__name__}")
