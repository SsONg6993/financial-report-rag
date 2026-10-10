from src.portfolios import Holding, PortfolioSnapshot
from src.sector_intelligence import (
    UNKNOWN_SECTOR,
    CorporateAction,
    analyze_sector_exposure,
)


def snapshot(period: str, apple_shares: float, unknown_value: float = 0) -> PortfolioSnapshot:
    holdings = [
        Holding(
            "APPLE INC",
            "COM",
            "037833100",
            apple_shares,
            apple_shares * 20,
            ticker="AAPL",
        )
    ]
    if unknown_value:
        holdings.append(
            Holding("UNMAPPED ISSUER", "COM", "000000000", 10, unknown_value)
        )
    return PortfolioSnapshot(
        "berkshire",
        period,
        period,
        f"https://www.sec.gov/fixture/{period}",
        period,
        holdings=holdings,
    )


def test_identifier_backed_allocation_keeps_unknown_in_coverage():
    analysis = analyze_sector_exposure([snapshot("2026-06-30", 100, 500)])
    allocation = {row["sector"]: row for row in analysis["allocation"]}
    assert allocation["Information Technology"]["reported_value"] == 2000
    assert allocation[UNKNOWN_SECTOR]["reported_value"] == 500
    assert analysis["coverage"]["classified_value_percentage"] == 0.8
    assert analysis["coverage"]["unknown_value_percentage"] == 0.2
    assert analysis["comparison"]["available"] is False


def test_quarter_changes_separate_reported_shares_from_weight_changes():
    previous = snapshot("2026-03-31", 100, 1000)
    current = snapshot("2026-06-30", 125, 500)
    analysis = analyze_sector_exposure([current, previous])
    change = next(item for item in analysis["position_changes"] if item["ticker"] == "AAPL")
    sector = next(item for item in analysis["sector_changes"] if item["sector"] == "Information Technology")
    assert change["activity"] == "INCREASED"
    assert change["share_change"] == 25
    assert sector["position_activity"]["INCREASED"] == 1
    assert "reported-value changes" in analysis["comparison"]["weight_change_note"]


def test_verified_corporate_action_adjusts_comparable_share_count():
    previous = snapshot("2026-03-31", 100)
    current = snapshot("2026-06-30", 200)
    action = CorporateAction(
        "037833100",
        "2026-05-01",
        2,
        "https://www.sec.gov/fixture/corporate-action",
    )
    analysis = analyze_sector_exposure([current, previous], corporate_actions=[action])
    change = analysis["position_changes"]
    assert change == []


def test_period_and_sector_filters_are_deterministic():
    analysis = analyze_sector_exposure(
        [snapshot("2026-06-30", 120), snapshot("2026-03-31", 100)],
        period="2026-03-31",
        sector="Information Technology",
    )
    assert analysis["reporting_period"] == "2026-03-31"
    assert [row["sector"] for row in analysis["allocation"]] == [
        "Information Technology"
    ]
