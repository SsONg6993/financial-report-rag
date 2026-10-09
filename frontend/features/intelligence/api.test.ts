import { describe, expect, it } from "vitest";
import { intelligenceFeedSchema, institutionalActivitySchema } from "./api";

const event = {
  id: "event-1", event_type: "portfolio_exit", entity_id: "berkshire",
  entity_name: "Berkshire Hathaway", ticker: "AAPL", headline: "Reported exit",
  source_type: "SEC Form 13F", source_url: "https://www.sec.gov/example",
  reporting_period: "2026-06-30", published_at: "2026-08-14", event_at: null,
  detected_at: "2026-08-15", importance_score: 0.5, facts: {}, read_at: null,
  why_shown: "Matches watchlist", priority: "critical",
  freshness_state: "dated",
};

describe("Intelligence API boundary", () => {
  it("keeps reporting and filing dates separate", () => {
    const parsed = intelligenceFeedSchema.parse({ events: [event], as_of: "2026-08-15", coverage: "Partial" });
    expect(parsed.events[0].reporting_period).toBe("2026-06-30");
    expect(parsed.events[0].published_at).toBe("2026-08-14");
  });
  it("rejects invalid source URLs", () => {
    expect(intelligenceFeedSchema.safeParse({ events: [{ ...event, source_url: "not-a-url" }], as_of: "x", coverage: "x" }).success).toBe(false);
  });
  it("preserves unavailable cross-period convergence", () => {
    const parsed = institutionalActivitySchema.parse({ ticker: "AAPL", tracked_managers: [], counts: null, convergence: false, coverage: "Incomplete" });
    expect(parsed.counts).toBeNull();
  });
});
