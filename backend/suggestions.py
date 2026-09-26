"""Evidence-backed candidate hypotheses, not generated investor motivation."""

from src.thesis import fact_evidence
from src.thesis_research import company_rows

CATEGORIES = {
    "Growth": [
        "Can revenue keep growing?",
        "Which segment drives growth?",
        "Is growth accelerating or slowing?",
    ],
    "Profitability": [
        "Are margins improving?",
        "Are costs growing faster than revenue?",
    ],
    "Competitive Advantage": ["What protects customer retention?"],
    "Valuation": ["What assumptions are priced in?"],
    "Catalyst": ["Which disclosed event could change the outlook?"],
    "Risk": ["Which risk could invalidate the thesis?"],
    "Balance Sheet": ["Can cash and earnings support debt obligations?"],
    "Cash Flow": ["Is cash generation resilient after investment?"],
}


def suggested_theses(company: dict, chunks: list[dict]) -> list[dict]:
    rows = company_rows(company)
    current = max(rows, key=lambda r: r.fiscal_year) if rows else None
    suggestions = []
    candidates = [
        (
            "Growth",
            "revenue_growth",
            0,
            "Revenue can continue growing year over year.",
            "Growth helps test demand durability.",
        ),
        (
            "Profitability",
            "gross_margin",
            round(current.gross_margin * 0.95, 3)
            if current and current.gross_margin is not None
            else None,
            "Gross margin can remain close to its latest annual level.",
            "Margin resilience tests pricing power and cost control.",
        ),
        (
            "Cash Flow",
            "free_cash_flow",
            0,
            "Free cash flow can remain positive after capital investment.",
            "Cash generation supports reinvestment without relying solely on financing.",
        ),
        (
            "Balance Sheet",
            "debt",
            current.debt * 1.1 if current and current.debt is not None else None,
            "Debt can remain within 10% of its latest annual level.",
            "Debt discipline limits financing pressure.",
        ),
    ]
    for category, metric, threshold, text, why in candidates:
        if current is None or threshold is None or getattr(current, metric) is None:
            continue
        operator = "<=" if metric == "debt" else ">" if threshold == 0 else ">="
        display = (
            f"{threshold:.1%}"
            if "margin" in metric or metric.endswith("_growth")
            else f"${threshold:,.0f}"
        )
        condition = f"Annual {metric.replace('_', ' ')} {operator} {display}"
        if metric == "gross_margin":
            text = f"Gross margin can remain at or above {threshold:.1%}."
        suggestions.append(
            {
                "id": f"{company['ticker']}:{metric}:{current.fiscal_year}",
                "category": category,
                "text": text,
                "why_it_matters": why,
                "evidence": [fact_evidence(current, metric)],
                "support_condition": condition,
                "invalidate_condition": "The comparable annual metric fails that threshold, or its definition changes.",
                "rule": {
                    "metric": metric,
                    "operator": operator,
                    "threshold": threshold,
                },
                "generator": "Evidence-backed Python template; annual evaluation",
                "period": f"FY{current.fiscal_year}",
            }
        )
    if chunks and len(suggestions) < 5:
        risk = next(
            (
                c
                for c in chunks
                if "risk" in c.get("section", "").lower() or "risk" in c["text"].lower()
            ),
            chunks[0],
        )
        suggestions.append(
            {
                "id": f"{company['ticker']}:risk",
                "category": "Risk",
                "text": "The disclosed operating risks can remain manageable without materially impairing cash generation.",
                "why_it_matters": "This is a hypothesis to investigate, not evidence that a risk is controlled.",
                "evidence": [{**risk, "text": risk["text"][:700]}],
                "support_condition": "New filings provide explicit evidence of mitigation and resilient cash generation.",
                "invalidate_condition": "New disclosures describe material operational disruption or financial impact.",
                "rule": None,
                "generator": "Evidence-backed template; optional Jev semantic evaluation",
                "period": risk.get("period", ""),
            }
        )
    return suggestions[:5]
