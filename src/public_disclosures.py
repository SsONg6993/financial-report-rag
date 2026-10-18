"""OGE disclosures retain ranges and provenance, separate from institutional holdings."""

import io
import re
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from difflib import SequenceMatcher
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
    source_text: str = ""
    row_number: str = ""
    confidence: str = "high"

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


PTR_LABEL = "Periodic transaction report (OGE 278-T)"
ANNUAL_LABEL = "Annual financial disclosure (OGE 278e)"
OGE_AMOUNT_BANDS = {
    (1_001, 15_000),
    (15_001, 50_000),
    (50_001, 100_000),
    (100_001, 250_000),
    (250_001, 500_000),
    (500_001, 1_000_000),
    (1_000_001, 5_000_000),
    (5_000_001, 25_000_000),
    (25_000_001, 50_000_000),
}
TRANSACTION_TYPES = {
    "purchase": "Purchase",
    "sale": "Sale",
    "salefull": "Sale (full)",
    "salepartial": "Sale (partial)",
    "exchange": "Exchange",
}
SALE_OCR_VARIANTS = {
    "ale", "alo", "aale", "aalo", "aato", "aele", "aelo", "aole", "aolo",
    "oalo", "sale", "salo", "sate", "sato", "selo", "silo", "slo", "snlo",
    "sole", "solo", "ule", "ulo",
}
YES_OCR_VARIANTS = {"yes", "yea", "yos", "yoa", "yot", "yoo", "vos"}
NO_OCR_VARIANTS = {"no", "n0"}
TABLE_SETTINGS = {
    "vertical_strategy": "lines",
    "horizontal_strategy": "lines",
    "snap_tolerance": 4,
    "join_tolerance": 4,
    "intersection_tolerance": 5,
}


def _document_kind(header: str) -> str:
    lowered = header.lower()
    if (
        "278-t" in lowered
        or "278t" in lowered
        or "periodic transaction report" in lowered
    ):
        return PTR_LABEL
    if "278e" in lowered or "annual financial disclosure" in lowered:
        return ANNUAL_LABEL
    raise ValueError("Document is not a recognized OGE public financial disclosure.")


def _document_person(header: str) -> str:
    trump = re.search(r"Donald\s+J[.]?\s+Trump", header, re.IGNORECASE)
    if trump:
        return "Donald J. Trump"
    patterns = (
        r"Filer(?:'s|\(s\))?\s*Name[^\n]*\n\s*([A-Za-z][A-Za-z .,'-]{2,80})",
        r"Last Name[^\n]*\n\s*([A-Za-z][A-Za-z .,'-]{2,50})",
        r"Name\s*[:\n]\s*([A-Za-z][A-Za-z .,'-]{2,80})",
    )
    for pattern in patterns:
        match = re.search(pattern, header, re.IGNORECASE)
        if match:
            value = re.sub(r"\s+", " ", match.group(1)).strip(" ,-_")
            if value:
                return value
    if "donald" in header.lower() and "trump" in header.lower():
        return "Donald J. Trump"
    return "Unknown official"


def _explicit_date(header: str, labels: tuple[str, ...]) -> str:
    label_pattern = "|".join(re.escape(label) for label in labels)
    match = re.search(
        rf"(?:{label_pattern})[^\n]{{0,45}}?(\d{{1,2}}[/.]\d{{1,2}}[/.]\d{{4}})",
        header,
        re.IGNORECASE,
    )
    if not match:
        return ""
    for date_format in ("%m/%d/%Y", "%m.%d.%Y"):
        try:
            return (
                datetime.strptime(match.group(1), date_format)
                .replace(tzinfo=UTC)
                .date()
                .isoformat()
            )
        except ValueError:
            continue
    return ""


def _source_document_date(source_url: str):
    match = re.search(r"(\d{2})[.]([\d]{2})[.](\d{4})", source_url)
    if not match:
        return None
    try:
        return datetime.strptime(match.group(0), "%m.%d.%Y").replace(tzinfo=UTC).date()
    except ValueError:
        return None


