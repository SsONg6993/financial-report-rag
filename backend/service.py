"""Thin product orchestration over existing financial services and SQLite storage."""

import json
import logging
import os
import re
import threading
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from backend.disclosures import fetch_disclosures
from backend.quarterly import quarter_facts, quarterly_changes
from backend.suggestions import CATEGORIES, suggested_theses
from backend.tickers import enrich_cached_classes
from src.ask import answer_question
from src.config import AppConfig
from src.decision import JevDecisionProvider
from src.local_store import LocalStore, utc_now
from src.market import YahooFinanceProvider
from src.portfolios import (
    BY_ID,
    INSTITUTIONS,
    PortfolioSnapshot,
    Sec13FProvider,
    compare_portfolios,
    disclosure_freshness,
    fetch_ark_holdings,
)
from src.sec import normalize_ticker
from src.thesis import evaluate_thesis
from src.thesis_research import (
    company_changes,
    company_rows,
    comparable_filings,
    filing_chunks,
    filing_language_changes,
    lexical_evidence,
    load_company,
)

# Request-triggered background refresh, separately cached per source. No hidden cron.
REFRESH_SECONDS = {
    "market": 300,
    "ark": 86400,
    "insiders": 1800,
    "ownership": 3600,
    "portfolio": 21600,
    "company": 21600,
    "oge": 86400,
}


