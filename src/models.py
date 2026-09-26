"""Small domain models shared by analytics, data providers, and the UI."""

from dataclasses import dataclass, field


@dataclass(slots=True)
class AnnualFinancials:
    fiscal_year: int
    revenue: float | None = None
    gross_profit: float | None = None
    operating_income: float | None = None
    net_income: float | None = None
    eps: float | None = None
    operating_cash_flow: float | None = None
    capital_expenditure: float | None = None
    free_cash_flow: float | None = None
    assets: float | None = None
    liabilities: float | None = None
    equity: float | None = None
    current_assets: float | None = None
    current_liabilities: float | None = None
    debt: float | None = None
    cash: float | None = None
    shares_outstanding: float | None = None
    revenue_growth: float | None = None
    gross_margin: float | None = None
    operating_margin: float | None = None
    net_margin: float | None = None
    fcf_margin: float | None = None
    roa: float | None = None
    roe: float | None = None
    roic: float | None = None
    debt_to_equity: float | None = None
    current_ratio: float | None = None
    source_url: str = ""


@dataclass(slots=True)
class MarketSnapshot:
    ticker: str
    price: float | None = None
    market_cap: float | None = None
    high_52_week: float | None = None
    low_52_week: float | None = None
    volume: float | None = None
    enterprise_value: float | None = None
    trailing_pe: float | None = None
    price_to_sales: float | None = None
    price_to_book: float | None = None
    ev_to_revenue: float | None = None
    ev_to_ebitda: float | None = None
    company_name: str = ""
    description: str = ""
    currency: str = "USD"
    history: list[dict] = field(default_factory=list)
    error: str | None = None
