"""Small SEC EDGAR client: ticker -> CIK -> annual filing -> cached HTML."""

import os
import re
from pathlib import Path

import requests


SEC_DATA = "https://data.sec.gov"
SEC_WWW = "https://www.sec.gov"
ANNUAL_FORMS = {"10-K", "20-F"}


def normalize_ticker(ticker: str) -> str:
    ticker = ticker.strip().upper()
    if not re.fullmatch(r"[A-Z0-9.-]{1,12}", ticker):
        raise ValueError("Enter a valid stock ticker (letters, numbers, . or -).")
    return ticker


def sec_session() -> requests.Session:
    user_agent = os.getenv("SEC_USER_AGENT", "").strip()
    if not user_agent or "@" not in user_agent:
        raise ValueError("Set SEC_USER_AGENT in .env with your name and email address.")
    session = requests.Session()
    session.headers.update({"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"})
    return session


def get_json(session: requests.Session, url: str) -> dict:
    response = session.get(url, timeout=30)
    response.raise_for_status()
    return response.json()


def list_annual_filings(ticker: str) -> list[dict]:
    ticker = normalize_ticker(ticker)
    session = sec_session()
    companies = get_json(session, f"{SEC_WWW}/files/company_tickers.json")
    company = next(
        (entry for entry in companies.values() if entry["ticker"].upper() == ticker), None
    )
    if company is None:
        raise ValueError(f"Ticker {ticker} was not found in the SEC ticker list.")

    cik = int(company["cik_str"])
    submissions = get_json(session, f"{SEC_DATA}/submissions/CIK{cik:010d}.json")
    recent = submissions["filings"]["recent"]
    filings = []
    for index, form in enumerate(recent["form"]):
        if form not in ANNUAL_FORMS:
            continue
        accession = recent["accessionNumber"][index]
        document = recent["primaryDocument"][index]
        report_date = recent["reportDate"][index]
        # The archive URL uses the numeric CIK and accession without dashes.
        source_url = (
            f"{SEC_WWW}/Archives/edgar/data/{cik}/"
            f"{accession.replace('-', '')}/{document}"
        )
        filings.append({
            "ticker": ticker,
            "company": submissions.get("name", company["title"]),
            "form": form,
            "year": int(report_date[:4]) if report_date else int(recent["filingDate"][index][:4]),
            "report_date": report_date,
            "filing_date": recent["filingDate"][index],
            "accession_number": accession,
            "source_url": source_url,
        })
    return filings


def download_filing(filing: dict, raw_dir: Path = Path("data/raw")) -> Path:
    path = raw_dir / normalize_ticker(filing["ticker"]) / str(filing["year"]) / "filing.html"
    if path.exists():
        return path
    response = sec_session().get(filing["source_url"], timeout=90)
    response.raise_for_status()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(response.content)
    return path
