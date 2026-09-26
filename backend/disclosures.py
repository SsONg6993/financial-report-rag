"""Official Form 4 and modern structured Schedule 13D/G document adapters."""

import math
from pathlib import Path

from lxml import etree

from src.portfolios import _text
from src.sec import list_company_filings, sec_session


def _number(text: str) -> float | None:
    try:
        value = float(text.replace(",", "")) if text else None
        return value if value is not None and math.isfinite(value) else None
    except ValueError:
        return None


def _value(node, name: str) -> str:
    nodes = node.xpath(f".//*[local-name()='{name}']")
    if not nodes:
        return ""
    values = nodes[0].xpath("./*[local-name()='value']/text()")
    return str(values[0]).strip() if values else "".join(nodes[0].itertext()).strip()


def parse_form4(xml: bytes, filing: dict) -> list[dict]:
    root = etree.fromstring(
        xml, etree.XMLParser(resolve_entities=False, no_network=True)
    )
    owners = root.xpath("//*[local-name()='reportingOwner']")
    names = "; ".join(_text(r, "rptOwnerName") for r in owners)
    roles = []
    for owner in owners:
        title = _text(owner, "officerTitle")
        roles.extend([title] if title else [])
        roles.extend(
            label
            for tag, label in [
                ("isDirector", "Director"),
                ("isTenPercentOwner", "10% owner"),
                ("isOther", "Other"),
            ]
            if _text(owner, tag) in {"1", "true"}
        )
    result = []
    for ordinal, row in enumerate(
        root.xpath(
            "//*[local-name()='nonDerivativeTransaction' or local-name()='derivativeTransaction']"
        )
    ):
        code = _text(row, "transactionCode")
        result.append(
            {
                "id": f"{filing['accession_number']}:{ordinal}",
                "source_type": "SEC Form 4",
                "ticker": filing["ticker"],
                "insider": names,
                "role": ", ".join(dict.fromkeys(roles)) or "Role not specified",
                "issuer": _text(root, "issuerName"),
                "security": _value(row, "securityTitle"),
                "transaction_date": _value(row, "transactionDate"),
                "reporting_period": _value(row, "transactionDate"),
                "filing_date": filing["filing_date"],
                "activity": "BUY"
                if code == "P"
                else "SELL"
                if code == "S"
                else "OTHER",
                "shares": _number(_value(row, "transactionShares")),
                "price": _number(_value(row, "transactionPricePerShare")),
                "transaction_code": code,
                "derivative": etree.QName(row).localname == "derivativeTransaction",
                "context": "Transaction code "
                + code
                + ". Purchases/sales are disclosures, not bullish/bearish signals. Footnotes may describe plans, exercises or tax transactions.",
                "footnotes": [
                    _text(n, "footnote") or "".join(n.itertext()).strip()
                    for n in root.xpath("//*[local-name()='footnote']")
                ],
                "source_url": filing["source_url"],
            }
        )
    return result


def parse_ownership(xml: bytes, filing: dict) -> list[dict]:
    root = etree.fromstring(
        xml, etree.XMLParser(resolve_entities=False, no_network=True)
    )
    people = root.xpath(
        "//*[local-name()='coverPageHeaderReportingPersonDetails' or local-name()='reportingPersonInfo']"
    )
    if not people:
        return [
            {
                "id": filing["accession_number"],
                "source_type": "SEC Schedule 13D/G",
                "ticker": filing["ticker"],
                "filer": "See original filing",
                "issuer": filing.get("company", ""),
                "ownership_percentage": None,
                "form": filing["form"],
                "filing_date": filing["filing_date"],
                "reporting_period": filing.get("report_date", ""),
                "activity": "DISCLOSED",
                "context": "Ownership filing available; structured ownership fields unavailable. No motive inferred.",
                "source_url": filing["source_url"],
            }
        ]
    return [
        {
            "id": f"{filing['accession_number']}:{i}",
            "source_type": "SEC Schedule 13D/G",
            "ticker": filing["ticker"],
            "filer": _text(person, "reportingPersonName") or "See original filing",
            "issuer": _text(root, "issuerName") or filing.get("company", ""),
            "ownership_percentage": _number(
                _text(person, "classPercent") or _text(person, "percentOfClass")
            ),
            "form": filing["form"],
            "filing_date": filing["filing_date"],
            "reporting_period": filing.get("report_date", ""),
            "activity": "DISCLOSED",
            "context": "Ownership disclosure; amendment"
            if filing["form"].endswith("/A")
            else "Ownership disclosure; no motive inferred.",
            "source_url": filing["source_url"],
        }
        for i, person in enumerate(people)
    ]


def fetch_disclosures(ticker: str, kind: str) -> dict:
    forms = (
        {"4", "4/A"}
        if kind == "insiders"
        else {
            "SC 13D",
            "SC 13D/A",
            "SC 13G",
            "SC 13G/A",
            "SCHEDULE 13D",
            "SCHEDULE 13D/A",
            "SCHEDULE 13G",
            "SCHEDULE 13G/A",
        }
    )
    filings = list_company_filings(ticker, forms)
    records, errors = [], []
    session = sec_session()
    for filing in filings[:8]:
        try:
            # Remove SEC's XML presentation stylesheet directory, if present.
            url = filing["source_url"]
            base = url.rsplit("/", 1)[0]
            if "/xsl" in base:
                base = base.rsplit("/", 1)[0]
            url = base + "/" + url.rsplit("/", 1)[1]
            path = (
                Path("data/raw")
                / ticker
                / filing["accession_number"]
                / "disclosure.xml"
            )
            if path.exists():
                document = path.read_bytes()
            else:
                response = session.get(url, timeout=20)
                response.raise_for_status()
                document = response.content
                path.parent.mkdir(parents=True, exist_ok=True)
                temporary = path.with_suffix(".incomplete")
                temporary.write_bytes(document)
                temporary.replace(path)
            if not url.lower().endswith(".xml"):
                if kind == "ownership":
                    records.append(
                        {
                            "id": filing["accession_number"],
                            "source_type": "SEC Schedule 13D/G",
                            "ticker": ticker,
                            "filer": "See original filing",
                            "issuer": filing.get("company", ""),
                            "ownership_percentage": None,
                            "form": filing["form"],
                            "filing_date": filing["filing_date"],
                            "reporting_period": filing.get("report_date", ""),
                            "activity": "DISCLOSED",
                            "context": "Legacy HTML filing: ownership fields not normalized. See source.",
                            "source_url": filing["source_url"],
                        }
                    )
                continue
            records.extend(
                (parse_form4 if kind == "insiders" else parse_ownership)(
                    document, filing
                )
            )
        except Exception as exc:  # noqa: BLE001 - one inaccessible filing must not discard other disclosures.
            errors.append(f"{filing['accession_number']}: {type(exc).__name__}")
    if filings and not records:
        raise RuntimeError(
            "Source documents could not be normalized; retry later or inspect EDGAR."
        )
    return {
        "records": records,
        "warnings": errors,
        "coverage": "Up to 8 recent documents; not exhaustive",
    }
