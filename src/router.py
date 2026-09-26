"""Small deterministic query router; ambiguous questions fall back to research."""

import re
from enum import Enum


class QueryIntent(str, Enum):
    METRIC_LOOKUP = "METRIC_LOOKUP"
    CALCULATION = "CALCULATION"
    FILING_RAG = "FILING_RAG"
    VALUATION = "VALUATION"
    PEER_COMPARISON = "PEER_COMPARISON"
    RISK_ANALYSIS = "RISK_ANALYSIS"
    GENERAL_RESEARCH = "GENERAL_RESEARCH"


def route_query(query: str) -> QueryIntent:
    normalized = query.lower().strip()
    if re.search(r"\b(compare|versus|vs\.?|peer)\b", normalized):
        return QueryIntent.PEER_COMPARISON
    if re.search(r"\b(dcf|intrinsic value|valuation|wacc|terminal value)\b", normalized):
        return QueryIntent.VALUATION
    if re.search(r"\b(classify|analyze|analyse|summarize|review)\b.*\b(risk|risks)\b", normalized):
        return QueryIntent.RISK_ANALYSIS
    if re.search(r"\b(cagr|growth rate|calculate|margin percentage|ratio)\b", normalized):
        return QueryIntent.CALCULATION
    if re.search(r"\b(why|driver|drove|management|risk|priority|outlook|commentary)\b", normalized):
        return QueryIntent.FILING_RAG
    metric = r"revenue|net sales|net income|eps|cash flow|assets|liabilities|equity"
    if re.search(metric, normalized) and re.search(r"\b(19|20)\d{2}\b", normalized):
        return QueryIntent.METRIC_LOOKUP
    return QueryIntent.GENERAL_RESEARCH
