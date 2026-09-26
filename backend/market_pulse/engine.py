"""Evidence gates precede classifications. No price or investor-motive predictions."""

import re
from datetime import datetime
from difflib import SequenceMatcher

from backend.market_pulse.models import (
    EventImpact,
    EvidenceRef,
    MarketEvent,
    MarketReaction,
)

# An event mechanism is not a claim about every stock in a sector. Company
# passages must independently establish the exposure described by the rule.
RULES = {
    "Energy": (
        r"\b(?:fuel|oil|natural gas|petroleum|diesel)\b",
        r"\b(?:cost|expense|produc|sale|revenue|consum|refin)\w*\b",
        [
            "Energy supply or price conditions",
            "Company fuel costs or energy-linked revenue",
            "Potential operating-margin sensitivity",
        ],
        "NEAR_TERM",
    ),
    "Artificial Intelligence": (
        r"\b(?:artificial intelligence|AI|GPU|data center|data centre)\b",
        r"\b(?:invest|spend|develop|product|service|infrastructure|revenue|demand)\w*\b",
        [
            "AI product or infrastructure development",
            "Company AI products, spending or infrastructure exposure",
            "Potential demand and investment-cost changes",
        ],
        "STRUCTURAL",
    ),
    "Semiconductors": (
        r"\b(?:semiconductor|chip|GPU|processor)\w*\b",
        r"\b(?:manufactur|supplier|supply|product|revenue|purchase)\w*\b",
        [
            "Semiconductor industry development",
            "Company product or supplier exposure",
            "Potential capacity, demand or input-cost changes",
        ],
        "STRUCTURAL",
    ),
    "Interest Rates / Central Banks": (
        r"\b(?:interest rate|borrowing|refinanc|debt)\w*\b",
        r"\b(?:cost|expense|risk|finance|liabilit|payment)\w*\b",
        [
            "Monetary-policy communication",
            "Company financing or interest-rate exposure",
            "Potential funding-cost sensitivity; direction not established",
        ],
        "NEAR_TERM",
    ),
    "Inflation": (
        r"\b(?:inflation|input cost|labor cost|labour cost)\w*\b",
        r"\b(?:cost|expense|margin|pricing|risk)\w*\b",
        [
            "Inflation data release",
            "Company cost or pricing exposure",
            "Potential margin sensitivity; surprise not established",
        ],
        "NEAR_TERM",
    ),
    "Trade / Tariffs": (
        r"\b(?:tariff|import|export|trade restriction)\w*\b",
        r"\b(?:cost|supply|sales|revenue|risk|business)\w*\b",
        [
            "Trade-policy development",
            "Company cross-border operations or suppliers",
            "Potential market-access or cost changes",
        ],
        "NEAR_TERM",
    ),
    "Sanctions": (
        r"\b(?:sanction|export control)\w*\b",
        r"\b(?:sale|revenue|market|business|risk)\w*\b",
        [
            "Sanctions or export controls",
            "Company restricted-market exposure",
            "Potential market-access constraints",
        ],
        "NEAR_TERM",
    ),
    "Regulation": (
        r"\b(?:regulat|antitrust|compliance)\w*\b",
        r"\b(?:cost|risk|business|product|operation)\w*\b",
        [
            "Regulatory development",
            "Company compliance or regulated-business exposure",
            "Potential operating constraints; applicability requires review",
        ],
        "UNCLEAR",
    ),
    "Supply Chain": (
        r"\b(?:supplier|supply chain|shipping)\w*\b",
        r"\b(?:risk|cost|delay|depend|manufactur)\w*\b",
        [
            "Supply-chain development",
            "Company supplier or logistics dependence",
            "Potential delivery or cost sensitivity",
        ],
        "NEAR_TERM",
    ),
    "War / Conflict": (
        r"\b(?:defense|defence|military|geopolitical)\w*\b",
        r"\b(?:contract|customer|revenue|risk|business)\w*\b",
        [
            "Conflict or geopolitical development",
            "Disclosed defense or geopolitical exposure",
            "Potential indirect demand or operating risks",
        ],
        "UNCLEAR",
    ),
}
RULES["Geopolitics"] = RULES["War / Conflict"]
RULES["Macroeconomics"] = (
    r"\b(?:current.account|balance.of.payments)\b",
    r"\b(?:exposure|risk|financing|currency)\b",
    [
        "International transaction and capital-flow data",
        "Potential cross-border funding or currency channels",
        "Company applicability requires specific exposure evidence; direction is unclear",
    ],
    "UNCLEAR",
)
RULES["GDP / Growth"] = (
    r"\b(?:consumer demand|economic conditions|macroeconomic)\w*\b",
    r"\b(?:revenue|sales|demand|risk|business)\w*\b",
    [
        "Reported economic growth data",
        "Company sensitivity to demand or economic conditions",
        "Potential indirect demand effects; surprise and direction not established",
    ],
    "NEAR_TERM",
)


