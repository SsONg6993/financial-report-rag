"""Deterministic answers for supported structured financial questions."""

import re

from src.analytics import cagr
from src.models import AnnualFinancials

METRICS = (
    ("operating cash flow", "operating_cash_flow", "Operating cash flow"),
    ("free cash flow", "free_cash_flow", "Free cash flow"),
    ("operating income", "operating_income", "Operating income"),
    ("net income", "net_income", "Net income"),
    ("net margin", "net_margin", "Net margin"),
    ("operating margin", "operating_margin", "Operating margin"),
    ("gross margin", "gross_margin", "Gross margin"),
    ("revenue growth", "revenue_growth", "Revenue growth"),
    ("revenue", "revenue", "Revenue"),
    ("net sales", "revenue", "Net sales"),
    ("eps", "eps", "Diluted EPS"),
    ("assets", "assets", "Assets"),
    ("liabilities", "liabilities", "Liabilities"),
    ("equity", "equity", "Equity"),
)


def _format_value(value: float, field: str) -> str:
    if "margin" in field or field.endswith("_growth"):
        return f"{value:.2%}"
    return f"{value:,.15g}"


def answer_structured_query(query: str, rows: list[AnnualFinancials]) -> str | None:
    if not rows:
        return None
    normalized = query.lower()
    unsupported_segments = ("services", "iphone", "ipad", "mac ", "wearables", "geographic")
    if any(segment in normalized for segment in unsupported_segments):
        return None
    if " and " in normalized or "compare" in normalized:
        return None
    years = [int(value) for value in re.findall(r"\b(?:19|20)\d{2}\b", normalized)]
    by_year = {row.fiscal_year: row for row in rows}
    if "cagr" in normalized and "revenue" in normalized and len(years) >= 2:
        start_year, end_year = years[0], years[-1]
        start = by_year.get(start_year)
        end = by_year.get(end_year)
        if start and end:
            value = cagr(start.revenue, end.revenue, end_year - start_year)
            if value is not None:
                return (
                    f"Revenue CAGR from FY{start_year} to FY{end_year} was {value:.2%} "
                    "(calculated in Python)."
                )
        return None
    metric = next((item for item in METRICS if item[0] in normalized), None)
    if metric is None:
        return None
    target = by_year.get(years[-1]) if years else rows[-1]
    if target is None:
        return None
    _, field, label = metric
    value = getattr(target, field)
    if value is None:
        return None
    return f"{label} in FY{target.fiscal_year} was {_format_value(value, field)} (SEC Company Facts)."
