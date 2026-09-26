"""Bounded Ask dispatch across locally loaded company and disclosure evidence."""

import re

from src.llm import generate_answer
from src.portfolios import BY_ID, PortfolioSnapshot, compare_portfolios
from src.router import QueryIntent, route_query
from src.structured_query import answer_structured_query
from src.thesis_research import (
    company_changes,
    company_rows,
    comparable_filings,
    filing_chunks,
    filing_language_changes,
)


def answer_question(question, ticker, store, config, ollama_model, retrieve):
    query = question.lower()
    # Explicit ticker symbols override the page's default company context.
    symbols = re.findall(r"\b[A-Z]{1,5}\b", question)
    known = set(store.watchlist()) | {ticker}
    requested_tickers = [symbol for symbol in symbols if symbol in known or symbol in {"AAPL", "GOOG", "GOOGL", "MSFT", "NVDA"}]
    target = requested_tickers[-1] if requested_tickers else ticker
    if "thesis" in query or "theses" in query:
        theses = store.theses(target)
        selected = [item for item in theses if item["status"] == "WEAKENED"] if "weaken" in query else theses
        return ("\n\n".join(f"{item['text']} — {item['status']}. {item.get('explanation', '')}" for item in selected)
                or "No matching evaluated thesis points in the local workspace.",
                [evidence for item in selected for evidence in item.get("current_evidence", [])])
    if "trump" in query or "oge" in query:
        documents = store.snapshots("oge", "donald_trump")
        evidence = [{"text": row["text"], "source_url": row["source_url"], "period": document.get("filing_date") or "Unknown filing date"}
                    for document in documents for row in document["excerpts"][:3]]
        if not evidence:
            return "Load an official OGE disclosure in Public Portfolios first.", []
        result = generate_answer(question + " Describe disclosure ranges neutrally; do not infer exact weights or motives.", evidence, ollama_model, config.ollama_base_url)
        return result.answer if result.available else "Ollama unavailable. Review original OGE excerpts below.", evidence
    requested = [key for key, entity in BY_ID.items() if key in query or entity.name.lower() in query]
    if requested or any(word in query for word in ("institution", "portfolio", "13f", "disclosed", "exposure")):
        evidence = []
        for entity_id in requested or [key for key in store.follows() if key in BY_ID]:
            snapshots = sorted((PortfolioSnapshot.from_dict(row) for row in store.snapshots("portfolio", entity_id)),
                               key=lambda row: row.reporting_period, reverse=True)
            if not snapshots:
                continue
            current = snapshots[0]
            if "change" in query:
                previous = next((row for row in snapshots[1:] if row.reporting_period < current.reporting_period), None)
                if previous:
                    for row in compare_portfolios(previous, current):
                        if row["activity"] != "UNCHANGED":
                            evidence.append({"text": f"{BY_ID[entity_id].name}: {row['activity']} {row['issuer']}; shares {row['shares_before']:,.0f} → {row['shares_after']:,.0f}.",
                                             "period": current.reporting_period, "filing_date": current.filing_date, "source_url": current.source_url})
            else:
                # Only verified ticker matches count; no absence claims without a complete mapping.
                for row in [holding for holding in current.holdings if holding.ticker == target]:
                    evidence.append({"text": f"{BY_ID[entity_id].name} reported {row.shares:,.0f} {row.share_type} of {row.issuer} {row.put_call}; reported value ${row.reported_value:,.0f}, {row.weight:.2%} of disclosed table.",
                                     "period": current.reporting_period, "filing_date": current.filing_date, "source_url": current.source_url})
        return ("\n\n".join(f"{row['text']} Reporting period {row['period']}; filed {row['filing_date']}." for row in evidence)
                or "No verified matching data is loaded. Load the official portfolio and verify the CUSIP-to-ticker mapping first.", evidence)
    saved = store.snapshots("company", target)
    if not saved:
        return "Load company evidence on Research first.", []
    company = saved[0]
    if "what changed" in query or "change" in query:
        changes = company_changes(company)
        if "filing" in query or "risk" in query:
            compared = comparable_filings(company.get("filings", []))
            if len(compared) >= 2:
                try:
                    current = filing_chunks(compared[0], store, config.chunk_size, config.chunk_overlap)
                    previous = filing_chunks(compared[1], store, config.chunk_size, config.chunk_overlap)
                    changes += filing_language_changes(previous, current)
                except Exception:  # noqa: BLE001 - report only established fact changes.
                    changes.append({"text": "Comparable filing text is unavailable; narrative changes could not be verified.", "current": {}})
        return "\n\n".join(row["text"] for row in changes) or "No comparable changes available.", [row["current"] for row in changes if row["current"]]
    structured = answer_structured_query(question, company_rows(company)) if route_query(question) in {QueryIntent.METRIC_LOOKUP, QueryIntent.CALCULATION} else None
    if structured:
        return structured, [{"text": structured, "source_url": company_rows(company)[-1].source_url}]
    filings = company.get("filings", [])
    if not filings:
        return "No company filing evidence loaded.", []
    try:
        chunks = filing_chunks(filings[0], store, config.chunk_size, config.chunk_overlap)
        evidence = retrieve(question, filings[0], chunks)
    except Exception as exc:  # noqa: BLE001 - independent financial workspace remains usable.
        return f"Filing retrieval unavailable: {exc}", []
    result = generate_answer(question + " Do not provide BUY/SELL/HOLD recommendations.", evidence, ollama_model, config.ollama_base_url)
    return result.answer if result.available else "Ollama unavailable. Retrieved dated evidence is shown below.", evidence
