"""Official institutional disclosures, normalized without inferring motives."""

import csv
import io
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from lxml import etree

from src.sec import SEC_DATA, SEC_WWW, sec_session


@dataclass(frozen=True)
class Institution:
    id: str
    name: str
    investor: str
    style: str
    cik: int | None = None
    source_type: str = "SEC Form 13F"


INSTITUTIONS = (
    Institution("berkshire", "Berkshire Hathaway", "Warren Buffett / Berkshire Hathaway", "Quality / Value / Long-term", 1067983),
    Institution("pershing", "Pershing Square", "Bill Ackman", "Concentrated / Activist", 1336528),
    Institution("appaloosa", "Appaloosa Management", "David Tepper", "Active / Macro / Cyclical", 1656456),
    Institution("bridgewater", "Bridgewater Associates", "", "Macro / Diversified", 1350694),
    Institution("ark", "ARK Invest — ARKK", "Cathie Wood", "Innovation / Growth", source_type="Official ARKK daily fund holdings"),
    Institution("scion", "Scion Asset Management", "Michael Burry", "Contrarian / Concentrated", 1649339),
)
BY_ID = {item.id: item for item in INSTITUTIONS}
DISCLOSURE_NOTE = (
    "13F reports are delayed, may be filed roughly 45 days after quarter end, and provide "
    "only a partial view of exposure. They omit many assets and hedges and do not establish "
    "current holdings or conviction. Option values describe underlying securities, not option premiums."
)


@dataclass
class Holding:
    issuer: str
    security_class: str
    cusip: str
    shares: float
    reported_value: float
    put_call: str = ""
    share_type: str = "SH"
    ticker: str = ""
    weight: float = 0.0
    sector: str = "Unclassified"

    @property
    def key(self):
        return self.cusip, self.security_class.upper(), self.put_call.upper(), self.share_type.upper()


@dataclass
class PortfolioSnapshot:
    institution_id: str
    reporting_period: str
    filing_date: str
    source_url: str
    accession: str
    source_type: str = "SEC Form 13F"
    holdings: list[Holding] = field(default_factory=list)
    notes: str = ""

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        return cls(**{**data, "holdings": [Holding(**row) for row in data["holdings"]]})


def _root(xml: bytes | str):
    return etree.fromstring(xml.encode() if isinstance(xml, str) else xml,
                            parser=etree.XMLParser(resolve_entities=False, no_network=True))


def _text(node, name: str, default: str = "") -> str:
    values = node.xpath(f".//*[local-name()='{name}']/text()")
    return str(values[0]).strip() if values else default


def parse_13f(xml: bytes | str, filing_date: str) -> list[Holding]:
    root = _root(xml)
    # SEC changed the value unit from thousands to dollars on January 3, 2023.
    factor = 1000 if filing_date < "2023-01-03" else 1
    grouped: dict[tuple, Holding] = {}
    for row in root.xpath("//*[local-name()='infoTable']"):
        item = Holding(_text(row, "nameOfIssuer"), _text(row, "titleOfClass"),
                       _text(row, "cusip"), float(_text(row, "sshPrnamt", "0")),
                       float(_text(row, "value", "0")) * factor,
                       _text(row, "putCall"), _text(row, "sshPrnamtType", "SH"))
        if not item.cusip or not item.issuer or item.shares < 0 or item.reported_value < 0:
            raise ValueError("Invalid 13F information-table row.")
        if item.key in grouped:
            grouped[item.key].shares += item.shares
            grouped[item.key].reported_value += item.reported_value
        else:
            grouped[item.key] = item
    total = sum(row.reported_value for row in grouped.values())
    for row in grouped.values():
        row.weight = row.reported_value / total if total else 0.0
    return sorted(grouped.values(), key=lambda row: row.reported_value, reverse=True)


def disclosure_freshness(period: str, today: date | None = None, source_type: str = "SEC Form 13F") -> str:
    try:
        age = ((today or datetime.now(UTC).date()) - date.fromisoformat(period)).days
    except ValueError:
        return "Reporting period unavailable"
    if age < 0:
        return "Reporting period is in the future — review source"
    threshold = 150 if source_type == "SEC Form 13F" else 7
    return f"{'Stale' if age > threshold else 'Historical disclosure'} · {age} days since reporting period"


