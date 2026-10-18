# Institutional Sector Intelligence

ThesisLens calculates sector exposure only from successful portfolio snapshots already saved in local SQLite. It does not refresh disclosures when the analytics endpoint or Ask workflow runs.

## Classification contract

The product uses **ThesisLens Sector Taxonomy v1 (SEC SIC based)**. This is a public, application-owned taxonomy, not licensed GICS data.

1. A holding must match an explicit normalized CUSIP in `src/sector_intelligence.py`.
2. That registry entry records the issuer's SEC CIK and SIC code. Its source link is the official SEC submissions JSON for the CIK.
3. The SIC is mapped deterministically to a familiar high-level sector label.
4. A missing CUSIP mapping is `Unknown`. Issuer names and tickers are never used to guess a sector.

The official SEC [SIC code list](https://www.sec.gov/search-filings/standard-industrial-classification-sic-code-list) explains that SIC codes in disseminated EDGAR filings indicate a company's type of business. The initial registry covers a small set of frequently disclosed securities. Coverage is therefore intentionally incomplete and is reported by both holding count and reported value.

## Calculations

- **Sector reported value** is the sum of non-negative reported values for holdings classified into that sector.
- **Sector weight** is sector reported value divided by total disclosed reported value, including Unknown positions in the denominator.
- **Concentration** includes the largest sector weight and a sector Herfindahl index, the sum of squared sector weights.
- **Sector weight change** compares the current and immediately preceding saved snapshot of the same institution and disclosure type.
- **Position activity** compares class-aware identities: CUSIP, security class, put/call, and share type. `NEW`, `INCREASED`, `REDUCED`, and `EXITED` describe changes in disclosed quantities, not confirmed trades.
- **Options** can contribute to disclosed sector value but are not counted as ordinary-share accumulation or reduction.
- **Corporate actions** are applied only when a dated factor and source are explicitly supplied to the analytics function. Otherwise the raw share change remains visible with a warning that it is not adjusted.

Combined multi-manager results sum reported values and show the average disclosed portfolio weight across every analyzed manager, treating an absent sector as zero. Manager reporting periods and portfolio sizes may differ, so the combined values are descriptive rather than a market-wide capital-flow estimate.

## Interpretation boundaries

13F reports are delayed and omit many assets, short positions, and hedges. ARKK daily fund holdings use a separate disclosure clock and remain labeled as daily fund data. A sector weight can change because positions changed, prices moved, or both. The records do not disclose transaction dates, execution prices, personal decision-makers, motives, or future purchases.

Ask therefore separates verified historical allocation, observed disclosed-share changes, deterministic ThesisLens interpretation, and what cannot be concluded. A forward-looking question receives historical evidence plus an explicit statement that future interest cannot be known from the disclosures.
