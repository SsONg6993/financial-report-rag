import { afterEach, describe, expect, it, vi } from "vitest";
import { z } from "zod";
import {
  api,
  evidenceSchema,
  investorSchema,
  money,
  percent,
  ruleSchema,
} from "./api";

afterEach(() => vi.unstubAllGlobals());

it("preserves unavailable values rather than fake zeroes", () => {
  expect(money(null)).toBe("Unavailable");
  expect(percent(undefined)).toBe("Unavailable");
  expect(percent(0.45)).toBe("45.0%");
});

it("validates typed threshold rules", () => {
  expect(
    ruleSchema.safeParse({
      metric: "gross_margin",
      operator: ">=",
      threshold: 0.45,
    }).success,
  ).toBe(true);
  expect(
    ruleSchema.safeParse({
      metric: "gross_margin",
      operator: "BUY",
      threshold: 0.45,
    }).success,
  ).toBe(false);
});

it("requires evidence text", () => {
  expect(
    evidenceSchema.safeParse({ source_url: "https://www.sec.gov/" }).success,
  ).toBe(false);
});

it("rejects malformed service responses", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValue(
        new Response(JSON.stringify({ value: "bad" }), { status: 200 }),
      ),
  );
  await expect(api("/test", z.object({ value: z.number() }))).rejects.toThrow(
    "unexpected format",
  );
});

it("provides an actionable API failure", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(new Response("", { status: 503 })),
  );
  await expect(api("/test", z.unknown())).rejects.toThrow("saved work is safe");
});

it("distinguishes backend network failure from an HTTP response", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("fetch failed")));
  await expect(api("/test", z.unknown())).rejects.toThrow(
    "Backend unavailable",
  );
});

it("identifies an API HTTP 500", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response("", {
        status: 500,
        headers: { "X-Request-ID": "request-123" },
      }),
    ),
  );
  await expect(api("/market-pulse", z.unknown())).rejects.toThrow(
    "HTTP 500 for /api/market-pulse. The backend is running but this request failed. Reference: request-123.",
  );
});

describe("investor response parsing", () => {
  it("treats an omitted summary estimate as unavailable", () => {
    const result = investorSchema.parse({
      id: "manager",
      name: "Manager",
      investor: "",
      style_tags: [],
      source_type: "SEC Form 13F",
      followed: false,
      available: true,
      latest_period: "2026-06-30",
      filing_date: "2026-08-14",
      source_url: "https://www.sec.gov/fixture",
      freshness: "Historical disclosure",
      refresh: { stale: false, ttl_seconds: 3600 },
      holdings: [
        {
          issuer: "EXAMPLE INC",
          ticker: "EXM",
          shares: 10,
          weight: 1,
          reported_value: 100,
          put_call: "",
          sector: "Unknown",
          cusip: "000000001",
          entry_price_estimate: {},
        },
      ],
      changes: [],
      timeline: [],
      notes: [],
      rationale: "No sourced rationale available.",
    });
    expect(result.holdings[0].entry_price_estimate).toBeUndefined();
  });
});