def compare_portfolios(previous: PortfolioSnapshot, current: PortfolioSnapshot) -> list[dict]:
    if previous.institution_id != current.institution_id or previous.source_type != current.source_type:
        raise ValueError("Compare the same institution and disclosure type.")
    if previous.reporting_period >= current.reporting_period:
        raise ValueError("Portfolio comparison needs two different ordered reporting periods.")
    before = {row.key: row for row in previous.holdings}
    after = {row.key: row for row in current.holdings}
    changes = []
    for key in sorted(before.keys() | after.keys()):
        old, new = before.get(key), after.get(key)
        old_shares, new_shares = old.shares if old else 0, new.shares if new else 0
        activity = "NEW" if old is None else "EXITED" if new is None else "INCREASED" if new_shares > old_shares else "REDUCED" if new_shares < old_shares else "UNCHANGED"
        item = new or old
        changes.append({"issuer": item.issuer, "ticker": item.ticker, "cusip": item.cusip,
                        "security_class": item.security_class, "put_call": item.put_call,
                        "activity": activity, "shares_before": old_shares, "shares_after": new_shares,
                        "share_change_pct": (new_shares - old_shares) / old_shares if old_shares else None,
                        "reporting_period": current.reporting_period, "previous_period": previous.reporting_period,
                        "filing_date": current.filing_date, "source_url": current.source_url})
    return changes


class Sec13FProvider:
    def __init__(self, session=None):
        self.session = session or sec_session()

    def get(self, url: str):
        time.sleep(0.12)  # Stay comfortably below SEC's ten-request-per-second ceiling.
        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        return response

    def filings(self, institution: Institution) -> list[dict]:
        payload = self.get(f"{SEC_DATA}/submissions/CIK{institution.cik:010d}.json").json()
        recent = payload["filings"]["recent"]
        # Include history if recent submissions contain fewer than two distinct periods.
        tables = [recent]
        if len({recent["reportDate"][i] for i, form in enumerate(recent["form"]) if form == "13F-HR"}) < 2:
            for older in payload["filings"].get("files", [])[:3]:
                tables.append(self.get(f"{SEC_DATA}/submissions/{older['name']}").json())
        found = []
        for table in tables:
            for i, form in enumerate(table.get("form", [])):
                if form != "13F-HR":
                    continue
                found.append({"accession": table["accessionNumber"][i],
                              "filing_date": table["filingDate"][i],
                              "reporting_period": table["reportDate"][i],
                              "document": table["primaryDocument"][i]})
        # Amendments require explicit restatement/additional-holdings handling; do not merge blindly.
        unique = {}
        for row in sorted(found, key=lambda x: x["filing_date"], reverse=True):
            unique.setdefault(row["reporting_period"], row)
        return sorted(unique.values(), key=lambda x: x["reporting_period"], reverse=True)

    def snapshot(self, institution: Institution, filing: dict) -> PortfolioSnapshot:
        base = f"{SEC_WWW}/Archives/edgar/data/{institution.cik}/{filing['accession'].replace('-', '')}/"
        primary_document = filing["document"].split("/")[-1]
        primary = self.get(urljoin(base, primary_document)).content
        root = _root(primary)
        period = _text(root, "periodOfReport")
        if period and ("/" in period or ("-" in period and len(period.split("-")[0]) != 4)):
            period = datetime.strptime(period, "%m-%d-%Y" if "-" in period else "%m/%d/%Y").replace(tzinfo=UTC).date().isoformat()
        if not period:
            period = filing["reporting_period"]
        listing = self.get(base + "index.json").json()["directory"]["item"]
        holdings = []
        for item in listing:
            name = item["name"]
            if not name.lower().endswith(".xml") or name == primary_document:
                continue
            xml = self.get(urljoin(base, name)).content
            if b"infoTable" in xml:
                holdings.extend(parse_13f(xml, filing["filing_date"]))
        if not holdings and _text(root, "tableEntryTotal") != "0":
            raise ValueError("No public 13F information table found in this filing.")
        # Each archive normally has one table; normalize weights over the full snapshot.
        total = sum(row.reported_value for row in holdings)
        for row in holdings:
            row.weight = row.reported_value / total if total else 0
        return PortfolioSnapshot(institution.id, period, filing["filing_date"],
                                 base + filing["document"], filing["accession"], holdings=holdings,
                                 notes="Original 13F-HR; amendments are not incorporated. No licensed CUSIP-to-ticker or sector mapping is assumed.")

    def latest_two(self, institution: Institution) -> list[PortfolioSnapshot]:
        snapshots = []
        for filing in self.filings(institution)[:2]:
            try:
                snapshots.append(self.snapshot(institution, filing))
            except (requests.RequestException, ValueError, etree.XMLSyntaxError):
                if not snapshots:
                    raise
                snapshots[0].notes += " Previous snapshot could not be loaded; comparison unavailable."
        return snapshots

    def resolve_tickers(self, snapshots: list[PortfolioSnapshot]):
        """Exact normalized issuer-name matching only; ambiguous share classes stay unmapped."""
        payload = self.get(f"{SEC_WWW}/files/company_tickers.json").json()
        names = {}
        for row in payload.values():
            key = re.sub(r"[^A-Z0-9]", "", row["title"].upper())
            names.setdefault(key, []).append(row["ticker"])
        for snapshot in snapshots:
            for holding in snapshot.holdings:
                key = re.sub(r"[^A-Z0-9]", "", holding.issuer.upper())
                matches = names.get(key, [])
                if len(matches) == 1:
                    holding.ticker = matches[0]
            snapshot.notes += " Tickers, where present, use unambiguous exact issuer-name matches in the SEC ticker directory; confirm security class before research."


