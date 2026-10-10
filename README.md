# ThesisLens

Follow great investors. Understand what they own. Verify the thesis yourself.

## Primary application: Next.js + FastAPI

The consumer app is now `frontend/`, with **Home, Discover, Research, Market Pulse, Ask, and Status** in its primary navigation. Streamlit is retained only as an internal/debug workspace. Public holdings are research inputs, not recommendations; position changes do not establish motive.

```text
Next.js 16 / React 19 / TypeScript / Tailwind 4 / shadcn / TanStack Query / Zod
                              ↓ same-origin /api proxy
FastAPI / Pydantic → existing src/ financial and retrieval services
                              ↓
SEC EDGAR + XBRL / local SQLite / Qdrant + BM25S / optional Jev + Ollama
```

### One-command Windows startup

After installing the Python and frontend dependencies once, start the complete local app from the repository root:

```powershell
.\start-thesislens.ps1
```

The manager verifies the project `.venv`, detects port conflicts, reuses only a matching healthy Backend, starts installed local Ollama when needed, checks the configured model without downloading it, starts one Frontend, waits for readiness, and opens `http://127.0.0.1:3000`. Use `-NoBrowser` for terminal-only startup. It records only process IDs, start times, a random instance identifier, and build metadata under ignored `.runtime/`; rotating logs are capped there as well.

```powershell
.\status-thesislens.ps1       # safe dependency summary; never prints secrets
.\status-thesislens.ps1 -Json # machine-readable summary
.\stop-thesislens.ps1         # stops only verified manager-owned process trees
```

An unrelated or unverifiable listener on port 8000 or 3000 is never terminated. Close it yourself after confirming ownership, then rerun startup. The manager does not install services, create startup tasks, change Windows settings, download models, use force-kill, or expose the local API to the network. The Status page provides the same Backend, Market Pulse, General AI, and Frontend diagnostics with a manual refresh control.

### Run the backend (PowerShell terminal 1)

Python 3.12 recommended; preserve an existing `.env`. A new installation needs `SEC_USER_AGENT` with a contact email, not credentials committed to source control.

```powershell
cd C:\Users\User\Documents\Projects\financial-report-rag
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

API reference: http://127.0.0.1:8000/docs. This is a **local, single-user** application, without authentication or tenant isolation. Do not expose the backend to the public internet. Production hosting requires authentication, authorization, rate limiting, and deployment hardening.

### Run the frontend (PowerShell terminal 2)

Node.js 22 LTS recommended. `package-lock.json` locks installed versions.

```powershell
cd C:\Users\User\Documents\Projects\financial-report-rag\frontend
npm.cmd ci
npm.cmd run dev
```

Open http://localhost:3000. Production verification: `npm.cmd run build`, then `npm.cmd run start`. Set server-side `API_URL` only if the backend is not at `http://127.0.0.1:8000`. No API credentials belong in `NEXT_PUBLIC_*` variables.

### Public-source intelligence (incremental V2)

The existing research product now also has an additive tracked-entity registry (18 featured managers/funds and explicit on-demand SEC CIK verification), source-cited normalized events, a personalized Intelligence Feed, comparable cached 13F activity in Research, and a dated daily brief. ARKK's daily fund holdings are compared separately from quarterly 13F; neither is a real-time trade signal. Follow official RSS sources from the feed. The enabled free providers reuse the existing official RSS and SEC caches; Berkshire's official letter index exposes year-only documents but does not fabricate publication dates or treat them as fresh updates. X/Twitter and paid APIs are disabled/unneeded.

The local notification outbox needs no credentials. For an explicit due RSS refresh and cache materialization, run `.\.venv\Scripts\python.exe -m backend.refresh --public-updates --intelligence` from the repository root. For one optional Telegram or self-hosted ntfy delivery attempt, run `.\.venv\Scripts\python.exe -m backend.refresh --notifications`. Use `--notification-dry-run` to preview Telegram, ntfy, and Hermes-consumer messages without credentials, network calls, or outbox changes. See [Hermes and notifications](docs/hermes-integration.md) for setup and security boundaries. These commands do not crawl all managers.

### Institutional portfolio network (V3)

Discover includes an interactive 2–5 manager comparison powered only by stored verified disclosures. It provides class-aware CUSIP matching, common and unique holding counts, all-manager and pairwise Jaccard similarity, disclosed-weight overlap, source dates, position changes, historical date playback, and a bounded zoomable/pannable network. See [the V3 calculation and coverage contract](docs/thesislens-v3-portfolio-network.md). Shared holdings are not evidence of shared intent, and 13F data remains delayed and incomplete.

