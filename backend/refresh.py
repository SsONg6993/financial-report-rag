"""Explicit source refresh CLI, reusing production adapters (no fabricated fixtures)."""

import argparse

from dotenv import load_dotenv


def main():
    load_dotenv()
    from backend.service import ResearchService

    parser = argparse.ArgumentParser()
    parser.add_argument("--company", action="append", default=[])
    parser.add_argument("--investor", action="append", default=[])
    parser.add_argument("--disclosures", action="store_true")
    parser.add_argument("--intelligence", action="store_true", help="Materialize dated events from existing caches")
    parser.add_argument("--public-updates", action="store_true", help="Refresh due official RSS sources")
    parser.add_argument("--notifications", action="store_true", help="Deliver at most one queued alert via optional free channel")
    parser.add_argument("--notification-dry-run", action="store_true", help="Preview Telegram, ntfy, and Hermes messages without sending")
    args = parser.parse_args()
    service = ResearchService()
    for key in args.investor:
        kind = "ark" if key == "ark" else "portfolio"
        service.refresh(kind, key)
        print(key, service.cache_state(kind, key))
    for ticker in args.company:
        ticker = ticker.upper()
        for kind in ["company", "market"] + (
            ["insiders", "ownership"] if args.disclosures else []
        ):
            service.refresh(kind, ticker)
            print(ticker, kind, service.cache_state(kind, ticker))
    if args.public_updates:
        service.market_pulse.refresh()
        print("public_updates", len(service.market_pulse.events()))
    if args.intelligence or args.public_updates or args.notifications:
        service.intelligence.ingest_cached()
        print("intelligence_events", len(service.store.intelligence_events(5000)))
    if args.notifications:
        from backend.notifications import NotificationDispatcher
        print("notifications", NotificationDispatcher(service.store).dispatch())
    if args.notification_dry_run:
        from backend.notifications import NotificationDispatcher
        dispatcher = NotificationDispatcher(service.store)
        for channel in ("telegram", "ntfy", "hermes"):
            print("dry_run", dispatcher.dry_run(channel))


if __name__ == "__main__":
    main()