def enrich_sectors(snapshot: PortfolioSnapshot):
    """Optional Yahoo sector metadata for verified tickers, never inferred from issuer names."""
    import yfinance as yf

    failures = 0
    for holding in snapshot.holdings:
        if not holding.ticker or holding.put_call:
            continue
        try:
            sector = yf.Ticker(holding.ticker).info.get("sector")
            if sector:
                holding.sector = sector
        except Exception:  # noqa: BLE001 - optional enrichment preserves official holdings.
            failures += 1
    snapshot.notes += f" Optional sector labels from Yahoo Finance; {failures} ticker lookups failed. Unmapped securities remain unclassified."


ARK_URL = "https://www.ark-funds.com/funds/arkk"


def parse_ark_csv(text: str, source_url: str) -> PortfolioSnapshot:
    rows = list(csv.DictReader(io.StringIO(text.lstrip("\ufeff"))))
    holdings = []
    periods = set()
    for original in rows:
        row = {key.strip().lower().replace(" ", ""): value for key, value in original.items() if key}
        if not row.get("ticker") or not row.get("company"):
            continue
        raw_date = row.get("date", "")
        period = next((datetime.strptime(raw_date, pattern).replace(tzinfo=UTC).date().isoformat()
                       for pattern in ("%m/%d/%Y", "%Y-%m-%d") if _date_matches(raw_date, pattern)), None)
        if not period:
            raise ValueError("ARK holdings lack a valid as-of date.")
        periods.add(period)
        holdings.append(Holding(row["company"], "ARKK fund holding", row.get("cusip", ""),
                                float(row.get("shares", "0").replace(",", "")),
                                float(row.get("marketvalue($)", row.get("marketvalue", "0")).replace(",", "").replace("$", "")),
                                ticker=row["ticker"]))
    if len(periods) != 1 or not holdings:
        raise ValueError("ARK data is empty or mixes reporting dates.")
    total = sum(row.reported_value for row in holdings)
    for row in holdings:
        row.weight = row.reported_value / total if total else 0
    period = next(iter(periods))
    return PortfolioSnapshot("ark", period, period, source_url, period,
                             "Official ARKK daily fund holdings", holdings,
                             "ARKK only; not all ARK strategies. As-of date is the fund's holdings date, not a 13F filing date.")


def _date_matches(value, pattern):
    try:
        datetime.strptime(value, pattern).replace(tzinfo=UTC)
        return True
    except ValueError:
        return False


def fetch_ark_holdings() -> PortfolioSnapshot:
    response = requests.get(ARK_URL, timeout=25)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    links = [urljoin(ARK_URL, a["href"]) for a in soup.select("a[href]")
             if "ARKK" in a["href"].upper() and ".csv" in a["href"].lower()]
    if not links:
        raise ValueError("Official ARKK CSV link unavailable. Open the official fund page; no substitute holdings are fabricated.")
    source = links[0]
    data = requests.get(source, timeout=25)
    data.raise_for_status()
    return parse_ark_csv(data.text, source)
