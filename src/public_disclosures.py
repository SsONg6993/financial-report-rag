"""OGE disclosures retain ranges and provenance, separate from institutional holdings."""

import io
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from urllib.parse import urlparse

import requests

OGE_SEARCH = "https://www.oge.gov/web/OGE.nsf/Officials%20Individual%20Disclosures%20Search%20Collection"
OGE_ANNUAL_NOTICE = "https://extapps2.oge.gov/web/oge.nsf/Resources/Available%2BNow%3A%2BThe%2BPresident%E2%80%99s%2Band%2BVice%2BPresident%E2%80%99s%2Bcertified%2Bannual%2Bfinancial%2Bdisclosure%2Breports"
OGE_TRUMP_PTR = "https://extapps2.oge.gov/201/presiden.nsf/pas%2Bindex/405e4ec4e27be8d185258df7002dd1c0/%24file/trump%2C%20donald%20j.-05.08.2026-278t%282%29.pdf"


@dataclass
class PublicDisclosure:
    person: str
    disclosure_type: str
    filing_date: str
    asset_name: str
    asset_type: str
    transaction_type: str = ""
    amount_range: str = ""
    income_range: str = ""
    source_url: str = ""
    notes: str = ""
    transaction_date: str = ""
    page: int | None = None

    def to_dict(self):
        return asdict(self)


def is_official_oge_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "https" and (parsed.hostname == "oge.gov" or
                                         (parsed.hostname or "").endswith(".oge.gov"))


def parse_disclosure_rows(rows: list[dict], person: str, disclosure_type: str,
                          filing_date: str, source_url: str) -> list[PublicDisclosure]:
    if not is_official_oge_url(source_url):
        raise ValueError("Disclosures must retain an official OGE source URL.")
    datetime.strptime(filing_date, "%Y-%m-%d").replace(tzinfo=UTC)
    result = []
    for row in rows:
        if not str(row.get("asset_name", "")).strip():
            continue
        result.append(PublicDisclosure(person, disclosure_type, filing_date,
                                       str(row["asset_name"]), str(row.get("asset_type", "Disclosed interest")),
                                       str(row.get("transaction_type", "")), str(row.get("amount_range", "")),
                                       str(row.get("income_range", "")), source_url,
                                       str(row.get("notes", "Ranges are preserved; no exact portfolio weight is inferred.")),
                                       str(row.get("transaction_date", "")), row.get("page")))
    return result


def parse_oge_pdf(content: bytes, source_url: str) -> dict:
    import pdfplumber

    if not is_official_oge_url(source_url):
        raise ValueError("Use an HTTPS PDF hosted by OGE.")
    records = []
    excerpts = []
    rejected_rows = 0
    source_date_match = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", source_url)
    source_document_date = datetime.strptime(source_date_match.group(0), "%m.%d.%Y").replace(tzinfo=UTC).date() if source_date_match else None
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        header = "\n".join(page.extract_text() or "" for page in pdf.pages[:2])
        if "278-T" not in header and "278e" not in header and "278e" not in header.lower():
            raise ValueError("Document is not a recognized OGE public financial disclosure.")
        person_match = re.search(r"(?:Filer(?:'s)? Name|Name)\s*[:\n]?\s*(Trump[^\n]*|Donald[^\n]*)", header, re.IGNORECASE)
        person = person_match.group(1).strip() if person_match else "Donald Trump"
        if "trump" not in header.lower():
            raise ValueError("The document does not identify Donald Trump.")
        kind = "Periodic transaction report (OGE 278-T)" if "278-T" in header else "Annual financial disclosure (OGE 278e)"
        filed_match = re.search(r"(?:Signed|Submitted|Filing Date)[^\n]{0,35}?(\d{1,2}/\d{1,2}/\d{4})", header, re.IGNORECASE)
        # Never invent a filing date from a transaction or unrelated date.
        filing_date = datetime.strptime(filed_match.group(1), "%m/%d/%Y").replace(tzinfo=UTC).date().isoformat() if filed_match else ""
        for page_number, page in enumerate(pdf.pages, 1):
            text = page.extract_text() or ""
            excerpts.append({"page": page_number, "text": text, "source_url": source_url + f"#page={page_number}"})
            if "278-T" not in header:
                continue  # Annual tables differ by section; retain exact excerpts for review.
            for table in page.extract_tables():
                for row in table:
                    cells = [str(cell or "").strip() for cell in row]
                    # Standard PTR table: row no, description, type, date, notification, amount.
                    if len(cells) < 6 or not cells[0].isdigit() or not cells[1]:
                        continue
                    amount = cells[-1]
                    transaction_type = cells[2].lower()
                    valid_amount = re.fullmatch(r"\$[\d,]+\s*[-–]\s*\$[\d,]+|Over \$[\d,]+", amount)
                    valid_date = re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}", cells[3])
                    if not valid_amount or not valid_date or transaction_type not in {"purchase", "sale", "sale (full)", "sale (partial)", "exchange"}:
                        rejected_rows += 1
                        continue
                    try:
                        transaction_date = datetime.strptime(cells[3], "%m/%d/%Y").replace(tzinfo=UTC).date()
                        if source_document_date and transaction_date > source_document_date:
                            rejected_rows += 1
                            continue
                    except ValueError:
                        rejected_rows += 1
                        continue
                    records.append(PublicDisclosure(person, kind, filing_date, cells[1], "Disclosed security / interest",
                                                     cells[2], amount, source_url=source_url,
                                                     transaction_date=cells[3], page=page_number,
                                                     notes="Extracted from OGE table; inspect original PDF for wrapped rows and footnotes."))
    total_rows = len(records) + rejected_rows
    quality = len(records) / total_rows if total_rows else 0
    # A heavily corrupted text layer is not a reliable normalized table.
    if total_rows and quality < 0.9:
        rejected_rows += len(records)
        records = []
    return {"person": person, "disclosure_type": kind, "filing_date": filing_date,
            "source_document_date": source_document_date.isoformat() if source_document_date else "",
            "source_url": source_url, "records": [row.to_dict() for row in records],
            "excerpts": excerpts, "rejected_rows": rejected_rows, "table_validation_rate": quality,
            "notes": f"Descriptive public disclosure, not an exact current brokerage portfolio. {rejected_rows} table rows could not be validated and were excluded. Source excerpts may have OCR/text-layer errors; verify in the original PDF. Missing filing dates remain unknown. Annual tables are retained as source excerpts for review."}


def fetch_oge_disclosure(url: str = OGE_TRUMP_PTR) -> dict:
    if not is_official_oge_url(url):
        raise ValueError("Enter an official oge.gov PDF URL.")
    response = requests.get(url, timeout=40)
    response.raise_for_status()
    if not response.content.startswith(b"%PDF"):
        raise ValueError("OGE returned an access page rather than a PDF. Use the official source link.")
    return parse_oge_pdf(response.content, url)
