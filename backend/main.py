"""Run: python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000."""

from typing import Annotated, Literal

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator

load_dotenv()
from backend.models import (
    Answer,
    Company,
    Feed,
    Holding,
    Investor,
    PositionChange,
    Suggestion,
    Thesis,
)
from backend.service import ResearchService
from src.company_directory import CompanyDirectory
from src.sec import normalize_ticker
from src.thesis import RULE_METRICS

app = FastAPI(
    title="ThesisLens",
    version="0.1.0",
    description="Local, single-user investment research. Public disclosures are research inputs, not trading instructions.",
)
service = ResearchService()
company_directory = CompanyDirectory()


class Rule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    metric: str
    operator: Literal[">", ">=", "<", "<="]
    threshold: float = Field(allow_inf_nan=False)

    @field_validator("metric")
    @classmethod
    def valid_metric(cls, value):
        if value not in RULE_METRICS:
            raise ValueError("Unsupported metric")
        return value


class ThesisInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ticker: str
    text: str = Field(min_length=1, max_length=2000)
    rule: Rule | None = None

    @field_validator("ticker")
    @classmethod
    def ticker_value(cls, value):
        return normalize_ticker(value)

    @field_validator("text")
    @classmethod
    def meaningful_text(cls, value):
        if not value.strip():
            raise ValueError("A thesis needs text")
        return value.strip()


class Toggle(BaseModel):
    enabled: bool


