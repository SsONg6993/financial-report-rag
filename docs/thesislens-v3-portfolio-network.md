# ThesisLens V3 — institutional portfolio network

## Branch and starting point

V3 is implemented on `codex/v3-portfolio-network`, created from commit `c41120c` (`Integrate ThesisLens V2 and improve company reliability UI`). This preserves the open V2 pull request and makes the V3 dependency on that reviewed foundation explicit.

## Calculation contract

- An overlap requires the same normalized CUSIP, reported security class, put/call designation, and shares/principal type. Tickers are presentation/navigation metadata and never establish an overlap.
- Unmapped holdings remain in the source snapshot but are excluded from overlap metrics. They are never matched by issuer-name or ticker guess.
- For a selected date, each manager uses the latest stored snapshot at or before that date. The UI exposes each actual reporting and filing date, and warns when dates or disclosure types differ.
- “Common” means present in every selected mapped portfolio. “Shared” means present in at least two selected mapped portfolios.
- Jaccard similarity is the size of the all-manager intersection divided by the union. Pairwise Jaccard is calculated separately for each pair.
- Disclosed portfolio weight overlap is the sum, over securities common to every selected manager, of the minimum disclosed weight among those managers. It compares reported-table weights, not economic exposure or investment intent.
- Position changes compare share counts between ordered snapshots for the same institution and disclosure type. Missing prior periods produce no fabricated change.
- Metrics use every mapped holding. The visualization is bounded to 40 securities, prioritizing ownership count and combined disclosed weight, to keep interaction readable.

## Coverage and interpretation

13F reports are delayed, incomplete, and omit many assets and hedges. Original filings are used; amendments are not silently consolidated. Options remain distinct from common stock. ARKK daily fund holdings remain a separate disclosure type and are explicitly labeled when compared with quarterly 13F coverage. A shared holding does not demonstrate shared rationale, timing, conviction, or coordination.

The feature uses only verified snapshots already stored by ThesisLens. Automated tests use synthetic fixtures exclusively. No paid data source, live refresh, logo service, or image-scraping dependency was added. Monograms remain the safe fallback until image usage rights and stable official assets are verified.
