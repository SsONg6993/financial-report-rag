from dataclasses import asdict
from datetime import date

import pytest

from src.decision import (
    Decision,
    DecisionSource,
    DecisionUnavailable,
    JevDecisionProvider,
)
from src.local_store import LocalStore
from src.models import AnnualFinancials
from src.portfolios import (
    Holding,
    PortfolioSnapshot,
    compare_portfolios,
    disclosure_freshness,
    parse_13f,
    parse_ark_csv,
)
from src.public_disclosures import parse_disclosure_rows
from src.thesis import (
    ThesisImpact,
    evaluate_thesis,
    financial_changes,
    threshold_satisfied,
)


def test_watchlist_follow_and_thesis_history_survive_restart(tmp_path):
    path = tmp_path / "research.sqlite3"
    store = LocalStore(path)
    store.watch("aapl")
    store.follow("berkshire")
    thesis = store.save_thesis("AAPL", "Gross margin above 45%", {"metric": "gross_margin", "operator": ">", "threshold": 0.45})
    result = evaluate_thesis(thesis, [AnnualFinancials(2025, gross_margin=0.469, source_url="https://data.sec.gov/facts")], [])
    store.record_evaluation(thesis, result)
    restarted = LocalStore(path)
    assert restarted.watchlist() == ["AAPL"]
    assert restarted.follows() == ["berkshire"]
    assert restarted.theses("AAPL")[0]["status"] == "STABLE"
    assert restarted.history(thesis["id"])[0]["supporting_evidence"][0]["value"] == 0.469
    edited = restarted.save_thesis("AAPL", "New claim", thesis_id=thesis["id"])
    assert edited["status"] == "NOT_EVALUATED"
    assert len(restarted.history(thesis["id"])) == 1


def test_thresholds_are_python_only_and_use_comparable_periods():
    class ForbiddenJudge:
        def thesis_impact(self, *args):
            pytest.fail("Numeric rule must not call Jev.")

    thesis = {"text": "Margin remains above 45%", "rule": {"metric": "gross_margin", "operator": ">", "threshold": 0.45}}
    rows = [AnnualFinancials(2024, gross_margin=0.44), AnnualFinancials(2025, gross_margin=0.469)]
    result = evaluate_thesis(thesis, rows, [], judge=ForbiddenJudge())
    assert result["status"] == "STRENGTHENED"
    assert result["threshold_satisfied"] is True
    rows[-1].gross_margin = 0.42
    assert evaluate_thesis(thesis, rows, [])["status"] == "WEAKENED"
    rows[-1].gross_margin = None
    assert evaluate_thesis(thesis, rows, [])["status"] == "UNCERTAIN"
    assert threshold_satisfied(0.45, thesis["rule"]) is False
    with pytest.raises(ValueError):
        threshold_satisfied(0.5, {"metric": "gross_margin", "operator": ">", "threshold": float("nan")})


@pytest.mark.parametrize("confidence,expected", [(0.9, "WEAKENED"), (0.4, "UNCERTAIN")])
def test_narrative_thesis_confidence_gate_and_evidence(confidence, expected):
    class Judge:
        def thesis_impact(self, text, previous, current):
            assert previous[0]["period"] == "2024"
            return Decision(ThesisImpact.WEAKENS, confidence, DecisionSource.JEV)

    evidence = [{"text": "Growth slowed", "period": "2025", "source_url": "https://www.sec.gov/source"}]
    result = evaluate_thesis({"text": "Growth continues"}, [], evidence, [{"period": "2024"}], Judge())
    assert result["status"] == expected
    assert result["current_evidence"] == evidence
    if expected == "WEAKENED":
        assert result["contradicting_evidence"] == evidence


def test_jev_unavailable_preserves_uncertain_evidence():
    class Offline:
        def thesis_impact(self, *args):
            raise DecisionUnavailable("offline")

    evidence = [{"text": "Services grew", "period": "2025"}]
    result = evaluate_thesis({"text": "Services drives growth"}, [], evidence, judge=Offline())
    assert result["status"] == "UNCERTAIN"
    assert result["current_evidence"] == evidence
    assert result["source"] == "deterministic"
    assert evaluate_thesis({"text": "Services drives growth"}, [], evidence)["status"] == "UNCERTAIN"


def test_jev_thesis_choice_is_bounded_and_retains_probabilities():
    class Response:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"answers": {"impact": {"choice": "STRENGTHENS", "confidence": 0.85,
                                          "probabilities": {"STRENGTHENS": 0.9, "UNCERTAIN": 0.1}}}}

    class Session:
        def post(self, *args, **kwargs):
            payload = kwargs["json"]
            assert payload["questions"]["impact"]["type"] == "choice"
            assert set(payload["questions"]["impact"]["criteria"]) == {"STRENGTHENS", "NEUTRAL", "WEAKENS", "UNCERTAIN"}
            assert set(payload["state"]) == {"user_thesis", "previous_evidence", "current_evidence"}
            return Response()

    decision = JevDecisionProvider("test-key", session=Session()).thesis_impact("Growth persists", [], [{"text": "Growth rose"}])
    assert decision.value is ThesisImpact.STRENGTHENS
    assert decision.probabilities["STRENGTHENS"] == 0.9


def test_financial_changes_do_not_compare_nonadjacent_years():
    assert financial_changes([AnnualFinancials(2022, gross_margin=0.4), AnnualFinancials(2025, gross_margin=0.5)]) == []
    changes = financial_changes([AnnualFinancials(2024, gross_margin=0.4), AnnualFinancials(2025, gross_margin=0.42)])
    assert changes[0]["text"].startswith("Gross margin changed +2.00 pp")
    assert changes[0]["previous"]["period"] == "FY2024"


