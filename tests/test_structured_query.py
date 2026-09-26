from src.models import AnnualFinancials
from src.structured_query import answer_structured_query

ROWS = [
    AnnualFinancials(fiscal_year=2023, revenue=100, net_income=10, net_margin=0.10),
    AnnualFinancials(fiscal_year=2024, revenue=110, net_income=12, net_margin=12 / 110),
    AnnualFinancials(fiscal_year=2025, revenue=121, net_income=15, net_margin=15 / 121),
]


def test_structured_metric_lookup_uses_requested_year():
    answer = answer_structured_query("What was revenue in 2024?", ROWS)
    assert answer == "Revenue in FY2024 was 110 (SEC Company Facts)."


def test_structured_cagr_uses_python_calculation():
    answer = answer_structured_query("Calculate revenue CAGR from 2023 to 2025", ROWS)
    assert answer == "Revenue CAGR from FY2023 to FY2025 was 10.00% (calculated in Python)."


def test_structured_query_returns_none_for_unsupported_narrative():
    assert answer_structured_query("Why did demand change?", ROWS) is None


def test_structured_revenue_growth_does_not_substitute_revenue_dollars():
    rows = [AnnualFinancials(fiscal_year=2025, revenue=100, revenue_growth=0.25)]
    assert answer_structured_query("What was revenue growth in 2025?", rows) == (
        "Revenue growth in FY2025 was 25.00% (SEC Company Facts)."
    )


def test_segment_revenue_declines_instead_of_substituting_total_revenue():
    assert answer_structured_query("What was Services revenue in 2025?", ROWS) is None
