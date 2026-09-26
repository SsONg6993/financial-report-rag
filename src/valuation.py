"""Transparent valuation helpers for educational analysis."""

from dataclasses import dataclass

from src.analytics import safe_divide
from src.models import AnnualFinancials, MarketSnapshot


@dataclass(frozen=True, slots=True)
class DcfAssumptions:
    revenue_growth: float = 0.05
    operating_margin: float = 0.20
    tax_rate: float = 0.21
    reinvestment_rate: float = 0.25
    discount_rate: float = 0.10
    terminal_growth: float = 0.025
    projection_years: int = 5


@dataclass(frozen=True, slots=True)
class DcfProjection:
    year: int
    revenue: float
    nopat: float
    free_cash_flow: float
    present_value: float


@dataclass(frozen=True, slots=True)
class DcfResult:
    assumptions: DcfAssumptions
    projections: tuple[DcfProjection, ...]
    terminal_value: float
    enterprise_value: float
    equity_value: float
    value_per_share: float | None


def scenario_margin_default(actual_margin: float | None) -> float:
    """Keep observed losses valid while constraining the educational widget."""
    return min(0.80, max(-0.80, float(actual_margin if actual_margin is not None else 0.20)))


def discounted_cash_flow(
    base_revenue: float,
    cash: float,
    debt: float,
    shares_outstanding: float,
    assumptions: DcfAssumptions,
) -> DcfResult:
    if assumptions.discount_rate <= assumptions.terminal_growth:
        raise ValueError("discount rate must exceed terminal growth")
    if assumptions.projection_years < 1:
        raise ValueError("projection years must be positive")
    revenue = base_revenue
    projections: list[DcfProjection] = []
    for year in range(1, assumptions.projection_years + 1):
        revenue *= 1 + assumptions.revenue_growth
        nopat = revenue * assumptions.operating_margin * (1 - assumptions.tax_rate)
        fcf = nopat * (1 - assumptions.reinvestment_rate)
        present_value = fcf / (1 + assumptions.discount_rate) ** year
        projections.append(DcfProjection(year, revenue, nopat, fcf, present_value))
    final_fcf = projections[-1].free_cash_flow
    terminal_value = final_fcf * (1 + assumptions.terminal_growth) / (
        assumptions.discount_rate - assumptions.terminal_growth
    )
    discounted_terminal = terminal_value / (
        1 + assumptions.discount_rate
    ) ** assumptions.projection_years
    enterprise_value = sum(item.present_value for item in projections) + discounted_terminal
    equity_value = enterprise_value + cash - debt
    return DcfResult(
        assumptions,
        tuple(projections),
        terminal_value,
        enterprise_value,
        equity_value,
        safe_divide(equity_value, shares_outstanding),
    )


def valuation_multiples(
    market: MarketSnapshot, latest: AnnualFinancials | None
) -> dict[str, float | None]:
    if latest is None:
        return {}
    return {
        "P/E": market.trailing_pe,
        "Price/Sales": market.price_to_sales,
        "Price/Book": market.price_to_book,
        "EV/Revenue": market.ev_to_revenue,
        "EV/EBITDA": market.ev_to_ebitda,
        "FCF Yield": safe_divide(latest.free_cash_flow, market.market_cap),
    }