def test_comparable_filing_selection_does_not_mix_quarters_and_annuals():
    from src.thesis_research import comparable_filings

    filings = [{"form": "10-Q", "report_date": "2026-06-27", "id": "current"},
               {"form": "10-Q", "report_date": "2026-03-28", "id": "other-quarter"},
               {"form": "10-K", "report_date": "2025-09-27", "id": "annual"},
               {"form": "10-Q", "report_date": "2025-06-28", "id": "prior-comparable"}]
    assert [row["id"] for row in comparable_filings(filings)] == ["current", "prior-comparable"]


XML = """<informationTable xmlns="http://www.sec.gov/edgar/document/thirteenf/informationtable">
<infoTable><nameOfIssuer>APPLE INC</nameOfIssuer><titleOfClass>COM</titleOfClass><cusip>037833100</cusip><value>200</value><shrsOrPrnAmt><sshPrnamt>10</sshPrnamt><sshPrnamtType>SH</sshPrnamtType></shrsOrPrnAmt></infoTable>
<infoTable><nameOfIssuer>APPLE INC</nameOfIssuer><titleOfClass>COM</titleOfClass><cusip>037833100</cusip><value>100</value><shrsOrPrnAmt><sshPrnamt>5</sshPrnamt><sshPrnamtType>SH</sshPrnamtType></shrsOrPrnAmt></infoTable>
<infoTable><nameOfIssuer>APPLE INC</nameOfIssuer><titleOfClass>COM</titleOfClass><cusip>037833100</cusip><value>300</value><putCall>PUT</putCall><shrsOrPrnAmt><sshPrnamt>20</sshPrnamt><sshPrnamtType>SH</sshPrnamtType></shrsOrPrnAmt></infoTable>
</informationTable>"""


def test_13f_namespace_units_duplicates_and_options():
    rows = parse_13f(XML, "2026-08-14")
    assert len(rows) == 2
    assert sum(row.weight for row in rows) == 1
    stock = next(row for row in rows if not row.put_call)
    assert stock.shares == 15 and stock.reported_value == 300
    assert sum(row.reported_value for row in parse_13f(XML, "2022-11-14")) == 600_000


def test_portfolio_change_classes_use_shares_not_prices():
    def h(cusip, shares, value=100):
        return Holding(cusip, "COM", cusip, shares, value)

    before = PortfolioSnapshot("fund", "2026-03-31", "2026-05-15", "source", "1",
                               holdings=[h("increase", 10), h("reduce", 20), h("exit", 5), h("same", 8)])
    after = PortfolioSnapshot("fund", "2026-06-30", "2026-08-14", "source", "2",
                              holdings=[h("increase", 12), h("reduce", 10), h("new", 5), h("same", 8, 999)])
    result = {row["cusip"]: row for row in compare_portfolios(before, after)}
    assert {key: row["activity"] for key, row in result.items()} == {
        "increase": "INCREASED", "reduce": "REDUCED", "exit": "EXITED", "new": "NEW", "same": "UNCHANGED"}
    assert result["increase"]["share_change_pct"] == 0.2
    assert result["new"]["share_change_pct"] is None
    assert all(row["reporting_period"] == "2026-06-30" for row in result.values())
    with pytest.raises(ValueError):
        compare_portfolios(after, before)


def test_stale_disclosures_explicitly_labeled():
    assert "Stale" in disclosure_freshness("2025-09-30", date(2026, 9, 26))
    assert "Historical" in disclosure_freshness("2026-06-30", date(2026, 9, 26))
    assert "unavailable" in disclosure_freshness("")


def test_public_official_ranges_remain_separate_and_exact_values_absent():
    rows = parse_disclosure_rows([{"asset_name": "Example bond", "asset_type": "Bond",
                                  "amount_range": "$100,001 - $250,000", "transaction_type": "Purchase"}],
                                "Donald Trump", "OGE 278-T", "2026-05-08", "https://www.oge.gov/report.pdf")
    assert rows[0].amount_range == "$100,001 - $250,000"
    assert "weight" not in asdict(rows[0]) and "reported_value" not in asdict(rows[0])
    with pytest.raises(ValueError):
        parse_disclosure_rows([], "Person", "Annual", "2026-05-08", "https://example.com/report.pdf")


def test_ark_is_fund_holdings_not_13f():
    snapshot = parse_ark_csv("date,fund,company,ticker,cusip,shares,market value ($),weight (%)\n09/25/2026,ARKK,Example,EX,123,10,100,100\n", "https://assets.ark-funds.com/holdings.csv")
    assert snapshot.source_type == "Official ARKK daily fund holdings"
    assert snapshot.holdings[0].ticker == "EX"
    assert snapshot.holdings[0].weight == 1


def test_failed_company_providers_retain_cached_sources(tmp_path, monkeypatch):
    from src.thesis_research import load_company

    store = LocalStore(tmp_path / "local.sqlite3")
    store.save_snapshot("company", "AAPL", "current", {"ticker": "AAPL", "filings": [],
                        "financials": [asdict(AnnualFinancials(2025, revenue=100))], "market": {}})

    def fail(*args, **kwargs):
        raise RuntimeError("offline")

    monkeypatch.setattr("src.thesis_research.list_company_filings", fail)
    monkeypatch.setattr("src.thesis_research.YahooFinanceProvider.snapshot", fail)
    company, errors = load_company("AAPL", store)
    assert company["financials"][0]["revenue"] == 100
    assert errors