def _extract_tables(page) -> list[list[list[str | None]]]:
    try:
        return page.extract_tables(table_settings=TABLE_SETTINGS) or []
    except TypeError:
        # Lightweight test doubles and older pdfplumber versions may not expose
        # the keyword. The fallback retains the same table boundaries.
        try:
            return page.extract_tables() or []
        except (AttributeError, IndexError, KeyError, OSError, ValueError):
            return []
    except (AttributeError, IndexError, KeyError, OSError, ValueError):
        return []


def _page_text(page) -> str:
    try:
        return page.extract_text() or ""
    except (AttributeError, IndexError, KeyError, OSError, TypeError, ValueError):
        return ""


def _row_cells(row: list[object]) -> list[str]:
    cells = [re.sub(r"\s+", " ", str(cell or "")).strip() for cell in row]
    if len(cells) < 6:
        cells.extend([""] * (6 - len(cells)))
    return cells


def _candidate_rows(
    tables: list[list[list[object]]],
    page_number: int,
    pending: tuple[int, list[str]] | None = None,
):
    raw_fragments = 0
    candidates: list[tuple[int, list[str]]] = []
    for table in tables:
        for raw_row in table:
            raw_fragments += 1
            cells = _row_cells(raw_row)
            row_marker = cells[0]
            row_match = re.fullmatch(r"\s*#?\s*(\d{1,6})\s*[.)]?\s*", row_marker)
            if row_match:
                if pending is not None:
                    candidates.append(pending)
                row_number = row_match.group(1)
                cells[0] = row_number
                pending = (page_number, cells)
                continue
            if pending is None:
                continue
            # Wrapped table rows can continue on the next visual line or page.
            # Only append non-empty cells; repeated headers are never candidates.
            header_text = " ".join(cells).lower()
            if row_marker.strip() or any(
                label in header_text
                for label in (
                    "description", "amount", "notification", "transactions",
                    "filer", "oge form", "donald",
                )
            ):
                continue
            pending_cells = pending[1]
            for index, value in enumerate(cells[1:6], 1):
                if value:
                    pending_cells[index] = f"{pending_cells[index]} {value}".strip()
    return candidates, raw_fragments, pending


def _letters(value: str) -> str:
    return re.sub(r"[^a-z]", "", value.lower())


def _normalized_transaction_type(value: str) -> str:
    compact = _letters(value)
    if not compact:
        return ""
    if compact in SALE_OCR_VARIANTS:
        return "Sale"
    if len(compact) >= 6 and (
        "rch" in compact
        or compact.startswith(("ounh", "unh", "lounh", "iounh"))
    ):
        return "Purchase"
    if compact in TRANSACTION_TYPES:
        return TRANSACTION_TYPES[compact]
    scored = sorted(
        (
            (SequenceMatcher(None, compact, candidate).ratio(), label)
            for candidate, label in TRANSACTION_TYPES.items()
        ),
        reverse=True,
    )
    # OCR may lose the first or last glyph, but a short unrelated token must
    # never become a transaction type.
    return scored[0][1] if len(compact) >= 5 and scored[0][0] >= 0.62 else ""


def _type_from_description(description: str) -> tuple[str, str]:
    words = description.split()
    for width in (2, 1):
        if len(words) < width:
            continue
        candidate = " ".join(words[-width:])
        normalized = _normalized_transaction_type(candidate)
        if normalized:
            return " ".join(words[:-width]).strip(" |,;:-"), normalized
    return description, ""


def _normalized_amount(value: str) -> str:
    raw = re.sub(r"\s+", " ", value).strip()
    over = re.search(r"over\s*[$s]?\s*([\d ,.]*)", raw, re.IGNORECASE)
    if over:
        digits = re.sub(r"\D", "", over.group(1))
        if digits and int(digits) == 50_000_000:
            return "Over $50,000,000"
        return ""
    parts = re.split(r"\s*(?:[-–—•]|\u00b7)\s*", raw, maxsplit=1)
    if len(parts) != 2:
        return ""
    numbers = []
    for part in parts:
        digits = re.sub(r"\D", "", part)
        if not digits:
            return ""
        numbers.append(int(digits))
    band = (numbers[0], numbers[1])
    if band not in OGE_AMOUNT_BANDS:
        return ""
    return f"${band[0]:,} - ${band[1]:,}"