def sentences(text: str) -> list[str]:
    """Keep abbreviations intact; incomplete RSS tails aren't standalone facts."""
    protected = re.sub(
        r"\b(?:U\.S\.|U\.K\.|Inc\.|Corp\.|e\.g\.|i\.e\.)",
        lambda match: match.group().replace(".", "\u2024"),
        text,
    )
    return [
        part.replace("\u2024", ".").strip()
        for part in re.split(r"(?<=[.!?])\s+|[\r\n]+", protected)
        if len(re.findall(r"\b[A-Za-z]+\b", part)) >= 5
        and (part.rstrip().endswith((".", "!", "?")) or part == protected)
    ]


def exposure_supported(category: str, text: str) -> bool:
    # Reject headings, table rows and sprawling paragraphs whose unrelated
    # keywords could otherwise masquerade as a company-specific causal channel.
    if len(text) > 600 or "|" in text or not text.endswith((".", "!", "?")):
        return False
    if category == "Energy":
        return bool(
            re.search(
                r"\bfuel\b.{0,65}\b(?:cost|expense|consumption|price)\w*\b|"
                r"\b(?:cost|expense|consumption|price)\w*\b.{0,65}\bfuel\b|"
                r"\b(?:oil|natural gas|petroleum|diesel)\b.{0,65}\b(?:production|sales|purchase|cost|expense|consumption)\w*\b|"
                r"\b(?:production|sales|purchase|cost|expense|consumption)\w*\b.{0,65}\b(?:oil|natural gas|petroleum|diesel)\b",
                text,
                re.IGNORECASE,
            )
        ) and not re.search(
            r"\bfuel(?:ing)?\s+(?:our|the|a|future|growth)", text, re.IGNORECASE
        )
    if category == "Interest Rates / Central Banks":
        return bool(
            re.search(
                r"\b(?:interest rates?|borrowing|refinancing)\b.{0,90}\b(?:cost|expense|risk|payment|affect|exposure)\w*\b|"
                r"\b(?:cost|expense|risk|payment|affect|exposure)\w*\b.{0,90}\b(?:interest rates?|borrowing|refinancing)\b",
                text,
                re.IGNORECASE,
            )
        )
    return True


def freshness(published: str | None, now: datetime, stale=False):
    if not published:
        return "DATE UNAVAILABLE"
    hours = (now - datetime.fromisoformat(published)).total_seconds() / 3600
    if hours < 0:
        return "FUTURE SOURCE TIME"
    label = (
        "JUST NOW"
        if hours < 0.25
        else f"{max(1, int(hours))} HOURS AGO"
        if hours < 24
        else "YESTERDAY"
        if hours < 48
        else f"{int(hours / 24)} DAYS AGO"
    )
    return label + (" · STALE CACHE" if stale else "")


def cluster(events: list[MarketEvent]) -> list[MarketEvent]:
    result = []
    for event in sorted(
        events, key=lambda e: (e.published_at or "", e.id), reverse=True
    ):
        title = re.sub(r"[^a-z0-9 ]", "", event.headline.lower())
        numeric = re.findall(r"\d+(?:\.\d+)?", title)
        existing = next(
            (
                e
                for e in result
                if e.source_url == event.source_url
                or (
                    e.category == event.category
                    and (e.published_at or "")[:10] == (event.published_at or "")[:10]
                    and re.findall(r"\d+(?:\.\d+)?", e.headline.lower()) == numeric
                    and SequenceMatcher(
                        None, re.sub(r"[^a-z0-9 ]", "", e.headline.lower()), title
                    ).ratio()
                    >= 0.9
                )
            ),
            None,
        )
        if existing:
            existing.related_sources.append(
                EvidenceRef(
                    text=event.headline,
                    source_url=event.source_url,
                    date=event.published_at,
                    source=event.source,
                )
            )
            existing.aliases.append(event.id)
        else:
            result.append(event.model_copy(deep=True))
    return result


