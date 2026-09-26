"""Evidence-linked deterministic risk classification with optional Jev enrichment."""

from dataclasses import dataclass

from src.decision import DecisionUnavailable, JevDecisionProvider

RISK_TERMS = {
    "CYBERSECURITY": ("cybersecurity", "cyber attack", "data breach", "information systems"),
    "REGULATORY": ("regulation", "regulatory", "antitrust", "compliance"),
    "GEOPOLITICAL": ("geopolitical", "china", "trade restriction", "sanction"),
    "MACROECONOMIC": ("macroeconomic", "inflation", "interest rate", "recession", "foreign exchange"),
    "COMPETITIVE": ("competition", "competitive", "market share"),
    "SUPPLY_CHAIN": ("supplier", "supply chain", "manufacturing partner"),
    "CUSTOMER_CONCENTRATION": ("concentration", "single customer", "major customer"),
    "FINANCIAL": ("liquidity", "credit", "debt", "cash flow"),
    "LEGAL": ("litigation", "lawsuit", "legal proceeding", "intellectual property"),
}


@dataclass(frozen=True, slots=True)
class RiskEvidence:
    category: str
    severity: float
    confidence: float
    evidence: str
    chunk_id: str
    section: str
    source: str = "deterministic"


def classify_risks(
    chunks: list[dict], jev: JevDecisionProvider | None = None
) -> list[RiskEvidence]:
    results: list[RiskEvidence] = []
    for chunk in chunks:
        text = chunk.get("text", "")
        lowered = text.lower()
        matches = [
            (category, sum(term in lowered for term in terms))
            for category, terms in RISK_TERMS.items()
        ]
        category, count = max(matches, key=lambda item: item[1])
        if count == 0:
            category = "OTHER"
        severity = min(4.0, 1.0 + count)
        confidence = min(0.95, 0.50 + 0.12 * count)
        source = "deterministic"
        if jev is not None:
            try:
                decision = jev.classify_risk(text)
                category = decision.category.value
                severity = decision.severity
                confidence = decision.confidence
                source = "jev"
            except DecisionUnavailable:
                pass
        results.append(
            RiskEvidence(
                category,
                severity,
                confidence,
                text,
                str(chunk.get("chunk_id", "")),
                str(chunk.get("section", "")),
                source,
            )
        )
    return results
