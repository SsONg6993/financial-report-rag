"""Duration-aware financial context; never infer quarters from cumulative cash flow."""

import math
from datetime import date

from src.companyfacts import CONCEPTS

LABELS = {
    "revenue": "Revenue",
    "operating_income": "Operating income",
    "net_income": "Net income",
    "eps": "Diluted EPS",
    "operating_cash_flow": "Operating cash flow",
    "capital_expenditure": "Capex",
    "free_cash_flow": "Free cash flow",
}
CASH = {"operating_cash_flow", "capital_expenditure", "free_cash_flow"}


def financial_context(payload, filings, annual):
    """Anchor to the latest filing, not the latest *available* revenue fact.

    Fiscal labels come from the current filing's own facts. Comparative facts'
    fy/fp describe their filing, not their observation, and must not be reused.
    """
    latest = max(
        (f for f in filings if f.get("form") in {"10-Q", "10-K"}),
        key=lambda f: (f.get("report_date", ""), f.get("filing_date", "")),
        default={},
    )
    if latest.get("form") != "10-Q":
        return annual_context(annual)
    end = latest.get("report_date", "")
    accession = latest.get("accession_number") or latest.get("accession")
    cik = payload.get("cik") or latest.get("cik")
    source = (
        f"https://data.sec.gov/api/xbrl/companyfacts/CIK{int(cik):010d}.json"
        if cik
        else latest.get("source_url", "")
    )
    gaap = payload.get("facts", {}).get("us-gaap", {})
    entries = {}
    for metric in LABELS:
        if metric == "free_cash_flow":
            continue
        valid = []
        for concept in CONCEPTS[metric]:
            for entry in (
                gaap.get(concept, {})
                .get("units", {})
                .get("USD/shares" if metric == "eps" else "USD", [])
            ):
                try:
                    duration = (
                        date.fromisoformat(entry["end"])
                        - date.fromisoformat(entry["start"])
                    ).days
                    value = float(entry["val"])
                except (KeyError, ValueError, TypeError):
                    continue
                if entry.get("form") not in {"10-Q", "10-K"} or not math.isfinite(
                    value
                ):
                    continue
                if not (
                    70 <= duration <= 105
                    or metric in CASH
                    and (150 <= duration <= 200 or 240 <= duration <= 290)
                ):
                    continue
                valid.append(
                    {**entry, "val": value, "duration": duration, "concept": concept}
                )
        entries[metric] = valid
    # Current facts must belong to the current filing, not a future comparative.
    current = {}
    for metric, candidates in entries.items():
        candidates = [
            e
            for e in candidates
            if e["end"] == end and (not accession or e.get("accn") == accession)
        ]
        if candidates:
            # Cash flow uses longest reported duration (YTD); income uses only quarter.
            if metric in CASH:
                duration = max(e["duration"] for e in candidates)
                candidates = [e for e in candidates if e["duration"] == duration]
            preferred = min(CONCEPTS[metric].index(e["concept"]) for e in candidates)
            candidates = [
                e
                for e in candidates
                if CONCEPTS[metric].index(e["concept"]) == preferred
            ]
            if len({(e["start"], e["end"], e["val"]) for e in candidates}) != 1:
                continue  # Ambiguous current-filing observations are not guessed.
            current[metric] = min(
                candidates,
                key=lambda e: (
                    CONCEPTS[metric].index(e["concept"]),
                    -int(e.get("filed", "0000-00-00").replace("-", "")),
                ),
            )
    anchor = next(
        (e for e in current.values() if e.get("fp") in {"Q1", "Q2", "Q3"}), {}
    )
    year = anchor.get("fy")
    period = (
        f"{anchor['fp']} {year}"
        if year and anchor
        else f"Quarter ended {end or 'unavailable'}"
    )
    metrics = []
    prior = {}
    for metric, fact in current.items():
        matches = [
            e
            for e in entries[metric]
            if e["concept"] == fact["concept"]
            and 357
            <= (date.fromisoformat(end) - date.fromisoformat(e["end"])).days
            <= 373
            and 357
            <= (date.fromisoformat(fact["start"]) - date.fromisoformat(e["start"])).days
            <= 373
            and abs(e["duration"] - fact["duration"]) <= 8
        ]
        if matches:
            # Prefer comparative values reported alongside the current observation.
            prior[metric] = max(
                matches,
                key=lambda e: (e.get("accn") == fact.get("accn"), e.get("filed", "")),
            )
    for facts in (current, prior):
        ocf, capex = facts.get("operating_cash_flow"), facts.get("capital_expenditure")
        if (
            ocf
            and capex
            and (ocf["start"], ocf["end"], ocf.get("accn"))
            == (capex["start"], capex["end"], capex.get("accn"))
        ):
            facts["free_cash_flow"] = {**ocf, "val": ocf["val"] - capex["val"]}
    for metric, label in LABELS.items():
        fact, before = current.get(metric), prior.get(metric)
        months = round(fact["duration"] / 30.4) if fact else None
        cash_period = (
            f"{months}M {year} YTD"
            if metric in CASH and months and months > 3 and year
            else period
        )
        previous_period = (
            cash_period.replace(str(year), str(int(year) - 1))
            if before and year
            else None
        )
        value = fact["val"] if fact else None
        previous = before["val"] if before else None
        # Signed EPS/income: report absolute change; % growth only for positive base.
        yoy = (
            (value - previous) / previous
            if value is not None and previous is not None and previous > 0
            else None
        )
        metrics.append(
            {
                "metric": metric,
                "label": label,
                "period": cash_period,
                "value": value,
                "previous": previous,
                "previous_period": previous_period,
                "yoy": yoy,
                "source_url": source,
                "start": fact.get("start") if fact else None,
                "end": end,
                "filed": fact.get("filed") if fact else None,
            }
        )
    revenue = metrics[0]
    metrics.insert(
        1,
        {
            **revenue,
            "metric": "revenue_growth",
            "label": "Revenue growth",
            "value": revenue["yoy"],
            "previous": None,
            "yoy": None,
        },
    )
    return {"kind": "quarterly", "period": period, "end": end, "metrics": metrics}


