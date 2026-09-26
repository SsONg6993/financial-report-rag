import { z } from "zod";

export const pulseEvidenceSchema = z.object({
  text: z.string(),
  source_url: z.string(),
  date: z.string().nullable(),
  source: z.string(),
});
export const impactSchema = z.object({
  event_id: z.string(),
  ticker: z.string(),
  company: z.string(),
  impact_type: z.enum([
    "POTENTIAL_TAILWIND",
    "POTENTIAL_HEADWIND",
    "MIXED",
    "INDIRECT",
    "UNCLEAR",
  ]),
  horizon: z.enum(["IMMEDIATE", "NEAR_TERM", "STRUCTURAL", "UNCLEAR"]),
  evidence_strength: z.enum(["STRONG", "MODERATE", "WEAK"]),
  explanation: z.string(),
  company_exposure: z.string(),
  mechanism: z.array(z.string()),
  confidence: z.string(),
  evidence_refs: z.array(pulseEvidenceSchema),
  watched: z.boolean(),
  portfolio_context: z.array(
    z.object({
      investor_id: z.string(),
      investor: z.string(),
      reporting_period: z.string(),
      filing_date: z.string(),
      source_url: z.string(),
      source_type: z.string(),
      note: z.string(),
    }),
  ),
  judgment: z
    .object({
      sufficiency: z.string(),
      confidence: z.number().nullable(),
      source: z.string(),
    })
    .nullable()
    .optional(),
});
export const eventSchema = z.object({
  id: z.string(),
  headline: z.string(),
  summary: z.string(),
  category: z.string(),
  source: z.string(),
  source_url: z.string(),
  published_at: z.string().nullable(),
  event_time: z.string().nullable(),
  regions: z.array(z.string()),
  sectors: z.array(z.string()),
  importance: z.string(),
  cached_at: z.string(),
  freshness: z.string(),
  stale: z.boolean(),
  recent: z.boolean(),
  what_happened: z.string(),
  why_it_matters: z.string(),
  what_to_watch: z.string(),
  generator: z.string(),
  related_sources: z.array(pulseEvidenceSchema),
  impacts: z.array(impactSchema),
  watchlist_relevant: z.boolean(),
  portfolio_relevant: z.boolean(),
});
export const pulseSchema = z.object({
  events: z.array(eventSchema),
  as_of: z.string(),
  watchlist_event_count: z.number(),
  coverage: z.string(),
  providers: z.array(
    z.object({
      source: z.string(),
      checked_at: z.string().nullable(),
      successful_at: z.string().nullable(),
      error: z.string().nullable(),
      stale: z.boolean(),
    }),
  ),
});
export const pulseDetailSchema = eventSchema.extend({
  reaction_note: z.string(),
  reactions: z.array(
    z.object({
      ticker: z.string(),
      label: z.string(),
      reference_price: z.number().nullable(),
      day_1_return: z.number().nullable(),
      day_5_return: z.number().nullable(),
      source_url: z.string().nullable(),
    }),
  ),
});
export type PulseEvent = z.infer<typeof eventSchema>;
export type PulseImpact = z.infer<typeof impactSchema>;

export function supportedWatchlistEvents(events: PulseEvent[]): PulseEvent[] {
  return events.filter(
    (event) =>
      event.recent &&
      event.watchlist_relevant &&
      event.impacts.some(
        (impact) => impact.watched && impact.impact_type !== "UNCLEAR",
      ),
  );
}
