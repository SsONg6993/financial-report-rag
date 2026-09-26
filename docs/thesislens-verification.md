# ThesisLens verification

Source checks performed September 26, 2026. These are actual retrieved results, not fixtures or investment conclusions.

- Apple: latest available company filing was a 10-Q for June 27, 2026. Comparable quarterly filing was June 28, 2025. Latest normalized annual Company Facts remained FY2025; the UI identifies that annual period separately. Current quarterly HTML produced 70 source-linked chunks.
- Apple annual gross-margin rule above 45%: FY2025 was 46.9052%, versus FY2024 46.2063%; Python returned threshold satisfied and STABLE. This evaluates the annual rule and does not imply a current-quarter metric.
- Berkshire: June 30, 2026 report filed August 14, 2026, 29 normalized positions; March 31, 2026 report filed May 15, 2026, 29 positions. Share comparisons: 1 NEW, 7 INCREASED, 6 REDUCED, 1 EXITED, 15 UNCHANGED.
- Pershing Square: latest returned original report was March 31, 2026, filed May 15, 2026, 11 positions; prior December 31, 2025 report filed February 17, 2026, 11 positions. Share comparisons: 1 NEW, 1 INCREASED, 6 REDUCED, 1 EXITED, 3 UNCHANGED. The March period is labeled stale under the 150-day policy as of this check.
- Selected OGE official transaction PDF: 113 pages, filename date May 8, 2026. Filing date could not be reliably extracted. Text/table extraction was heavily corrupted (roughly 3.1% row validation); the parser excluded 3,556 unreliable candidate rows and exposed source excerpts without presenting them as normalized verified transactions.
- Official ARKK website was accessible only as a restricted/limited page in this environment and did not expose a downloadable holdings CSV. The adapter reports unavailable and links to the official fund page. No substitute holdings were manufactured.

Local cached source snapshots are excluded from Git. Institutional snapshots identify original 13F filings; amendments are not incorporated. SEC 13F contains issuer/CUSIP rather than tickers or sectors. Unmatched share classes require verification before navigation to a company, and optional sector enrichment reports partial coverage.

Jev thesis judgments were verified with typed mock responses and failure/low-confidence cases; no live Jev performance claim is made. Ollama remains optional; deterministic thresholds, source excerpts, portfolio activity, and local history operate independently.
