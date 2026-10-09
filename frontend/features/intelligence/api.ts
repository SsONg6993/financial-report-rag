import { z } from "zod";

export const intelligenceEventSchema = z.object({
  id: z.string(), event_type: z.string(), entity_id: z.string(), entity_name: z.string(),
  ticker: z.string().nullable(), headline: z.string(), source_type: z.string(),
  source_url: z.url(), reporting_period: z.string().nullable(), published_at: z.string(),
  event_at: z.string().nullable(), detected_at: z.string(), importance_score: z.number(),
  facts: z.record(z.string(), z.unknown()), read_at: z.string().nullable(),
  freshness_state: z.enum(["dated", "stale"]),
  why_shown: z.string(), priority: z.enum(["critical", "normal", "digest"]),
});
export const intelligenceFeedSchema = z.object({
  events: z.array(intelligenceEventSchema), as_of: z.string(), coverage: z.string(),
});
export const institutionalActivitySchema = z.object({
  ticker: z.string(),
  tracked_managers: z.array(z.object({
    manager_id: z.string(), manager: z.string(), reporting_period: z.string(),
    filing_date: z.string(), source_url: z.url(), reported_shares: z.number(), activity: z.string(),
  })),
  counts: z.record(z.string(), z.number()).nullable(), convergence: z.boolean(), coverage: z.string(),
});
export const publicSourcesSchema = z.object({
  sources: z.array(z.object({
    id: z.string(), name: z.string(), source_url: z.url(), followed: z.boolean(),
    checked_at: z.string().nullable(), error: z.string().nullable(),
  })),
  note: z.string(),
});