def _normalized_transaction_date(value: str, document_date):
    compact = re.sub(r"\s+", "", value).replace("|", "/")
    if not re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}", compact):
        return "", "invalid_transaction_date"
    try:
        parsed = datetime.strptime(compact, "%m/%d/%Y").replace(tzinfo=UTC).date()
    except ValueError:
        return "", "invalid_transaction_date"
    if document_date and parsed > document_date:
        return "", "future_transaction_date"
    return parsed.isoformat(), ""


def _normalize_notification(value: str) -> str:
    compact = _letters(value)
    if not compact:
        return ""
    if compact in YES_OCR_VARIANTS:
        return "Yes"
    if compact in NO_OCR_VARIANTS:
        return "No"
    yes_score = SequenceMatcher(None, compact, "yes").ratio()
    no_score = SequenceMatcher(None, compact, "no").ratio()
    if max(yes_score, no_score) < 0.45:
        return ""
    return "Yes" if yes_score >= no_score else "No"


def _parse_ptr_candidate(
    cells: list[str], person: str, filing_date: str, source_url: str,
    page_number: int, document_date,
) -> tuple[PublicDisclosure | None, str]:
    row_number, description, type_cell, date_cell, notification, amount_cell = cells[:6]
    transaction_type = _normalized_transaction_type(type_cell)
    if not transaction_type:
        description, transaction_type = _type_from_description(description)
    else:
        description = re.sub(r"(?:\s+[|Il])$", "", description).strip()
    if not description or len(re.sub(r"\W", "", description)) < 2:
        return None, "missing_asset_description"
    if not transaction_type:
        return None, "unrecognized_transaction_type"
    transaction_date, date_error = _normalized_transaction_date(date_cell, document_date)
    if date_error:
        return None, date_error
    amount_range = _normalized_amount(amount_cell)
    if not amount_range:
        return None, "invalid_amount_range"
    if not _normalize_notification(notification):
        return None, "invalid_notification_field"
    source_text = " | ".join(value for value in cells[:6] if value)
    return (
        PublicDisclosure(
            person,
            PTR_LABEL,
            filing_date,
            description,
            "Disclosed security / interest",
            transaction_type,
            amount_range,
            source_url=source_url,
            transaction_date=transaction_date,
            page=page_number,
            source_text=source_text,
            row_number=row_number,
            confidence="moderate" if description != cells[1] or type_cell.lower() != transaction_type.lower() else "high",
            notes="Verified against the OGE 278-T row schema; values remain disclosure ranges.",
        ),
        "",
    )


