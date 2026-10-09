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
from backend.entity_registry import TrackedEntityRegistry
from backend.intelligence import IntelligenceService
from backend.period_facts import financial_context, quarterly_comparisons
from backend.quarterly import quarter_facts, quarterly_changes
from backend.research_context import comparisons, risk_cards, structured_answer
from backend.suggestions import CATEGORIES, suggested_theses
from backend.tickers import enrich_cached_classes
from src.ask import answer_question
from src.ask_intent import AskIntent, route_ask
from src.company_directory import CompanyDirectory
from src.config import AppConfig
from src.decision import JevDecisionProvider
from src.entry_price import estimate_entry_price
from src.llm import generate_general_answer
from src.local_store import LocalStore, utc_now
from src.market import ResilientMarketProvider
from src.portfolio_overlap import analyze_overlap
from src.portfolios import (
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
        self.registry = TrackedEntityRegistry(self.store)
        self._inflight: set[tuple[str, str]] = set()
        self._lock = threading.Lock()
        from backend.market_pulse.service import MarketPulseService

        self.market_pulse = MarketPulseService(self)
        self.intelligence = IntelligenceService(self)
        from backend.public_updates import (
            OfficialDisclosureProvider,
            RSSPublicUpdateProvider,
            WebsiteFeedProvider,
        )

        self.public_providers = {
            "rss": RSSPublicUpdateProvider(self.market_pulse),
            "official_disclosure": OfficialDisclosureProvider(self),
            "website": WebsiteFeedProvider(),
        }

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
                institution = self.registry.get(key)
                if institution is None:
                    raise ValueError("Investor not found")
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
                    raise RuntimeError(
                        "; ".join(warnings)
                        or "No supported SEC filings or facts available"
                    )
                for filing in comparable_filings(company.get("filings", [])):
                    try:
                        filing_chunks(filing, self.store)
                    except Exception:  # noqa: BLE001 - parsed text is independent of structured facts.
                        warnings.append(
                            "Filing evidence unavailable; structured analytics remain available."
                        )
                enrich_cached_classes(self.store, key)
                chunks = self.chunks(key)
                selected = [
                    c
                    for c in chunks
                    if "risk"
                    in (c.get("section", "") + c.get("section_title", "")).lower()
                ]
                self.store.save_snapshot(
                    "risk_summary",
                    key,
                    "current",
                    {
                        "cards": risk_cards(selected, self.config),
                        "filing": (company.get("filings") or [{}])[0].get(
                            "accession_number"
                        ),
                    },
                )
            elif kind == "market":
                market = asdict(ResilientMarketProvider().snapshot(key))
                if market.get("error") or not market.get("price"):
                    raise RuntimeError(market.get("error") or "No valid quote returned")
                self.store.save_snapshot("market", key, "current", market)
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
        institution = self.registry.get(key)
        if institution is None:
            raise ValueError("Investor not found")
        snapshots = self.portfolios(key)
        latest = snapshots[0] if snapshots else None
        state = self.cache_state("ark" if key == "ark" else "portfolio", key)
        freshness = (
            disclosure_freshness(
                latest.reporting_period, source_type=latest.source_type
            )
            if latest
            else "Data unavailable"
        )
        if key == "ark" and latest and state.get("error"):
            state = {**state, "stale": True}
            freshness = (
                f"Stale cached snapshot · holdings date {latest.reporting_period}"
            )
        previous = snapshots[1] if len(snapshots) > 1 else None
        previous_by_key = (
            {holding.key: holding for holding in previous.holdings} if previous else {}
        )
        holdings = []
        for holding in latest.holdings if latest else []:
            ticker_verified = bool(
                holding.ticker
                and (
                    holding.ticker_source
                    or latest.source_type == "Official ARKK daily fund holdings"
                    or "unambiguous exact issuer-name matches" in str(latest.notes)
                )
            )
            market_rows = (
                self.store.snapshots("market", holding.ticker)
                if ticker_verified
                else []
            )
            holdings.append(
                {
                    **asdict(holding),
                    "ticker_verified": ticker_verified,
                    "entry_price_estimate": estimate_entry_price(
                        holding,
                        previous_by_key.get(holding.key),
                        previous,
                        latest,
                        market_rows[0] if market_rows else None,
                    ),
                }
            )
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
            "holdings": holdings,
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
            "notes": [
                note
                for note in (
                    *(
                        (
                            [latest.notes]
                            if isinstance(latest.notes, str)
                            else latest.notes
                        )
                        if latest
                        else [
                            "No usable disclosure cached. Refresh is attempted when this profile is opened."
                        ]
                    ),
                    institution.data_quality_notes,
                    institution.source_notes,
                )
                if note
            ],
            "rationale": "No sourced investor rationale available.",
        }

    def investors(self) -> list[dict]:
        return [self.investor(i.id) for i in self.registry.all()]

    def portfolio_overlap(
        self, institution_ids: list[str], period: str | None = None
    ) -> dict:
        unique_ids = list(dict.fromkeys(institution_ids))
        if not 2 <= len(unique_ids) <= 5:
            raise ValueError("Select between 2 and 5 distinct institutions.")
        missing = [key for key in unique_ids if self.registry.get(key) is None]
        if missing:
            raise ValueError("Unknown institution: " + ", ".join(missing))
        return analyze_overlap(
            {key: self.portfolios(key) for key in unique_ids}, period=period
        )

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
        identity = CompanyDirectory().cached_ticker(ticker)
        company_refresh = self.cache_state("company", ticker)
        saved_market = self.store.snapshots("market", ticker)
        market = dict(
            saved_market[0] if saved_market else (data or {}).get("market", {})
        )
        market_state = self.cache_state("market", ticker)
        quote_time = market.get("quote_as_of") or (data or {}).get("market_as_of")
        if market.get("price") is not None:
            market["status"] = (
                "cached"
                if market_state["stale"]
                or market_state.get("error")
                or not saved_market
                else market.get("status", "delayed")
            )
        else:
            market["status"] = "unavailable"
        market["quote_as_of"] = quote_time
        market["stale"] = market["status"] == "cached"
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
            failure = str(company_refresh.get("error") or "")
            availability = (
                "unknown_symbol"
                if f"Ticker {ticker} was not found in the SEC ticker list" in failure
                else "missing_filings"
                if "No supported SEC filings or facts available" in failure
                else "provider_error"
                if failure
                else "loading"
                if not company_refresh.get("checked_at")
                else "missing_filings"
            )
            return {
                "ticker": ticker,
                "available": False,
                "name": identity["name"] if identity else ticker,
                "identity": identity,
                "availability_status": availability,
                "market": market,
                "market_as_of": quote_time or "",
                "metric_context": [],
                "risk_cards": [],
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
                "refresh": company_refresh,
            }
        financials = sorted(data.get("financials", []), key=lambda r: r["fiscal_year"])
        annual = financials[-1] if financials else {}
        quarters = []
        facts_payload = {}
        path = (
            Path(os.getenv("THESISLENS_CACHE_DIR", "data/cache"))
            / ticker
            / "companyfacts.json"
        )
        if path.exists():
            facts_payload = json.loads(path.read_text(encoding="utf-8"))
            quarters = quarter_facts(facts_payload)
        period_context = financial_context(
            facts_payload, data.get("filings", []), annual
        )
        chunks = self.chunks(ticker)
        overview_chunk = next(
            (
                chunk
                for chunk in chunks
                if "business"
                in str(chunk.get("section_title", chunk.get("section", ""))).lower()
                and chunk.get("source_url")
                and chunk.get("text")
            ),
            None,
        )
        suggestions = suggested_theses(data, chunks)
        ignored = self.store.snapshots("ignored_suggestions", ticker)
        ignored_ids = ignored[0].get("ids", []) if ignored else []
        suggestions = [s for s in suggestions if s["id"] not in ignored_ids]
        changes = quarterly_changes(quarters)
        if period_context["kind"] == "quarterly" and not any(
            r["period"] == period_context["end"] and r.get("revenue") is not None
            for r in quarters
        ):
            changes = []
        if not changes and period_context["kind"] == "annual":
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
        saved_risks = self.store.snapshots("risk_summary", ticker)
        risk_summary = (
            saved_risks[0].get("cards", [])
            if saved_risks
            and saved_risks[0].get("filing")
            == (filings[0].get("accession_number") if filings else None)
            else []
        )
        # Quarterly risk sections often reference the annual filing rather than
        # repeat every risk. Include supported risk language elsewhere in the
        # cached filing, keeping its actual date and full original excerpt.
        deterministic_risks = risk_cards(risk_chunks + chunks)
        if len(risk_summary) < len(deterministic_risks):
            risk_summary = deterministic_risks
        return {
            "ticker": ticker,
            "available": True,
            "identity": identity,
            "availability_status": (
                "provider_error"
                if company_refresh.get("error")
                else "filings_only"
                if not financials
                else "ready"
            ),
            "overview": {
                "text": overview_chunk["text"][:450],
                "source_url": overview_chunk["source_url"],
                "period": overview_chunk.get("period", ""),
            }
            if overview_chunk
            else None,
            "filing_timeline": [
                {
                    "form": filing["form"],
                    "report_date": filing["report_date"],
                    "filing_date": filing["filing_date"],
                    "source_url": filing["source_url"],
                }
                for filing in data.get("filings", [])[:8]
            ],
            "name": (
                data.get("market", {}).get("company_name")
                or (data.get("filings") or [{}])[0].get("company")
                or ticker
            ),
            "market": market,
            "market_as_of": quote_time or "",
            "annual": annual,
            "metric_context": comparisons(financials)
            if period_context["kind"] == "annual"
            else quarterly_comparisons(period_context),
            "financial_context": period_context,
            "risk_cards": risk_summary or deterministic_risks,
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
            "refresh": company_refresh,
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

    def ask(
        self,
        question: str,
        ticker: str | None = None,
        mode: str = "auto",
    ) -> dict:
        route = route_ask(question, mode, ticker)
        metadata = {
            "intent": route.intent.value,
            "mode": mode,
            "configuration_error": None,
            "privacy": "No private workspace data was sent to an external model.",
        }
        if route.intent is AskIntent.GENERAL:
            result = generate_general_answer(
                question,
                self.config.ollama_model,
                self.config.ollama_base_url,
                self.config.allow_remote_llm,
            )
            if not result.available:
                return {
                    **metadata,
                    "answer": result.error or "General AI is unavailable.",
                    "evidence": [],
                    "source": "General AI configuration",
                    "configuration_error": result.error,
                }
            privacy = (
                "The question was sent to an explicitly enabled configured LLM endpoint; "
                "no portfolio, filing, watchlist, or database content was included."
                if self.config.allow_remote_llm
                else "The question was sent only to the configured local Ollama service; "
                "no portfolio, filing, watchlist, or database content was included."
            )
            return {
                **metadata,
                "answer": result.answer or "",
                "evidence": [],
                "source": f"General AI · {self.config.ollama_model}",
                "privacy": privacy,
            }
        if route.intent is AskIntent.UNSUPPORTED:
            return {
                **metadata,
                "answer": (
                    "This request is unavailable in the selected mode. ThesisLens cannot "
                    "access private accounts or execute transactions. For a general topic, "
                    "switch to General mode; for research, name a company, filing, or investor."
                ),
                "evidence": [],
                "source": "Intent and privacy guard",
            }
        if route.intent is AskIntent.CURRENT_PUBLIC_INFORMATION:
            result = self.market_pulse.answer(question, route.ticker or "")
            return {**result, **metadata}
        if route.intent is AskIntent.PORTFOLIO_ANALYSIS and not route.ticker:
            return {**self._portfolio_overview(question), **metadata}
        if not route.ticker:
            return {
                **metadata,
                "answer": (
                    "A verified company context is required for financial research. "
                    "Include a ticker such as AAPL or select Auto/General for a general question."
                ),
                "evidence": [],
                "source": "Research context guard",
            }
        return {**self._ask_research(question, route.ticker), **metadata}

    def _portfolio_overview(self, question: str) -> dict:
        query = question.lower()
        aliases = {
            "buffett": "berkshire",
            "ackman": "pershing",
            "wood": "ark",
            "burry": "scion",
            "tepper": "appaloosa",
            "druckenmiller": "duquesne",
        }
        selected = [
            item.id
            for item in self.registry.all()
            if re.search(r"\b" + re.escape(item.id) + r"\b", query)
            or any(alias in query and item.id == key for alias, key in aliases.items())
        ]
        selected = list(dict.fromkeys(selected))
        if len(selected) >= 2:
            data = self.portfolio_overlap(selected[:5])
            summary = data["summary"]
            jaccard = (
                f"{summary['jaccard']:.1%}" if summary["jaccard"] is not None else "N/A"
            )
            answer = (
                f"The selected disclosures contain {summary['shared_count']} security "
                f"identity/identities held by at least two managers and "
                f"{summary['common_count']} common to every selected manager. "
                f"Jaccard similarity is {jaccard}. This describes reported overlap, "
                "not shared intent."
            )
            evidence = [
                {
                    "text": f"{row['name']}: {row['holding_count']} disclosed holdings; "
                    f"reporting period {row.get('reporting_period', 'unavailable')}.",
                    "period": row.get("reporting_period", ""),
                    "source_url": row.get("source_url", ""),
                }
                for row in data["institutions"]
            ]
            return {
                "answer": answer,
                "evidence": evidence,
                "source": "Verified class-aware disclosure overlap",
            }
        return {
            "answer": (
                "Name two to five supported institutions to compare, or include a verified "
                "ticker to inspect a disclosed position."
            ),
            "evidence": [],
            "source": "Institutional portfolio routing",
        }

    def _ask_research(self, question: str, ticker: str) -> dict:
        if re.search(
            r"\b(public updates?|official updates?|latest (?:insider|institutional) (?:activity|filings?))\b",
            question,
            re.IGNORECASE,
        ):
            category = (
                "insiders"
                if re.search(r"\binsider\b", question, re.IGNORECASE)
                else (
                    "institutions"
                    if re.search(r"\binstitutional\b", question, re.IGNORECASE)
                    else "public_updates"
                )
            )
            events = self.intelligence.feed(category, 20)["events"]
            ticker_events = [event for event in events if event["ticker"] == ticker]
            selected = (ticker_events or events)[:5]
            evidence = [
                {
                    "text": f"{event['headline']} Filed/published {event['published_at'][:10]}"
                    + (
                        f"; reporting period {event['reporting_period']}"
                        if event["reporting_period"]
                        else ""
                    ),
                    "source_url": event["source_url"],
                    "period": event["reporting_period"] or event["published_at"][:10],
                }
                for event in selected
            ]
            return {
                "answer": "\n\n".join(item["text"] for item in evidence)
                or "No matching dated official event is cached. This is not evidence of no real-world activity.",
                "evidence": evidence,
                "source": "Deterministic public-source event lookup",
            }
        symbols = re.findall(r"\b[A-Z][A-Z0-9.-]{0,11}\b", question)
        target = next(
            (
                s
                for s in reversed(symbols)
                if s not in {"FCF", "SEC", "RAG", "PE", "AI"}
            ),
            ticker,
        )
        if re.search(
            r"\b(news|macro events?|market pulse|oil prices?|ai news)\b|holdings.*exposure.*oil",
            question,
            re.IGNORECASE,
        ) and not re.search(
            r"\bwhy.*\b(buy|bought|sell|sold|reduce|reduced)\b", question, re.IGNORECASE
        ):
            return self.market_pulse.answer(question, target)
        company = self.company(target)
        query = question.lower()
        aliases = {
            "buffett": "berkshire",
            "ackman": "pershing",
            "wood": "ark",
            "burry": "scion",
            "tepper": "appaloosa",
            "druckenmiller": "duquesne",
        }
        named_id = next(
            (
                value
                for name, value in aliases.items()
                if re.search(r"\b" + name + r"\b", query)
            ),
            None,
        )
        investor = next(
            (
                i
                for i in self.registry.all()
                if re.search(r"\b" + re.escape(i.id) + r"\b", query) or i.id == named_id
            ),
            None,
        )
        if (
            not investor
            and re.search(r"\bwhy\b", query)
            and re.search(
                r"\b(buy|bought|sell|sold|reduce|reduced|increase|increased|exit|exited)\b",
                query,
            )
        ):
            return structured_answer(
                question,
                company,
                [],
                "No sourced investor explanation is available for this transaction. A reported position change alone does not establish the reason.",
                self.config,
                protected=True,
            )
        protected = bool(investor and re.search(r"\bwhy\b", query))
        if protected:
            portfolio = self.investor(investor.id)
            change = next(
                (c for c in portfolio["changes"] if c["ticker"] == target), None
            )
            evidence = []
            if change and change["activity"] != "UNCHANGED":
                description = change["activity"].lower()
                short = f"{investor.name}'s filing confirms a reported {target} position change ({description}), but the filing does not provide the reason. There is no sourced {investor.name} explanation in the available data."
                evidence = [
                    {
                        "text": f"Reported position change: {change['activity']}; share change {change.get('pct_change')}. Investor rationale is not supplied by the filing.",
                        "source_url": portfolio["source_url"],
                        "period": portfolio["latest_period"],
                    }
                ]
            else:
                short = f"There is no sourced {investor.name} explanation in the available data. A {target} position change could not be verified from the comparable cached disclosures; the filing does not provide the reason."
            return structured_answer(
                question, company, evidence, short, self.config, protected=True
            )
        if any(
            word in query
            for word in (
                "investors",
                "disclose",
                "exposure",
                "compare berkshire",
                "new",
            )
        ):
            original = self._ask_lookup(question, target)
            return structured_answer(
                question,
                company,
                original["evidence"],
                original["answer"][:650],
                self.config,
                protected=True,
            )
        if "thesis" in query or "idea" in query:
            short = (
                company["suggestions"][0]["text"]
                if company["suggestions"]
                else "There is not enough sourced evidence to suggest a tracking idea yet."
            )
            evidence = [e for s in company["suggestions"][:3] for e in s["evidence"]]
        elif "changed" in query or "change" in query:
            short = (
                " ".join(c["text"] for c in company["changes"][:2])
                or "No comparable sourced changes are available."
            )
            evidence = [
                e for c in company["changes"][:3] for e in c.get("evidence", [])
            ]
        else:
            evidence = lexical_evidence(question, self.chunks(target), 5)
            short = (
                f"The available {target} research includes dated financial facts and filing evidence."
                if company["available"]
                else f"Verified {target} company evidence is not cached yet."
            )
            if evidence:
                topics = [card["title"].lower() for card in risk_cards(evidence)[:3]]
                short = (
                    f"The retrieved {target} filing evidence highlights {', '.join(topics)}. Review these alongside the dated financial context below."
                    if topics
                    else f"Review {target}'s growth, cash generation, and the next comparable filing. The retrieved excerpts do not establish a specific risk conclusion."
                )
        return structured_answer(question, company, evidence, short, self.config)

    def _ask_lookup(self, question: str, ticker: str) -> dict:
        query = question.lower()
        if re.search(r"\bwhy\b", query) and any(
            i.id in query for i in self.registry.all()
        ):
            matched = next(i for i in self.registry.all() if i.id in query)
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
            explicit = [i.id for i in self.registry.all() if i.id in query]
            keys = explicit or self.store.follows()
            evidence = []
            for key in keys:
                if self.registry.get(key) is None:
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