class AskInput(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    ticker: str = "AAPL"


def valid_ticker(ticker):
    try:
        return normalize_ticker(ticker)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


def valid_investor(key):
    if service.registry.get(key) is None:
        raise HTTPException(404, "Investor not found")
    return key


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/home/feed", response_model=Feed)
def home(background: BackgroundTasks):
    for key in service.store.follows():
        if service.registry.get(key) is not None:
            service.schedule(background, "ark" if key == "ark" else "portfolio", key)
    for ticker in service.store.watchlist():
        for kind in ("company", "market", "insiders", "ownership"):
            service.schedule(background, kind, ticker)
    return service.home()


@app.get("/api/investors", response_model=list[Investor])
def investors():
    return service.investors()


@app.get("/api/portfolio-overlap")
def portfolio_overlap(
    investors: Annotated[list[str], Query(min_length=2, max_length=5)],
    period: str | None = None,
):
    try:
        return service.portfolio_overlap(investors, period)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get("/api/companies/search")
def search_companies(q: str = ""):
    if len(q) > 100:
        raise HTTPException(422, "Search is too long")
    try:
        return company_directory.search(q)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc


@app.get("/api/companies/resolve")
def resolve_company(q: str):
    if len(q) > 100:
        raise HTTPException(422, "Search is too long")
    try:
        return company_directory.resolve(q)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc


class ResolveManager(BaseModel):
    cik: int = Field(ge=1, le=9_999_999_999)


@app.get("/api/investors/search")
def search_investors(q: str = ""):
    return [
        {
            "id": item.id,
            "name": item.name,
            "cik": item.cik,
            "manager_type": item.manager_type,
            "source_url": item.cik_source_url,
        }
        for item in service.registry.search(q)
    ]


@app.post("/api/investors/resolve", status_code=201)
def resolve_investor(data: ResolveManager):
    """Only explicit user-selected CIKs are checked against public SEC filings."""
    try:
        item = service.registry.resolve_cik(data.cik)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except Exception as exc:  # SEC source boundary; surface a typed unavailable response.
        raise HTTPException(
            503, f"SEC resolution unavailable: {type(exc).__name__}"
        ) from exc
    return {
        "id": item.id,
        "name": item.name,
        "cik": item.cik,
        "source_url": item.cik_source_url,
    }


@app.get("/api/investors/{key}", response_model=Investor)
def investor(key: str, background: BackgroundTasks):
    valid_investor(key)
    service.schedule(background, "ark" if key == "ark" else "portfolio", key)
    return service.investor(key)


@app.get("/api/investors/{key}/holdings", response_model=list[Holding])
def holdings(key: str):
    return service.investor(valid_investor(key))["holdings"]


@app.get("/api/investors/{key}/changes", response_model=list[PositionChange])
def investor_changes(key: str):
    return service.investor(valid_investor(key))["changes"]


@app.put("/api/investors/{key}/follow")
def follow(key: str, toggle: Toggle):
    service.store.follow(valid_investor(key), toggle.enabled)
    return {"enabled": toggle.enabled}


@app.get("/api/company/{ticker}", response_model=Company)
def company(ticker: str, background: BackgroundTasks):
    ticker = valid_ticker(ticker)
    for kind in ("company", "market"):
        service.schedule(background, kind, ticker)
    return service.company(ticker)


@app.get("/api/company/{ticker}/changes")
def company_changes(ticker: str):
    return service.company(valid_ticker(ticker))["changes"]


@app.get("/api/company/{ticker}/suggested-theses", response_model=list[Suggestion])
def suggestions(ticker: str):
    return service.company(valid_ticker(ticker))["suggestions"]


@app.get("/api/company/{ticker}/theses", response_model=list[Thesis])
def theses(ticker: str):
    return service.theses(valid_ticker(ticker))


@app.put("/api/company/{ticker}/watch")
def watch(ticker: str, toggle: Toggle):
    service.store.watch(valid_ticker(ticker), toggle.enabled)
    return {"enabled": toggle.enabled}


@app.put("/api/company/{ticker}/suggestions/{suggestion_id}/ignore")
def ignore_suggestion(ticker: str, suggestion_id: str, toggle: Toggle):
    ticker = valid_ticker(ticker)
    if not suggestion_id.startswith(ticker + ":") or len(suggestion_id) > 100:
        raise HTTPException(422, "Invalid suggestion identifier")
    previous = service.store.snapshots("ignored_suggestions", ticker)
    ids = set(previous[0].get("ids", [])) if previous else set()
    if toggle.enabled:
        ids.add(suggestion_id)
    else:
        ids.discard(suggestion_id)
    service.store.save_snapshot(
        "ignored_suggestions", ticker, "current", {"ids": sorted(ids)}
    )
    return {"enabled": toggle.enabled}


@app.get("/api/public-officials")
def public_officials():
    documents = service.store.snapshots("oge", "donald_trump")
    return [
        {
            "person": d["person"],
            "disclosure_type": d["disclosure_type"],
            "filing_date": d.get("filing_date", ""),
            "source_document_date": d.get("source_document_date", ""),
            "source_url": d["source_url"],
            "records": d.get("records", [])[:50],
            "notes": d.get("notes", ""),
            "table_validation_rate": d.get("table_validation_rate"),
        }
        for d in documents[:3]
    ]


@app.post("/api/theses", status_code=201, response_model=Thesis)
def create_thesis(data: ThesisInput):
    rule = data.rule.model_dump() if data.rule else None
    existing = next(
        (
            t
            for t in service.store.theses(data.ticker)
            if t["text"] == data.text and t["rule"] == rule
        ),
        None,
    )
    return existing or service.store.save_thesis(data.ticker, data.text, rule)


@app.put("/api/theses/{thesis_id}", response_model=Thesis)
def update_thesis(thesis_id: str, data: ThesisInput):
    old = service.find_thesis(thesis_id)
    if not old or old["ticker"] != data.ticker:
        raise HTTPException(404, "Thesis not found")
    return service.store.save_thesis(
        data.ticker, data.text, data.rule.model_dump() if data.rule else None, thesis_id
    )


@app.post("/api/theses/{thesis_id}/evaluate", response_model=Thesis)
def evaluate(thesis_id: str):
    thesis = service.find_thesis(thesis_id)
    if not thesis:
        raise HTTPException(404, "Thesis not found")
    return service.evaluate(thesis)


@app.get("/api/disclosures")
def disclosures():
    return {
        "activity": service.home()["activity"],
        "recent": service.home()["recent_disclosures"],
        "public_officials": service.store.snapshots("oge", "donald_trump"),
    }


@app.post("/api/ask", response_model=Answer)
def ask(data: AskInput, background: BackgroundTasks):
    if any(
        word in data.question.lower()
        for word in ("news", "macro", "market pulse", "oil prices")
    ):
        service.market_pulse.schedule(background)
    return service.ask(data.question.strip(), valid_ticker(data.ticker))


@app.get("/api/market-pulse")
def market_pulse(background: BackgroundTasks):
    service.market_pulse.schedule(background)
    return service.market_pulse.feed()


@app.get("/api/market-pulse/watchlist")
def market_pulse_watchlist(background: BackgroundTasks):
    service.market_pulse.schedule(background)
    feed = service.market_pulse.feed()
    return {
        **feed,
        "events": [
            e for e in feed["events"] if e["watchlist_relevant"] and e["recent"]
        ],
    }


@app.post("/api/market-pulse/refresh", status_code=202)
def market_pulse_refresh(background: BackgroundTasks):
    service.market_pulse.schedule(background)
    return {"status": "Refresh requested; source-specific cooldowns still apply."}


@app.get("/api/market-pulse/{event_id}")
def market_pulse_detail(event_id: str):
    result = service.market_pulse.detail(event_id)
    if result is None:
        raise HTTPException(404, "Event unavailable or outside recent cached coverage")
    return result


@app.get("/api/market-pulse/{event_id}/impacts")
def market_pulse_impacts(event_id: str):
    return {"impacts": market_pulse_detail(event_id)["impacts"]}


@app.get("/api/intelligence/feed")
def intelligence_feed(category: str = "all", limit: int = 50):
    try:
        return service.intelligence.feed(category, limit)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get("/api/intelligence/company/{ticker}")
def institutional_activity(ticker: str):
    return service.intelligence.company_activity(valid_ticker(ticker))


@app.get("/api/intelligence/daily-brief")
def intelligence_daily_brief():
    return service.intelligence.daily_brief()


@app.get("/api/intelligence/outbox")
def intelligence_outbox():
    return {"notifications": service.store.notifications(),
            "note": "Local queue; external delivery is optional and disabled by default."}


@app.get("/api/intelligence/sources")
def public_sources():
    followed = set(service.store.source_follows())
    sources = [{"id": item.id, "name": item.name, "source_url": item.url,
                "followed": item.id in followed,
                "checked_at": service.market_pulse.state(item).get("checked_at"),
                "error": service.market_pulse.state(item).get("error")}
               for item in service.market_pulse.providers]
    sources.append({"id": "berkshire-letters", "name": "Berkshire shareholder letters",
                    "source_url": service.public_providers["website"].URL,
                    "followed": "berkshire-letters" in followed,
                    "checked_at": None, "error": "Year-only index; no dated feed events"})
    return {"sources": sources,
            "note": "Official public sources only. X/Twitter is disabled."}


@app.put("/api/intelligence/sources/{source_id}/follow")
def follow_public_source(source_id: str, data: Toggle):
    if not any(provider.resolve_source(source_id) for provider in service.public_providers.values()):
        raise HTTPException(404, "Unsupported public source")
    service.store.follow_source(source_id, data.enabled)
    return {"source_id": source_id, "followed": data.enabled}


@app.put("/api/intelligence/events/{event_id}/read")
def intelligence_mark_read(event_id: str):
    if not service.store.mark_intelligence_read(event_id):
        raise HTTPException(404, "Event not found")
    return {"event_id": event_id, "read": True}


@app.put("/api/intelligence/events/{event_id}/dismiss")
def intelligence_dismiss(event_id: str):
    if not service.store.dismiss_notification(event_id):
        raise HTTPException(404, "Event not found")
    return {"event_id": event_id, "dismissed": True}


# Keep the existing catch-all disclosure route after the specific Pulse routes.
@app.get("/api/{kind}/{ticker}")
def timed_disclosures(
    kind: Literal["insiders", "ownership"], ticker: str, background: BackgroundTasks
):
    ticker = valid_ticker(ticker)
    service.schedule(background, kind, ticker)
    snapshots = service.store.snapshots(kind, ticker)
    return {
        **(
            snapshots[0]
            if snapshots
            else {"records": [], "warnings": ["Data not yet available"]}
        ),
        "refresh": service.cache_state(kind, ticker),
        "available": bool(snapshots),
    }
