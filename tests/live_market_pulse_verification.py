"""Manual live QA. Public feeds + local Ollama only; never refresh SEC/holdings."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv

load_dotenv()
from backend.service import ResearchService

service = ResearchService()
pulse = service.market_pulse
pulse.refresh()
feed = pulse.feed()
report = {
    "as_of": feed["as_of"],
    "providers": feed["providers"],
    "event_count": len(feed["events"]),
    "watchlist": service.store.watchlist(),
    "watchlist_relevant_count": feed["watchlist_event_count"],
    "examples": [],
}
for source in (
    "Bureau of Economic Analysis",
    "U.S. Energy Information Administration",
    "NVIDIA Newsroom",
    "Federal Reserve",
):
    event = next(
        (
            e
            for e in sorted(
                feed["events"], key=lambda e: e["published_at"], reverse=True
            )
            if e["source"] == source
            and (
                source != "NVIDIA Newsroom"
                or e["category"] in {"Artificial Intelligence", "Semiconductors"}
            )
        ),
        None,
    )
    if event:
        report["examples"].append(
            {
                k: event[k]
                for k in (
                    "id",
                    "headline",
                    "source",
                    "source_url",
                    "published_at",
                    "event_time",
                    "freshness",
                    "recent",
                    "stale",
                    "what_happened",
                    "why_it_matters",
                    "generator",
                    "watchlist_relevant",
                )
            }
        )
        report["examples"][-1]["supported_impacts"] = [
            {
                "ticker": i["ticker"],
                "type": i["impact_type"],
                "strength": i["evidence_strength"],
                "evidence_date": i["evidence_refs"][0]["date"]
                if i["evidence_refs"]
                else None,
                "watched": i["watched"],
                "portfolio_count": len(i["portfolio_context"]),
            }
            for i in event["impacts"]
            if i["impact_type"] != "UNCLEAR"
        ]
    else:
        report["examples"].append(
            {
                "source": source,
                "status": "No usable current cached example; not fabricated",
            }
        )
reopened = ResearchService().market_pulse.feed()
report["persistence_verified"] = [e["id"] for e in feed["events"]] == [
    e["id"] for e in reopened["events"]
]
print(json.dumps(report, indent=2))