Playwright E2E is isolated: `cd frontend; npm run test:e2e` starts dedicated localhost servers, forces offline mode, initializes/migrates a synthetic database at `.e2e-runtime/thesislens-e2e.sqlite3`, and replaces **only that guarded test database** at the start of each run. The browser tests never connect to `data/local/thesislens.sqlite3`; external QA URLs and a personal `THESISLENS_DB` are rejected before startup. `.e2e-runtime/`, screenshots, browser traces, generated caches, and `.env` are ignored. The fixture contains synthetic public-research data—not copied personal records. Do not guess or restore any user records changed by earlier browser runs.

SQLite V2 migration is additive and transactional. Before upgrading a personal database, stop both app servers and make a dated copy of `data/local/thesislens.sqlite3` to a private backup outside the repository. Do not overwrite the source database if an upgrade fails; preserve it and the backup for diagnosis. Migration tests cover clean install, V1 watchlist/follows/theses/evaluations preservation, idempotence, and rollback on schema conflict.

Company search uses the free [SEC ticker/CIK/exchange directory](https://www.sec.gov/files/company_tickers_exchange.json), cached for 24 hours at `data/cache/company_directory.json`. Search by exact ticker or company name, inspect autocomplete suggestions, and explicitly choose between multiple share classes. The directory is separate from filings and financial facts: an identified company can still have missing or temporarily unavailable research. A failed directory refresh keeps the last validated directory with a stale label. `BRK.B` resolves to the SEC listing `BRK-B`; non-US exchange suffixes such as `.TO` are not silently treated as US tickers. No paid search service or credential is required. The UI defaults to dark mode; its optional light-mode choice is saved in this browser.

### Product API

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/api/health`, `/api/readiness` | Lightweight liveness and version-aware local dependency readiness |
| GET | `/api/home/feed`, `/api/investors` | Discovery, activity, ideas, watchlist |
| GET | `/api/investors/{id}`, `/holdings`, `/changes` | Profile, reported positions, deterministic share changes |
| PUT | `/api/investors/{id}/follow` | Persist followed institution |
| GET | `/api/company/{ticker}`, `/changes`, `/suggested-theses`, `/theses` | Company research and evidence |
| GET | `/api/companies/search?q=`, `/api/companies/resolve?q=` | Validated SEC identity suggestions and explicit resolution |
| PUT | `/api/company/{ticker}/watch` | Persist watchlist |
| PUT | `/api/company/{ticker}/suggestions/{suggestion_id}/ignore` | Persist ignored suggestion (set `enabled:false` to restore) |
| POST / PUT | `/api/theses`, `/api/theses/{id}` | Track/edit a thesis |
| POST | `/api/theses/{id}/evaluate` | Evidence-linked evaluation and timeline |
| GET | `/api/disclosures`, `/api/insiders/{ticker}`, `/api/ownership/{ticker}` | Separate disclosure clocks and source metadata |
| GET | `/api/public-officials` | Quality-gated, range-preserving OGE summaries |
| POST | `/api/ask` | Bounded factual lookups, Python comparisons, optional grounded Ollama |

Suffixes in the table use their preceding investor/company prefix. All write requests are validated with Pydantic; key product responses have Pydantic contracts, and frontend boundaries use Zod.

### Freshness and source handling

Request-triggered background refresh uses persistent check/error timestamps, process-local single-flight suppression, source timeouts, and a conservative SEC rate limit of 4 requests/second per backend process. Cached research remains available during refresh or source failures. Failed checks are cached too; reopening a page does not repeatedly hammer a blocked source.

| Source | Check interval | Important distinction |
| --- | --- | --- |
| Yahoo market snapshot | 5 minutes | Optional, delayed/unavailable; timestamp is shown |
| Official ARKK holdings | 24 hours | Fund-level daily holdings, not institutional 13F |
| SEC Form 4 | 30 minutes | Insider transaction date and filing date; P/S codes label BUY/SELL, not recommendations |
| Schedule 13D/G | 1 hour | Disclosed ownership percentage, filer and amendment; no inferred motives |
| Institutional 13F | 6 hours | Filing checks; quarterly reporting dates and filing dates remain separate |
| Company filings + facts | 6 hours | Financial reporting periods are independent of check time |
| OGE | 24 hours in refresh service | Separate official PDF import; range preservation and quality gates |

There is no unattended scheduler. Home refreshes followed investors/watchlist companies; opening an investor/company profile checks its sources. Form 4/ownership panels refresh independently. OGE importing remains explicit in the internal workspace. Immutable SEC disclosure documents are cached by accession and written through an incomplete file before promotion.

Optional explicit warm-up (real sources, not demo fixtures):

```powershell
cd C:\Users\User\Documents\Projects\financial-report-rag
.\.venv\Scripts\python.exe -m backend.refresh --investor berkshire --investor pershing --company AAPL --company NVDA --company GOOGL --disclosures
```

`--company` and `--investor` can be repeated. `THESISLENS_OFFLINE=true` disables request-triggered network refresh while retaining cached functionality.

Featured adapters: Berkshire, Pershing, Appaloosa, Bridgewater, Scion, Duquesne, Soros, Tiger Global, Coatue, and official ARKK. Unavailable/stale investors stay visible. Exact issuer-name ticker matching is deliberately incomplete; an unmapped security is not guessed. Common share classes can be resolved from explicit cached SEC filing-cover rows (for example Alphabet Class A/GOOGL and Class C/GOOG), with the mapping source retained. Duplicate legacy cache keys are deduplicated by source/period before comparisons. Sector exposure can remain Unclassified. Originals only: 13F amendments are not consolidated.

### Suggested theses and What Changed

Research creates up to five **evidence-backed Python hypotheses**, transparently labelled by generator. These are not claimed to be live AI-generated when an LLM is unavailable. Growth, margin, positive FCF and debt tests use available annual facts; a filing-linked risk hypothesis is included when text is available. Each has why it matters, supporting/invalidating conditions, source citations and Track/Edit/Ignore. Eight beginner-friendly categories provide research prompts. Sparse evidence may produce fewer than three suggestions rather than fabricated claims.

Numeric evaluations remain Python-only and explicitly annual. Editing a suggested statement removes its automatic rule; editing a tracked claim resets its current status while preserving history. Narrative evidence evaluation uses optional Jev Choice/confidence and falls back to UNCERTAIN with evidence. Jev is not a calculator, recommendation engine, or replacement for Ollama.

What Changed adds current quarter vs same period last year from SEC facts. It only accepts 70–105-day duration facts, aligns numerator/denominator starts, and never labels YTD cash flow as a quarter. Revenue/margin/FCF/CapEx changes have both-period citations; annual fallback is explicit. Filing phrases compare matching fiscal periods and describe observed text, not a newly created/resolved economic risk. **Segment/geographic XBRL extraction, quarter cash-flow derivation from YTD, broad theme/tone classification and automatic catalyst inference are not yet implemented.**

Ask protects investor motives: “Why did Berkshire reduce AAPL?” returns no sourced explanation when no direct rationale exists. Followed-company exposure is a verified lookup; no match under incomplete mappings is not proof of absence. Existing hybrid retrieval is used when a matching local index exists; otherwise BM25 evidence remains available. The API does not automatically build new dense indexes; the internal workspace retains ingestion/indexing, advanced valuation and reranking.

### Verification and screenshots

See `docs/consumer-verification.md` for actual measured test results, source observations and limitations. Browser tests use a copy of the real local database; they must not target personal saved research. Synthetic fixtures exist only in Python unit tests.

Screenshot locations after browser QA: `frontend/test-results/home-desktop.png`, `discover-desktop.png`, `investor-desktop.png`, `research-desktop.png`, `nvda-desktop.png`, `ask-desktop.png`, and `runtime-dashboard-desktop.png`, plus mobile variants. These are generated artifacts, not mocked screens. Documentation screenshot slots: Home / Discover / Research / investor profile / Runtime Status (capture with the E2E suite).

```powershell
# Python tests, from repository root
.\.venv\Scripts\python.exe -m pytest -q --basetemp=.pytest_cache\basetemp
# Frontend checks, from frontend/
npm.cmd run typecheck
npm.cmd test
npm.cmd run build
npx.cmd playwright install chromium
npm.cmd run test:e2e
```

E2E starts its own isolated backend on port 18765 and frontend on port 13000; it does not use the personal database or the normal development servers. Enable the optional live Zod contract tests against a separately running local backend with `$env:LIVE_API='true'` before `npm.cmd test`. The installed React/Next/TypeScript/Tailwind/shadcn/TanStack/Zod/UI/Playwright skills shaped component boundaries, validation, cache policies, keyboard access and browser QA. The TypeSafe skill required live API/Choice/citation guidance before reusing Jev judgments.

## Internal/debug Streamlit workspace (retained)

An evidence-driven investment thesis monitoring and public-disclosure research system.

ThesisLens helps investors track whether new company evidence strengthens or weakens their own investment thesis, while using public institutional and public-official disclosures for research and idea discovery. It reports evidence relationships and research questions, without BUY / SELL / HOLD recommendations or a numeric investment score.

### Four internal/debug pages

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
.\.venv\Scripts\python.exe -m pytest -q --basetemp=.pytest_cache\basetemp
.\.venv\Scripts\python.exe -m ruff check app.py src backend tests
```

Tests preserve prior backend coverage and add local persistence/history, deterministic rules, semantic fallback, 13F parsing/units/options, portfolio activity classes, stale labels, range-preserving OGE handling, provider degradation, comparable-period selection, and four-page Streamlit rendering.

See `docs/thesislens-verification.md` for actual source checks and limitations, and [THIRD_PARTY.md](THIRD_PARTY.md) for dependencies, licenses, rationale, and modifications.
