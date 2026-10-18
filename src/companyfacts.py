"""SEC Company Facts normalization and cache helpers."""

import json
from datetime import date
from pathlib import Path

from src.analytics import calculate_history
from src.models import AnnualFinancials
from src.sec import SEC_DATA, get_json, normalize_ticker, sec_session

CONCEPTS: dict[str, tuple[str, ...]] = {
    "revenue": ("RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet"),
    "gross_profit": ("GrossProfit",),
    "operating_income": ("OperatingIncomeLoss",),
    "net_income": ("NetIncomeLoss", "ProfitLoss"),
    "eps": ("EarningsPerShareDiluted",),
    "assets": ("Assets",),
    "liabilities": ("Liabilities",),
    "equity": ("StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"),
    "operating_cash_flow": ("NetCashProvidedByUsedInOperatingActivities",),
    "capital_expenditure": ("PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsForProceedsFromOtherPropertyPlantAndEquipment"),
    "shares_outstanding": ("CommonStockSharesOutstanding", "WeightedAverageNumberOfDilutedSharesOutstanding"),
    "current_assets": ("AssetsCurrent",),
    "current_liabilities": ("LiabilitiesCurrent",),
    "cash": ("CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"),
}

PREFERRED_UNITS = {
    "eps": ("USD/shares",),
    "shares_outstanding": ("shares",),
}


def _annual_entries(concept: dict, metric: str) -> list[dict]:
    units = concept.get("units", {})
    allowed_units = PREFERRED_UNITS.get(metric, ("USD",))
    entries: list[dict] = []
    for unit in allowed_units:
        entries.extend(units.get(unit, []))
    valid = []
    for entry in entries:
        if entry.get("form") not in {"10-K", "20-F", "40-F"} or entry.get("fp") != "FY":
            continue
        start, end = entry.get("start"), entry.get("end")
        if start and end:
            try:
                duration = (date.fromisoformat(end) - date.fromisoformat(start)).days
                if duration < 250:
                    continue
            except ValueError:
                continue
        valid.append(entry)
    return valid


def _year_for_entry(entry: dict) -> int | None:
    end = str(entry.get("end", ""))
    if len(end) >= 4 and end[:4].isdigit():
        return int(end[:4])
    fiscal_year = entry.get("fy")
    return int(fiscal_year) if fiscal_year is not None else None


def _first_concept_values(gaap: dict, concepts: tuple[str, ...], metric: str) -> dict[int, tuple[str, float]]:
    result: dict[int, tuple[str, float]] = {}
    for concept_name in concepts:
        concept = gaap.get(concept_name)
        if not concept:
            continue
        concept_result: dict[int, tuple[str, float]] = {}
        for entry in _annual_entries(concept, metric):
            year = _year_for_entry(entry)
            value = entry.get("val")
            if year is None or not isinstance(value, (int, float)):
                continue
            filed = str(entry.get("filed", ""))
            existing = concept_result.get(year)
            if existing is None or filed >= existing[0]:
                concept_result[year] = (filed, float(value))
        for year, filed_value in concept_result.items():
            result.setdefault(year, filed_value)
    return result


def normalize_company_facts(payload: dict, ticker: str) -> list[AnnualFinancials]:
    gaap = payload.get("facts", {}).get("us-gaap", {})
    values: dict[int, dict[str, tuple[str, float]]] = {}
    for metric, concepts in CONCEPTS.items():
        for year, filed_value in _first_concept_values(gaap, concepts, metric).items():
            values.setdefault(year, {})[metric] = filed_value

    total_debt = _first_concept_values(
        gaap,
        (
            "LongTermDebtAndFinanceLeaseObligations",
            "LongTermDebtAndCapitalLeaseObligations",
            "LongTermDebt",
        ),
        "debt",
    )
    current = _first_concept_values(
        gaap,
        ("LongTermDebtAndFinanceLeaseObligationsCurrent", "LongTermDebtCurrent"),
        "debt",
    )
    noncurrent = _first_concept_values(
        gaap,
        ("LongTermDebtAndFinanceLeaseObligationsNoncurrent", "LongTermDebtNoncurrent"),
        "debt",
    )
    for year in (current.keys() | noncurrent.keys()) - total_debt.keys():
            current_filed, current_value = current.get(year, ("", 0.0))
            noncurrent_filed, noncurrent_value = noncurrent.get(year, ("", 0.0))
            total_debt[year] = (max(current_filed, noncurrent_filed), current_value + noncurrent_value)
    short_term_debt = _first_concept_values(
        gaap,
        ("CommercialPaper", "ShortTermBorrowings", "ShortTermDebtCurrent"),
        "debt",
    )
    for year in total_debt.keys() | short_term_debt.keys():
        long_filed, long_value = total_debt.get(year, ("", 0.0))
        short_filed, short_value = short_term_debt.get(year, ("", 0.0))
        values.setdefault(year, {})["debt"] = (
            max(long_filed, short_filed),
            long_value + short_value,
        )
    rows = []
    for year, metrics in sorted(values.items()):
        data = {name: value for name, (_, value) in metrics.items()}
        rows.append(
            AnnualFinancials(
                fiscal_year=year,
                source_url=f"https://data.sec.gov/api/xbrl/companyfacts/CIK{int(payload.get('cik', 0)):010d}.json",
                **data,
            )
        )
    return calculate_history(rows)


def fetch_company_facts(
    cik: int,
    ticker: str,
    cache_dir: Path = Path("data/cache"),
    refresh: bool = False,
) -> list[AnnualFinancials]:
    ticker = normalize_ticker(ticker)
    cache_path = cache_dir / ticker / "companyfacts.json"
    if cache_path.exists() and not refresh:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    else:
        payload = get_json(
            sec_session(), f"{SEC_DATA}/api/xbrl/companyfacts/CIK{cik:010d}.json",
            timeout=60,
        )
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = cache_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload), encoding="utf-8")
        temporary.replace(cache_path)
    return normalize_company_facts(payload, ticker)
