"""Conservative SEC quarter normalization. Never mix YTD with quarter durations."""

import math
from datetime import date

from src.companyfacts import CONCEPTS


def quarter_facts(payload: dict) -> list[dict]:
    gaap = payload.get("facts", {}).get("us-gaap", {})
    periods: dict[str, dict] = {}
    source = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{int(payload.get('cik', 0)):010d}.json"
    for metric in (
        "revenue",
        "gross_profit",
        "net_income",
        "operating_income",
        "operating_cash_flow",
        "capital_expenditure",
    ):
        for concept in CONCEPTS[metric]:
            for entry in gaap.get(concept, {}).get("units", {}).get("USD", []):
                if entry.get("form") not in {"10-Q", "10-K"} or not entry.get("start"):
                    continue
                try:
                    duration = (
                        date.fromisoformat(entry["end"])
                        - date.fromisoformat(entry["start"])
                    ).days
                    value = float(entry["val"])
                except (ValueError, KeyError, TypeError):
                    continue
                if not 70 <= duration <= 105 or not math.isfinite(value):
                    continue
                row = periods.setdefault(
                    entry["end"],
                    {"period": entry["end"], "source_url": source, "facts": {}},
                )
                old = row["facts"].get(metric)
                if old is None or (
                    old["concept"] == concept and entry.get("filed", "") >= old["filed"]
                ):
                    row["facts"][metric] = {
                        "value": value,
                        "start": entry["start"],
                        "filed": entry.get("filed", ""),
                        "concept": concept,
                    }
    rows = []
    for period, row in sorted(periods.items()):
        facts = row.pop("facts")
        row.update({key: value["value"] for key, value in facts.items()})
        row["fact_metadata"] = facts
        revenue = row.get("revenue")
        for numerator, metric in [
            ("gross_profit", "gross_margin"),
            ("net_income", "net_margin"),
            ("operating_income", "operating_margin"),
        ]:
            aligned = (
                numerator in facts
                and "revenue" in facts
                and facts[numerator]["start"] == facts["revenue"]["start"]
            )
            row[metric] = row[numerator] / revenue if revenue and aligned else None
        ocf, capex = facts.get("operating_cash_flow"), facts.get("capital_expenditure")
        row["free_cash_flow"] = (
            ocf["value"] - capex["value"]
            if ocf and capex and ocf["start"] == capex["start"]
            else None
        )
        rows.append(row)
    return rows


def quarterly_changes(rows: list[dict]) -> list[dict]:
    revenues = [r for r in rows if r.get("revenue") is not None]
    if not revenues:
        return []
    current = revenues[-1]
    today = date.fromisoformat(current["period"])
    matches = [
        r
        for r in revenues[:-1]
        if 335 <= (today - date.fromisoformat(r["period"])).days <= 395
    ]
    if not matches:
        return []
    previous = min(
        matches, key=lambda r: abs((today - date.fromisoformat(r["period"])).days - 365)
    )
    changes = []
    for metric in (
        "revenue",
        "gross_margin",
        "net_margin",
        "free_cash_flow",
        "capital_expenditure",
    ):
        before, after = previous.get(metric), current.get(metric)
        if before is None or after is None or before == 0:
            continue
        margin = "margin" in metric
        delta = after - before if margin else (after - before) / abs(before)
        if abs(delta) < (0.005 if margin else 0.05):
            continue
        category = (
            "Monitor"
            if metric == "capital_expenditure"
            else "Improved"
            if delta > 0
            else "Worsened"
        )
        text = f"{metric.replace('_', ' ').title()}: {delta * 100:+.1f}{' percentage points' if margin else '%'} vs prior comparable quarter"
        evidence = [
            {
                "text": f"{metric}: {r[metric]:,.4f}",
                "period": r["period"],
                "source_url": r["source_url"],
                "source_type": "SEC Company Facts (quarter)",
            }
            for r in (previous, current)
        ]
        changes.append(
            {
                "category": category,
                "text": text,
                "evidence": evidence,
                "comparison": "quarter-year-over-year",
            }
        )
    return changes
