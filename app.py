"""ThesisLens: run with streamlit run app.py."""

import os
from dataclasses import asdict
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from src.config import AppConfig
from src.decision import JevDecisionProvider
from src.embeddings import Embeddings
from src.llm import generate_answer
from src.local_store import LocalStore
from src.portfolios import (
    ARK_URL,
    BY_ID,
    DISCLOSURE_NOTE,
    INSTITUTIONS,
    PortfolioSnapshot,
    Sec13FProvider,
    compare_portfolios,
    disclosure_freshness,
    enrich_sectors,
    fetch_ark_holdings,
)
from src.public_disclosures import (
    OGE_ANNUAL_NOTICE,
    OGE_SEARCH,
    OGE_TRUMP_PTR,
    fetch_oge_disclosure,
)
from src.retriever import Retriever, collection_name
from src.search import FilingSearch
from src.sec import normalize_ticker
from src.thesis import RULE_METRICS, evaluate_thesis, health_summary
from src.thesis_research import (
    company_changes,
    company_rows,
    comparable_filings,
    filing_chunks,
    filing_language_changes,
    lexical_evidence,
    load_company,
)
from src.valuation import DcfAssumptions, discounted_cash_flow, scenario_margin_default

load_dotenv()
CONFIG = AppConfig.from_env()
st.set_page_config(page_title="ThesisLens", page_icon="◉", layout="wide")


@st.cache_resource
def local_store(path: str):
    return LocalStore(path)


@st.cache_resource
def dense_retriever(path: str):
    return Retriever(None, store_dir=Path(path))


@st.cache_resource
def embeddings(model: str):
    return Embeddings(model)


def money(value):
    if value is None:
        return "Unavailable"
    for scale, label in ((1e12, "T"), (1e9, "B"), (1e6, "M")):
        if abs(value) >= scale:
            return f"${value / scale:,.2f}{label}"
    return f"${value:,.2f}"


def open_research(ticker):
    st.session_state.selected_ticker = ticker
    st.session_state.navigation = "Research"
    st.session_state.pending_company_load = ticker


def cached_company(ticker):
    rows = STORE.snapshots("company", ticker)
    return rows[0] if rows else {"ticker": ticker}


def portfolio_snapshots(entity_id):
    return sorted((PortfolioSnapshot.from_dict(row) for row in STORE.snapshots("portfolio", entity_id)),
                  key=lambda row: row.reporting_period, reverse=True)


def jev_provider():
    if not use_jev or not CONFIG.typesafe_api_key:
        return None
    return JevDecisionProvider(CONFIG.typesafe_api_key, CONFIG.jev_model)


def evidence_view(items):
    for index, item in enumerate(items, 1):
        period = item.get("period", item.get("year", "Period unavailable"))
        with st.expander(f"{item.get('section', item.get('source_type', 'Evidence'))} · {period} · excerpt {index}"):
            st.write(item.get("text", ""))
            if item.get("source_url"):
                st.link_button("Open source", item["source_url"])
            st.caption(f"{item.get('chunk_id', item.get('metric', ''))} · filed {item.get('filing_date', 'date unavailable')}")


def retrieve(query, filing, chunks):
    """Use hybrid when a compatible index exists; BM25 otherwise."""
    try:
        retriever = dense_retriever(CONFIG.qdrant_path)
        name = collection_name(filing, embedding_model)
        if retrieval_mode != "BM25" and retriever.has_index(name):
            retriever.embeddings = embeddings(embedding_model)
            reranker = None
            if use_reranker:
                from src.reranker import CrossEncoderReranker

                reranker = CrossEncoderReranker(reranker_model)
            return FilingSearch(retriever, name, chunks).search(
                query, top_k=top_k, mode=retrieval_mode, reranker=reranker)
    except Exception as exc:  # noqa: BLE001 - preserve lexical retrieval.
        st.session_state.retrieval_note = f"BM25 fallback: {type(exc).__name__}"
    return lexical_evidence(query, chunks, top_k)


def public_context(ticker):
    entries = []
    for entity_id in STORE.follows():
        if entity_id not in BY_ID:
            continue
        snapshots = portfolio_snapshots(entity_id)
        if not snapshots:
            continue
        current = snapshots[0]
        for holding in [row for row in current.holdings if row.ticker == ticker]:
            activity = "Reported position"
            prior = next((row for row in snapshots[1:] if row.reporting_period < current.reporting_period), None)
            if prior:
                change = next((row for row in compare_portfolios(prior, current)
                               if row["cusip"] == holding.cusip and row["put_call"] == holding.put_call), None)
                if change:
                    activity += " " + change["activity"].lower()
            entries.append({"institution": BY_ID[entity_id].name, "text": activity,
                            "period": current.reporting_period, "filing_date": current.filing_date,
                            "source_url": current.source_url})
    return entries


