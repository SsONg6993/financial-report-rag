"""Optional market-data providers; failures return an explicit partial snapshot."""

import math
from datetime import UTC, datetime
from typing import Protocol

import requests

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
            try:
                info = security.info or {}
            except Exception:  # noqa: BLE001 - price history can work when quote metadata fails.
                info = {}
            try:
                history_frame = security.history(period="1y", auto_adjust=False)
            except Exception:  # noqa: BLE001 - history failures must not discard a valid quote.
                history_frame = None
            history = []
            if history_frame is not None and not history_frame.empty:
                history = [
                    {"date": str(index.date()), "close": float(row["Close"])}
                    for index, row in history_frame.iterrows()
                    if row.get("Close") is not None
                ]
            return MarketSnapshot(
                ticker=ticker,
                price=info.get("currentPrice") or info.get("regularMarketPrice") or (history[-1]["close"] if history else None),
                previous_close=info.get("regularMarketPreviousClose") or info.get("previousClose") or (history[-2]["close"] if len(history) > 1 else None),
                quote_as_of=datetime.fromtimestamp(info["regularMarketTime"], UTC).isoformat() if info.get("regularMarketTime") else (history[-1]["date"] if history else None),
                fetched_at=datetime.now(UTC).isoformat(),
                provider="Yahoo Finance",
                source_url=f"https://finance.yahoo.com/quote/{ticker}/",
                status="delayed",
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


class NasdaqProvider:
    """Independent quote fallback; missing valuation fields remain absent."""

    def snapshot(self, ticker: str) -> MarketSnapshot:
        ticker = normalize_ticker(ticker)
        url = f"https://api.nasdaq.com/api/quote/{ticker}/info?assetclass=stocks"
        headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
        def numeric(value):
            try:
                result = float(str(value).replace("$", "").replace(",", ""))
                return result if math.isfinite(result) else None
            except (TypeError, ValueError):
                return None
        try:
            response = requests.get(url, headers=headers, timeout=12)
            response.raise_for_status()
            data = response.json()["data"]
            quote = data["primaryData"]
            summary = {}
            try:
                response = requests.get(f"https://api.nasdaq.com/api/quote/{ticker}/summary?assetclass=stocks", headers=headers, timeout=12)
                response.raise_for_status()
                summary = response.json()["data"].get("summaryData", {})
            except (requests.RequestException, ValueError, KeyError, TypeError):
                pass  # Quote remains usable if optional company metadata fails.
            return MarketSnapshot(
                ticker=ticker, price=numeric(quote.get("lastSalePrice")),
                previous_close=numeric(summary.get("PreviousClose", {}).get("value")),
                market_cap=numeric(summary.get("MarketCap", {}).get("value")),
                trailing_pe=numeric(summary.get("PERatio", {}).get("value")),
                quote_as_of=quote.get("lastTradeTimestamp"), fetched_at=datetime.now(UTC).isoformat(),
                provider="Nasdaq", source_url=f"https://www.nasdaq.com/market-activity/stocks/{ticker.lower()}",
                company_name=data.get("companyName", ticker),
                status="live" if quote.get("isRealTime") is True else "delayed",
            )
        except (requests.RequestException, ValueError, KeyError, TypeError):
            return MarketSnapshot(ticker=ticker, error="Nasdaq quote unavailable")


class ResilientMarketProvider:
    def __init__(self, providers=None):
        self.providers = providers if providers is not None else [YahooFinanceProvider(), NasdaqProvider()]

    def snapshot(self, ticker: str) -> MarketSnapshot:
        for provider in self.providers:
            try:
                result = provider.snapshot(ticker)
                if result.price is not None and math.isfinite(result.price) and result.price > 0:
                    return result
            except Exception:  # noqa: BLE001, S112 - independent providers must not gate each other.
                continue
        return MarketSnapshot(ticker=ticker, error="All market quote providers unavailable")