def build_impact(
    event: MarketEvent,
    ticker: str,
    company: str,
    chunks: list[dict],
    watched=False,
    portfolio=None,
) -> EventImpact:
    impact = EventImpact(
        event_id=event.id,
        ticker=ticker,
        company=company,
        explanation="Available company evidence does not establish this event's relevance.",
        company_exposure="Not established from available company sources.",
        watched=watched,
        portfolio_context=portfolio or [],
    )
    rule = RULES.get(event.category)
    if not rule:
        return impact
    # An issuer's announcement is not an industry-wide shock. Another company's
    # generic AI exposure alone cannot establish involvement in this project.
    if event.provider_id == "nvidia" and ticker != "NVDA":
        names = {
            "MSFT": "Microsoft",
            "META": "Meta",
            "AAPL": "Apple",
            "RKLB": "Rocket Lab",
        }
        name = names.get(ticker, company)
        if not re.search(
            r"\b" + re.escape(name) + r"\b",
            event.headline + " " + event.summary,
            re.IGNORECASE,
        ):
            return impact
    topic, exposure, mechanism, horizon = rule
    candidates = []
    for chunk in chunks:
        if not chunk.get("source_url") or not chunk.get("period"):
            continue
        for sentence in sentences(chunk.get("text", "")):
            if (
                re.search(topic, sentence, re.IGNORECASE)
                and re.search(exposure, sentence, re.IGNORECASE)
                and exposure_supported(event.category, sentence)
            ):
                candidates.append((sentence, chunk))
    # A company's own product announcement can establish its direct product
    # exposure. It cannot establish a different company's exposure.
    if (
        not candidates
        and ticker == "NVDA"
        and event.provider_id == "nvidia"
        and re.search(
            r"\bnvidia\b", event.headline + " " + event.summary, re.IGNORECASE
        )
    ):
        text = event.headline + ". " + event.summary
        if re.search(topic, text, re.IGNORECASE) and re.search(
            exposure, text, re.IGNORECASE
        ):
            candidates.append(
                (
                    event.summary,
                    {
                        "source_url": event.source_url,
                        "period": event.published_at,
                        "source_type": event.source,
                    },
                )
            )
    if not candidates:
        return impact
    text, chunk = candidates[0]
    if (
        event.category == "Energy"
        and "natural gas" in (event.headline + " " + event.summary).lower()
        and not any(
            term in (event.headline + " " + event.summary).lower()
            for term in ("crude oil", "diesel", "jet fuel")
        )
        and "natural gas" not in text.lower()
    ):
        return impact  # Gas prices are not automatically an airline jet-fuel shock.
    # Rules establish a disclosed channel, not causal relevance to every event
    # sharing a word. Explicit regions narrow region-specific events.
    restricted = [
        r for r in event.regions if r in {"China", "Russia", "Ukraine", "Middle East"}
    ]
    if restricted and not any(r.lower() in text.lower() for r in restricted):
        return impact
    impact.company_exposure = text
    impact.evidence_refs = [
        EvidenceRef(
            text=text,
            source_url=chunk["source_url"],
            date=chunk["period"],
            source=chunk.get("source_type", "SEC filing"),
        )
    ]
    impact.mechanism = mechanism
    impact.horizon = horizon
    impact.evidence_strength = "MODERATE"
    impact.impact_type = "INDIRECT"
    impact.explanation = "The company source supports this exposure channel. Its size, direction and stock-price effect remain uncertain."
    impact.confidence = (
        "Moderate support for exposure; uncertain event effect, not price direction"
    )
    if event.category in {"Artificial Intelligence", "Semiconductors"}:
        impact.impact_type = "MIXED"
        impact.explanation = "New infrastructure or products may change demand and investment costs. Exposure does not establish net financial benefit."
    if event.category == "Energy":
        # Direction only for explicit energy price moves AND explicit cost /
        # producer evidence. Historical seasonal comparisons are not new shocks.
        event_text = event.headline.lower()
        increase = bool(
            re.search(
                r"(?:oil|fuel|gas|diesel).*?(?:surge|spike|rise|rose|higher)",
                event_text,
            )
        )
        decrease = bool(
            re.search(r"(?:oil|fuel|gas|diesel).*?(?:fall|fell|lower|drop)", event_text)
        )
        fuel_cost = bool(
            re.search(
                r"fuel.*?(?:cost|expense)|(?:cost|expense).*?fuel", text, re.IGNORECASE
            )
        )
        producer = bool(
            re.search(
                r"(?:produce|production|sales).*?(?:oil|natural gas)|(?:oil|natural gas).*?(?:production|sales)",
                text,
                re.IGNORECASE,
            )
        )
        historical = bool(
            re.search(
                r"last summer|last year|in 20\d\d|averaged",
                event.headline + " " + event.summary,
                re.IGNORECASE,
            )
        )
        if (increase != decrease) and (fuel_cost != producer) and not historical:
            headwind = (increase and fuel_cost) or (decrease and producer)
            impact.impact_type = (
                "POTENTIAL_HEADWIND" if headwind else "POTENTIAL_TAILWIND"
            )
            impact.explanation = "The reported price move may pressure fuel costs or change producer revenue; hedging, timing and other costs can offset the effect."
            impact.evidence_strength = "STRONG"
    return impact


def empty_reaction(event: MarketEvent, ticker: str):
    # No timestamp-aligned price history is currently supplied. Current quotes
    # must never be relabeled as event-reference prices or daily reactions.
    return MarketReaction(
        event_id=event.id, ticker=ticker, event_time=event.event_time
    ).model_dump()
