"""Manual live QA: refresh quotes and local summaries only, never SEC adapters."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv

load_dotenv()
from backend.research_context import risk_cards
from backend.service import ResearchService

service = ResearchService()
report = {"model": service.config.ollama_model, "companies": {}}
for ticker in ("META", "AAPL", "RKLB"):
    service.refresh("market", ticker)
    company = service.company(ticker)
    chunks = [c for c in service.chunks(ticker) if "risk" in (c.get("section", "") + c.get("section_title", "")).lower()]
    cards = risk_cards(chunks, service.config)
    if cards:
        filing = ((service.cached_company(ticker) or {}).get("filings") or [{}])[0].get("accession_number")
        service.store.save_snapshot("risk_summary", ticker, "current", {"cards": cards, "filing": filing})
    answer = service.ask(f"What should I watch for {ticker}?", ticker)
    quote = {key: value for key, value in company["market"].items() if key not in {"history", "description"}}
    report["companies"][ticker] = {"available": company["available"], "market": quote,
        "comparisons": company["metric_context"], "risk_titles": [card["title"] for card in (cards or company["risk_cards"])],
        "ask_source": answer["source"], "ask_sections": answer["sections"]}
print(json.dumps(report, indent=2))
