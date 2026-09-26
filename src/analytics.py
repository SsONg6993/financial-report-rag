"""Deterministic financial calculations; missing inputs stay missing."""

from dataclasses import replace

from src.models import AnnualFinancials


def safe_divide(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return numerator / denominator


def yoy_growth(current: float | None, previous: float | None) -> float | None:
    if current is None or previous in (None, 0):
        return None
    return current / previous - 1


def cagr(start: float | None, end: float | None, years: int) -> float | None:
    if start is None or end is None or start <= 0 or end < 0 or years <= 0:
        return None
    return (end / start) ** (1 / years) - 1


def calculate_financials(row: AnnualFinancials) -> AnnualFinancials:
    fcf = (
        row.operating_cash_flow - abs(row.capital_expenditure)
        if row.operating_cash_flow is not None and row.capital_expenditure is not None
        else None
    )
    invested_capital = None
    if row.debt is not None and row.equity is not None:
        invested_capital = row.debt + row.equity - (row.cash or 0)
    nopat = row.operating_income * 0.79 if row.operating_income is not None else None
    return replace(
        row,
        free_cash_flow=fcf,
        gross_margin=safe_divide(row.gross_profit, row.revenue),
        operating_margin=safe_divide(row.operating_income, row.revenue),
        net_margin=safe_divide(row.net_income, row.revenue),
        fcf_margin=safe_divide(fcf, row.revenue),
        roa=safe_divide(row.net_income, row.assets),
        roe=safe_divide(row.net_income, row.equity),
        roic=safe_divide(nopat, invested_capital),
        debt_to_equity=safe_divide(row.debt, row.equity),
        current_ratio=safe_divide(row.current_assets, row.current_liabilities),
    )


def calculate_history(rows: list[AnnualFinancials]) -> list[AnnualFinancials]:
    ordered = sorted(rows, key=lambda item: item.fiscal_year)
    result: list[AnnualFinancials] = []
    for index, row in enumerate(ordered):
        calculated = calculate_financials(row)
        previous = ordered[index - 1].revenue if index else None
        calculated.revenue_growth = yoy_growth(row.revenue, previous)
        result.append(calculated)
    return result
