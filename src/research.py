"""Evidence-first bull/bear synthesis and Markdown report assembly."""

from dataclasses import dataclass

from src.models import AnnualFinancials, MarketSnapshot
from src.risk import RiskEvidence


@dataclass(frozen=True, slots=True)
class BullBearAnalysis:
    bull: tuple[str, ...]
    bear: tuple[str, ...]
    uncertainties: tuple[str, ...]


def build_bull_bear(financials: list[AnnualFinancials], risks: list[RiskEvidence]) -> BullBearAnalysis:
    bull: list[str] = []
    bear: list[str] = []
    uncertainties: list[str] = []
    if financials:
        latest = financials[-1]
        if latest.revenue_growth is not None:
            target = bull if latest.revenue_growth > 0 else bear
            target.append(f"Revenue growth was {latest.revenue_growth:.1%} in FY{latest.fiscal_year} (SEC Company Facts).")
        if latest.free_cash_flow is not None:
            target = bull if latest.free_cash_flow > 0 else bear
            target.append(f"Free cash flow was {latest.free_cash_flow:,.0f} in FY{latest.fiscal_year} (calculated from SEC facts).")
        if latest.net_margin is not None:
            target = bull if latest.net_margin >= 0.10 else bear
            target.append(f"Net margin was {latest.net_margin:.1%} in FY{latest.fiscal_year} (calculated).")
    for risk in risks[:5]:
        bear.append(f"{risk.category.title()}: {risk.evidence[:220]}… [{risk.section} / {risk.chunk_id}]")
    if not financials:
        uncertainties.append("Structured SEC financial history was unavailable.")
    if not risks:
        uncertainties.append("No risk-factor evidence has been retrieved yet.")
    uncertainties.append("Market prices, future growth, margins, and discount rates remain uncertain.")
    return BullBearAnalysis(tuple(bull), tuple(bear), tuple(uncertainties))


def markdown_report(
    ticker: str,
    company: str,
    financials: list[AnnualFinancials],
    market: MarketSnapshot,
    analysis: BullBearAnalysis,
    risks: list[RiskEvidence],
) -> str:
    latest = financials[-1] if financials else None
    lines = [
        f"# {company or ticker} ({ticker}) Research Report",
        "",
        "## Company Overview",
        market.description or "Company description unavailable.",
        "",
        "## Financial Performance",
    ]
    if latest:
        lines.extend([
            f"- Fiscal year: {latest.fiscal_year}",
            f"- Revenue: {latest.revenue:,.0f}" if latest.revenue is not None else "- Revenue: unavailable",
            f"- Net income: {latest.net_income:,.0f}" if latest.net_income is not None else "- Net income: unavailable",
            f"- Free cash flow: {latest.free_cash_flow:,.0f}" if latest.free_cash_flow is not None else "- Free cash flow: unavailable",
        ])
    else:
        lines.append("Structured financial history unavailable.")
    lines.extend(["", "## Valuation", "Valuation depends on live market data and user-selected DCF assumptions."])
    bull_lines = [f"- {item}" for item in analysis.bull] or ["- None identified."]
    bear_lines = [f"- {item}" for item in analysis.bear] or ["- None identified."]
    lines.extend(["", "## Bull Evidence", *bull_lines])
    lines.extend(["", "## Bear Evidence", *bear_lines])
    lines.extend(["", "## Key Uncertainties", *[f"- {item}" for item in analysis.uncertainties]])
    lines.extend(["", "## Sources"])
    if latest and latest.source_url:
        lines.append(f"- SEC Company Facts: {latest.source_url}")
    lines.extend(f"- {risk.section}, chunk {risk.chunk_id}" for risk in risks[:10])
    lines.extend([
        "",
        "---",
        "This project is an educational financial research and decision-support tool. It does not provide personalized investment advice and should not be relied upon as the sole basis for investment decisions.",
    ])
    return "\n".join(lines)