def quarterly_comparisons(context):
    return [
        {
            "metric": item["metric"],
            "label": item["label"],
            "current": item["value"],
            "previous": item["previous"],
            "current_period": item["period"],
            "previous_period": item["previous_period"],
            "delta": item["value"] - item["previous"]
            if item["value"] is not None and item["previous"] is not None
            else None,
            "relative_change": item["yoy"],
            "status": "Comparable periods"
            if item["previous"] is not None
            else "Comparison unavailable",
            "meaning": f"Compare {item['period']} with {item['previous_period'] or 'an unavailable prior-year period'}."
            + (
                " Cumulative YTD cash flow, not standalone quarterly cash flow."
                if "YTD" in item["period"]
                else ""
            ),
            "source_url": item["source_url"],
            "previous_source_url": item["source_url"]
            if item["previous"] is not None
            else "",
        }
        for item in context["metrics"]
        if item["metric"] in {"revenue", "net_income", "free_cash_flow"}
    ]


def annual_context(annual):
    period = (
        f"Latest annual · FY{annual['fiscal_year']}"
        if annual.get("fiscal_year")
        else "Latest annual · period unavailable"
    )
    return {
        "kind": "annual",
        "period": period,
        "end": "",
        "metrics": [
            {
                "metric": key,
                "label": LABELS.get(key, "Revenue growth"),
                "period": period,
                "value": annual.get(key),
                "previous": None,
                "previous_period": None,
                "yoy": None,
                "source_url": annual.get("source_url", ""),
            }
            for key in ("revenue", "revenue_growth", "free_cash_flow")
        ],
    }


def number_lines(context):
    lines = []
    for item in context.get("metrics", []):
        value = item["value"]
        formatted = (
            "Unavailable"
            if value is None
            else f"{value:.1%}"
            if item["metric"] == "revenue_growth"
            else f"${value:,.2f}"
            if item["metric"] == "eps"
            else f"${value:,.0f}"
        )
        comparison = (
            f" · {item['yoy']:+.1%} YoY vs {item['previous_period']}"
            if item.get("yoy") is not None
            else " · Comparable growth unavailable"
        )
        if item["metric"] == "revenue_growth" and value is not None:
            comparison = (
                f" · YoY vs {item.get('previous_period') or 'prior year'}"
                if context["kind"] == "quarterly"
                else " · Annual context"
            )
        if item.get("previous") is not None:
            previous = (
                f"${item['previous']:,.2f}"
                if item["metric"] == "eps"
                else f"${item['previous']:,.0f}"
            )
            comparison += f" · Previous {item['previous_period']}: {previous}"
        lines.append(f"{item['label']} — {item['period']}\n{formatted}{comparison}")
    return lines
