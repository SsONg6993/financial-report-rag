# Consumer app verification — 2026-09-26

## Architecture and scope

Primary product: `frontend/` Next.js 16.3.6, React 19.3.0, strict TypeScript, Tailwind 4, CLI-installed shadcn/Radix components, TanStack Query and Zod. `backend/` exposes FastAPI/Pydantic adapters to the existing `src/` services. Streamlit remains internal/debug; no existing analytics, SEC, RAG, valuation, Jev or Ollama module was removed.

Four primary areas: Home, Discover, Research, Ask. Investor profiles and ticker research are nested routes. API endpoints, source refresh policies and exact setup commands are listed in README.

## Actual verification results

| Check | Actual result |
| --- | --- |
| Full Python suite, including preserved tests and new adapter tests | 71 passed, 2 upstream deprecation warnings, 10.58 seconds |
| Ruff on new backend, tests and changed Python modules | Passed |
| Frontend Vitest boundary tests + 4 live cached API/Zod contracts | 9 passed, 0 failures |
| Production Next.js build | Passed; static Home/Discover/Research landing/Ask, dynamic investor and ticker routes |
| TypeScript check | Passed |
| Production Playwright desktop + iPhone-size Chromium | 14 passed, 0 failures, 24.0 seconds |

Browser journeys verified real cached source data, not fabricated responses:

- Home/Discover source dates, all 10 investor cards, mobile overflow checks.
- Berkshire profile → AAPL → track a suggested thesis → evaluate → reload → retained timeline.
- NVDA suggested hypotheses and sourced changes → track → evaluate supporting financial evidence.
- Watchlist without requiring a manually written thesis.
- Follow Berkshire → Ask which followed investors disclose GOOGL → factual answer with original SEC source.
- Ask why Berkshire reduced AAPL → no investor explanation invented.
- Real AAPL Form 4 context, insider role, transaction shares/price/code and source dates.
- Simulated API HTTP 503 → actionable retry state; unknown company → explicit missing evidence, not fake metrics.

Visual inspection: actual screenshots of desktop Home, Discover, investor profile, AAPL Research; mobile Research viewport, Form 4 context and Ask. Screenshots were also captured for NVDA, full mobile Home/Discover/investor profiles, and errors. No horizontal overflow in the asserted layouts. Generated images are in `frontend/test-results/` (ignored by Git).

Tests used `data/local/qa-next.sqlite3`, a disposable copy of the real local source database. Watch/follow/track/evaluate actions were kept out of the personal database. Live source ingestion and verified ticker enrichment updated source caches only. Repeated accepted suggestions are marked Tracked; repeated creation of the same text/rule is idempotent. No synthetic test fixture is served by the real application.

## Live source observations

These observations are date-specific and not permanent claims of freshness.

| Institution | Latest cached period | Reported positions | Observation |
| --- | --- | ---: | --- |
| Berkshire | 2026-06-30 | 29 | Official original 13F; prior comparable period cached |
| Pershing | 2026-03-31 | 11 | Stale; later original filing not returned by the adapter |
| Appaloosa | 2026-06-30 | 27 | Official 13F refresh succeeded |
| Bridgewater | 2026-06-30 | 997 | Official 13F refresh succeeded; profile displays a limited top-holdings subset |
| Scion | 2025-09-30 | 8 | Stale; no newer original returned |
| Duquesne | 2026-06-30 | 95 | Official 13F refresh succeeded |
| Soros | 2026-06-30 | 266 | Official 13F refresh succeeded |
| Tiger Global | 2026-06-30 | 46 | Official 13F refresh succeeded |
| Coatue | 2026-06-30 | 66 | Official 13F refresh succeeded |
| ARKK | Unavailable | — | Official site returned HTTP 403; no substitute dataset or invented holdings |

Company source refresh succeeded for AAPL, NVDA and GOOGL. Research produced respectively 5, 4 and 4 evidence-backed suggested hypotheses, and 3, 3 and 2 comparable-quarter changes. Those counts can change with new evidence or ignored suggestions.

AAPL Form 4: 11 normalized transaction records from up to 8 recent documents. One real example: Jennifer Newstead, sale code S, transaction 2026-09-22, filed 2026-09-24, 2,399 shares at $340.06; original filing includes a Rule 10b5-1 plan footnote. This is not interpreted as a bearish recommendation.

Modern Schedule 13G fields were verified against an actual SEC document: Vanguard Capital Management disclosed 7.48% in a filing dated 2026-04-29. Other filings/people are separate records, not an aggregate current ownership claim. Legacy/unrecognized documents keep source links and unknown fields.

Alphabet issuer-name mapping was ambiguous. Its cached 2026-06-30 SEC 10-Q cover explicitly associates Class A common stock with GOOGL and Class C capital stock with GOOG. Only explicit common/capital-stock rows plus exact issuer and 13F class matches are enriched; preferred/depositary securities are not guessed. The mapping source URL is retained. Legacy accession-key and reporting-period-key duplicates are deduplicated before comparison.

OGE remains separate and range-preserving. The existing cached official PDF did not produce sufficiently validated transaction rows; the consumer app explains the quality gate and links the original document rather than displaying rejected text as verified transactions.

## Limitations and unmeasured capabilities

- Local single-user deployment only; no auth, tenant isolation or public-hosting hardening.
- Refresh is request-triggered, not an unattended scheduler; source failures are cached through their respective retry/check intervals.
- 13F originals only; amendments not consolidated, incomplete exact ticker and sector coverage, delayed/partial portfolio visibility.
- Form 4 and ownership coverage is limited to up to 8 recent documents per check, not a complete historical transactions database. Derivative records and footnotes are retained by the adapter; original documents remain authoritative.
- Suggested hypotheses are deterministic evidence-backed templates, transparently labelled—not claimed to be live model-generated. Numeric evaluation is annual, not quarterly. Sparse data produces fewer hypotheses rather than invented support.
- Quarter duration facts are conservative; YTD-to-quarter cash-flow derivation, segment/geographic normalization and broad management-tone/catalyst inference are not implemented.
- Detailed DCF, dense index building, advanced reranking and technical evaluation stay in the internal Python workspace. Consumer Ask reuses a matching existing dense/Qdrant index when available, with BM25 fallback.
- Jev remained disabled; Ollama was unavailable. No live model-quality, accuracy, latency or superiority results are claimed. Deterministic analytics, sourced lookups, retrieval and quantitative thesis evaluation were verified independently.
- Two Python warnings come from the installed Starlette/HTTPX and AnyIO compatibility paths, not failing tests.

## Reproduce browser QA without modifying personal research

Stop any running QA backend before resetting its disposable database. From the repository root:

```powershell
Copy-Item -LiteralPath data/local/thesislens.sqlite3 -Destination data/local/qa-next.sqlite3
$env:THESISLENS_DB='data/local/qa-next.sqlite3'
$env:THESISLENS_OFFLINE='true'
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

In a second terminal, from `frontend/`:

```powershell
npm.cmd ci
npm.cmd run build
npm.cmd run start -- --hostname 127.0.0.1
```

In a third terminal, from `frontend/`:

```powershell
$env:LIVE_API='true'
npm.cmd test
npm.cmd run test:e2e
npm.cmd run typecheck
```

Use a fresh QA database copy for a full run: both projects accept different untracked hypotheses. The assertions require real cached Berkshire/AAPL/NVDA/GOOGL and AAPL Form 4 sources; source warm-up is described in README. Do not run this suite against the personal database.
