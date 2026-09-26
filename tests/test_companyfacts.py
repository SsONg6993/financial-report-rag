from src.companyfacts import normalize_company_facts


def fact(units, label="Metric"):
    return {"label": label, "units": units}


def test_companyfacts_normalizes_annual_metrics_and_uses_latest_filed_value():
    payload = {
        "cik": 320193,
        "entityName": "Apple Inc.",
        "facts": {
            "us-gaap": {
                "RevenueFromContractWithCustomerExcludingAssessedTax": fact(
                    {
                        "USD": [
                            {"fy": 2024, "fp": "FY", "form": "10-K", "start": "2023-10-01", "end": "2024-09-28", "filed": "2024-11-01", "val": 390_000},
                            {"fy": 2025, "fp": "FY", "form": "10-K", "start": "2023-10-01", "end": "2024-09-28", "filed": "2025-10-31", "val": 391_035},
                            {"fy": 2025, "fp": "Q3", "form": "10-Q", "start": "2025-01-01", "end": "2025-06-30", "filed": "2025-08-01", "val": 99},
                        ]
                    }
                ),
                "NetIncomeLoss": fact({"USD": [{"fy": 2025, "fp": "FY", "form": "10-K", "start": "2024-09-29", "end": "2025-09-27", "filed": "2025-10-31", "val": 112_010}]}),
                "NetCashProvidedByUsedInOperatingActivities": fact({"USD": [{"fy": 2025, "fp": "FY", "form": "10-K", "start": "2024-09-29", "end": "2025-09-27", "filed": "2025-10-31", "val": 111_482}]}),
                "PaymentsToAcquirePropertyPlantAndEquipment": fact({"USD": [{"fy": 2025, "fp": "FY", "form": "10-K", "start": "2024-09-29", "end": "2025-09-27", "filed": "2025-10-31", "val": 12_715}]}),
            }
        },
    }

    rows = normalize_company_facts(payload, "AAPL")

    assert [row.fiscal_year for row in rows] == [2024, 2025]
    assert rows[0].revenue == 391_035
    assert rows[1].net_income == 112_010
    assert rows[1].free_cash_flow == 98_767


def test_companyfacts_returns_missing_values_instead_of_inventing_them():
    rows = normalize_company_facts({"facts": {"us-gaap": {}}}, "ABC")
    assert rows == []


def test_companyfacts_combines_current_and_noncurrent_debt_when_total_is_absent():
    annual = lambda value: [
        {
            "fy": 2025,
            "fp": "FY",
            "form": "10-K",
            "end": "2025-09-27",
            "filed": "2025-10-31",
            "val": value,
        }
    ]
    payload = {
        "facts": {
            "us-gaap": {
                "LongTermDebtCurrent": fact({"USD": annual(12_000)}),
                "LongTermDebtNoncurrent": fact({"USD": annual(86_000)}),
                "Assets": fact({"USD": annual(300_000)}),
            }
        }
    }

    rows = normalize_company_facts(payload, "ABC")

    assert rows[0].debt == 98_000


def test_companyfacts_uses_concept_fallback_per_year_and_adds_short_term_debt():
    def annual(year, value):
        return {
            "fy": year,
            "fp": "FY",
            "form": "10-K",
            "end": f"{year}-12-31",
            "filed": f"{year + 1}-02-01",
            "val": value,
        }

    payload = {
        "facts": {
            "us-gaap": {
                "RevenueFromContractWithCustomerExcludingAssessedTax": fact({"USD": [annual(2025, 120)]}),
                "Revenues": fact({"USD": [annual(2024, 100)]}),
                "LongTermDebt": fact({"USD": [annual(2025, 80)]}),
                "LongTermDebtCurrent": fact({"USD": [annual(2024, 10)]}),
                "LongTermDebtNoncurrent": fact({"USD": [annual(2024, 70)]}),
                "CommercialPaper": fact({"USD": [annual(2024, 5), annual(2025, 7)]}),
            }
        }
    }

    rows = normalize_company_facts(payload, "ABC")

    assert [(row.fiscal_year, row.revenue, row.debt) for row in rows] == [
        (2024, 100, 85),
        (2025, 120, 87),
    ]
