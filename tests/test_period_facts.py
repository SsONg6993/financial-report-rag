import pytest

from backend.period_facts import financial_context, number_lines
from backend.research_context import structured_answer
from src.config import AppConfig


def facts():
    def entry(start, end, value, fp="Q2", accession="current"):
        return {
            "start": start,
            "end": end,
            "val": value,
            "form": "10-Q",
            "fy": 2026,
            "fp": fp,
            "filed": "2026-08-10",
            "accn": accession,
        }

    return {
        "cik": 1,
        "facts": {
            "us-gaap": {
                "RevenueFromContractWithCustomerExcludingAssessedTax": {
                    "units": {
                        "USD": [
                            entry("2026-01-01", "2026-06-30", 250),
                            entry("2026-04-01", "2026-06-30", 150),
                            entry("2025-04-01", "2025-06-30", 100),
                        ]
                    }
                },
                "NetCashProvidedByUsedInOperatingActivities": {
                    "units": {
                        "USD": [
                            entry("2026-01-01", "2026-06-30", 80),
                            entry("2025-01-01", "2025-06-30", 60),
                        ]
                    }
                },
                "PaymentsToAcquirePropertyPlantAndEquipment": {
                    "units": {
                        "USD": [
                            entry("2026-01-01", "2026-06-30", 30),
                            entry("2025-01-01", "2025-06-30", 20),
                        ]
                    }
                },
            }
        },
    }


FILING = {"form": "10-Q", "report_date": "2026-06-30", "accession_number": "current"}
ANNUAL = {
    "fiscal_year": 2025,
    "revenue": 601800000,
    "free_cash_flow": -100,
    "source_url": "https://sec.gov/annual",
}


def context(payload=None, filing=None):
    return financial_context(payload or facts(), [filing or FILING], ANNUAL)


def test_quarter_vs_same_quarter_prior_year():
    result = context()
    revenue = result["metrics"][0]
    assert result["period"] == "Q2 2026"
    assert revenue["value"] == 150  # Not 250 YTD
    assert revenue["previous"] == 100
    assert (
        revenue["previous_period"] == "Q2 2025"
    )  # Comparative fp/fy are filing metadata
    assert revenue["yoy"] == 0.5


def test_ytd_cash_flow_explicit_and_aligned():
    result = {m["metric"]: m for m in context()["metrics"]}
    assert result["operating_cash_flow"]["period"] == "6M 2026 YTD"
    assert result["capital_expenditure"]["period"] == "6M 2026 YTD"
    assert result["free_cash_flow"]["value"] == 50
    assert result["free_cash_flow"]["previous"] == 40
    assert result["free_cash_flow"]["previous_period"] == "6M 2025 YTD"


def test_incompatible_cash_durations_unavailable():
    payload = facts()
    payload["facts"]["us-gaap"]["PaymentsToAcquirePropertyPlantAndEquipment"]["units"][
        "USD"
    ][0]["start"] = "2026-04-01"
    assert (
        next(m for m in context(payload)["metrics"] if m["metric"] == "free_cash_flow")[
            "value"
        ]
        is None
    )


def test_annual_fallback_labeled():
    result = financial_context(
        {}, [{"form": "10-K", "report_date": "2025-12-31"}], ANNUAL
    )
    assert result["kind"] == "annual"
    assert "Latest annual · FY2025" in number_lines(result)[0]


def test_latest_quarter_missing_never_falls_back_to_annual():
    result = financial_context({}, [FILING], ANNUAL)
    assert result["kind"] == "quarterly"
    assert all(m["value"] is None for m in result["metrics"])
    assert "FY2025" not in " ".join(number_lines(result))


def test_ambiguous_current_observations_are_unavailable():
    payload = facts()
    entries = payload["facts"]["us-gaap"][
        "RevenueFromContractWithCustomerExcludingAssessedTax"
    ]["units"]["USD"]
    entries.append({**entries[1], "val": 999})
    assert context(payload)["metrics"][0]["value"] is None


def test_same_duration_wrong_quarter_is_not_comparable():
    payload = facts()
    old = payload["facts"]["us-gaap"][
        "RevenueFromContractWithCustomerExcludingAssessedTax"
    ]["units"]["USD"][2]
    old.update(start="2025-03-01", end="2025-05-31")
    assert context(payload)["metrics"][0]["previous"] is None


def test_eps_uses_per_share_quarter_not_ytd_or_dollar_units():
    payload = facts()
    template = payload["facts"]["us-gaap"][
        "RevenueFromContractWithCustomerExcludingAssessedTax"
    ]["units"]["USD"]
    payload["facts"]["us-gaap"]["EarningsPerShareDiluted"] = {
        "units": {
            "USD/shares": [
                {**template[0], "val": 3.0},
                {**template[1], "val": 1.5},
                {**template[2], "val": 1.0},
            ],
            "USD": [{**template[1], "val": 999}],
        }
    }
    eps = next(m for m in context(payload)["metrics"] if m["metric"] == "eps")
    assert (eps["value"], eps["previous"], eps["yoy"]) == (1.5, 1.0, 0.5)


def test_no_mixed_period_summary(monkeypatch):
    monkeypatch.setattr(
        "backend.research_context.synthesis",
        lambda *_: {
            "short_answer": "Revenue FY2025 is latest",
            "why": ["FY2025"],
            "watch": ["FY2025"],
        },
    )
    company = {
        "annual": ANNUAL,
        "financial_context": context(),
        "suggestions": [{"text": "FY2025 annual idea"}],
    }
    result = structured_answer(
        "RKLB latest quarter?",
        company,
        [{"period": "2026-06-30", "text": "Quarter evidence"}],
        "Annual FY2025 revenue",
        AppConfig.from_env(),
    )
    assert "FY2025" not in result["answer"]
    assert "FY2025" not in " ".join(
        result["sections"]["numbers"] + result["sections"]["watch"]
    )
    assert "FY2025" in " ".join(result["sections"]["annual_context"])


@pytest.mark.parametrize(
    "metric",
    [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "NetCashProvidedByUsedInOperatingActivities",
    ],
)
def test_wrong_accession_cannot_supply_latest_facts(metric):
    payload = facts()
    for e in payload["facts"]["us-gaap"][metric]["units"]["USD"]:
        e["accn"] = "different"
    key = "revenue" if metric.startswith("Revenue") else "operating_cash_flow"
    assert (
        next(m for m in context(payload)["metrics"] if m["metric"] == key)["value"]
        is None
    )