STORE = local_store(os.getenv("THESISLENS_DB", "data/local/thesislens.sqlite3"))
if st.session_state.get("pending_research"):
    open_research(st.session_state.pop("pending_research"))
with st.sidebar:
    st.title("ThesisLens")
    page = st.radio("Navigate", ["Home", "Research", "Public Portfolios", "Ask"], key="navigation")
    st.caption("Your thesis. Dated evidence. A clearer research agenda.")
    with st.expander("Advanced Settings"):
        retrieval_mode = st.selectbox("Retrieval mode", ["Hybrid", "BM25", "Dense"])
        top_k = st.slider("Evidence excerpts", 1, 10, 5)
        embedding_model = st.text_input("Embedding model", CONFIG.embedding_model)
        ollama_model = st.text_input("Ollama model", CONFIG.ollama_model)
        use_reranker = st.checkbox("Local reranker", False)
        reranker_model = st.text_input("Reranker model", "cross-encoder/ms-marco-MiniLM-L-6-v2")
        use_jev = st.checkbox("Jev thesis judgments", value=CONFIG.enable_jev)
        if use_jev and not CONFIG.typesafe_api_key:
            st.caption("Jev key unavailable; narrative judgments remain uncertain.")
        show_debug = st.checkbox("Show decision diagnostics", False)

if page == "Home":
    st.title("What changed in the companies you care about?")
    with st.form("watchlist_add"):
        ticker_input = st.text_input("Add a company to your watchlist", placeholder="AAPL")
        if st.form_submit_button("Add to watchlist"):
            try:
                STORE.watch(ticker_input)
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
    st.subheader("My Watchlist")
    if not STORE.watchlist():
        st.info("Add a company, write your thesis, and track the evidence over time.")
    for ticker in STORE.watchlist():
        company = cached_company(ticker)
        market, filings = company.get("market", {}), company.get("filings", [])
        with st.container(border=True):
            left, right = st.columns([4, 1])
            left.markdown(f"### {ticker} · {market.get('company_name') or ticker}")
            left.write(health_summary(STORE.theses(ticker)))
            left.caption(f"Price {money(market.get('price'))} · latest filing {filings[0]['filing_date'] if filings else 'not loaded'}")
            if market.get("price") is not None:
                left.caption(f"Price observed {company.get('market_as_of') or 'date unavailable; refresh sources'}")
            changes = company_changes(company)
            left.write(changes[0]["text"] if changes else "No verified period change loaded yet.")
            right.button("Research", key=f"home_{ticker}", on_click=open_research, args=(ticker,))
    st.subheader("What Changed")
    for ticker in STORE.watchlist():
        for change in company_changes(cached_company(ticker))[:3]:
            st.write(f"{ticker} · {change['text']}")
            st.markdown(f"[SEC facts · {change['current']['period']}]({change['current']['source_url']})")
    st.subheader("People & Institutions I Follow")
    for entity in INSTITUTIONS:
        saved = portfolio_snapshots(entity.id)
        st.write(f"{'●' if entity.id in STORE.follows() else '○'} {entity.name} · {entity.investor or entity.style}")
        st.caption(f"{entity.source_type} · {saved[0].reporting_period if saved else 'No snapshot loaded'}")
    st.caption("Public Financial Disclosures · Donald Trump · OGE reports are listed separately on Public Portfolios.")

