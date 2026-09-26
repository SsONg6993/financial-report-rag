"""Public, source-independent Market Pulse contracts."""

from typing import Literal

from pydantic import BaseModel, Field

Category = Literal[
    "Macroeconomics",
    "Inflation",
    "Interest Rates / Central Banks",
    "Employment",
    "GDP / Growth",
    "Geopolitics",
    "War / Conflict",
    "Energy",
    "Trade / Tariffs",
    "Sanctions",
    "Supply Chain",
    "Technology",
    "Artificial Intelligence",
    "Semiconductors",
    "Regulation",
    "M&A",
    "Corporate / Industry Events",
]
ImpactType = Literal[
    "POTENTIAL_TAILWIND", "POTENTIAL_HEADWIND", "MIXED", "INDIRECT", "UNCLEAR"
]
Horizon = Literal["IMMEDIATE", "NEAR_TERM", "STRUCTURAL", "UNCLEAR"]
Strength = Literal["STRONG", "MODERATE", "WEAK"]


class EvidenceRef(BaseModel):
    text: str
    source_url: str
    date: str | None = None
    source: str


class MarketEvent(BaseModel):
    id: str
    headline: str
    summary: str
    category: Category
    source: str
    source_url: str
    published_at: str | None = None
    event_time: str | None = None
    regions: list[str] = Field(default_factory=list)
    sectors: list[str] = Field(default_factory=list)
    importance: Literal["HIGH", "NORMAL"] = "NORMAL"
    cached_at: str
    provider_id: str
    related_sources: list[EvidenceRef] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)


class EventImpact(BaseModel):
    event_id: str
    ticker: str
    company: str
    impact_type: ImpactType = "UNCLEAR"
    horizon: Horizon = "UNCLEAR"
    evidence_strength: Strength = "WEAK"
    explanation: str
    company_exposure: str
    mechanism: list[str] = Field(default_factory=list)
    confidence: str = "Insufficient evidence; not a stock-price forecast"
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    watched: bool = False
    portfolio_context: list[dict] = Field(default_factory=list)
    judgment: dict | None = None


class MarketReaction(BaseModel):
    event_id: str
    ticker: str
    event_time: str | None = None
    reference_price: float | None = None
    reference_at: str | None = None
    day_1_return: float | None = None
    day_5_return: float | None = None
    observed_at: str | None = None
    source_url: str | None = None
    label: str = (
        "Observed after the event; correlation/context, not proof of causation."
    )