def parse_oge_pdf(content: bytes, source_url: str) -> dict:
    import pdfplumber

    if not is_official_oge_url(source_url):
        raise ValueError("Use an HTTPS PDF hosted by OGE.")
    records: list[PublicDisclosure] = []
    excerpts = []
    rejection_reasons: Counter[str] = Counter()
    source_document_date = _source_document_date(source_url)
    raw_fragment_count = 0
    candidate_count = 0
    duplicate_count = 0
    pages_with_text = 0
    pages_with_tables = 0
    text_layer_degraded = False
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        header = "\n".join(_page_text(page) for page in pdf.pages[:2])
        kind = _document_kind(f"{header}\n{source_url}")
        person = _document_person(header)
        filing_date = _explicit_date(header, ("Submitted", "Filing Date"))
        certification_date = _explicit_date(header, ("OGE Certification", "Certification Date"))
        seen: set[tuple[str, str, str, str]] = set()
        pending_candidate: tuple[int, list[str]] | None = None
        for page_number, page in enumerate(pdf.pages, 1):
            text = _page_text(page)
            if text.strip():
                pages_with_text += 1
            if "\ufffd" in text or "(cid:" in text:
                text_layer_degraded = True
            excerpts.append({"page": page_number, "text": text, "source_url": source_url + f"#page={page_number}"})
            if kind != PTR_LABEL:
                continue
            tables = _extract_tables(page)
            if tables:
                pages_with_tables += 1
            candidates, page_fragments, pending_candidate = _candidate_rows(
                tables, page_number, pending_candidate
            )
            raw_fragment_count += page_fragments
            candidate_count += len(candidates)
            for candidate_page, cells in candidates:
                record, reason = _parse_ptr_candidate(
                    cells, person, filing_date, source_url, candidate_page,
                    source_document_date,
                )
                if record is None:
                    rejection_reasons[reason] += 1
                    continue
                identity = (
                    record.row_number,
                    record.asset_name.casefold(),
                    record.transaction_date,
                    record.amount_range,
                )
                if identity in seen:
                    duplicate_count += 1
                    rejection_reasons["duplicate_extraction"] += 1
                    continue
                seen.add(identity)
                records.append(record)
        if kind == PTR_LABEL and pending_candidate is not None:
            candidate_count += 1
            candidate_page, cells = pending_candidate
            record, reason = _parse_ptr_candidate(
                cells, person, filing_date, source_url, candidate_page,
                source_document_date,
            )
            if record is None:
                rejection_reasons[reason] += 1
            else:
                identity = (
                    record.row_number,
                    record.asset_name.casefold(),
                    record.transaction_date,
                    record.amount_range,
                )
                if identity in seen:
                    duplicate_count += 1
                    rejection_reasons["duplicate_extraction"] += 1
                else:
                    records.append(record)
    rejected_rows = sum(rejection_reasons.values()) - duplicate_count
    coverage = len(records) / candidate_count if candidate_count else 0.0
    text_layer_status = "degraded" if text_layer_degraded else "usable"
    if pages_with_text == 0:
        text_layer_status = "unusable"
    if kind == ANNUAL_LABEL:
        status = "source_only"
        confidence = "not_applicable"
    elif not records:
        status = "review_required"
        confidence = "low"
    else:
        status = "partial_verified" if rejected_rows else "verified"
        confidence = "high" if coverage >= 0.9 else "moderate" if coverage >= 0.5 else "low"
    notes = [
        "OGE disclosures report value ranges, not exact transaction values or current holdings.",
        "Only rows satisfying the OGE 278-T schema are shown; ambiguous OCR output remains unverified.",
    ]
    if kind == ANNUAL_LABEL:
        notes.append("OGE 278e annual disclosures use a different schema and are retained as source excerpts only.")
    return {"person": person, "disclosure_type": kind, "filing_date": filing_date,
            "source_document_date": source_document_date.isoformat() if source_document_date else "",
            "certification_date": certification_date,
            "source_url": source_url, "records": [row.to_dict() for row in records],
            "excerpts": excerpts, "rejected_rows": rejected_rows, "table_validation_rate": coverage,
            "notes": notes,
            "extraction": {
                "status": status,
                "method": "layout_aware_table",
                "text_layer_status": text_layer_status,
                "ocr_used": False,
                "ocr_reason": "not_needed" if text_layer_status != "unusable" else "local_ocr_unavailable",
                "pages_total": len(excerpts),
                "pages_with_text": pages_with_text,
                "pages_with_tables": pages_with_tables,
                "raw_fragment_count": raw_fragment_count,
                "candidate_count": candidate_count,
                "verified_count": len(records),
                "rejected_count": rejected_rows,
                "deduplicated_count": duplicate_count,
                "coverage_rate": coverage,
                "confidence": confidence,
                "rejection_reasons": dict(sorted(rejection_reasons.items())),
            }}


def fetch_oge_disclosure(url: str = OGE_TRUMP_PTR) -> dict:
    if not is_official_oge_url(url):
        raise ValueError("Enter an official oge.gov PDF URL.")
    response = requests.get(url, timeout=40)
    response.raise_for_status()
    if not response.content.startswith(b"%PDF"):
        raise ValueError("OGE returned an access page rather than a PDF. Use the official source link.")
    return parse_oge_pdf(response.content, url)
