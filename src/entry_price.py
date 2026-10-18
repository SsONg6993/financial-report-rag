"""Conservative institutional entry-price ranges from stored public evidence."""

from __future__ import annotations

import math
from datetime import date, timedelta

from src.portfolios import Holding, PortfolioSnapshot


def _unavailable(reason: str, window: dict | None = None) -> dict:
    return {
        "status": "not_reliably_estimable",
        "label": "Not reliably estimable",
        "actual_purchase_price": None,
        "estimated_average": None,
        "price_low": None,
        "price_high": None,
        "confidence": "insufficient",
        "window": window,
        "method": "No acquisition cost inferred from quarter-end reported value.",
        "assumptions": [reason],
        "source_url": "",
    }


def estimate_entry_price(
    current: Holding,
    previous: Holding | None,
    previous_snapshot: PortfolioSnapshot | None,
    current_snapshot: PortfolioSnapshot,
    market: dict | None,
) -> dict:
    """Estimate only an indicative close-price range for a verified share increase."""
    if current.put_call or current.share_type.upper() != "SH":
        return _unavailable("Options and non-share positions are not estimated.")
    if not current.ticker:
        return _unavailable("A verified ticker mapping is required.")
    if previous_snapshot is None:
        return _unavailable("A comparable prior disclosure is required.")
    before = previous.shares if previous else 0
    added = current.shares - before
    window = {
        "start": previous_snapshot.reporting_period,
        "end": current_snapshot.reporting_period,
        "shares_added": added,
    }
    if added <= 0:
        return _unavailable(
            "The disclosed share count did not increase during this window.", window
        )
    history = (market or {}).get("history") or []
    if not history:
        return _unavailable("Stored historical prices do not cover the window.", window)
    start = date.fromisoformat(previous_snapshot.reporting_period)
    end = date.fromisoformat(current_snapshot.reporting_period)
    rows = []
    for row in history:
        try:
            day = date.fromisoformat(str(row["date"])[:10])
            close = float(row["close"])
        except (KeyError, TypeError, ValueError):
            continue
        if start < day <= end and math.isfinite(close) and close > 0:
            if float(row.get("stock_split") or 0) != 0:
                return _unavailable(
                    "A stock split occurred in the possible acquisition window; "
                    "share-change comparability requires manual adjustment.",
                    window,
                )
            rows.append((day, close))
    if not rows:
        return _unavailable(
            "No valid closes fall inside the acquisition window.", window
        )
    if rows[0][0] > start + timedelta(days=10) or rows[-1][0] < end - timedelta(
        days=10
    ):
        return _unavailable(
            "Historical prices do not span enough of the possible acquisition window.",
            window,
        )
    closes = [close for _, close in rows]
    return {
        "status": "indicative_range",
        "label": "Indicative acquisition-window range",
        "actual_purchase_price": None,
        "estimated_average": sum(closes) / len(closes),
        "price_low": min(closes),
        "price_high": max(closes),
        "confidence": "low",
        "window": window,
        "method": (
            "Arithmetic mean and range of unadjusted daily closes during the entire "
            "possible acquisition window; not a transaction-weighted purchase price."
        ),
        "assumptions": [
            (
                "The position increase occurred sometime after the prior reporting date and "
                "on or before the current reporting date."
            ),
            "No non-split corporate action or transfer changed the share count.",
            "13F dates and daily closes cannot identify transaction dates or execution prices.",
        ],
        "source_url": (market or {}).get("source_url", ""),
    }
