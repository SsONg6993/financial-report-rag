"""Run: python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000."""

from typing import Literal

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException
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
from src.portfolios import BY_ID
from src.sec import normalize_ticker
from src.thesis import RULE_METRICS

app = FastAPI(
    title="ThesisLens",
    version="0.1.0",
    description="Local, single-user investment research. Public disclosures are research inputs, not trading instructions.",
)
service = ResearchService()


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
    if key not in BY_ID:
        raise HTTPException(404, "Investor not found")
    return key


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/home/feed", response_model=Feed)
def home(background: BackgroundTasks):
    for key in service.store.follows():
        if key in BY_ID:
            service.schedule(background, "ark" if key == "ark" else "portfolio", key)
    for ticker in service.store.watchlist():
        for kind in ("company", "market", "insiders", "ownership"):
            service.schedule(background, kind, ticker)
    return service.home()


@app.get("/api/investors", response_model=list[Investor])
def investors():
    return service.investors()


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


@app.post("/api/ask", response_model=Answer)
def ask(data: AskInput):
    return service.ask(data.question.strip(), valid_ticker(data.ticker))
