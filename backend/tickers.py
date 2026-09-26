"""Resolve ambiguous common-stock classes only from explicit SEC filing cover rows."""

import re
import warnings
from pathlib import Path

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

from src.portfolios import INSTITUTIONS, PortfolioSnapshot


def cover_class_tickers(html: str) -> dict[str, str]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", XMLParsedAsHTMLWarning)
        soup = BeautifulSoup(html, "lxml")
    candidates: dict[str, set[str]] = {}
    for symbol in soup.find_all(attrs={"name": "dei:TradingSymbol"}):
        row = symbol.find_parent("tr")
        if row is None:
            continue
        match = re.match(
            r"Class\s+([A-Z])\s+(?:Common|Capital)\s+Stock\b",
            row.get_text(" ", strip=True),
            re.IGNORECASE,
        )
        ticker = symbol.get_text(strip=True)
        if match and re.fullmatch(r"[A-Z0-9.-]{1,12}", ticker):
            candidates.setdefault(match[1].upper(), set()).add(ticker)
    return {
        key: next(iter(values))
        for key, values in candidates.items()
        if len(values) == 1
    }


def enrich_cached_classes(store, ticker: str):
    company = store.snapshots("company", ticker)
    if not company or not company[0].get("filings"):
        return
    filing = company[0]["filings"][0]
    path = (
        Path("data/raw")
        / ticker
        / filing["accession_number"].replace("-", "")
        / "filing.html"
    )
    if not path.exists():
        return
    mapping = cover_class_tickers(path.read_text(encoding="utf-8", errors="replace"))
    issuer = re.sub(r"[^A-Z0-9]", "", filing.get("company", "").upper())
    if not issuer or not mapping:
        return
    for institution in INSTITUTIONS:
        for data in store.snapshots("portfolio", institution.id):
            snapshot = PortfolioSnapshot.from_dict(data)
            changed = False
            for holding in snapshot.holdings:
                exact_name = re.sub(r"[^A-Z0-9]", "", holding.issuer.upper()) == issuer
                share_class = re.search(
                    r"\b(?:CL|CLASS)\s+([A-Z])\b", holding.security_class.upper()
                )
                if (
                    not holding.ticker
                    and exact_name
                    and share_class
                    and share_class[1] in mapping
                ):
                    holding.ticker = mapping[share_class[1]]
                    holding.ticker_source = filing["source_url"]
                    changed = True
            if changed:
                store.save_snapshot(
                    "portfolio",
                    institution.id,
                    snapshot.reporting_period,
                    snapshot.to_dict(),
                )
