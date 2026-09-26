# Market Pulse

Market Pulse adds one source-backed research workflow: event → economic mechanism → company exposure → evidence → watchlist / followed public disclosure relevance. It does not issue trading instructions, predict returns, or infer today's investor positions.

## Architecture and API

`backend/market_pulse` contains typed events, provider adapters, deterministic exposure gates, and the persistence/integration service. The existing SQLite `LocalStore` holds source snapshots, summaries and optional semantic judgments. No investor adapter or financial-period parser is changed.

Endpoints: `GET /api/market-pulse`, `GET /api/market-pulse/watchlist`, `GET /api/market-pulse/{id}`, `GET /api/market-pulse/{id}/impacts`, and `POST /api/market-pulse/refresh` (202, cooldowns still apply). Specific routes precede the existing disclosure catch-all.

Frontend feature: `frontend/features/market-pulse`; thin App Router pages compose it. Home shows up to three recent events. The dedicated page separates recent events (7 days) from earlier coverage. Detail pages distinguish facts, mechanisms, exposure evidence, and unavailable reaction observations. Research links retain event context without replacing company Research.

## Sources and cache

| Official provider | Feed | Check interval |
| --- | --- | --- |
| BEA | https://apps.bea.gov/rss/rss.xml | 60 minutes |
| Federal Reserve | https://www.federalreserve.gov/feeds/press_monetary.xml | 60 minutes |
| BLS | https://www.bls.gov/feed/cpi.rss | 60 minutes |
| EIA | https://www.eia.gov/rss/todayinenergy.xml | 30 minutes |
| NVIDIA Newsroom | https://nvidianews.nvidia.com/cats/press_release.xml | 30 minutes |

Adapters accept RSS/Atom, follow redirects, respect ETag/Last-Modified, bound payloads to 2 MB, and reject entities, invalid/undated items, and far-future dates. Failures retain previous successful events with stale labels and a retry cooldown. HTTP 304 requires an existing cache. Independent sources refresh concurrently; page requests use the cache. `THESISLENS_OFFLINE=true` disables scheduled refreshes and remote judgments.

Publication time is distinct from cache time and underlying event time. Unknown event time stays unknown. Last-30-day coverage is retained for display; older stories are not described as latest. Clustering uses canonical URLs or highly similar same-day/category headlines with matching numeric tokens. It preserves source links and ID aliases; it does not assume differently worded stories are the same event.

## Classification and impact rules

Headline-driven categories cover macro, inflation, rates, employment, GDP, geopolitics, conflict, energy, trade, sanctions, supply chains, technology, AI, semiconductors, regulation, M&A and corporate events. A supported category is not a promise of comprehensive provider coverage.

Candidate companies come from the watchlist, followed cached portfolios and a small research universe (maximum 60). Being a candidate is not relevance. Dated cached filing passages must establish a functional exposure channel. Tables, headings, sprawling mixed-topic text, metaphorical “fuel our business”, and bare debt totals do not qualify. Natural gas is not automatically jet fuel; explicit restricted geography narrows matches. An NVIDIA project announcement does not automatically affect every AI company.

Outputs are potential tailwind/headwind, mixed, indirect, or unclear; evidence strength and exposure confidence are separate from market direction. A fuel-cost or producer channel can support an explicitly reported price move, but historical seasonal comparisons do not become new shocks. Missing evidence yields UNCLEAR, not fabricated financial effects. These conservative rules are not comprehensive semantic event-to-company reasoning.

Qwen/Ollama selects only validated indices into bounded extractive source sentences and deterministic mechanism/watch text. It cannot add figures, URLs, or company exposures. At most three summaries are synthesized per refresh; failures use extractive fallback. Abbreviations remain intact; incomplete RSS tails are not standalone facts. Existing Ollama settings apply (currently qwen3:4b).

Optional Jev uses the existing TypeSafe adapter to judge semantic sufficiency of already-supported exposure channels. It can downgrade insufficient support, never manufacture exposure or calculate facts. Existing `ENABLE_JEV`, API-key/model/confidence settings apply. Checks are bounded to three detail impacts, with 24-hour caching and deterministic fallback. No live Jev success is claimed when disabled/unavailable.

## Watchlist, portfolios and Ask

Only supported recent exposure qualifies for the watchlist count/filter. Followed holdings are read from existing snapshots; reporting period, filing date, original disclosure and delayed-position disclaimer accompany overlap. There is no SEC or holdings refresh in this feature.

Ask routes news, macro events, AI news, oil-price and portfolio/oil exposure questions to source-backed Pulse analysis. Investor purchase/sale-motive questions remain in the existing workflow. Unavailable current coverage is explicit and does not establish that no real-world events occurred. No annual financial metrics are injected into these news summaries.

## Market reaction and limits

The observation model separates event reference price/time, 1-day and 5-day returns, observation time and source. No timestamp-aligned price-history provider is wired yet, so all missing observations remain unavailable. Current quotes are never substituted for historical event prices. UI states that observations are context/correlation, not proof of causation.

Coverage is intentionally small and primary-source led, not a generic global news feed. No dedicated war-news provider, full-article scraping, paywall bypass or Reuters/AP license integration is present. Country and industry reasoning is conservative and incomplete. Only existing company evidence is used; uncached companies remain unclear. Model summaries are limited extractive selections, not unconstrained synthesis.

## Verification

Run Python through this project's `.venv`, with project-local pytest basetemp. `tests/test_market_pulse.py` covers normalization, clustering, freshness, 304/failure retention, exposure gates, watchlist relevance, delayed portfolio context, missing/noncausal reactions, model safeguards, API/Ask and optional Jev fallback. `tests/live_market_pulse_verification.py` fetches only due official feeds and checks persistence; it never refreshes SEC/holdings.

Frontend schema tests cover validated impact states and watchlist filtering. Playwright uses isolated API responses or an offline cached backend, checks stale/empty states, the event-to-Research workflow, source dates, missing reactions, and mobile overflow. Existing company Research and Ask flows are regression-tested too. Synthetic fixtures are test-only and never served by the live feature.
