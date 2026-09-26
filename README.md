# ThesisLens

An evidence-driven investment thesis monitoring and public-disclosure research system.

ThesisLens helps investors track whether new company evidence strengthens or weakens their own investment thesis, while using public institutional and public-official disclosures for research and idea discovery. It reports evidence relationships and research questions, without BUY / SELL / HOLD recommendations or a numeric investment score.

## Four pages

- **Home**: locally persisted watchlist, thesis-health counts, meaningful comparable-period changes, and followed disclosures.
- **Research**: a compact company summary, editable thesis points, evidence evaluation, thesis timeline, dated changes, and an investigation checklist. Valuation and technical evidence tools are collapsed.
- **Public Portfolios**: official institutional disclosures, reported holdings and share changes, plus a separate OGE public-financial-disclosure section.
- **Ask**: questions across locally loaded theses, company facts, filing evidence, and public portfolio snapshots.

The previous ten-tab dashboard has been replaced. Financial calculations, risk extraction, valuation, retrieval, reranking, evaluation, and optional providers remain reusable backend modules.

## Install and run

Python 3.12 is recommended. The existing project virtual environment is supported.

```powershell
cd C:\Users\User\Documents\Projects\financial-report-rag
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

For a new installation only, copy `.env.example` to `.env`; preserve an existing `.env`. Set `SEC_USER_AGENT` to an identifying application name and contact email. Never commit credentials.

```powershell
cd C:\Users\User\Documents\Projects\financial-report-rag
.\.venv\Scripts\python.exe -m streamlit run app.py
```

## Optional providers

```dotenv
SEC_USER_AGENT=ThesisLens your-email@example.com
THESISLENS_DB=data/local/thesislens.sqlite3
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
QDRANT_PATH=data/vector_store
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2
ENABLE_JEV=false
TYPESAFE_API_KEY=
JEV_MODEL=jev-latest
JEV_CONFIDENCE_THRESHOLD=0.70
```

Ollama synthesizes research questions and final explanations from supplied evidence. Install Ollama and run `ollama pull llama3.2` if desired. Without Ollama, structured answers, thesis thresholds, portfolio comparisons, and retrieved evidence remain available.

Jev is optional. It supplies bounded Choice judgments about the relationship between a user thesis and previous/current evidence, with confidence and probabilities. Numeric rules execute exclusively in Python. Missing credentials, service failures, and low-confidence narrative judgments preserve an **UNCERTAIN** status and retain the evidence for investigation. The confidence threshold is configurable and needs validation on domain-specific labels; it is not a calibrated investment probability.

The installed [TypeSafe AI skill](https://github.com/typesafe-ai/skills) guided narrow questions, explicit evidence state, uncertainty handling, and code-owned execution. The adapter follows the [current HTTP API](https://docs.typesafe.ai/api) and [evidence relationship cookbook](https://docs.typesafe.ai/cookbooks/citation_check). Existing routing, relevance, sufficiency, risk, and bounded workflow adapters remain available internally.

## Thesis model and workflow

Each local thesis contains an ID, ticker, text, optional metric/operator/threshold rule, creation/update dates, last evaluation date, status, and supporting/contradicting evidence. Evaluations retain the claim as evaluated, previous/current evidence, reporting periods, provenance, confidence, optional probabilities, and explanation. Editing resets current status to **NOT_EVALUATED** and preserves the historical evaluations.

Statuses are **STRENGTHENED**, **STABLE**, **WEAKENED**, **UNCERTAIN**, and **NOT_EVALUATED**.

Explicit quantitative rules compare the latest normalized annual metric against a user-defined threshold. Ratios use fractions: 45% is `0.45`. An adjacent prior fiscal year supplies the previous comparison. A met threshold is stable; crossing from unmet to met strengthens it; an unmet threshold weakens it; unavailable values remain uncertain. These statuses describe the stated threshold.

Narrative evaluation retrieves current filing evidence and a comparable same-form period approximately one year earlier. Jev optionally judges the relationship to the thesis; absent reliable semantic judgment, the user can inspect dated evidence without an invented status. Source excerpts include accession, period, filing date, section, chunk ordinal, and character offsets.

“What Changed” calculates annual financial deltas and reports observed phrase appearances/removals in comparable filings. Phrase absence is not treated as evidence that a risk was resolved. Segment/geography and nuanced management-language changes are not inferred without reliable evidence.

## Disclosure sources

| Entity | Source | Coverage |
| --- | --- | --- |
| Berkshire Hathaway / Warren Buffett | SEC 13F, CIK 1067983 | Public original quarterly information tables |
| Pershing Square / Bill Ackman | SEC 13F, CIK 1336528 | Public original quarterly information tables |
| Appaloosa / David Tepper | SEC 13F, CIK 1656456 | Public original quarterly information tables |
| Bridgewater Associates | SEC 13F, CIK 1350694 | Public original quarterly information tables |
| Scion Asset Management / Michael Burry | SEC 13F, CIK 1649339 | Latest available original reports, explicitly dated |
| ARK Invest / Cathie Wood | Official ARKK fund CSV | ARKK daily holdings, distinct from 13F and other ARK funds |
| Donald Trump | Official OGE PDF reports and source directory | Public financial disclosures, separate range-preserving model |

13F values filed from January 3, 2023 use dollars; earlier filings use thousands of dollars. Rows aggregate by CUSIP, security class, put/call, and shares/principal type. Position changes use share counts, not changes in market value. Public-table weights describe the reported table only; option values can represent underlying securities rather than premiums.

13F reports are delayed, may be filed roughly 45 days after quarter end, exclude many assets and hedges, and do not establish current conviction or trading motives. Amendments are not yet merged: snapshots explicitly identify original filings. Comparisons show both periods and filing dates.

13F has no ticker or sector fields. Unambiguous exact issuer-name matches against the official SEC ticker directory can supply tickers; unmatched/ambiguous classes need user verification. Optional Yahoo Finance sector enrichment shows coverage and leaves unmatched holdings unclassified.

OGE reports are not exact brokerage portfolios. Amount/income ranges are preserved, weights are never inferred, and unknown filing dates remain unknown. The selected official May 2026 transaction PDF has a noisy text layer: invalid rows are excluded and source-page excerpts are available for verification. Annual PDFs retain source excerpts; reliable annual section normalization and OCR require further work. OGE access requirements may prevent automatic downloads.

## AAPL + Berkshire example

1. On Home, add `AAPL`; select Research and load company evidence.
2. Create four points: Services growth, gross margin above 45%, China stabilization, and strong FCF. Attach explicit quantitative rules where useful.
3. Evaluate. Python evaluates annual financial thresholds; narrative evidence is shown with Jev confidence when available, otherwise it remains uncertain.
4. Inspect the annual “Since Last Comparable Period” facts, comparable filing excerpts, thesis timelines, and research checklist.
5. On Public Portfolios, follow Berkshire and Pershing Square and load their official disclosures.
6. Review reporting dates, top holdings, share-change classifications, and stale labels. Select Apple’s reported holding and open Research using its verified ticker.
7. Open OGE disclosures separately, then use Ask for company evidence, weakening theses, and dated portfolio context.

## Local persistence and retrieval

SQLite stores the watchlist, follows, theses, history, company/filing snapshots, parsed chunks, institutional snapshots, ticker mappings, and OGE excerpts under `data/local/`. Back up the SQLite file to preserve personal research. It is excluded from Git.

Filing HTML is cached by accession under `data/raw/`; Company Facts use `data/cache/`. Existing local Qdrant collections remain available. Hybrid retrieval uses compatible prebuilt vector indexes with BM25S and RRF; otherwise evidence uses BM25. Prepare an optional dense index in Research → Advanced Evidence Tools. Model-loading/store/reranker failures preserve lexical retrieval.

Backend evaluation inputs and functions are retained. Existing AAPL FY2025 retrieval qrels are keyword-derived bootstrap labels, not human-adjudicated chunk judgments; they must only be used with their intended corpus.

## Verification

```powershell
.\.venv\Scripts\python.exe -m pytest -q
python -m ruff check app.py src tests
```

Tests preserve prior backend coverage and add local persistence/history, deterministic rules, semantic fallback, 13F parsing/units/options, portfolio activity classes, stale labels, range-preserving OGE handling, provider degradation, comparable-period selection, and four-page Streamlit rendering.

See `docs/thesislens-verification.md` for actual source checks and limitations, and [THIRD_PARTY.md](THIRD_PARTY.md) for dependencies, licenses, rationale, and modifications.
