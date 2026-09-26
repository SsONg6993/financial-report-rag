import pytest

from src.analytics import cagr, calculate_financials, safe_divide, yoy_growth
from src.models import AnnualFinancials
from src.valuation import DcfAssumptions, discounted_cash_flow, scenario_margin_default


def test_growth_and_cagr_are_deterministic_and_safe():
    assert yoy_growth(120, 100) == pytest.approx(0.2)
    assert cagr(100, 121, 2) == pytest.approx(0.1)
    assert safe_divide(5, 0) is None
    assert yoy_growth(None, 100) is None


def test_financial_ratios_and_fcf_use_python_values():
    row = AnnualFinancials(
        fiscal_year=2025,
        revenue=200,
        gross_profit=80,
        operating_income=40,
        net_income=30,
        operating_cash_flow=50,
        capital_expenditure=15,
        assets=300,
        liabilities=120,
        equity=180,
        current_assets=90,
        current_liabilities=60,
        debt=45,
    )

    calculated = calculate_financials(row)

    assert calculated.free_cash_flow == 35
    assert calculated.gross_margin == pytest.approx(0.4)
    assert calculated.operating_margin == pytest.approx(0.2)
    assert calculated.net_margin == pytest.approx(0.15)
    assert calculated.fcf_margin == pytest.approx(0.175)
    assert calculated.roe == pytest.approx(1 / 6)
    assert calculated.current_ratio == pytest.approx(1.5)


def test_dcf_exposes_assumptions_and_value_bridge():
    result = discounted_cash_flow(
        base_revenue=1000,
        cash=100,
        debt=50,
        shares_outstanding=100,
        assumptions=DcfAssumptions(
            revenue_growth=0.05,
            operating_margin=0.20,
            tax_rate=0.21,
            reinvestment_rate=0.25,
            discount_rate=0.10,
            terminal_growth=0.025,
            projection_years=5,
        ),
    )

    assert len(result.projections) == 5
    assert result.enterprise_value > 0
    assert result.equity_value == pytest.approx(result.enterprise_value + 50)
    assert result.value_per_share == pytest.approx(result.equity_value / 100)


def test_dcf_rejects_terminal_growth_at_or_above_discount_rate():
    with pytest.raises(ValueError, match="terminal growth"):
        discounted_cash_flow(
            1000,
            0,
            0,
            100,
            DcfAssumptions(discount_rate=0.05, terminal_growth=0.05),
        )


def test_negative_actual_margin_is_valid_dcf_scenario_default():
    assert scenario_margin_default(-0.10) == -0.10
    assert scenario_margin_default(-2.0) == -0.80