elif page == "Research":
    st.title("Company Research")
    with st.form("company_search"):
        ticker_input = st.text_input("Company ticker", value=st.session_state.get("selected_ticker", "AAPL"))
        refresh = st.checkbox("Refresh public sources", False)
        load = st.form_submit_button("Load company evidence")
    try:
        ticker = normalize_ticker(ticker_input)
    except ValueError:
        ticker = st.session_state.get("selected_ticker", "AAPL")
        st.warning("Enter a valid ticker.")
    if load or st.session_state.get("pending_company_load") == ticker:
        st.session_state.pop("pending_company_load", None)
        st.session_state.selected_ticker = ticker
        with st.spinner("Loading SEC facts, filings, and available market data…"):
            _, errors = load_company(ticker, STORE, refresh)
        for error in errors:
            st.warning(error)
    company = cached_company(ticker)
    rows = company_rows(company)
    latest = rows[-1] if rows else None
    market, filings = company.get("market", {}), company.get("filings", [])
    st.subheader(f"{market.get('company_name') or ticker} · {ticker}")
    if latest:
        st.caption(f"Annual financial facts: FY{latest.fiscal_year} · sources loaded {company.get('loaded_at', 'date unavailable')}")
    if market.get("price") is not None:
        st.caption(f"Price observed {company.get('market_as_of') or 'date unavailable; refresh sources'}")
    for warning in company.get("provider_warnings", []):
        st.caption(warning)
    st.button("Add to watchlist", on_click=STORE.watch, args=(ticker,))
    for column, label, value in zip(st.columns(5), ["Price", "Market cap", "Revenue", "Net income", "FCF"],
                                    [market.get("price"), market.get("market_cap"), latest.revenue if latest else None,
                                     latest.net_income if latest else None, latest.free_cash_flow if latest else None]):
        column.metric(label, money(value))
    if filings:
        st.markdown(f"Latest filing: [{filings[0]['form']} · {filings[0]['report_date']} · filed {filings[0]['filing_date']}]({filings[0]['source_url']})")
    else:
        st.info("Load company evidence to begin.")
    st.subheader("My Investment Thesis")
    with st.form("new_thesis"):
        thesis_text = st.text_area("Your thesis point", placeholder="Gross margin will remain above 45%.")
        use_rule = st.checkbox("Add a quantitative threshold")
        col1, col2, col3 = st.columns(3)
        metric = col1.selectbox("Metric", list(RULE_METRICS), format_func=RULE_METRICS.get)
        comparison = col2.selectbox("Condition", [">=", ">", "<=", "<"])
        threshold = col3.number_input("Threshold (ratios as fractions, e.g. 0.45)", value=0.45)
        if st.form_submit_button("Save thesis point"):
            try:
                rule = {"metric": metric, "operator": comparison, "threshold": threshold} if use_rule else None
                STORE.save_thesis(ticker, thesis_text, rule)
                STORE.watch(ticker)
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
    theses = STORE.theses(ticker)
    if st.button("Evaluate thesis evidence", disabled=not theses or not rows):
        with st.spinner("Comparing structured facts and dated filing evidence…"):
            current_chunks, previous_chunks = [], []
            for i, filing in enumerate(comparable_filings(filings)):
                try:
                    chunks = filing_chunks(filing, STORE, CONFIG.chunk_size, CONFIG.chunk_overlap)
                    if i == 0:
                        current_chunks = chunks
                    else:
                        previous_chunks = chunks
                except Exception as exc:  # noqa: BLE001 - numeric rules still work.
                    st.warning(f"Filing evidence unavailable: {exc}")
            for thesis in theses:
                current = retrieve(thesis["text"], filings[0], current_chunks) if current_chunks else []
                previous = lexical_evidence(thesis["text"], previous_chunks, top_k)
                evaluation = evaluate_thesis(thesis, rows, current, previous, jev_provider(), CONFIG.jev_confidence_threshold)
                STORE.record_evaluation(thesis, evaluation)
        st.rerun()
    theses = STORE.theses(ticker)
    st.write(health_summary(theses))
    labels = {"STRENGTHENED": "✅ Strengthened", "STABLE": "➖ Stable", "WEAKENED": "⚠ Weakened",
              "UNCERTAIN": "? Uncertain", "NOT_EVALUATED": "Not evaluated"}
    for thesis in theses:
        with st.container(border=True):
            st.write(thesis["text"])
            st.caption(f"{labels[thesis['status']]} · created {thesis['created_at'][:10]} · evaluated {(thesis.get('last_evaluated_at') or 'never')[:10]}")
            st.write(thesis.get("explanation", ""))
            if thesis.get("confidence") is not None:
                st.caption(f"Decision confidence {thesis['confidence']:.2f} · {thesis.get('source', '')}")
            with st.expander("Supporting / Contradicting Evidence"):
                st.write("Supporting evidence")
                evidence_view(thesis.get("supporting_evidence", []))
                st.write("Contradicting evidence")
                evidence_view(thesis.get("contradicting_evidence", []))
                if not thesis.get("supporting_evidence") and not thesis.get("contradicting_evidence"):
                    st.caption("Relationship unresolved. Review retrieved evidence:")
                    evidence_view(thesis.get("current_evidence", []))
            with st.expander("Edit thesis / Timeline"):
                with st.form(f"edit_{thesis['id']}"):
                    edited = st.text_area("Thesis text", thesis["text"])
                    existing_rule = thesis.get("rule") or {}
                    enabled = st.checkbox("Quantitative rule", bool(existing_rule))
                    metric_edit = st.selectbox("Metric", list(RULE_METRICS), index=list(RULE_METRICS).index(existing_rule.get("metric", "gross_margin")), format_func=RULE_METRICS.get)
                    op_edit = st.selectbox("Condition", [">=", ">", "<=", "<"], index=[">=", ">", "<=", "<"].index(existing_rule.get("operator", ">=")))
                    value_edit = st.number_input("Threshold", value=float(existing_rule.get("threshold", 0.45)))
                    if st.form_submit_button("Save edit"):
                        STORE.save_thesis(ticker, edited, {"metric": metric_edit, "operator": op_edit, "threshold": value_edit} if enabled else None, thesis["id"])
                        st.rerun()
                history = STORE.history(thesis["id"])
                if history:
                    st.dataframe(pd.DataFrame([{"Evaluated": item["evaluated_at"], "Period": item.get("period", "See evidence"), "Status": item["status"], "Thesis": item["text"]} for item in history]), hide_index=True)
    st.subheader("Since Last Comparable Period")
    changes = company_changes(company)
    by_accession = {row["filing"]["accession_number"]: row["chunks"] for row in STORE.snapshots("filing_chunks", ticker)}
    comparable = comparable_filings(filings)
    if len(comparable) >= 2:
        changes += filing_language_changes(by_accession.get(comparable[1]["accession_number"], []), by_accession.get(comparable[0]["accession_number"], []))
    for change in changes:
        st.write(f"{change['category']} · {change['text']}")
        evidence_view([item for item in [change.get("previous"), change.get("current")] if item])
    if not changes:
        st.caption("Two comparable periods are required before reporting a change.")
    st.subheader("What should I investigate?")
    unresolved = [item for item in theses if item["status"] in {"UNCERTAIN", "WEAKENED", "NOT_EVALUATED"}]
    for item in unresolved:
        st.write(f"• Investigate the evidence and assumptions behind: {item['text']}")
    if st.button("Synthesize research checklist", disabled=not unresolved):
        context = [{"section": "User thesis", "text": str({"thesis": item["text"], "status": item["status"], "evidence": item.get("current_evidence", [])})} for item in unresolved]
        result = generate_answer("Create at most five research questions about unresolved evidence. Do not recommend trades or invent facts.", context, ollama_model, CONFIG.ollama_base_url)
        if result.available:
            st.write(result.answer)
        else:
            st.caption("Ollama unavailable; the checklist above remains available.")
    with st.expander("Public Disclosure Context"):
        context = public_context(ticker)
        if context:
            st.dataframe(pd.DataFrame(context), hide_index=True)
        else:
            st.caption("No verified ticker match in loaded followed portfolios. CUSIP-only holdings are not assumed to be absent.")
    with st.expander("Valuation"):
        if latest and latest.revenue:
            cols = st.columns(3)
            growth = cols[0].number_input("Revenue growth assumption", value=0.05)
            margin = cols[1].number_input("Operating margin assumption", value=scenario_margin_default(latest.operating_margin))
            discount = cols[2].number_input("Discount rate", value=0.10)
            terminal = st.number_input("Terminal growth", value=0.025)
            cash = st.number_input("Cash assumption", min_value=0.0, value=float(latest.cash or 0))
            debt = st.number_input("Debt assumption", min_value=0.0, value=float(latest.debt or 0))
            shares = st.number_input("Shares assumption", min_value=0.0, value=float(latest.shares_outstanding or 0))
            if any(value is None for value in (latest.cash, latest.debt, latest.shares_outstanding)):
                st.caption("Some SEC inputs are missing; review the explicit assumptions.")
            if st.button("Calculate scenario"):
                try:
                    result = discounted_cash_flow(latest.revenue, cash, debt, shares,
                                                  DcfAssumptions(revenue_growth=growth, operating_margin=margin, discount_rate=discount, terminal_growth=terminal))
                    st.metric("Scenario value per share", money(result.value_per_share))
                    st.caption("Scenario sensitivity, not a price target.")
                except ValueError as exc:
                    st.warning(str(exc))
    with st.expander("Advanced Evidence Tools"):
        if filings and st.button("Prepare local dense index"):
            try:
                chunks = filing_chunks(filings[0], STORE, CONFIG.chunk_size, CONFIG.chunk_overlap)
                retriever = dense_retriever(CONFIG.qdrant_path)
                retriever.embeddings = embeddings(embedding_model)
                retriever.build_index(collection_name(filings[0], embedding_model), chunks)
                st.success("Local dense index ready.")
            except Exception as exc:  # noqa: BLE001 - optional acceleration.
                st.warning(f"Dense index unavailable; BM25 remains available: {exc}")
        if show_debug:
            st.write(st.session_state.get("retrieval_note", "No fallback recorded."))
            for item in theses:
                st.json({key: item.get(key) for key in ("text", "status", "confidence", "source", "explanation")})

