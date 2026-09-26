import { describe, expect, it } from "vitest";
import { eventSchema, impactSchema, supportedWatchlistEvents } from "./api";

const impact = {
  event_id: "test",
  ticker: "DAL",
  company: "Delta",
  impact_type: "INDIRECT",
  horizon: "NEAR_TERM",
  evidence_strength: "MODERATE",
  explanation: "Potential fuel cost sensitivity.",
  company_exposure: "Fuel is a cost.",
  mechanism: ["Oil", "Fuel costs"],
  confidence: "Exposure, not a forecast",
  evidence_refs: [],
  watched: true,
  portfolio_context: [],
};
const event = {
  id: "test",
  headline: "Test event",
  summary: "Synthetic fixture only",
  category: "Energy",
  source: "Test source",
  source_url: "https://example.org/event",
  published_at: "2026-09-26T10:00:00Z",
  event_time: null,
  regions: [],
  sectors: ["Energy"],
  importance: "NORMAL",
  cached_at: "2026-09-26T12:00:00Z",
  freshness: "2 HOURS AGO",
  stale: false,
  recent: true,
  what_happened: "Test",
  why_it_matters: "Mechanism",
  what_to_watch: "Next update",
  generator: "Test",
  related_sources: [],
  impacts: [impact],
  watchlist_relevant: true,
  portfolio_relevant: false,
};

describe("Market Pulse boundary and watchlist policy", () => {
  it("keeps unknown event time explicit", () => {
    expect(eventSchema.parse(event).event_time).toBeNull();
  });
  it("rejects sensational or trading classifications", () => {
    expect(
      impactSchema.safeParse({ ...impact, impact_type: "BUY" }).success,
    ).toBe(false);
  });
  it("selects only recent supported watchlist exposure", () => {
    const supported = eventSchema.parse(event);
    const unclear = eventSchema.parse({
      ...event,
      impacts: [{ ...impact, impact_type: "UNCLEAR" }],
    });
    const old = eventSchema.parse({ ...event, recent: false });
    expect(supportedWatchlistEvents([supported, unclear, old])).toEqual([
      supported,
    ]);
  });
  it("does not confuse exposure evidence with a price forecast", () => {
    expect(impactSchema.parse(impact).confidence).toContain("not a forecast");
  });
});
