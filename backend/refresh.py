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


if __name__ == "__main__":
    main()
