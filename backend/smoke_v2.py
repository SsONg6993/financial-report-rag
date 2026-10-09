"""Explicit, bounded official-source V2 audit; no personal DB or paid endpoints."""

import argparse
import json
import os
import tempfile
from pathlib import Path

from dotenv import load_dotenv

from backend.disclosures import parse_form4
from backend.market_pulse.providers import default_providers
from backend.service import ResearchService
from src.local_store import LocalStore, utc_now
from src.portfolios import INSTITUTIONS, Sec13FProvider, compare_portfolios
from src.sec import SEC_DATA, list_company_filings, sec_session


def audit_managers():
    session = sec_session()
    rows = []
    for manager in INSTITUTIONS:
        if manager.cik is None:
            rows.append({"id": manager.id, "registry_name": manager.name, "type": "daily fund",
                         "cik": None, "original_13f": False, "status": "ARKK official daily source, not 13F"})
            continue
        try:
            response = session.get(f"{SEC_DATA}/submissions/CIK{manager.cik:010d}.json", timeout=20)
            response.raise_for_status()
            payload = response.json()
            recent = payload["filings"]["recent"]
            indices = [i for i, form in enumerate(recent["form"]) if form == "13F-HR"]
            latest = max(indices, key=lambda i: recent["reportDate"][i]) if indices else None
            rows.append({"id": manager.id, "registry_name": manager.name,
                         "sec_name": payload.get("name"), "person_label": manager.investor,
                         "manager_type": manager.manager_type, "cik": manager.cik,
                         "cik_match": int(payload.get("cik", 0)) == manager.cik,
                         "original_13f": bool(indices),
                         "latest_report": recent["reportDate"][latest] if latest is not None else None,
                         "latest_filed": recent["filingDate"][latest] if latest is not None else None,
                         "source_url": f"https://www.sec.gov/edgar/browse/?CIK={manager.cik}&owner=exclude",
                         "status": "verified" if indices else "original 13F unavailable in recent index"})
        except Exception as exc:  # noqa: BLE001 - independent public source check.
            rows.append({"id": manager.id, "cik": manager.cik,
                         "status": f"unavailable: {type(exc).__name__}"})
    return rows


def smoke():
    # Scratch SQLite disappears with this context; no personal DB/cache is opened.
    with tempfile.TemporaryDirectory(prefix="thesislens-v2-smoke-") as directory:
        store = LocalStore(Path(directory) / "smoke.sqlite3")
        service = ResearchService(store)
        provider = Sec13FProvider()
        result = {"managers": {}, "company": {}, "form4": {}, "rss": {}}
        for key in ("berkshire", "baupost"):
            manager = next(item for item in INSTITUTIONS if item.id == key)
            try:
                filings = provider.filings(manager)[:2 if key == "berkshire" else 1]
                snapshots = [provider.snapshot(manager, filing) for filing in filings]
                for snapshot in snapshots:
                    store.save_snapshot("portfolio", key, snapshot.reporting_period, snapshot.to_dict())
                latest = snapshots[0]
                result["managers"][key] = {"source_url": latest.source_url,
                    "reporting_period": latest.reporting_period, "filing_date": latest.filing_date,
                    "holdings": len(latest.holdings), "persisted": len(service.portfolios(key)) == len(snapshots)}
                if key == "berkshire" and len(snapshots) == 2:
                    changes = compare_portfolios(snapshots[1], snapshots[0])
                    result["comparisons"] = {
                        "activities": {activity: sum(item["activity"] == activity for item in changes)
                                       for activity in ("NEW", "INCREASED", "REDUCED", "EXITED", "UNCHANGED")},
                        "before_period": snapshots[1].reporting_period,
                        "after_period": latest.reporting_period,
                        "filing_date": latest.filing_date,
                        "values_consistent": all(
                            item["share_change"] == item["shares_after"] - item["shares_before"]
                            and abs(item["weight_change"] - (item["weight_after"] - item["weight_before"])) < 1e-9
                            and item["reporting_period"] == latest.reporting_period
                            and item["filing_date"] == latest.filing_date
                            for item in changes),
                    }
            except Exception as exc:  # noqa: BLE001 - report source-specific failure.
                result["managers"][key] = {"error": type(exc).__name__}
        try:
            filings = list_company_filings("AAPL", {"10-Q", "4", "4/A"})
            quarterly = next(row for row in filings if row["form"] == "10-Q")
            result["company"] = {"source_url": quarterly["source_url"],
                                 "reporting_period": quarterly["report_date"],
                                 "filing_date": quarterly["filing_date"]}
            form4 = next(row for row in filings if row["form"] in {"4", "4/A"})
            url = form4["source_url"]
            base = url.rsplit("/", 1)[0]
            if "/xsl" in base:
                base = base.rsplit("/", 1)[0]
            document = sec_session().get(base + "/" + url.rsplit("/", 1)[1], timeout=20)
            document.raise_for_status()
            records = parse_form4(document.content, form4)
            store.save_snapshot("insiders", "AAPL", "current", {"records": records})
            result["form4"] = {"source_url": form4["source_url"],
                               "filing_date": form4["filing_date"],
                               "transaction_date": records[0]["transaction_date"] if records else None,
                               "records": len(records), "persisted": bool(store.snapshots("insiders", "AAPL"))}
        except Exception as exc:  # noqa: BLE001 - report source-specific failure.
            result["company_or_form4_error"] = type(exc).__name__
        official = next(item for item in default_providers() if item.id == "fed")
        try:
            fetched = official.fetch({})
            rows = [event.model_dump() for event in fetched.events or []]
            state = {"events": rows, "checked_at": utc_now(), "successful_at": utc_now(),
                     "error": None, "etag": fetched.etag, "last_modified": fetched.last_modified}
            store.save_snapshot("pulse_provider", official.id, "current", state)
            result["rss"] = {"url": official.url, "events": len(rows),
                             "published_at": rows[0]["published_at"] if rows else None,
                             "persisted": bool(store.snapshots("pulse_provider", official.id))}

            class Unavailable:
                id = official.id
                name = official.name
                ttl_seconds = 0
                category = official.category
                issuer = official.issuer
                def fetch(self, _state):
                    raise RuntimeError("simulated failure")

            service.market_pulse.providers = [Unavailable()]
            service.market_pulse.refresh()
            retained = service.market_pulse.state(service.market_pulse.providers[0])
            result["rss"]["last_good_retained"] = retained.get("events") == rows and bool(retained.get("error"))
        except Exception as exc:  # noqa: BLE001 - report source-specific failure.
            result["rss"] = {"url": official.url, "error": type(exc).__name__}
        first = service.intelligence.feed(limit=100)["events"]
        second = service.intelligence.feed(limit=100)["events"]
        result["events"] = {"first_count": len(first), "second_count": len(second),
                            "deduplicated": len(first) == len(second),
                            "source_urls_present": all(item["source_url"].startswith("https://") for item in first)}
        result["scratch_database_only"] = True
        return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    if not args.audit and not args.smoke:
        parser.error("Choose --audit and/or --smoke for explicit official-source requests")
    load_dotenv()
    os.environ["THESISLENS_OFFLINE"] = "true"
    result = {}
    if args.audit:
        result["registry"] = audit_managers()
    if args.smoke:
        result["smoke"] = smoke()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
