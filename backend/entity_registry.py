"""Featured and user-resolved SEC filers. No guessed CIK or startup crawl."""

import json
import re
from dataclasses import asdict

from src.local_store import LocalStore, utc_now
from src.portfolios import INSTITUTIONS, Institution
from src.sec import SEC_DATA, sec_session


class TrackedEntityRegistry:
    def __init__(self, store: LocalStore):
        self.store = store

    def all(self) -> list[Institution]:
        with self.store.connect() as db:
            rows = db.execute(
                "SELECT payload FROM tracked_entities ORDER BY id"
            ).fetchall()
        dynamic = [Institution(**json.loads(row[0])) for row in rows]
        return [
            *INSTITUTIONS,
            *(item for item in dynamic if item.id not in {s.id for s in INSTITUTIONS}),
        ]

    def get(self, key: str) -> Institution | None:
        return next((item for item in self.all() if item.id == key), None)

    def search(self, query: str) -> list[Institution]:
        needle = query.strip().casefold()
        return [
            item
            for item in self.all()
            if needle
            in (item.name + " " + item.investor + " " + str(item.cik or "")).casefold()
        ][:50]

    def resolve_cik(self, cik: int, session=None) -> Institution:
        """Explicit on-demand SEC resolution; no record is saved on mismatch."""
        if cik <= 0 or cik > 9_999_999_999:
            raise ValueError("Enter a valid SEC CIK.")
        known = next((item for item in self.all() if item.cik == cik), None)
        if known:
            return known
        client = session or sec_session()
        response = client.get(f"{SEC_DATA}/submissions/CIK{cik:010d}.json", timeout=30)
        response.raise_for_status()
        payload = response.json()
        if int(payload.get("cik", 0)) != cik:
            raise ValueError("SEC CIK did not match the requested filer.")
        name = str(payload.get("name", "")).strip()
        if not name or not re.search(r"[A-Za-z]", name):
            raise ValueError("SEC filer name unavailable.")
        recent = payload.get("filings", {}).get("recent", {})
        if "13F-HR" not in recent.get("form", []):
            raise ValueError(
                "No original 13F-HR in the available SEC filing index; filer remains unsupported."
            )
        source = f"https://www.sec.gov/edgar/browse/?CIK={cik}&owner=exclude"
        item = Institution(
            id=f"sec-{cik}",
            name=name,
            investor="",
            style="Institutional manager",
            cik=cik,
            cik_source_url=source,
            source_notes="CIK and 13F-HR availability verified against SEC submissions on demand.",
            data_quality_notes="13F is delayed and partial; amendments are not consolidated.",
        )
        with self.store.connect() as db:
            db.execute(
                "INSERT OR IGNORE INTO tracked_entities VALUES (?, ?, ?, ?)",
                (item.id, cik, json.dumps(asdict(item)), utc_now()),
            )
        return item
