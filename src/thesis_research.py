"""Company loading and filing evidence orchestration shared by the four pages."""

from dataclasses import asdict

from src.bm25 import BM25Retriever
from src.chunker import chunk_filing
from src.companyfacts import fetch_company_facts
from src.local_store import utc_now
from src.market import YahooFinanceProvider
from src.models import AnnualFinancials, MarketSnapshot
from src.parser import parse_filing
from src.sec import download_filing, list_company_filings, normalize_ticker
from src.thesis import financial_changes, serialize_financials


def load_company(ticker: str, store, refresh: bool = False, include_market: bool = True) -> tuple[dict | None, list[str]]:
    ticker = normalize_ticker(ticker)
    cached = store.snapshots("company", ticker)
    existing = cached[0] if cached else {}
    errors = []
    filings = existing.get("filings", [])
    try:
        filings = list_company_filings(ticker)
    except Exception as exc:  # noqa: BLE001 - retain usable cached SEC sources.
        errors.append(f"SEC filing list unavailable: {exc}")
    financials = existing.get("financials", [])
    if filings:
        try:
            financials = serialize_financials(fetch_company_facts(int(filings[0]["cik"]), ticker, refresh=refresh))
        except Exception as exc:  # noqa: BLE001 - partial provider failures are independent.
            errors.append(f"SEC facts unavailable: {exc}")
    market = existing.get("market", asdict(MarketSnapshot(ticker)))
    market_as_of = existing.get("market_as_of", "")
    try:
        observed_market = asdict(YahooFinanceProvider().snapshot(ticker)) if include_market else market
        if observed_market.get("error"):
            errors.append(observed_market["error"])
        else:
            market = observed_market
            market_as_of = utc_now() if include_market else market_as_of
    except Exception as exc:  # noqa: BLE001 - market data never gates SEC research.
        errors.append(f"Market data unavailable: {exc}")
    if not filings and not financials:
        return None, errors
    data = {"ticker": ticker, "filings": filings, "financials": financials, "market": market,
            "loaded_at": utc_now(), "market_as_of": market_as_of, "provider_warnings": errors}
    store.save_snapshot("company", ticker, "current", data)
    for filing in filings:
        store.save_snapshot("filing", ticker, filing["accession_number"], filing)
    return data, errors


def company_rows(company: dict) -> list[AnnualFinancials]:
    return [AnnualFinancials(**row) for row in company.get("financials", [])]


def filing_chunks(filing: dict, store, chunk_size: int = 1600, chunk_overlap: int = 200) -> list[dict]:
    cache_key = f"{filing['accession_number']}:{chunk_size}:{chunk_overlap}"
    cached = store.snapshots("filing_chunks", filing["ticker"])
    match = next((row for row in cached if row["cache_key"] == cache_key), None)
    if match:
        return match["chunks"]
    text = parse_filing(download_filing(filing).read_text(encoding="utf-8", errors="replace"))
    chunks = chunk_filing(text, filing["ticker"], filing["year"], filing["form"], chunk_size,
                          chunk_overlap, filing.get("company", ""), filing.get("filing_date", ""),
                          filing["source_url"])
    for chunk in chunks:
        chunk["period"] = filing.get("report_date", str(filing["year"]))
        chunk["accession_number"] = filing["accession_number"]
    store.save_snapshot("filing_chunks", filing["ticker"], cache_key,
                        {"cache_key": cache_key, "filing": filing, "chunks": chunks})
    return chunks


def lexical_evidence(query: str, chunks: list[dict], top_k: int = 5) -> list[dict]:
    return BM25Retriever(chunks).search(query, top_k) if chunks else []


def comparable_filings(filings: list[dict]) -> list[dict]:
    """Latest filing plus same-form, approximately same fiscal period one year earlier."""
    from datetime import date

    if not filings:
        return []
    latest = filings[0]
    try:
        current_date = date.fromisoformat(latest["report_date"])
    except (KeyError, ValueError):
        return [latest]
    candidates = []
    for filing in filings[1:]:
        if filing["form"] != latest["form"]:
            continue
        try:
            difference = (current_date - date.fromisoformat(filing["report_date"])).days
            if 335 <= difference <= 395:
                candidates.append((abs(difference - 365), filing))
        except (KeyError, ValueError):
            continue
    return [latest, min(candidates, key=lambda row: row[0])[1]] if candidates else [latest]


def company_changes(company: dict) -> list[dict]:
    return financial_changes(company_rows(company))


def filing_language_changes(previous: list[dict], current: list[dict]) -> list[dict]:
    """Report observed theme mentions, never infer that the economic risk is new."""
    if not previous or not current:
        return []
    themes = {"tariff": "tariff", "cybersecurity": "cybersecurity", "export restrictions": "export restrictions"}
    changes = []
    for label, phrase in themes.items():
        before = [row for row in previous if phrase in row["text"].lower()]
        after = [row for row in current if phrase in row["text"].lower()]
        if bool(before) != bool(after):
            evidence = after[0] if after else before[0]
            changes.append({"category": "New" if after else "Monitor",
                            "text": f"The phrase '{label}' {'appeared' if after else 'was not found'} in the current parsed filing compared with the prior filing. This is a text observation, not proof of a new or resolved risk.",
                            "current": evidence, "previous": before[0] if before else {}})
    return changes
