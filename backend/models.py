"""Product response contracts. Source-specific metadata remains available as extras."""

from pydantic import BaseModel, ConfigDict, Field


class ResponseModel(BaseModel):
    model_config = ConfigDict(extra="allow")


class Evidence(ResponseModel):
    text: str
    source_url: str = ""
    period: str = ""


class RefreshState(ResponseModel):
    stale: bool
    ttl_seconds: int
    checked_at: str | None = None
    error: str | None = None


class Holding(ResponseModel):
    issuer: str
    ticker: str
    shares: float
    weight: float
    reported_value: float
    put_call: str
    sector: str
    cusip: str
    security_class: str = ""
    share_type: str = "SH"
    ticker_source: str = ""
    ticker_verified: bool = False
    entry_price_estimate: dict = Field(default_factory=dict)


class PositionChange(ResponseModel):
    issuer: str
    ticker: str
    activity: str
    pct_change: float | None
    reporting_period: str
    filing_date: str
    source_url: str


class Investor(ResponseModel):
    id: str
    name: str
    investor: str
    style_tags: list[str]
    source_type: str
    followed: bool
    available: bool
    latest_period: str | None
    filing_date: str | None
    source_url: str | None
    freshness: str
    refresh: RefreshState
    holdings: list[Holding]
    changes: list[PositionChange]
    notes: list[str]
    rationale: str


class Thesis(ResponseModel):
    id: str
    ticker: str
    text: str
    rule: dict | None
    status: str
    supporting_evidence: list[Evidence] = Field(default_factory=list)
    contradicting_evidence: list[Evidence] = Field(default_factory=list)
    history: list[dict] = Field(default_factory=list)


class Suggestion(ResponseModel):
    id: str
    category: str
    text: str
    why_it_matters: str
    evidence: list[Evidence]
    support_condition: str
    invalidate_condition: str
    rule: dict | None
    generator: str
    period: str


class Company(ResponseModel):
    ticker: str
    name: str
    available: bool
    market: dict = Field(default_factory=dict)
    annual: dict = Field(default_factory=dict)
    suggestions: list[Suggestion]
    changes: list[dict]
    theses: list[Thesis]
    risks: list[Evidence]
    warnings: list[str]
    refresh: RefreshState


class Feed(ResponseModel):
    activity: list[PositionChange]
    investors: list[Investor]
    ideas: list[dict]
    watchlist: list[dict]
    recent_disclosures: list[dict]
    as_of: str


class Answer(ResponseModel):
    answer: str
    evidence: list[Evidence]
    source: str
    intent: str = "financial_research"
    mode: str = "auto"
    configuration_error: str | None = None
    configuration_error_code: str | None = None
    privacy: str = "No private workspace data was sent to an external model."