class ResearchService:
    def __init__(self, store: LocalStore | None = None):
        self.store = store or LocalStore(
            os.getenv("THESISLENS_DB", "data/local/thesislens.sqlite3")
        )
        self.config = AppConfig.from_env()
        self._inflight: set[tuple[str, str]] = set()
        self._lock = threading.Lock()

    def cache_state(self, kind: str, key: str) -> dict:
        cached = self.store.snapshots("refresh", f"{kind}:{key}")
        state = cached[0] if cached else {}
        saved = state.get("checked_at")
        try:
            age = (
                (datetime.now(UTC) - datetime.fromisoformat(saved)).total_seconds()
                if saved
                else float("inf")
            )
        except ValueError:
            age = float("inf")
        return {
            **state,
            "stale": age > REFRESH_SECONDS[kind],
            "ttl_seconds": REFRESH_SECONDS[kind],
        }

    def schedule(self, background, kind: str, key: str):
        if os.getenv("THESISLENS_OFFLINE", "false").lower() == "true":
            return
        state = self.cache_state(kind, key)
        token = (kind, key)
        with self._lock:
            if not state["stale"] or token in self._inflight:
                return
            self._inflight.add(token)
        background.add_task(self.refresh, kind, key)

    def refresh(self, kind: str, key: str):
        try:
            warnings = []
            if kind in {"portfolio", "ark"}:
                institution = BY_ID[key]
                provider = Sec13FProvider()
                snapshots = (
                    [fetch_ark_holdings()]
                    if kind == "ark"
                    else list(provider.latest_two(institution))
                )
                snapshots = [s for s in snapshots if s is not None]
                if kind != "ark":
                    try:
                        provider.resolve_tickers(snapshots)
                    except Exception:  # noqa: BLE001 - optional enrichment does not gate holdings.
                        warnings.append(
                            "SEC ticker enrichment unavailable; unmapped holdings remain unnamed tickers."
                        )
                for snapshot in snapshots:
                    self.store.save_snapshot(
                        "portfolio", key, snapshot.reporting_period, snapshot.to_dict()
                    )
            elif kind == "company":
                company, warnings = load_company(
                    key, self.store, refresh=True, include_market=False
                )
                if not company:
                    raise RuntimeError("SEC company data unavailable")
                for filing in comparable_filings(company.get("filings", [])):
                    try:
                        filing_chunks(filing, self.store)
                    except Exception:  # noqa: BLE001 - parsed text is independent of structured facts.
                        warnings.append(
                            "Filing evidence unavailable; structured analytics remain available."
                        )
                enrich_cached_classes(self.store, key)
            elif kind == "market":
                company = self.cached_company(key)
                if company:
                    market = asdict(YahooFinanceProvider().snapshot(key))
                    if market.get("error"):
                        raise RuntimeError(market["error"])
                    company.update(market=market, market_as_of=utc_now())
                    self.store.save_snapshot("company", key, "current", company)
            elif kind in {"insiders", "ownership"}:
                self.store.save_snapshot(
                    kind, key, "current", fetch_disclosures(key, kind)
                )
            elif kind == "oge":
                # Existing official disclosure parser is deliberately kept separate.
                from src.public_disclosures import fetch_oge_disclosure

                payload = fetch_oge_disclosure()
                self.store.save_snapshot("oge", key, "current", payload)
            self.store.save_snapshot(
                "refresh",
                f"{kind}:{key}",
                "current",
                {"checked_at": utc_now(), "error": None, "warnings": warnings},
            )
        except Exception as exc:  # noqa: BLE001 - source boundary preserves stale usable data.
            # Persist check failure to avoid hammering unavailable/auth-restricted sources.
            self.store.save_snapshot(
                "refresh",
                f"{kind}:{key}",
                "current",
                {
                    "checked_at": utc_now(),
                    "error": f"{type(exc).__name__}: {str(exc)[:180]}",
                    "warnings": [],
                },
            )
        finally:
            with self._lock:
                self._inflight.discard((kind, key))

    def cached_company(self, ticker: str) -> dict | None:
        data = self.store.snapshots("company", normalize_ticker(ticker))
        return data[0] if data else None

    def portfolios(self, key: str) -> list[PortfolioSnapshot]:
        # Legacy snapshots were keyed by accession; the API uses reporting period.
        # The same filing can therefore exist under two cache keys, not two periods.
        unique = {}
        for row in self.store.snapshots("portfolio", key):
            snapshot = PortfolioSnapshot.from_dict(row)
            token = (snapshot.source_type, snapshot.reporting_period)
            old = unique.get(token)
            quality = (
                snapshot.filing_date,
                sum(bool(h.ticker_source) for h in snapshot.holdings),
            )
            old_quality = (
                (old.filing_date, sum(bool(h.ticker_source) for h in old.holdings))
                if old
                else None
            )
            if old is None or quality > old_quality:
                unique[token] = snapshot
        return sorted(unique.values(), key=lambda s: s.reporting_period, reverse=True)

    def investor(self, key: str) -> dict:
        institution = BY_ID[key]
        snapshots = self.portfolios(key)
        latest = snapshots[0] if snapshots else None
        state = self.cache_state("ark" if key == "ark" else "portfolio", key)
        freshness = (
            disclosure_freshness(latest.reporting_period, source_type=latest.source_type)
            if latest
            else "Data unavailable"
        )
        if key == "ark" and latest and state.get("error"):
            state = {**state, "stale": True}
            freshness = f"Stale cached snapshot · holdings date {latest.reporting_period}"
        return {
            **asdict(institution),
            "style_tags": institution.style.split(" / "),
            "followed": key in self.store.follows(),
            "available": bool(latest),
            "latest_period": latest.reporting_period if latest else None,
            "filing_date": latest.filing_date if latest else None,
            "source_url": latest.source_url if latest else None,
            "freshness": freshness,
            "refresh": state,
            "holdings": [asdict(h) for h in latest.holdings] if latest else [],
            "changes": [
                {**c, "pct_change": c["share_change_pct"]}
                for c in compare_portfolios(snapshots[1], latest)
            ]
            if len(snapshots) > 1
            else [],
            "timeline": [
                {
                    "period": s.reporting_period,
                    "filing_date": s.filing_date,
                    "source_url": s.source_url,
                }
                for s in snapshots[:8]
            ],
            "notes": ([latest.notes] if isinstance(latest.notes, str) else latest.notes)
            if latest
            else [
                "No usable disclosure cached. Refresh is attempted when this profile is opened."
            ],
            "rationale": "No sourced investor rationale available.",
        }

    def investors(self) -> list[dict]:
        return [self.investor(i.id) for i in INSTITUTIONS]

    def chunks(self, ticker: str) -> list[dict]:
        company = self.cached_company(ticker) or {}
        filings = comparable_filings(company.get("filings", []))
        accession = filings[0]["accession_number"] if filings else None
        snapshots = self.store.snapshots("filing_chunks", ticker)
        snapshot = next(
            (
                s
                for s in snapshots
                if s.get("filing", {}).get("accession_number") == accession
            ),
            None,
        )
        return snapshot.get("chunks", []) if snapshot else []

    def company(self, ticker: str) -> dict:
        ticker = normalize_ticker(ticker)
        data = self.cached_company(ticker)
        radar = []
        for institution in self.investors():
            holdings = [
                h
                for h in institution["holdings"]
                if h["ticker"] == ticker and not h["put_call"]
            ]
            if holdings:
                radar.append(
                    {
                        "text": f"Disclosed by {institution['name']}",
                        "period": institution["latest_period"],
                        "source_url": institution["source_url"],
                    }
                )
        if ticker in self.store.watchlist():
            radar.append({"text": "On your watchlist", "period": "", "source_url": ""})
        if not data:
            return {
                "ticker": ticker,
                "available": False,
                "name": ticker,
                "warnings": [
                    "Company data not yet available. A background refresh is attempted; retry shortly."
                ],
                "radar": radar,
                "suggestions": [],
                "changes": [],
                "theses": [],
                "risks": [],
                "quarterly": [],
                "templates": CATEGORIES,
                "watchlisted": ticker in self.store.watchlist(),
                "refresh": self.cache_state("company", ticker),
            }
        financials = sorted(data.get("financials", []), key=lambda r: r["fiscal_year"])
        annual = financials[-1] if financials else {}
        quarters = []
        path = Path("data/cache") / ticker / "companyfacts.json"
        if path.exists():
            quarters = quarter_facts(json.loads(path.read_text(encoding="utf-8")))
        chunks = self.chunks(ticker)
        suggestions = suggested_theses(data, chunks)
        ignored = self.store.snapshots("ignored_suggestions", ticker)
        ignored_ids = ignored[0].get("ids", []) if ignored else []
        suggestions = [s for s in suggestions if s["id"] not in ignored_ids]
        changes = quarterly_changes(quarters)
        if not changes:
            changes = [
                {**c, "comparison": "annual (quarterly comparison unavailable)"}
                for c in company_changes(data)
            ]
        snapshots = self.store.snapshots("filing_chunks", ticker)
        filings = comparable_filings(data.get("filings", []))
        if len(filings) > 1:
            previous = next(
                (
                    s.get("chunks", [])
                    for s in snapshots
                    if s.get("filing", {}).get("accession_number")
                    == filings[1]["accession_number"]
                ),
                [],
            )
            for change in filing_language_changes(previous, chunks):
                changes.append(
                    {
                        "category": change["category"],
                        "text": change["text"],
                        "evidence": [
                            e
                            for e in (change.get("previous"), change.get("current"))
                            if e and e.get("text")
                        ],
                    }
                )
        risk_chunks = [
            c
            for c in chunks
            if "risk" in (c.get("section", "") + c.get("section_title", "")).lower()
        ]
        if not risk_chunks:
            risk_chunks = [
                c
                for c in lexical_evidence(
                    "risk factors material risks regulation export restrictions supply chain",
                    chunks,
                    5,
                )
                if any(
                    term in c["text"].lower()
                    for term in ("risk factors", "risks", "export restrictions")
                )
            ]
        return {
            "ticker": ticker,
            "available": True,
            "name": (
                data.get("market", {}).get("company_name")
                or (data.get("filings") or [{}])[0].get("company")
                or ticker
            ),
            "market": data.get("market", {}),
            "market_as_of": data.get("market_as_of", ""),
            "annual": annual,
            "quarterly": quarters[-8:],
            "radar": radar,
            "suggestions": suggestions,
            "changes": changes,
            "theses": self.theses(ticker),
            "risks": [{**c, "text": c["text"][:800]} for c in risk_chunks[:3]],
            "templates": CATEGORIES,
            "watchlisted": ticker in self.store.watchlist(),
            "warnings": data.get("provider_warnings", []),
            "loaded_at": data.get("loaded_at"),
            "refresh": self.cache_state("company", ticker),
        }

    def theses(self, ticker: str) -> list[dict]:
        return [
            {**t, "history": self.store.history(t["id"])}
            for t in self.store.theses(ticker)
        ]

    def find_thesis(self, thesis_id: str) -> dict | None:
        with self.store.connect() as db:
            row = db.execute(
                "SELECT payload FROM theses WHERE id=?", (thesis_id,)
            ).fetchone()
        return json.loads(row[0]) if row else None

    def evaluate(self, thesis: dict) -> dict:
        company = self.cached_company(thesis["ticker"]) or {}
        chunks = lexical_evidence(thesis["text"], self.chunks(thesis["ticker"]))
        judge = (
            JevDecisionProvider(self.config.typesafe_api_key, self.config.jev_model)
            if self.config.enable_jev and self.config.typesafe_api_key
            else None
        )
        old = self.store.history(thesis["id"])
        previous = old[-1].get("current_evidence", []) if old else []
        result = evaluate_thesis(
            thesis,
            company_rows(company),
            chunks,
            previous,
            judge,
            self.config.jev_confidence_threshold,
        )
        self.store.record_evaluation(thesis, result)
        return {**thesis, **result, "history": self.store.history(thesis["id"])}

    def home(self) -> dict:
        investors = self.investors()
        activity = []
        company_holders: dict[str, list[dict]] = {}
        for investor in investors:
            for change in investor["changes"]:
                if change["activity"] != "UNCHANGED":
                    activity.append(
                        {
                            **change,
                            "institution": investor["name"],
                            "institution_id": investor["id"],
                            "source_type": investor["source_type"],
                            "freshness": investor["freshness"],
                        }
                    )
            for holding in investor["holdings"]:
                if holding["ticker"] and not holding["put_call"]:
                    company_holders.setdefault(holding["ticker"], []).append(investor)
        activity.sort(
            key=lambda r: (r.get("filing_date", ""), bool(r.get("ticker"))),
            reverse=True,
        )
        ideas = []
        for ticker, holders in sorted(
            company_holders.items(), key=lambda r: (-len(r[1]), r[0])
        )[:6]:
            company = self.cached_company(ticker) or {}
            annual = max(
                company.get("financials", []),
                key=lambda r: r["fiscal_year"],
                default={},
            )
            followed = sum(h["followed"] for h in holders)
            reasons = [
                f"Disclosed by {len(holders)} supported institution(s); {followed} followed"
            ]
            if annual.get("free_cash_flow") is not None:
                reasons.append(
                    f"FY{annual['fiscal_year']} free cash flow: ${annual['free_cash_flow'] / 1e9:.2f}B"
                )
            ideas.append(
                {
                    "ticker": ticker,
                    "reasons": reasons,
                    "source_url": holders[0]["source_url"],
                    "period": holders[0]["latest_period"],
                    "watchlisted": ticker in self.store.watchlist(),
                }
            )
        watchlist = []
        for ticker in self.store.watchlist():
            theses = self.store.theses(ticker)
            watchlist.append(
                {
                    "ticker": ticker,
                    "tracked": len(theses),
                    "attention": sum(
                        t["status"] in {"WEAKENED", "UNCERTAIN"} for t in theses
                    ),
                    "available": bool(self.cached_company(ticker)),
                }
            )
        disclosures = []
        with self.store.connect() as db:
            disclosure_tickers = [
                r[0]
                for r in db.execute(
                    "SELECT DISTINCT entity_id FROM snapshots WHERE kind IN ('insiders','ownership')"
                )
            ]
        for ticker in disclosure_tickers:
            for kind in ("insiders", "ownership"):
                for payload in self.store.snapshots(kind, ticker)[:1]:
                    disclosures.extend(payload.get("records", []))
        return {
            "activity": activity[:12],
            "ideas": ideas,
            "watchlist": watchlist,
            "investors": investors,
            "recent_disclosures": disclosures[:8],
            "freshness_policy": REFRESH_SECONDS,
            "as_of": utc_now(),
        }

    def ask(self, question: str, ticker: str) -> dict:
        query = question.lower()
        if re.search(r"\bwhy\b", query) and any(key in query for key in BY_ID):
            matched = next(i for i in INSTITUTIONS if i.id in query)
            return {
                "answer": f"There is no sourced {matched.name} explanation in the available data. A reported position change does not establish motive. Company-level context is separate ThesisLens analysis; open Research to investigate financial trends and filing evidence.",
                "evidence": [],
                "source": "deterministic safety guard",
            }
        symbols = re.findall(r"\b[A-Z]{1,5}\b", question)
        target = next(
            (s for s in reversed(symbols) if s not in {"FCF", "SEC", "RAG"}), ticker
        )
        if "new" in query and ("fcf" in query or "free cash flow" in query):
            evidence = []
            for activity in self.home()["activity"]:
                if activity["activity"] != "NEW" or not activity["ticker"]:
                    continue
                data = self.cached_company(activity["ticker"]) or {}
                row = max(
                    data.get("financials", []),
                    key=lambda r: r["fiscal_year"],
                    default={},
                )
                if (row.get("free_cash_flow") or 0) > 0:
                    evidence.append(
                        {
                            "text": f"{activity['ticker']}: newly disclosed by {activity['institution']}; FY{row['fiscal_year']} positive FCF ${row['free_cash_flow']:,.0f}. Positive FCF is not a strength rating.",
                            "period": activity["reporting_period"],
                            "source_url": row.get("source_url", ""),
                        }
                    )
            return {
                "answer": "\n\n".join(e["text"] for e in evidence)
                or "No newly disclosed, verified ticker with cached positive FCF was found in the limited activity feed. Missing fundamentals and incomplete mappings prevent a complete screen.",
                "evidence": evidence,
                "source": "Python disclosure/fundamentals screen",
            }
        if any(
            word in query
            for word in ("investors", "disclose", "exposure", "compare berkshire")
        ):
            explicit = [i.id for i in INSTITUTIONS if i.id in query]
            keys = explicit or self.store.follows()
            evidence = []
            for key in keys:
                if key not in BY_ID:
                    continue
                investor = self.investor(key)
                for holding in investor["holdings"]:
                    if holding["ticker"] == target:
                        text = f"{investor['name']} reported {holding['shares']:,.0f} shares of {holding['issuer']} {holding['put_call']}; {holding['weight']:.2%} of its disclosed table. Filed {investor['filing_date']}."
                        evidence.append(
                            {
                                "text": text,
                                "period": investor["latest_period"],
                                "source_url": investor["source_url"],
                            }
                        )
            return {
                "answer": "\n\n".join(
                    e["text"] + " Reporting period " + e["period"] + "."
                    for e in evidence
                )
                or "No verified matching holdings are available in the followed institutions’ cached disclosures. Ticker mapping is incomplete; this is not proof of absence.",
                "evidence": evidence,
                "source": "Verified disclosure lookups",
            }
        if "thesis" in query or "theses" in query:
            suggestions = self.company(target)["suggestions"]
            return {
                "answer": "\n\n".join(
                    s["text"] + " " + s["support_condition"] for s in suggestions
                )
                or "No sourced company evidence is cached yet. Open Research and retry after refresh.",
                "evidence": [e for s in suggestions for e in s["evidence"]],
                "source": "evidence-backed templates",
            }
        if "what changed" in query:
            changes = self.company(target)["changes"]
            return {
                "answer": "\n\n".join(c["text"] for c in changes)
                or "No comparable sourced changes available.",
                "evidence": [e for c in changes for e in c.get("evidence", [])],
                "source": "Python comparisons",
            }
        answer, evidence = answer_question(
            question,
            target,
            self.store,
            self.config,
            self.config.ollama_model,
            self.retrieve,
        )
        return {
            "answer": answer,
            "evidence": evidence,
            "source": "Existing bounded research workflow",
        }

    def retrieve(self, question: str, filing: dict, chunks: list[dict]) -> list[dict]:
        """Reuse an existing local hybrid index; never gate research on model installation."""
        from src.retriever import Retriever, collection_name
        from src.search import FilingSearch

        retriever = None
        try:
            retriever = Retriever(None, Path(self.config.qdrant_path))
            name = collection_name(filing, self.config.embedding_model)
            if retriever.has_index(name):
                from src.embeddings import Embeddings

                retriever.embeddings = Embeddings(self.config.embedding_model)
                return FilingSearch(retriever, name, chunks).search(question)
        except Exception as exc:  # noqa: BLE001 - index/model availability must not gate retrieval.
            logging.getLogger(__name__).warning(
                "Hybrid retrieval unavailable (%s); using BM25", type(exc).__name__
            )
        finally:
            if retriever is not None:
                retriever.client.close()
        return lexical_evidence(question, chunks)
