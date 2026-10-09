import { describe, expect, it } from "vitest";
import { networkLayout, nextPlaybackPeriod } from "./layout";
import type { PortfolioOverlap } from "@/lib/api";

const fixture = {
  institutions: [
    {
      id: "alpha",
      name: "Alpha",
      available: true,
      holding_count: 1,
      mapped_count: 1,
      unmapped_count: 0,
      unique_count: 0,
    },
    {
      id: "beta",
      name: "Beta",
      available: true,
      holding_count: 1,
      mapped_count: 1,
      unmapped_count: 0,
      unique_count: 0,
    },
  ],
  network: {
    securities: [
      {
        id: "cusip|com||sh",
        ticker: "AAA",
        issuer: "AAA Inc",
        cusip: "cusip",
        security_class: "COM",
        put_call: "",
        owner_count: 2,
        owners: [],
        combined_weight: 0.4,
      },
    ],
    edges: [],
    truncated: false,
    security_limit: 40,
  },
} as unknown as PortfolioOverlap;

describe("portfolio network layout", () => {
  it("places institution and security nodes deterministically", () => {
    const first = networkLayout(fixture);
    const second = networkLayout(fixture);
    expect([...first.institutions]).toEqual([...second.institutions]);
    expect(first.institutions.get("alpha")?.x).toBeLessThan(
      first.securities.get("cusip|com||sh")?.x ?? 0,
    );
  });

  it("plays historical periods chronologically without inventing dates", () => {
    const periods = ["2026-06-30", "2026-03-31", "2025-12-31"];
    expect(nextPlaybackPeriod(periods, null)).toBe("2025-12-31");
    expect(nextPlaybackPeriod(periods, "2025-12-31")).toBe("2026-03-31");
    expect(nextPlaybackPeriod(periods, "2026-06-30")).toBe("2025-12-31");
  });
});
