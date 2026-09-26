"""Evidence-linked thesis evaluation: numeric rules in Python, semantics optional."""

import dataclasses
import math
import operator
from enum import Enum
from typing import Protocol

from src.decision import Decision, DecisionSource, DecisionUnavailable
from src.local_store import utc_now
from src.models import AnnualFinancials


class ThesisImpact(str, Enum):
    STRENGTHENS = "STRENGTHENS"
    NEUTRAL = "NEUTRAL"
    WEAKENS = "WEAKENS"
    UNCERTAIN = "UNCERTAIN"


class ThesisJudge(Protocol):
    def thesis_impact(self, thesis: str, previous: list[dict], current: list[dict]) -> Decision[ThesisImpact]: ...


RULE_METRICS = {
    "gross_margin": "Gross margin", "operating_margin": "Operating margin",
    "revenue_growth": "Revenue growth", "free_cash_flow": "Free cash flow",
    "revenue": "Revenue", "debt": "Debt", "capital_expenditure": "Capital expenditure",
}
OPERATORS = {">": operator.gt, ">=": operator.ge, "<": operator.lt, "<=": operator.le}


def threshold_satisfied(value: float | None, rule: dict) -> bool | None:
    if rule.get("metric") not in RULE_METRICS or rule.get("operator") not in OPERATORS:
        raise ValueError("Unsupported quantitative thesis rule.")
    threshold = float(rule["threshold"])
    if not math.isfinite(threshold):
        raise ValueError("Threshold must be finite.")
    if value is None or not math.isfinite(value):
        return None
    return OPERATORS[rule["operator"]](value, threshold)


def fact_evidence(row: AnnualFinancials, metric: str) -> dict:
    value = getattr(row, metric)
    display = f"{value:.2%}" if value is not None and ("margin" in metric or metric.endswith("_growth")) else f"{value:,.2f}" if value is not None else "unavailable"
    return {"text": f"{RULE_METRICS.get(metric, metric)} in FY{row.fiscal_year}: {display}",
            "source_url": row.source_url, "period": f"FY{row.fiscal_year}",
            "source_type": "SEC Company Facts", "metric": metric, "value": value}


def evaluate_thesis(thesis: dict, rows: list[AnnualFinancials], current: list[dict],
                    previous: list[dict] | None = None, judge: ThesisJudge | None = None,
                    confidence_threshold: float = 0.7) -> dict:
    result = {"evaluated_at": utc_now(), "status": "UNCERTAIN", "confidence": None,
              "source": "deterministic", "supporting_evidence": [], "contradicting_evidence": [],
              "current_evidence": current, "previous_evidence": previous or [],
              "explanation": "Available evidence does not establish the relationship to this thesis."}
    rule = thesis.get("rule")
    if rule:
        metric = rule["metric"]
        ordered = sorted(rows, key=lambda row: row.fiscal_year)
        if not ordered:
            result["explanation"] = "No comparable structured financial evidence is available."
            return result
        latest = ordered[-1]
        satisfied = threshold_satisfied(getattr(latest, metric), rule)
        result["threshold_satisfied"] = satisfied
        result["period"] = f"FY{latest.fiscal_year}"
        evidence = fact_evidence(latest, metric)
        result["current_evidence"] = [evidence]
        # Only adjacent fiscal years count as the previous comparable annual period.
        prior = next((row for row in ordered if row.fiscal_year == latest.fiscal_year - 1), None)
        before = threshold_satisfied(getattr(prior, metric), rule) if prior else None
        result["previous_evidence"] = [fact_evidence(prior, metric)] if prior else []
        if satisfied is None:
            result["explanation"] = "The required SEC metric is missing; the threshold cannot be evaluated."
        else:
            result["status"] = "STRENGTHENED" if satisfied and before is False else "STABLE" if satisfied else "WEAKENED"
            result["supporting_evidence" if satisfied else "contradicting_evidence"] = [evidence]
            result["confidence"] = 1.0
            result["explanation"] = f"Python evaluated {metric} {rule['operator']} {rule['threshold']}; threshold satisfied = {satisfied}."
        return result
    if not current:
        result["explanation"] = "No filing evidence was retrieved. Index the relevant filing and evaluate again."
        return result
    if judge:
        try:
            decision = judge.thesis_impact(thesis["text"], previous or [], current)
            result["confidence"] = decision.confidence
            result["probabilities"] = decision.probabilities
            result["source"] = decision.source.value
            if not math.isfinite(decision.confidence) or not 0 <= decision.confidence <= 1:
                raise DecisionUnavailable("Invalid thesis decision confidence.")
            if decision.confidence >= confidence_threshold:
                result["status"] = {
                    ThesisImpact.STRENGTHENS: "STRENGTHENED", ThesisImpact.NEUTRAL: "STABLE",
                    ThesisImpact.WEAKENS: "WEAKENED", ThesisImpact.UNCERTAIN: "UNCERTAIN",
                }[decision.value]
                if decision.value in {ThesisImpact.STRENGTHENS, ThesisImpact.WEAKENS}:
                    key = "supporting_evidence" if decision.value is ThesisImpact.STRENGTHENS else "contradicting_evidence"
                    result[key] = current
                result["explanation"] = "Typed evidence-to-thesis judgment; inspect the dated excerpts below."
            else:
                result["explanation"] = "Thesis judgment confidence is below the configured threshold. Review evidence."
        except (DecisionUnavailable, ValueError, TypeError):
            result["source"] = DecisionSource.DETERMINISTIC.value
            result["explanation"] = "Optional thesis judge unavailable. Evidence is retained for manual investigation."
    return result


def financial_changes(rows: list[AnnualFinancials]) -> list[dict]:
    ordered = sorted(rows, key=lambda row: row.fiscal_year)
    if len(ordered) < 2 or ordered[-1].fiscal_year - ordered[-2].fiscal_year != 1:
        return []
    prior, current = ordered[-2:]
    changes = []
    for metric in ("revenue_growth", "gross_margin", "operating_margin", "free_cash_flow", "debt", "capital_expenditure"):
        before, after = getattr(prior, metric), getattr(current, metric)
        if before is None or after is None:
            continue
        percentage = "margin" in metric or metric.endswith("_growth")
        delta = after - before
        meaningful = abs(delta) >= 0.005 if percentage else before != 0 and abs(delta / before) >= 0.05
        if not meaningful:
            continue
        movement = f"{delta * 100:+.2f} pp" if percentage else f"{delta / abs(before):+.1%}"
        favorable = delta > 0 if metric not in {"debt", "capital_expenditure"} else delta < 0
        changes.append({"category": "Monitor" if metric == "capital_expenditure" else "Improved" if favorable else "Worsened",
                        "text": f"{RULE_METRICS[metric]} changed {movement} from FY{prior.fiscal_year} to FY{current.fiscal_year}.",
                        "previous": fact_evidence(prior, metric), "current": fact_evidence(current, metric)})
    return changes


def health_summary(theses: list[dict]) -> str:
    labels = {"STRENGTHENED": "strengthened", "STABLE": "stable", "WEAKENED": "weakening",
              "UNCERTAIN": "uncertain", "NOT_EVALUATED": "not evaluated"}
    counts = {key: sum(item["status"] == key for item in theses) for key in labels}
    return " · ".join(f"{count} {labels[key]}" for key, count in counts.items() if count) or "No thesis points yet"


def serialize_financials(rows: list[AnnualFinancials]) -> list[dict]:
    return [dataclasses.asdict(row) for row in rows]
