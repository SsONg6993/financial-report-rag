import { z } from "zod";

export const evidenceSchema = z.object({
  text: z.string(),
  source_url: z.string().default(""),
  period: z.string().optional(),
  source_type: z.string().optional(),
});
export const ruleSchema = z.object({
  metric: z.string(),
  operator: z.enum([">", ">=", "<", "<="]),
  threshold: z.number(),
});
export const suggestionSchema = z.object({
  id: z.string(),
  category: z.string(),
  text: z.string(),
  why_it_matters: z.string(),
  evidence: z.array(evidenceSchema),
  support_condition: z.string(),
  invalidate_condition: z.string(),
  rule: ruleSchema.nullable(),
  generator: z.string(),
  period: z.string(),
});
export const thesisSchema = z.object({
  id: z.string(),
  ticker: z.string(),
  text: z.string(),
  rule: ruleSchema.nullable(),
  status: z.string(),
  explanation: z.string().optional(),
  supporting_evidence: z.array(evidenceSchema).default([]),
  contradicting_evidence: z.array(evidenceSchema).default([]),
  history: z
    .array(
      z.object({
        status: z.string(),
        evaluated_at: z.string(),
        period: z.string().optional(),
        explanation: z.string().optional(),
      }),
    )
    .default([]),
});
const refreshSchema = z.object({
  stale: z.boolean(),
  ttl_seconds: z.number(),
  checked_at: z.string().nullable().optional(),
  error: z.string().nullable().optional(),
});
const holdingSchema = z.object({
  issuer: z.string(),
  ticker: z.string(),
  shares: z.number(),
  weight: z.number(),
  reported_value: z.number(),
  put_call: z.string(),
  sector: z.string(),
  cusip: z.string(),
});
export const changeSchema = z
  .object({
    issuer: z.string(),
    ticker: z.string(),
    activity: z.string(),
    pct_change: z.number().nullable(),
    reporting_period: z.string().optional(),
    current_period: z.string().optional(),
    filing_date: z.string().optional(),
    source_url: z.string().optional(),
  })
  .passthrough();
