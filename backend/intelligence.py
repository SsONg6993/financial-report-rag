"""Normalized, source-cited public events from existing dated caches only."""

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Literal

from pydantic import BaseModel, Field

from src.local_store import utc_now
from src.portfolios import compare_portfolios

EventType = Literal[
    "institutional_filing", "fund_holdings_update", "portfolio_new_position", "portfolio_increase",
    "portfolio_reduction", "portfolio_exit", "insider_transaction",
    "ownership_change", "public_update",
]


class IntelligenceEvent(BaseModel):
    id: str
    event_type: EventType
    entity_id: str
    entity_name: str
    ticker: str | None = None
    headline: str
    source_type: str
    source_url: str
    provenance: str = "Original public source"
    freshness_state: Literal["dated", "stale"] = "dated"
    reporting_period: str | None = None
    published_at: str
    event_at: str | None = None
    detected_at: str
    importance_score: float = Field(ge=0, le=1)
    facts: dict = Field(default_factory=dict)
    schema_version: int = 1
    read_at: str | None = None
    why_shown: str = "Public-source coverage"
    priority: Literal["critical", "normal", "digest"] = "digest"


def event_id(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()[:24]


def adjacent_quarters(previous: str, current: str) -> bool:
    try:
        before, after = datetime.fromisoformat(previous), datetime.fromisoformat(current)
    except ValueError:
        return False
    return before.month in {3, 6, 9, 12} and after.month in {3, 6, 9, 12} and (
        (after.year * 12 + after.month) - (before.year * 12 + before.month) == 3
    )


def comparable_snapshots(manager, previous: str, current: str) -> bool:
    if manager.id != "ark":
        return adjacent_quarters(previous, current)
    try:
        gap = (datetime.fromisoformat(current) - datetime.fromisoformat(previous)).days
    except ValueError:
        return False
    return 1 <= gap <= 7


def change_importance(change: dict) -> float:
    """Bounded event-ranking heuristic, explicitly not an investment score."""
    base = 0.4 if change["activity"] in {"NEW", "EXITED"} else 0.1
    relative = min(abs(change.get("share_change_pct") or 0), 1) * 0.3
    weight = min(abs(change.get("weight_change") or 0), 0.1) * 2
    size = min((change.get("value_after") or change.get("value_before") or 0) / 1e9, 1) * 0.1
    return round(min(base + relative + weight + size, 1), 3)


class IntelligenceService:
    def __init__(self, research):
        self.research = research
        self.store = research.store

    def _save(self, event: IntelligenceEvent):
        if not event.source_url.startswith("https://"):
            return
        new = self.store.save_intelligence_event(event.model_dump())
        if new and self._priority(event)[0] != "digest":
            try:
                age = datetime.now(UTC).date() - datetime.fromisoformat(event.published_at[:10]).date()
            except ValueError:
                return
            if timedelta(0) <= age <= timedelta(days=2):
                self.store.enqueue_notification(event.id, "local", self._priority(event)[0])

    def _priority(self, event: IntelligenceEvent) -> tuple[str, str]:
        watched = event.ticker in self.store.watchlist() if event.ticker else False
        followed = event.entity_id in self.store.follows()
        source_followed = event.entity_id in self.store.source_follows()
        if event.event_type in {"portfolio_new_position", "portfolio_exit"} and watched and followed:
            return "critical", "Followed manager's reported new/exit position overlaps your watchlist"
        if event.event_type == "insider_transaction" and watched and event.facts.get("activity") in {"BUY", "SELL"}:
            return "critical", "Reported Form 4 transaction overlaps your watchlist"
        if followed or watched or source_followed:
            return "normal", "Matches a followed manager, source or watchlist company"
        return "digest", "Other tracked public-source event"

    def ingest_cached(self):
        """Idempotent cache materialization; never performs SEC or web requests."""
        stamp = utc_now()
        for manager in self.research.registry.all():
            snapshots = self.research.portfolios(manager.id)
            if not snapshots:
                continue
            current = snapshots[0]
            is_fund = manager.id == "ark"
            self._save(IntelligenceEvent(
                id=event_id("filing", manager.id, current.accession, current.reporting_period),
                event_type="fund_holdings_update" if is_fund else "institutional_filing", entity_id=manager.id,
                entity_name=manager.name, headline=f"{manager.name} published daily holdings" if is_fund else f"{manager.name} filed reported holdings",
                source_type=current.source_type, source_url=current.source_url,
                reporting_period=current.reporting_period, published_at=current.filing_date,
                detected_at=stamp, importance_score=0.25,
                facts={"accession": current.accession, "filing_date": current.filing_date},
            ))
            if len(snapshots) < 2 or not comparable_snapshots(manager, snapshots[1].reporting_period, current.reporting_period):
                continue
            for change in compare_portfolios(snapshots[1], current):
                if change["activity"] == "UNCHANGED":
                    continue
                kind = {"NEW": "portfolio_new_position", "INCREASED": "portfolio_increase",
                        "REDUCED": "portfolio_reduction", "EXITED": "portfolio_exit"}[change["activity"]]
                ticker = change["ticker"] or None
                self._save(IntelligenceEvent(
                    id=event_id("position", manager.id, current.accession, current.reporting_period,
                                change["cusip"], change["security_class"], change["put_call"]),
                    event_type=kind, entity_id=manager.id, entity_name=manager.name,
                    ticker=ticker, headline=f"{manager.name}: reported position {change['activity'].lower()} in {ticker or change['issuer']}",
                    source_type=current.source_type, source_url=current.source_url,
                    reporting_period=current.reporting_period, published_at=current.filing_date,
                    detected_at=stamp, importance_score=change_importance(change),
                    facts={k: change[k] for k in ("activity", "issuer", "shares_before", "shares_after",
                           "share_change", "share_change_pct", "value_before", "value_after", "weight_before", "weight_after",
                           "weight_change", "previous_period", "filing_date")},
                ))
        with self.store.connect() as db:
            tickers = [r[0] for r in db.execute(
                "SELECT DISTINCT entity_id FROM snapshots WHERE kind IN ('insiders','ownership')")]
        for ticker in tickers:
            for kind in ("insiders", "ownership"):
                snapshots = self.store.snapshots(kind, ticker)
                for row in (snapshots[0].get("records", []) if snapshots else []):
                    source_url = row.get("source_url", "")
                    filing_date = row.get("filing_date", "")
                    if not source_url or not filing_date:
                        continue
                    person = row.get("insider") or row.get("filer") or ticker
                    event_type = "insider_transaction" if kind == "insiders" else "ownership_change"
                    self._save(IntelligenceEvent(
                        id=event_id(event_type, str(row.get("id", "")), ticker, source_url),
                        event_type=event_type, entity_id=ticker, entity_name=person,
                        ticker=ticker, headline=f"{person}: {row.get('activity', 'public disclosure')} reported for {ticker}",
                        source_type=row.get("source_type", "SEC disclosure"), source_url=source_url,
                        reporting_period=row.get("reporting_period"), published_at=filing_date,
                        event_at=row.get("transaction_date"), detected_at=stamp,
                        importance_score=0.5 if row.get("activity") in {"BUY", "SELL"} else 0.25,
                        facts={"activity": row.get("activity"), "filing_date": filing_date,
                               "transaction_date": row.get("transaction_date")},
                    ))
        # Existing official RSS snapshots are reused; this does not refresh feeds.
        for source_event in self.research.market_pulse.events():
            issuer = next((p.issuer for p in self.research.market_pulse.providers
                           if p.id == source_event.provider_id), None)
            self._save(IntelligenceEvent(
                id=event_id("public", source_event.provider_id, source_event.source_url),
                event_type="public_update", entity_id=source_event.provider_id,
                entity_name=source_event.source, ticker=issuer,
                headline=source_event.headline, source_type="Official public feed",
                source_url=source_event.source_url,
                published_at=source_event.published_at, event_at=source_event.event_time,
                detected_at=stamp, importance_score=0.15,
                facts={"category": source_event.category, "provider_id": source_event.provider_id},
            ))

    def feed(self, category: str = "all", limit: int = 50) -> dict:
        self.ingest_cached()
        items = [IntelligenceEvent.model_validate(row) for row in self.store.intelligence_events(1000)]
        watched = set(self.store.watchlist())
        followed = set(self.store.follows())
        sources = set(self.store.source_follows())
        groups = {
            "investors": {"institutional_filing", "fund_holdings_update", "portfolio_new_position", "portfolio_increase", "portfolio_reduction", "portfolio_exit"},
            "institutions": {"institutional_filing", "portfolio_new_position", "portfolio_increase", "portfolio_reduction", "portfolio_exit"},
            "insiders": {"insider_transaction"},
            "companies": {"ownership_change"},
            "public_updates": {"public_update"},
        }
        if category not in {"all", "my_watchlist", *groups}:
            raise ValueError("Unknown feed filter")
        if category in groups:
            items = [e for e in items if e.event_type in groups[category]]
        if category == "institutions":
            items = [e for e in items if e.source_type == "SEC Form 13F"]
        if category == "my_watchlist":
            items = [e for e in items if e.ticker in watched]
        ranked = []
        for event in items:
            priority, reason = self._priority(event)
            rank = int(event.entity_id in followed or event.entity_id in sources or event.ticker in watched)
            threshold = 150 if event.source_type == "SEC Form 13F" else (7 if event.entity_id == "ark" else 30)
            source_date = event.reporting_period or event.published_at[:10]
            try:
                stale = (datetime.now(UTC).date() - datetime.fromisoformat(source_date[:10]).date()).days > threshold
            except ValueError:
                stale = True
            ranked.append((rank, event.model_copy(update={"priority": priority, "why_shown": reason,
                                                   "freshness_state": "stale" if stale else "dated"})))
        ranked.sort(key=lambda row: (row[0], row[1].published_at, row[1].importance_score), reverse=True)
        result = [event for _, event in ranked]
        return {"events": [e.model_dump() for e in result[:max(1, min(limit, 100))]],
                "as_of": utc_now(), "coverage": "Cached public sources and tracked filings only; 13F positions are delayed and partial."}

    def company_activity(self, ticker: str) -> dict:
        rows = []
        for manager in self.research.registry.all():
            if manager.source_type != "SEC Form 13F":
                continue
            snapshots = self.research.portfolios(manager.id)
            if not snapshots:
                continue
            latest = snapshots[0]
            holdings = [h for h in latest.holdings if h.ticker == ticker and not h.put_call]
            changes = []
            if len(snapshots) > 1 and adjacent_quarters(snapshots[1].reporting_period, latest.reporting_period):
                changes = [c for c in compare_portfolios(snapshots[1], latest) if c["ticker"] == ticker and not c["put_call"]]
            if not holdings and not any(c["activity"] == "EXITED" for c in changes):
                continue
            rows.append({"manager_id": manager.id, "manager": manager.name,
                         "reporting_period": latest.reporting_period, "filing_date": latest.filing_date,
                         "source_url": latest.source_url, "reported_shares": sum(h.shares for h in holdings),
                         "activity": changes[0]["activity"] if len(changes) == 1 else "NOT_COMPARABLE"})
        periods = {r["reporting_period"] for r in rows}
        comparable = len(periods) == 1
        counts = {k: sum(r["activity"] == k for r in rows) for k in ("INCREASED", "REDUCED", "NEW", "EXITED")}
        return {"ticker": ticker, "tracked_managers": rows, "counts": counts if comparable else None,
                "convergence": comparable and sum(counts.values()) >= 2,
                "coverage": "Only cached tracked 13F managers; periods must match for aggregate counts. Not current holdings or sentiment."}

    def daily_brief(self) -> dict:
        self.ingest_cached()
        today = datetime.now(UTC).date().isoformat()
        events = [IntelligenceEvent.model_validate(row) for row in self.store.intelligence_events(1000)
                  if row["published_at"][:10] == today]
        watched = set(self.store.watchlist())
        return {"date": today,
                "institutional_activity": [e.model_dump() for e in events if e.source_type == "SEC Form 13F" and (e.event_type.startswith("portfolio_") or e.event_type == "institutional_filing")][:20],
                "fund_holdings": [e.model_dump() for e in events if e.source_type != "SEC Form 13F" and (e.event_type.startswith("portfolio_") or e.event_type == "fund_holdings_update")][:20],
                "watchlist": [e.model_dump() for e in events if e.ticker in watched][:20],
                "worth_investigating": [e.model_dump() for e in events if e.ticker in watched and e.importance_score >= 0.3][:10],
                "insiders": [e.model_dump() for e in events if e.event_type == "insider_transaction"][:20],
                "public_updates": [e.model_dump() for e in events if e.event_type == "public_update"][:20],
                "note": "No events in a section means no matching cached, dated public event—not proof of no real-world activity."}
