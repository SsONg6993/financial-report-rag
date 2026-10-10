"""Deterministic sector analytics over saved institutional disclosures.

Classifications use a small, auditable registry keyed by CUSIP.  The registry
maps official SEC SIC codes into the public ThesisLens Sector Taxonomy v1.  It
does not claim to be licensed GICS data, and issuer names are never guessed.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from src.portfolios import Holding, PortfolioSnapshot

TAXONOMY_NAME = "ThesisLens Sector Taxonomy v1 (SEC SIC based)"
TAXONOMY_SOURCE_URL = "https://www.sec.gov/search-filings/standard-industrial-classification-sic-code-list"
UNKNOWN_SECTOR = "Unknown"


@dataclass(frozen=True, slots=True)
class SectorClassification:
    sector: str
    sic: str
    ticker: str
    cik: int

    @property
    def source_url(self) -> str:
        return f"https://data.sec.gov/submissions/CIK{self.cik:010d}.json"


# CUSIP is the identity boundary. Entries are intentionally explicit and can be
# extended only with a verified identifier, SEC CIK/SIC, and taxonomy mapping.
SECURITY_SECTORS: dict[str, SectorClassification] = {
    "02079K107": SectorClassification("Communication Services", "7370", "GOOG", 1652044),
    "02079K305": SectorClassification("Communication Services", "7370", "GOOGL", 1652044),
    "023135106": SectorClassification("Consumer Discretionary", "5961", "AMZN", 1018724),
    "025816109": SectorClassification("Financials", "6199", "AXP", 4962),
    "037833100": SectorClassification("Information Technology", "3571", "AAPL", 320193),
    "060505104": SectorClassification("Financials", "6021", "BAC", 70858),
    "084670702": SectorClassification("Financials", "6331", "BRK.B", 1067983),
    "191216100": SectorClassification("Consumer Staples", "2086", "KO", 21344),
    "30303M102": SectorClassification("Communication Services", "7370", "META", 1326801),
    "594918104": SectorClassification("Information Technology", "7372", "MSFT", 789019),
    "67066G104": SectorClassification("Information Technology", "3674", "NVDA", 1045810),
    "674599105": SectorClassification("Energy", "1311", "OXY", 797468),
    "88160R101": SectorClassification("Consumer Discretionary", "3711", "TSLA", 1318605),
}


@dataclass(frozen=True, slots=True)
class CorporateAction:
    """A verified split adjustment applicable between two reporting dates."""

    cusip: str
    effective_date: str
    factor: float
    source_url: str


def normalize_cusip(value: str) -> str:
    return "".join(character for character in value.upper() if character.isalnum())


def classify_holding(holding: Holding) -> dict:
    classification = SECURITY_SECTORS.get(normalize_cusip(holding.cusip))
    if classification is None:
        return {
            "sector": UNKNOWN_SECTOR,
            "classification_status": "unknown",
            "taxonomy": TAXONOMY_NAME,
            "taxonomy_code": None,
            "classification_source_url": None,
        }
    return {
        "sector": classification.sector,
        "classification_status": "verified_identifier",
        "taxonomy": TAXONOMY_NAME,
        "taxonomy_code": f"SEC SIC {classification.sic}",
        "classification_source_url": classification.source_url,
    }

def _allocation(snapshot: PortfolioSnapshot) -> tuple[list[dict], dict]:
    total_value = sum(max(0.0, holding.reported_value) for holding in snapshot.holdings)
    sectors: dict[str, dict] = {}
    known_value = 0.0
    known_count = 0
    for holding in snapshot.holdings:
        classification = classify_holding(holding)
        sector = classification["sector"]
        value = max(0.0, holding.reported_value)
        row = sectors.setdefault(
            sector,
            {
                "sector": sector,
                "reported_value": 0.0,
                "weight": 0.0,
                "holding_count": 0,
                "holdings": [],
            },
        )
        row["reported_value"] += value
        row["holding_count"] += 1
        row["holdings"].append(
            {
                "ticker": holding.ticker,
                "issuer": holding.issuer,
                "cusip": holding.cusip,
                "security_class": holding.security_class,
                "put_call": holding.put_call,
                "shares": holding.shares,
                "reported_value": value,
                "weight": value / total_value if total_value else 0.0,
                **classification,
            }
        )
        if sector != UNKNOWN_SECTOR:
            known_value += value
            known_count += 1
    for row in sectors.values():
        row["weight"] = row["reported_value"] / total_value if total_value else 0.0
        row["holdings"].sort(key=lambda item: item["reported_value"], reverse=True)
    rows = sorted(sectors.values(), key=lambda item: (-item["reported_value"], item["sector"]))
    unknown_value = max(0.0, total_value - known_value)
    coverage = {
        "holding_count": len(snapshot.holdings),
        "option_holding_count": sum(bool(holding.put_call) for holding in snapshot.holdings),
        "classified_holding_count": known_count,
        "classified_holding_percentage": known_count / len(snapshot.holdings) if snapshot.holdings else 0.0,
        "reported_value_total": total_value,
        "classified_reported_value": known_value,
        "classified_value_percentage": known_value / total_value if total_value else 0.0,
        "unknown_reported_value": unknown_value,
        "unknown_value_percentage": unknown_value / total_value if total_value else 0.0,
    }
    return rows, coverage


def _find_action(
    cusip: str,
    previous_period: str,
    current_period: str,
    actions: Iterable[CorporateAction],
) -> CorporateAction | None:
    normalized = normalize_cusip(cusip)
    return next(
        (
            action
            for action in actions
            if normalize_cusip(action.cusip) == normalized
            and previous_period < action.effective_date <= current_period
            and action.factor > 0
        ),
        None,
    )


def _position_changes(
    previous: PortfolioSnapshot,
    current: PortfolioSnapshot,
    actions: Iterable[CorporateAction],
) -> list[dict]:
    before = {holding.key: holding for holding in previous.holdings}
    after = {holding.key: holding for holding in current.holdings}
    changes = []
    for key in sorted(before.keys() | after.keys()):
        old, new = before.get(key), after.get(key)
        holding = new or old
        if holding is None:
            continue
        action = _find_action(
            holding.cusip,
            previous.reporting_period,
            current.reporting_period,
            actions,
        )
        raw_before = old.shares if old else 0.0
        adjusted_before = raw_before * action.factor if action else raw_before
        after_shares = new.shares if new else 0.0
        activity = (
            "NEW"
            if old is None
            else "EXITED"
            if new is None
            else "INCREASED"
            if after_shares > adjusted_before
            else "REDUCED"
            if after_shares < adjusted_before
            else "UNCHANGED"
        )
        classification = classify_holding(holding)
        changes.append(
            {
                "sector": classification["sector"],
                "issuer": holding.issuer,
                "ticker": holding.ticker,
                "cusip": holding.cusip,
                "security_class": holding.security_class,
                "put_call": holding.put_call,
                "activity": activity,
                "shares_before": raw_before,
                "comparable_shares_before": adjusted_before,
                "shares_after": after_shares,
                "share_change": after_shares - adjusted_before,
                "corporate_action_adjusted": action is not None,
                "corporate_action_source_url": action.source_url if action else None,
                "share_change_interpretation": (
                    "Derivative exposure change; not an ordinary-share trade."
                    if holding.put_call
                    else "Observed change in reported shares; not proof of a trade."
                ),
            }
        )
    return changes


def analyze_sector_exposure(
    snapshots: list[PortfolioSnapshot],
    *,
    period: str | None = None,
    sector: str | None = None,
    corporate_actions: Iterable[CorporateAction] = (),
) -> dict:
    ordered = sorted(snapshots, key=lambda item: item.reporting_period, reverse=True)
    eligible = [item for item in ordered if period is None or item.reporting_period <= period]
    if not eligible:
        raise ValueError("No saved disclosure is available for the requested period.")
    current = eligible[0]
    previous = next(
        (item for item in eligible[1:] if item.source_type == current.source_type),
        None,
    )
    allocation, coverage = _allocation(current)
    previous_allocation, _ = _allocation(previous) if previous else ([], {})
    previous_weights = {row["sector"]: row for row in previous_allocation}
    sector_changes = []
    for row in allocation:
        prior = previous_weights.get(row["sector"])
        sector_changes.append(
            {
                "sector": row["sector"],
                "weight_before": prior["weight"] if prior else 0.0,
                "weight_after": row["weight"],
                "weight_change": row["weight"] - (prior["weight"] if prior else 0.0),
                "reported_value_before": prior["reported_value"] if prior else 0.0,
                "reported_value_after": row["reported_value"],
            }
        )
    for row in previous_allocation:
        if row["sector"] not in {item["sector"] for item in allocation}:
            sector_changes.append(
                {
                    "sector": row["sector"],
                    "weight_before": row["weight"],
                    "weight_after": 0.0,
                    "weight_change": -row["weight"],
                    "reported_value_before": row["reported_value"],
                    "reported_value_after": 0.0,
                }
            )
    position_changes = _position_changes(previous, current, corporate_actions) if previous else []
    activity_counts: dict[str, dict[str, int]] = {}
    for change in position_changes:
        if change["put_call"]:
            continue
        counts = activity_counts.setdefault(
            change["sector"],
            {"NEW": 0, "INCREASED": 0, "REDUCED": 0, "EXITED": 0, "UNCHANGED": 0},
        )
        counts[change["activity"]] += 1
    for row in sector_changes:
        row["position_activity"] = activity_counts.get(
            row["sector"],
            {"NEW": 0, "INCREASED": 0, "REDUCED": 0, "EXITED": 0, "UNCHANGED": 0},
        )
    sector_filter = sector.strip() if sector else None
    if sector_filter:
        allocation = [row for row in allocation if row["sector"].casefold() == sector_filter.casefold()]
        sector_changes = [row for row in sector_changes if row["sector"].casefold() == sector_filter.casefold()]
        position_changes = [row for row in position_changes if row["sector"].casefold() == sector_filter.casefold()]
    hhi = sum(row["weight"] ** 2 for row in allocation) if not sector_filter else None
    return {
        "institution_id": current.institution_id,
        "reporting_period": current.reporting_period,
        "previous_period": previous.reporting_period if previous else None,
        "filing_date": current.filing_date,
        "source_url": current.source_url,
        "source_type": current.source_type,
        "available_periods": [item.reporting_period for item in ordered],
        "taxonomy": TAXONOMY_NAME,
        "taxonomy_source_url": TAXONOMY_SOURCE_URL,
        "sector_filter": sector_filter,
        "allocation": allocation,
        "sector_changes": sorted(sector_changes, key=lambda item: abs(item["weight_change"]), reverse=True),
        "position_changes": [item for item in position_changes if item["activity"] != "UNCHANGED"],
        "coverage": coverage,
        "concentration": {
            "largest_sector": allocation[0]["sector"] if allocation else None,
            "largest_sector_weight": allocation[0]["weight"] if allocation else None,
            "herfindahl_index": hhi,
        },
        "comparison": {
            "available": previous is not None,
            "reason": None if previous else "Only one comparable saved disclosure is available.",
            "weight_change_note": "Sector weight changes combine position changes and quarter-end reported-value changes; they are not trade measures.",
            "share_change_note": "Share changes compare disclosed quantities for class-aware non-option positions. Option rows are not counted as ordinary-share accumulation. Changes do not identify transaction dates or intent, and unverified corporate actions are not adjusted.",
        },
    }
