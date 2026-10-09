from src.portfolio_overlap import analyze_overlap, security_identity
from src.portfolios import Holding, PortfolioSnapshot


def holding(cusip, ticker, weight, shares=100, security_class="COM", put_call=""):
    return Holding(
        ticker + " INC",
        security_class,
        cusip,
        shares,
        weight * 1_000_000,
        put_call=put_call,
        ticker=ticker,
        weight=weight,
    )


def snapshot(manager, period, holdings, source_type="SEC Form 13F"):
    return PortfolioSnapshot(
        manager,
        period,
        "2026-08-14",
        f"https://www.sec.gov/{manager}/{period}",
        f"{manager}-{period}",
        source_type=source_type,
        holdings=holdings,
    )


def test_security_identity_is_class_and_option_aware():
    common = holding("037833100", "AAPL", 0.2)
    assert security_identity(common) == "037833100|COM||SH"
    assert security_identity(
        holding("037833100", "AAPL", 0.2, security_class="CL A")
    ) != security_identity(common)
    assert security_identity(
        holding("037833100", "AAPL", 0.2, put_call="PUT")
    ) != security_identity(common)
    assert security_identity(holding("", "AAPL", 0.2)) is None


def test_overlap_math_uses_verified_identifiers_and_all_selected_managers():
    data = {
        "berkshire": [
            snapshot(
                "berkshire",
                "2026-06-30",
                [
                    holding("A", "AAPL", 0.4),
                    holding("B", "KO", 0.2),
                ],
            )
        ],
        "pershing": [
            snapshot(
                "pershing",
                "2026-06-30",
                [
                    holding("A", "AAPL", 0.3),
                    holding("C", "GOOG", 0.25),
                ],
            )
        ],
        "coatue": [
            snapshot(
                "coatue",
                "2026-06-30",
                [
                    holding("A", "AAPL", 0.1),
                    holding("D", "NVDA", 0.5),
                ],
            )
        ],
    }
    result = analyze_overlap(data)
    assert result["summary"] == {
        "common_count": 1,
        "shared_count": 1,
        "union_count": 4,
        "jaccard": 0.25,
        "weight_overlap": 0.1,
    }
    assert [row["unique_count"] for row in result["institutions"]] == [1, 1, 1]
    assert result["securities"][0]["owner_count"] == 3


def test_ticker_match_without_cusip_does_not_create_overlap():
    data = {
        "berkshire": [snapshot("berkshire", "2026-06-30", [holding("", "AAPL", 0.4)])],
        "pershing": [snapshot("pershing", "2026-06-30", [holding("", "AAPL", 0.3)])],
    }
    result = analyze_overlap(data)
    assert result["summary"]["union_count"] == 0
    assert result["summary"]["shared_count"] == 0
    assert result["institutions"][0]["unmapped_count"] == 1
    assert any("lacked a usable" in note for note in result["coverage_notes"])


def test_period_alignment_uses_latest_snapshot_at_or_before_selected_date():
    data = {
        "berkshire": [
            snapshot("berkshire", "2026-06-30", [holding("A", "AAPL", 0.4, 120)]),
            snapshot("berkshire", "2026-03-31", [holding("A", "AAPL", 0.3, 100)]),
        ],
        "pershing": [
            snapshot("pershing", "2026-03-31", [holding("A", "AAPL", 0.2)]),
        ],
    }
    result = analyze_overlap(data, "2026-06-30")
    assert [row["reporting_period"] for row in result["institutions"]] == [
        "2026-06-30",
        "2026-03-31",
    ]
    assert result["changes"][0]["activity"] == "INCREASED"
    assert result["changes"][0]["pct_change"] == 0.2
    assert any(
        "different available reporting dates" in note
        for note in result["coverage_notes"]
    )


def test_empty_stale_and_mixed_disclosure_datasets_are_explicit():
    data = {
        "berkshire": [],
        "ark": [
            snapshot(
                "ark",
                "2025-01-02",
                [holding("A", "AAPL", 1)],
                "Official ARKK daily fund holdings",
            )
        ],
    }
    result = analyze_overlap(data)
    assert result["institutions"][0]["available"] is False
    assert result["institutions"][1]["freshness"].startswith("Stale")
    assert any(
        "No eligible stored snapshot" in note for note in result["coverage_notes"]
    )


def test_selection_limits_are_enforced():
    try:
        analyze_overlap({"berkshire": []})
    except ValueError as exc:
        assert "2 and 5" in str(exc)
    else:
        raise AssertionError("Expected selection validation")


def test_missing_snapshot_is_not_reported_as_zero_similarity():
    result = analyze_overlap({
        "berkshire": [],
        "pershing": [snapshot("pershing", "2026-06-30", [holding("A", "AAPL", 0.4)])],
    })
    assert result["summary"]["jaccard"] is None
    assert result["summary"]["weight_overlap"] is None
    assert result["pairwise"][0]["jaccard"] is None
    assert result["pairwise"][0]["weight_overlap"] is None


def test_unsorted_snapshots_select_latest_and_compare_previous():
    old = snapshot("berkshire", "2026-03-31", [holding("A", "AAPL", 0.3, 100)])
    new = snapshot("berkshire", "2026-06-30", [holding("A", "AAPL", 0.4, 120)])
    result = analyze_overlap({
        "berkshire": [old, new],
        "pershing": [snapshot("pershing", "2026-06-30", [holding("A", "AAPL", 0.2)])],
    })
    assert result["institutions"][0]["reporting_period"] == "2026-06-30"
    assert result["changes"][0]["activity"] == "INCREASED"


def test_no_mapped_securities_has_undefined_similarity():
    result = analyze_overlap({
        "berkshire": [snapshot("berkshire", "2026-06-30", [])],
        "pershing": [snapshot("pershing", "2026-06-30", [])],
    })
    assert result["summary"]["jaccard"] is None
    assert result["summary"]["weight_overlap"] is None
