"""Validated, cached SEC company identity directory for search and resolution.

Identity lookup is deliberately independent of filings and XBRL availability.
Fuzzy results are suggestions only; they never silently choose a company.
"""

from __future__ import annotations

import difflib
import json
import os
import re
import tempfile
import time
import unicodedata
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import requests

from src.sec import SEC_WWW, sec_session

DIRECTORY_URL = f"{SEC_WWW}/files/company_tickers_exchange.json"
TTL = timedelta(hours=24)
UNSUPPORTED_SUFFIXES = {"TO", "L", "HK", "SS", "SZ", "AX", "DE", "PA", "MI"}
LEGAL_SUFFIXES = (
    " INCORPORATED", " CORPORATION", " TECHNOLOGIES", " TECHNOLOGY",
    " HOLDINGS", " HOLDING", " COMPANY", " CORP", " INC", " LTD", " PLC", " CO",
)


def _words(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return " ".join(re.findall(r"[A-Z0-9]+", ascii_value.upper()))


def _name_keys(name: str) -> set[str]:
    key = _words(name)
    keys = {key}
    while key:
        shorter = next((key[: -len(suffix)] for suffix in LEGAL_SUFFIXES if key.endswith(suffix)), "")
        if not shorter:
            break
        key = shorter.strip()
        keys.add(key)
    return keys


@dataclass(frozen=True)
class CompanyIdentity:
    ticker: str
    cik: int
    name: str
    exchange: str
    source_url: str = DIRECTORY_URL

    def to_dict(self) -> dict:
        return asdict(self)


def _validate(payload: dict) -> list[CompanyIdentity]:
    fields = payload.get("fields")
    data = payload.get("data")
    if not isinstance(fields, list) or not isinstance(data, list) or not data:
        raise ValueError("Invalid SEC company directory")
    required = {"cik", "name", "ticker", "exchange"}
    if not required.issubset(fields):
        raise ValueError("SEC company directory columns changed")
    index = {field: fields.index(field) for field in required}
    entries = []
    for row in data:
        if not isinstance(row, list) or len(row) != len(fields):
            raise ValueError("Invalid SEC company directory row")
        ticker = str(row[index["ticker"]]).strip().upper()
        name = str(row[index["name"]]).strip()
        exchange = str(row[index["exchange"]]).strip()
        cik = int(row[index["cik"]])
        if not re.fullmatch(r"[A-Z0-9.-]{1,12}", ticker) or not name or cik <= 0:
            raise ValueError("Invalid SEC company identity")
        entries.append(CompanyIdentity(ticker, cik, name, exchange))
    return entries


class CompanyDirectory:
    def __init__(self, path: Path | None = None):
        self.path = path or Path(os.getenv("THESISLENS_CACHE_DIR", "data/cache")) / "company_directory.json"

    def load(self, refresh: bool = False) -> tuple[list[CompanyIdentity], dict]:
        cached = None
        if self.path.exists():
            try:
                cached = json.loads(self.path.read_text(encoding="utf-8"))
                entries = _validate(cached["directory"])
                checked = datetime.fromisoformat(cached["checked_at"])
                if checked.tzinfo is None:
                    raise ValueError("Directory timestamp has no timezone")
                if not refresh and datetime.now(UTC) - checked < TTL:
                    return entries, {"checked_at": cached["checked_at"], "stale": False, "error": None}
            except (KeyError, ValueError, TypeError, json.JSONDecodeError):
                cached = None
        error = None
        for attempt in range(3):
            try:
                response = sec_session().get(DIRECTORY_URL, timeout=30)
                response.raise_for_status()
                directory = response.json()
                entries = _validate(directory)
                checked_at = datetime.now(UTC).isoformat()
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=self.path.parent, delete=False) as output:
                    json.dump({"checked_at": checked_at, "directory": directory}, output)
                    temporary = Path(output.name)
                temporary.replace(self.path)
                return entries, {"checked_at": checked_at, "stale": False, "error": None}
            except (requests.RequestException, ValueError, TypeError) as exc:
                error = f"{type(exc).__name__}: {str(exc)[:160]}"
                if isinstance(exc, requests.HTTPError) and exc.response is not None and exc.response.status_code not in {429, 500, 502, 503, 504}:
                    break
                if isinstance(exc, (ValueError, TypeError)):
                    break
                if attempt < 2:
                    time.sleep((0.5, 1.5)[attempt])
        if cached is not None:
            return _validate(cached["directory"]), {"checked_at": cached["checked_at"], "stale": True, "error": error}
        raise RuntimeError(f"SEC company directory unavailable: {error}")

    def cached_ticker(self, ticker: str) -> dict | None:
        """Use a validated local identity without delaying the research page."""
        if not self.path.exists():
            return None
        try:
            cached = json.loads(self.path.read_text(encoding="utf-8"))
            canonical = ticker.upper().replace(".", "-")
            return next(
                (entry.to_dict() for entry in _validate(cached["directory"])
                 if entry.ticker.replace(".", "-") == canonical),
                None,
            )
        except (KeyError, ValueError, TypeError, json.JSONDecodeError):
            return None

    def search(self, query: str, limit: int = 8) -> dict:
        entries, state = self.load()
        query = query.strip()[:100]
        words = _words(query)
        symbol = query.upper().replace(".", "-")
        scored = []
        for entry in entries:
            names = _name_keys(entry.name)
            ticker = entry.ticker.replace(".", "-")
            if symbol == ticker:
                score = 100
            elif words in names:
                score = 95
            elif ticker.startswith(symbol) and symbol:
                score = 80
            elif words and any(name.startswith(words + " ") for name in names):
                score = 70
            elif words and any(words in name for name in names):
                score = 55
            else:
                score = 0
            if score:
                scored.append((score, entry))
        if not scored and len(words) >= 4:
            for entry in entries:
                ratio = max(
                    (difflib.SequenceMatcher(None, words, name).ratio()
                     for name in _name_keys(entry.name)),
                    default=0,
                )
                if ratio >= 0.75:
                    scored.append((40 * ratio, entry))
        scored.sort(key=lambda pair: (-pair[0], pair[1].name, pair[1].ticker))
        return {"results": [entry.to_dict() for _, entry in scored[:limit]], **state}

    def resolve(self, query: str) -> dict:
        query = query.strip()
        if not query:
            return {"status": "invalid", "matches": [], "message": "Enter a company name or ticker."}
        if re.search(r"[^\w\s.,&'()/\-]", query):
            return {"status": "invalid", "matches": [], "message": "Enter a valid company name or ticker."}
        suffix = query.upper().rsplit(".", 1)
        if len(suffix) == 2 and suffix[1] in UNSUPPORTED_SUFFIXES:
            return {"status": "unsupported_market", "matches": [], "message": "This market is not covered by SEC company research."}
        results = self.search(query)
        matches = results["results"]
        key = _words(query)
        exact = [
            item for item in matches
            if item["ticker"].replace(".", "-") == query.upper().replace(".", "-")
            or key in _name_keys(item["name"])
        ]
        # A unique leading company name is safe; fuzzy matches remain suggestions.
        if not exact:
            exact = [
                item for item in matches
                if any(name.startswith(key + " ") for name in _name_keys(item["name"]))
            ]
        if len(exact) == 1:
            selected = exact[0]
            status = "resolved"
        elif exact:
            selected = None
            status = "ambiguous"
        else:
            selected = None
            status = "unknown"
        return {"status": status, "company": selected, "matches": exact or matches,
                "message": None if selected else ("Choose a specific listing." if exact else "No exact SEC company match. Review suggestions or search by ticker."),
                **{key: results[key] for key in ("checked_at", "stale", "error")}}