elif page == "Public Portfolios":
    st.title("Public Portfolios")
    st.subheader("Institutional Portfolios")
    st.info(DISCLOSURE_NOTE)
    entity_id = st.selectbox("Institution", list(BY_ID), format_func=lambda key: BY_ID[key].name)
    entity = BY_ID[entity_id]
    st.write(f"{entity.investor} · {entity.style}" if entity.investor else entity.style)
    followed = st.checkbox("Follow this institution", value=entity_id in STORE.follows(), key=f"follow_{entity_id}")
    STORE.follow(entity_id, followed)
    if st.button("Load latest available disclosures"):
        try:
            with st.spinner("Loading official disclosures…"):
                if entity_id == "ark":
                    snapshots = [fetch_ark_holdings()]
                else:
                    provider = Sec13FProvider()
                    snapshots = provider.latest_two(entity)
                    try:
                        provider.resolve_tickers(snapshots)
                    except Exception:  # noqa: BLE001 - ticker lookup must not gate 13F ingestion.
                        st.caption("SEC ticker lookup unavailable; holdings retain their reported issuers and CUSIPs.")
                for snapshot in snapshots:
                    STORE.save_snapshot("portfolio", entity_id, f"{snapshot.reporting_period}:{snapshot.accession}", snapshot.to_dict())
            st.success("Official snapshots saved locally.")
        except Exception as exc:  # noqa: BLE001 - retain dated cache.
            st.warning(f"Provider unavailable; showing any cached dated disclosure: {exc}")
    snapshots = portfolio_snapshots(entity_id)
    if snapshots:
        current = snapshots[0]
        previous = next((row for row in snapshots[1:] if row.reporting_period < current.reporting_period), None)
        st.caption(f"{current.source_type} · reporting period {current.reporting_period} · filed/as-of {current.filing_date}")
        st.warning(disclosure_freshness(current.reporting_period, source_type=current.source_type))
        st.link_button("Official source", current.source_url)
        st.caption(current.notes)
        changes = compare_portfolios(previous, current) if previous else []
        change_map = {(row["cusip"], row["security_class"], row["put_call"]): row for row in changes}
        st.subheader("Top Holdings")
        table = [{"Ticker / Issuer": row.ticker or row.issuer, "CUSIP": row.cusip, "Class": row.security_class,
                  "Put/Call": row.put_call, "Reported Value": row.reported_value, "Portfolio %": row.weight * 100,
                  "Shares / principal": row.shares,
                  "Change": change_map.get((row.cusip, row.security_class, row.put_call), {}).get("activity", "Comparison unavailable")}
                 for row in current.holdings]
        st.dataframe(pd.DataFrame(table), hide_index=True, use_container_width=True)
        if current.holdings:
            chosen = st.selectbox("Explore a disclosed issuer", current.holdings,
                                  format_func=lambda row: f"{row.issuer} · {row.security_class} · {row.put_call or 'shares'}")
            mapping_key = chosen.cusip + ":" + chosen.security_class
            mappings = STORE.snapshots("ticker_mapping", mapping_key)
            mapped = chosen.ticker or (mappings[0]["ticker"] if mappings else "")
            research_ticker = st.text_input("Verified company ticker", value=mapped,
                                           help="13F uses CUSIPs. Verify the issuer and share class before entering its ticker.")
            if st.button("Research this company", disabled=not research_ticker.strip()):
                try:
                    target = normalize_ticker(research_ticker)
                    STORE.save_snapshot("ticker_mapping", mapping_key, "current", {"ticker": target, "issuer": chosen.issuer})
                    for row in current.holdings:
                        if row.cusip == chosen.cusip and row.security_class == chosen.security_class:
                            row.ticker = target
                    STORE.save_snapshot("portfolio", entity_id, f"{current.reporting_period}:{current.accession}", current.to_dict())
                    st.session_state.pending_research = target
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
        else:
            st.caption("This official report declares zero information-table entries.")
        st.subheader("Activity")
        if changes:
            st.caption(f"{previous.reporting_period} → {current.reporting_period}; reported shares, not inferred trading dates or motives.")
            st.dataframe(pd.DataFrame(changes), hide_index=True, use_container_width=True)
        else:
            st.caption("Another comparable snapshot is required. ARK uses saved daily holdings dates.")
        with st.expander("Sector Exposure"):
            if st.button("Load sectors for matched tickers"):
                with st.spinner("Loading optional market sector metadata…"):
                    enrich_sectors(current)
                    STORE.save_snapshot("portfolio", entity_id, f"{current.reporting_period}:{current.accession}", current.to_dict())
            classified = [row for row in current.holdings if row.sector != "Unclassified"]
            if classified:
                frame = pd.DataFrame([asdict(row) for row in classified])
                st.bar_chart(frame.groupby("sector")["reported_value"].sum())
                total_value = sum(row.reported_value for row in current.holdings)
                covered = sum(row.reported_value for row in classified) / total_value if total_value else 0.0
                st.caption(f"Sector coverage: {covered:.1%} of the disclosed table; unmatched holdings excluded. Sector labels: Yahoo Finance.")
            else:
                st.caption("Official 13F tables do not provide sectors. No unverified sector mapping is inferred.")
    else:
        st.caption("No official snapshot loaded.")
        if entity_id == "ark":
            st.link_button("Official ARKK holdings", ARK_URL)
    st.subheader("Portfolio Change Feed")
    for followed_id in STORE.follows():
        if followed_id not in BY_ID:
            continue
        saved = portfolio_snapshots(followed_id)
        if len(saved) >= 2:
            prior = next((row for row in saved[1:] if row.reporting_period < saved[0].reporting_period), None)
            if prior:
                for change in [row for row in compare_portfolios(prior, saved[0]) if row["activity"] != "UNCHANGED"][:5]:
                    st.write(f"{BY_ID[followed_id].name} · {change['activity']} · {change['issuer']}")
                    st.caption(f"Period {change['reporting_period']} · filed/as-of {change['filing_date']}")
    st.divider()
    st.subheader("Public Financial Disclosures")
    st.write("Donald Trump · U.S. Office of Government Ethics")
    st.caption("Range-based assets, interests, income, and reported transactions. Separate from 13F; no exact portfolio weights are inferred.")
    st.link_button("Official OGE disclosure search", OGE_SEARCH)
    st.link_button("OGE annual report notice", OGE_ANNUAL_NOTICE)
    oge_url = st.text_input("Official OGE PDF URL", value=OGE_TRUMP_PTR)
    if st.button("Load OGE disclosure"):
        try:
            with st.spinner("Reading the official public disclosure…"):
                disclosure = fetch_oge_disclosure(oge_url)
                STORE.save_snapshot("oge", "donald_trump", oge_url, disclosure)
        except Exception as exc:  # noqa: BLE001 - source outage visible.
            st.warning(f"Official disclosure could not be parsed: {exc}")
    for disclosure in STORE.snapshots("oge", "donald_trump"):
        st.write(disclosure["disclosure_type"])
        st.caption(f"Filed {disclosure.get('filing_date') or 'date not reliably extracted; see original'} · document filename date {disclosure.get('source_document_date') or 'unknown'} · {disclosure['notes']}")
        st.link_button("Open official disclosure", disclosure["source_url"])
        if disclosure["records"]:
            st.dataframe(pd.DataFrame(disclosure["records"]), hide_index=True)
        with st.expander("Original source excerpts"):
            selected_page = st.selectbox("Source page", disclosure["excerpts"],
                                         format_func=lambda row: f"Page {row['page']}",
                                         key=f"oge_page_{disclosure['source_url']}")
            st.text(selected_page["text"])
            st.link_button("Verify original PDF page", selected_page["source_url"])

else:
    st.title("Ask")
    ticker = st.selectbox("Company context", STORE.watchlist() or [st.session_state.get("selected_ticker", "AAPL")])
    question = st.text_input("What would you like to investigate?", placeholder="Which of my thesis points are weakening?")
    if st.button("Ask", disabled=not question.strip()):
        from src.ask import answer_question

        with st.spinner("Finding dated company and disclosure evidence…"):
            answer, evidence = answer_question(question, ticker, STORE, CONFIG, ollama_model, retrieve)
        st.write(answer)
        evidence_view(evidence)

st.divider()
st.caption("ThesisLens · An evidence-driven investment thesis monitoring and public-disclosure research system.")
