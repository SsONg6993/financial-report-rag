import { describe, expect, it } from "vitest";
import { companyResolveSchema, companySearchSchema } from "../../lib/api";

const identity = {
  ticker: "KEYS",
  cik: 1601046,
  name: "Keysight Technologies, Inc.",
  exchange: "NYSE",
  source_url: "https://www.sec.gov/files/company_tickers_exchange.json",
};

describe("SEC company identity contracts", () => {
  it("retains source, ticker, CIK, exchange and freshness", () => {
    expect(companySearchSchema.parse({
      results: [identity],
      checked_at: "2026-10-09T00:00:00+00:00",
      stale: true,
      error: "Temporary upstream timeout",
    })).toMatchObject({ results: [identity], stale: true });
  });

  it("keeps ambiguous listings separate from a resolved company", () => {
    const result = companyResolveSchema.parse({
      status: "ambiguous",
      company: null,
      matches: [{ ...identity, ticker: "GOOG" }, { ...identity, ticker: "GOOGL" }],
      message: "Choose a specific listing.",
    });
    expect(result.company).toBeNull();
    expect(result.matches).toHaveLength(2);
  });
});