export const investorSchema = z.object({
  id: z.string(),
  name: z.string(),
  investor: z.string(),
  style_tags: z.array(z.string()),
  source_type: z.string(),
  followed: z.boolean(),
  available: z.boolean(),
  latest_period: z.string().nullable(),
  filing_date: z.string().nullable(),
  source_url: z.string().nullable(),
  freshness: z.string(),
  refresh: refreshSchema,
  holdings: z.array(holdingSchema),
  changes: z.array(changeSchema),
  timeline: z.array(
    z.object({
      period: z.string(),
      filing_date: z.string(),
      source_url: z.string(),
    }),
  ),
  notes: z.array(z.string()),
  rationale: z.string(),
});
export const companySchema = z.object({
  ticker: z.string(),
  available: z.boolean(),
  name: z.string(),
  market: z
    .object({
      price: z.number().nullable().optional(),
      market_cap: z.number().nullable().optional(),
      trailing_pe: z.number().nullable().optional(),
      currency: z.string().optional(),
      previous_close: z.number().nullable().optional(),
      quote_as_of: z.string().nullable().optional(),
      fetched_at: z.string().nullable().optional(),
      provider: z.string().optional(),
      source_url: z.string().optional(),
      status: z.enum(["live", "delayed", "cached", "unavailable"]).optional(),
      stale: z.boolean().optional(),
    })
    .optional(),
  market_as_of: z.string().optional(),
  financial_context: z
    .object({
      kind: z.enum(["annual", "quarterly"]),
      period: z.string(),
      end: z.string(),
      metrics: z.array(
        z.object({
          metric: z.string(),
          label: z.string(),
          period: z.string(),
          value: z.number().nullable(),
          previous: z.number().nullable(),
          previous_period: z.string().nullable(),
          yoy: z.number().nullable(),
          source_url: z.string(),
          start: z.string().nullable().optional(),
        }),
      ),
    })
    .optional(),
  metric_context: z
    .array(
      z.object({
        metric: z.string(),
        label: z.string(),
        current: z.number().nullable(),
        previous: z.number().nullable(),
        current_period: z.string(),
        previous_period: z.string().nullable(),
        delta: z.number().nullable(),
        relative_change: z.number().nullable(),
        status: z.string(),
        meaning: z.string(),
        source_url: z.string(),
        previous_source_url: z.string(),
      }),
    )
    .default([]),
  risk_cards: z
    .array(
      z.object({
        title: z.string(),
        summary: z.string(),
        why_it_matters: z.string(),
        period: z.string(),
        source_url: z.string(),
        evidence: evidenceSchema,
      }),
    )
    .default([]),
  annual: z
    .object({
      fiscal_year: z.number().optional(),
      revenue: z.number().nullable().optional(),
      revenue_growth: z.number().nullable().optional(),
      net_margin: z.number().nullable().optional(),
      free_cash_flow: z.number().nullable().optional(),
      source_url: z.string().optional(),
    })
    .optional(),
  radar: z.array(
    z.object({
      text: z.string(),
      period: z.string().nullable(),
      source_url: z.string().nullable(),
    }),
  ),
  suggestions: z.array(suggestionSchema),
  changes: z.array(
    z.object({
      category: z.string(),
      text: z.string(),
      comparison: z.string().optional(),
      evidence: z.array(evidenceSchema).optional(),
      current: evidenceSchema.optional(),
      previous: evidenceSchema.optional(),
    }),
  ),
  theses: z.array(thesisSchema),
  risks: z.array(evidenceSchema),
  templates: z.record(z.string(), z.array(z.string())),
  warnings: z.array(z.string()),
  watchlisted: z.boolean(),
  refresh: refreshSchema,
});
export const homeSchema = z.object({
  activity: z.array(
    changeSchema.extend({
      institution: z.string(),
      institution_id: z.string(),
      source_type: z.string(),
      freshness: z.string(),
    }),
  ),
  ideas: z.array(
    z.object({
      ticker: z.string(),
      reasons: z.array(z.string()),
      source_url: z.string(),
      period: z.string().nullable(),
      watchlisted: z.boolean(),
    }),
  ),
  watchlist: z.array(
    z.object({
      ticker: z.string(),
      tracked: z.number(),
      attention: z.number(),
      available: z.boolean(),
    }),
  ),
  investors: z.array(investorSchema),
  recent_disclosures: z.array(
    z.object({
      source_type: z.string(),
      ticker: z.string(),
      activity: z.string(),
      filing_date: z.string(),
      reporting_period: z.string(),
      source_url: z.string(),
    }),
  ),
  as_of: z.string(),
});
export const answerSchema = z.object({
  answer: z.string(),
  evidence: z.array(evidenceSchema),
  source: z.string(),
  sections: z
    .object({
      short_answer: z.string(),
      why: z.array(z.string()),
      numbers: z.array(z.string()),
      watch: z.array(z.string()),
      annual_context: z.array(z.string()).default([]),
    })
    .optional(),
  synthesis_available: z.boolean().optional(),
  model: z.string().optional(),
});
export const disclosureSchema = z.object({
  available: z.boolean(),
  refresh: refreshSchema,
  warnings: z.array(z.string()),
  records: z.array(
    z.object({
      id: z.string(),
      source_type: z.string(),
      ticker: z.string(),
      filing_date: z.string(),
      reporting_period: z.string(),
      activity: z.string(),
      source_url: z.string(),
      insider: z.string().optional(),
      role: z.string().optional(),
      transaction_date: z.string().optional(),
      shares: z.number().nullable().optional(),
      price: z.number().nullable().optional(),
      transaction_code: z.string().optional(),
      context: z.string(),
      filer: z.string().optional(),
      ownership_percentage: z.number().nullable().optional(),
      form: z.string().optional(),
    }),
  ),
});

export type Investor = z.infer<typeof investorSchema>;
export type Evidence = z.infer<typeof evidenceSchema>;
export type Suggestion = z.infer<typeof suggestionSchema>;
export type Thesis = z.infer<typeof thesisSchema>;
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}
export async function api<T>(
  path: string,
  schema: z.ZodType<T>,
  options?: RequestInit,
): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...options?.headers },
  });
  if (!response.ok)
    throw new ApiError(
      response.status === 422
        ? "Please check the information you entered."
        : "The research service is unavailable. Your saved work is safe; please retry.",
      response.status,
    );
  const parsed = schema.safeParse(await response.json());
  if (!parsed.success)
    throw new ApiError(
      "The source returned an unexpected format. Please retry after the service updates.",
      502,
    );
  return parsed.data;
}
export async function write(
  path: string,
  body: unknown,
  method = "PUT",
): Promise<void> {
  await api(path, z.unknown(), { method, body: JSON.stringify(body) });
}
export function money(value: number | null | undefined): string {
  return value == null
    ? "Unavailable"
    : new Intl.NumberFormat("en-US", {
        style: "currency",
        currency: "USD",
        notation: Math.abs(value) >= 1e6 ? "compact" : "standard",
        maximumFractionDigits: 2,
      }).format(value);
}
export function percent(value: number | null | undefined): string {
  return value == null ? "Unavailable" : `${(value * 100).toFixed(1)}%`;
}
