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
    name = "yahoo"

    def __init__(self, timeout: float = 12.0):
        self.timeout = timeout

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
                    {
                        "date": str(index.date()),
                        "close": float(row["Close"]),
                        "stock_split": float(row.get("Stock Splits") or 0),
                    }
                    for index, row in history_frame.iterrows()
                    if row.get("Close") is not None
                ]
            return MarketSnapshot(
                ticker=ticker,
                price=info.get("currentPrice")
                or info.get("regularMarketPrice")
                or (history[-1]["close"] if history else None),
                previous_close=info.get("regularMarketPreviousClose")
                or info.get("previousClose")
                or (history[-2]["close"] if len(history) > 1 else None),
                quote_as_of=datetime.fromtimestamp(
                    info["regularMarketTime"], UTC
                ).isoformat()
                if info.get("regularMarketTime")
                else (history[-1]["date"] if history else None),
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
            return MarketSnapshot(
                ticker=ticker,
                error=f"Yahoo Finance unavailable: {type(exc).__name__}",
                error_code="provider_unavailable",
            )


class NasdaqProvider:
    """Independent quote fallback; missing valuation fields remain absent."""

    name = "nasdaq"

    def __init__(self, timeout: float = 12.0):
        self.timeout = timeout

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
            response = requests.get(url, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()["data"]
            quote = data["primaryData"]
            summary = {}
            try:
                response = requests.get(
                    f"https://api.nasdaq.com/api/quote/{ticker}/summary?assetclass=stocks",
                    headers=headers,
                    timeout=self.timeout,
                )
                response.raise_for_status()
                summary = response.json()["data"].get("summaryData", {})
            except (requests.RequestException, ValueError, KeyError, TypeError):
                pass  # Quote remains usable if optional company metadata fails.
            return MarketSnapshot(
                ticker=ticker,
                price=numeric(quote.get("lastSalePrice")),
                previous_close=numeric(summary.get("PreviousClose", {}).get("value")),
                market_cap=numeric(summary.get("MarketCap", {}).get("value")),
                trailing_pe=numeric(summary.get("PERatio", {}).get("value")),
                quote_as_of=quote.get("lastTradeTimestamp"),
                fetched_at=datetime.now(UTC).isoformat(),
                provider="Nasdaq",
                source_url=f"https://www.nasdaq.com/market-activity/stocks/{ticker.lower()}",
                company_name=data.get("companyName", ticker),
                status="live" if quote.get("isRealTime") is True else "delayed",
            )
        except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
            return MarketSnapshot(
                ticker=ticker,
                error=f"Nasdaq unavailable: {type(exc).__name__}",
                error_code="provider_unavailable",
            )


class ResilientMarketProvider:
    def __init__(self, providers=None, *, cache_ttl_seconds: int = 300):
        self.providers = (
            providers
            if providers is not None
            else [YahooFinanceProvider(), NasdaqProvider()]
        )
        self.cache_ttl_seconds = cache_ttl_seconds

    @classmethod
    def from_config(cls, config):
        factories = {
            "yahoo": lambda: YahooFinanceProvider(config.market_data_timeout),
            "nasdaq": lambda: NasdaqProvider(config.market_data_timeout),
        }
        providers = [
            factories[name]()
            for name in config.market_data_providers
            if name in factories
        ]
        return cls(providers, cache_ttl_seconds=config.market_cache_ttl_seconds)

    def snapshot(self, ticker: str) -> MarketSnapshot:
        attempts = []
        if not self.providers:
            return MarketSnapshot(
                ticker=normalize_ticker(ticker),
                error="No market-data provider is configured",
                error_code="not_configured",
                cache_ttl_seconds=self.cache_ttl_seconds,
            )
        for provider in self.providers:
            try:
                result = provider.snapshot(ticker)
                attempts.append(
                    {
                        "provider": getattr(provider, "name", provider.__class__.__name__),
                        "status": "success" if result.price else "unavailable",
                        "reason": result.error,
                    }
                )
                if (
                    result.price is not None
                    and math.isfinite(result.price)
                    and result.price > 0
                ):
                    result.attempts = attempts
                    result.cache_ttl_seconds = self.cache_ttl_seconds
                    return result
            except Exception as exc:  # noqa: BLE001 - provider isolation is intentional.
                attempts.append(
                    {
                        "provider": getattr(provider, "name", provider.__class__.__name__),
                        "status": "error",
                        "reason": type(exc).__name__,
                    }
                )
                continue
        return MarketSnapshot(
            ticker=normalize_ticker(ticker),
            error="All configured market quote providers are unavailable",
            error_code="provider_unavailable",
            attempts=attempts,
            cache_ttl_seconds=self.cache_ttl_seconds,
        )
