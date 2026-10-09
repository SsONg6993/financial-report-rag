import { afterEach, expect, it, vi } from "vitest";
import { z } from "zod";
import { api, money, percent, ruleSchema, evidenceSchema } from "./api";
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
    vi.fn().mockResolvedValue(new Response("", { status: 500 })),
  );
  await expect(api("/market-pulse", z.unknown())).rejects.toThrow(
    "HTTP 500 for /api/market-pulse",
  );
});
