import { describe, expect, it } from "vitest";
import { sectorIntelligenceSchema } from "../../lib/api";

const activity = { NEW: 0, INCREASED: 1, REDUCED: 0, EXITED: 0 };
const response = {
  institutions: [
    {
      institution_id: "berkshire",
      name: "Berkshire Hathaway",
      investor: "Warren Buffett / Berkshire Hathaway",
      reporting_period: "2026-06-30",
      previous_period: "2026-03-31",
      filing_date: "2026-08-14",
      source_url: "https://www.sec.gov/fixture",
      source_type: "SEC Form 13F",
      available_periods: ["2026-06-30", "2026-03-31"],
      taxonomy: "ThesisLens Sector Taxonomy v1 (SEC SIC based)",
      taxonomy_source_url:
        "https://www.sec.gov/search-filings/standard-industrial-classification-sic-code-list",
      sector_filter: null,
      allocation: [
        {
          sector: "Information Technology",
          reported_value: 100,
          weight: 0.8,
          holding_count: 1,
          holdings: [
            {
              ticker: "AAPL",
              issuer: "APPLE INC",
              cusip: "037833100",
              security_class: "COM",
              put_call: "",
              shares: 10,
              reported_value: 100,
              weight: 0.8,
              sector: "Information Technology",
              classification_status: "verified_identifier",
              taxonomy: "ThesisLens Sector Taxonomy v1 (SEC SIC based)",
              taxonomy_code: "SEC SIC 3571",
              classification_source_url:
                "https://data.sec.gov/submissions/CIK0000320193.json",
            },
          ],
        },
      ],
      sector_changes: [
        {
          sector: "Information Technology",
          weight_before: 0.7,
          weight_after: 0.8,
          weight_change: 0.1,
          reported_value_before: 80,
          reported_value_after: 100,
          position_activity: activity,
        },
      ],
      position_changes: [],
      coverage: {
        holding_count: 2,
        option_holding_count: 0,
        classified_holding_count: 1,
        classified_holding_percentage: 0.5,
        reported_value_total: 125,
        classified_reported_value: 100,
        classified_value_percentage: 0.8,
        unknown_reported_value: 25,
        unknown_value_percentage: 0.2,
      },
      concentration: {
        largest_sector: "Information Technology",
        largest_sector_weight: 0.8,
        herfindahl_index: 0.68,
      },
      comparison: {
        available: true,
        reason: null,
        weight_change_note: "Weight is not a trade measure.",
        share_change_note: "Shares are reported quantities.",
      },
    },
  ],
  unavailable_institutions: [],
  aggregate: [
    {
      sector: "Information Technology",
      reported_value: 100,
      average_weight: 0.8,
      institution_count: 1,
      holding_count: 1,
      position_activity: activity,
    },
  ],
  coverage: {
    institution_count: 1,
    requested_institution_count: 1,
    reported_value_total: 125,
    classified_reported_value: 100,
    classified_value_percentage: 0.8,
    unknown_value_percentage: 0.2,
  },
  period_filter: null,
  sector_filter: null,
  coverage_notes: ["Reporting periods can differ."],
  interpretation_policy: "Historical evidence is not a prediction.",
};

describe("sector intelligence API boundary", () => {
  it("preserves unknown coverage and distinct position activity", () => {
    const parsed = sectorIntelligenceSchema.parse(response);
    expect(parsed.coverage.unknown_value_percentage).toBe(0.2);
    expect(
      parsed.institutions[0].sector_changes[0].position_activity.INCREASED,
    ).toBe(1);
  });

  it("requires dated original-source metadata", () => {
    expect(
      sectorIntelligenceSchema.safeParse({
        ...response,
        institutions: [
          { ...response.institutions[0], reporting_period: undefined },
        ],
      }).success,
    ).toBe(false);
  });
});
