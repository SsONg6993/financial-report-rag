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
  security_class: z.string().default(""),
  share_type: z.string().default("SH"),
  ticker_source: z.string().default(""),
  ticker_verified: z.boolean().default(false),
  entry_price_estimate: z
    .object({
      status: z.enum(["not_reliably_estimable", "indicative_range"]),
      label: z.string(),
      actual_purchase_price: z.number().nullable(),
      estimated_average: z.number().nullable(),
      price_low: z.number().nullable(),
      price_high: z.number().nullable(),
      confidence: z.string(),
      window: z
        .object({
          start: z.string(),
          end: z.string(),
          shares_added: z.number(),
        })
        .nullable(),
      method: z.string(),
      assumptions: z.array(z.string()),
      source_url: z.string(),
    })
    .optional(),
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
const overlapOwnerSchema = z.object({
  institution_id: z.string(),
  shares: z.number(),
  reported_value: z.number(),
  weight: z.number(),
});
const overlapSecuritySchema = z.object({
  id: z.string(),
  ticker: z.string(),
  issuer: z.string(),
  cusip: z.string(),
  security_class: z.string(),
  put_call: z.string(),
  owner_count: z.number(),
  owners: z.array(overlapOwnerSchema),
  combined_weight: z.number(),
});
export const portfolioOverlapSchema = z.object({
  requested_period: z.string().nullable(),
  periods: z.array(z.string()),
  institutions: z.array(
    z.object({
      id: z.string(),
      name: z.string(),
      investor: z.string().optional(),
      available: z.boolean(),
      holding_count: z.number(),
      mapped_count: z.number(),
      unmapped_count: z.number(),
      unique_count: z.number(),
      reporting_period: z.string().optional(),
      filing_date: z.string().optional(),
      source_url: z.string().optional(),
      source_type: z.string().optional(),
      freshness: z.string().optional(),
    }),
  ),
  securities: z.array(overlapSecuritySchema),
  network: z.object({
    securities: z.array(overlapSecuritySchema),
    truncated: z.boolean(),
    security_limit: z.number(),
    edges: z.array(overlapOwnerSchema.extend({ security_id: z.string() })),
  }),
  summary: z.object({
    common_count: z.number(),
    shared_count: z.number(),
    union_count: z.number(),
    jaccard: z.number().nullable(),
    weight_overlap: z.number().nullable(),
  }),
  pairwise: z.array(
    z.object({
      left: z.string(),
      right: z.string(),
      comparable: z.boolean(),
      shared_count: z.number().nullable(),
      jaccard: z.number().nullable(),
      weight_overlap: z.number().nullable(),
    }),
  ),
  history: z.array(
    z.object({
      institution_id: z.string(),
      institution_name: z.string(),
      reporting_period: z.string(),
      source_type: z.string(),
      holding_count: z.number(),
      mapped_count: z.number(),
      disclosed_value_total: z.number(),
      top_five_weight: z.number(),
      filing_date: z.string(),
      source_url: z.string(),
      top_holdings: z.array(
        z.object({
          ticker: z.string(),
          issuer: z.string(),
          weight: z.number(),
          reported_value: z.number(),
          cusip: z.string(),
          security_class: z.string(),
        }),
      ),
    }),
  ),
  changes: z.array(changeSchema.extend({ institution_id: z.string() })),
  coverage_notes: z.array(z.string()),
});
const sectorActivitySchema = z.object({
  NEW: z.number(),
  INCREASED: z.number(),
  REDUCED: z.number(),
  EXITED: z.number(),
  UNCHANGED: z.number().optional(),
});
const sectorAllocationSchema = z.object({
  sector: z.string(),
  reported_value: z.number(),
  weight: z.number(),
  holding_count: z.number(),
  holdings: z.array(
    z.object({
      ticker: z.string(),
      issuer: z.string(),
      cusip: z.string(),
      security_class: z.string(),
      put_call: z.string(),
      shares: z.number(),
      reported_value: z.number(),
      weight: z.number(),
      sector: z.string(),
      classification_status: z.string(),
      taxonomy: z.string(),
      taxonomy_code: z.string().nullable(),
      classification_source_url: z.string().nullable(),
    }),
  ),
});
const sectorInstitutionSchema = z.object({
  institution_id: z.string(),
  name: z.string(),
  investor: z.string(),
  reporting_period: z.string(),
  previous_period: z.string().nullable(),
  filing_date: z.string(),
  source_url: z.string(),
  source_type: z.string(),
  available_periods: z.array(z.string()),
  taxonomy: z.string(),
  taxonomy_source_url: z.string(),
  sector_filter: z.string().nullable(),
  allocation: z.array(sectorAllocationSchema),
  sector_changes: z.array(
    z.object({
      sector: z.string(),
      weight_before: z.number(),
      weight_after: z.number(),
      weight_change: z.number(),
      reported_value_before: z.number(),
      reported_value_after: z.number(),
      position_activity: sectorActivitySchema,
    }),
  ),
  position_changes: z.array(
    z.object({
      sector: z.string(),
      issuer: z.string(),
      ticker: z.string(),
      cusip: z.string(),
      security_class: z.string(),
      put_call: z.string(),
      activity: z.string(),
      shares_before: z.number(),
      comparable_shares_before: z.number(),
      shares_after: z.number(),
      share_change: z.number(),
      corporate_action_adjusted: z.boolean(),
      corporate_action_source_url: z.string().nullable(),
      share_change_interpretation: z.string(),
    }),
  ),
  coverage: z.object({
    holding_count: z.number(),
    option_holding_count: z.number(),
    classified_holding_count: z.number(),
    classified_holding_percentage: z.number(),
    reported_value_total: z.number(),
    classified_reported_value: z.number(),
    classified_value_percentage: z.number(),
    unknown_reported_value: z.number(),
    unknown_value_percentage: z.number(),
  }),
  concentration: z.object({
    largest_sector: z.string().nullable(),
    largest_sector_weight: z.number().nullable(),
    herfindahl_index: z.number().nullable(),
  }),
  comparison: z.object({
    available: z.boolean(),
    reason: z.string().nullable(),
    weight_change_note: z.string(),
    share_change_note: z.string(),
  }),
});
export const sectorIntelligenceSchema = z.object({
  institutions: z.array(sectorInstitutionSchema),
  unavailable_institutions: z.array(z.string()),
  aggregate: z.array(
    z.object({
      sector: z.string(),
      reported_value: z.number(),
      average_weight: z.number(),
      institution_count: z.number(),
      holding_count: z.number(),
      position_activity: sectorActivitySchema,
    }),
  ),
  coverage: z.object({
    institution_count: z.number(),
    requested_institution_count: z.number(),
    reported_value_total: z.number(),
    classified_reported_value: z.number(),
    classified_value_percentage: z.number(),
    unknown_value_percentage: z.number(),
  }),
  period_filter: z.string().nullable(),
  sector_filter: z.string().nullable(),
  coverage_notes: z.array(z.string()),
  interpretation_policy: z.string(),
});
export const companySchema = z.object({
  ticker: z.string(),
  available: z.boolean(),
  name: z.string(),
  identity: z
    .object({
      ticker: z.string(),
      cik: z.number(),
      name: z.string(),
      exchange: z.string(),
      source_url: z.string(),
    })
    .nullable()
    .optional(),
  availability_status: z
    .enum([
      "ready",
      "filings_only",
      "provider_error",
      "loading",
      "missing_filings",
      "unknown_symbol",
    ])
    .optional(),
  overview: z
    .object({
      text: z.string(),
      source_url: z.string(),
      period: z.string(),
      section: z.string().optional(),
    })
    .nullable()
    .optional(),
  overview_fallback: z
    .object({ message: z.string(), source_url: z.string() })
    .nullable()
    .optional(),
  classification: z
    .object({
      sector: z.string(),
      taxonomy: z.string(),
      taxonomy_code: z.string().nullable(),
      source_url: z.string().nullable(),
      status: z.string(),
    })
    .optional(),
  filing_timeline: z
    .array(
      z.object({
        form: z.string(),
        report_date: z.string(),
        filing_date: z.string(),
        source_url: z.string(),
      }),
    )
    .default([]),
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
      availability: z
        .object({
          available: z.boolean(),
          reason: z.string().nullable(),
          message: z.string(),
          configured_providers: z.array(z.string()),
          attempts: z.array(
            z.object({
              provider: z.string(),
              status: z.string(),
              reason: z.string().nullable().optional(),
            }),
          ),
          checked_at: z.string().nullable().optional(),
          ttl_seconds: z.number(),
        })
        .optional(),
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
export const companyIdentitySchema = z.object({
  ticker: z.string(),
  cik: z.number(),
  name: z.string(),
  exchange: z.string(),
  source_url: z.string(),
});
export const companySearchSchema = z.object({
  results: z.array(companyIdentitySchema),
  checked_at: z.string(),
  stale: z.boolean(),
  error: z.string().nullable(),
});
export const companyResolveSchema = z.object({
  status: z.enum([
    "resolved",
    "ambiguous",
    "unknown",
    "unsupported_market",
    "invalid",
  ]),
  company: companyIdentitySchema.nullable().optional(),
  matches: z.array(companyIdentitySchema),
  message: z.string().nullable(),
  checked_at: z.string().optional(),
  stale: z.boolean().optional(),
  error: z.string().nullable().optional(),
});
export const homeSchema = z.object({
  market_overview: z
    .array(
      z.object({
        ticker: z.string(),
        price: z.number().nullable(),
        previous_close: z.number().nullable(),
        change: z.number().nullable(),
        currency: z.string(),
        quote_as_of: z.string().nullable(),
        provider: z.string().nullable(),
        source_url: z.string().nullable(),
        status: z.string(),
        available: z.boolean(),
        missing_reason: z.string().nullable(),
      }),
    )
    .default([]),
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
  sector_analysis: sectorIntelligenceSchema.optional(),
  sector_sections: z
    .object({
      short_answer: z.string(),
      accumulation: z.array(z.string()),
      reductions: z.array(z.string()),
      historical_changes: z.array(z.string()),
      limitations: z.array(z.string()),
    })
    .optional(),
  synthesis_available: z.boolean().optional(),
  model: z.string().optional(),
  intent: z
    .enum([
      "general",
      "financial_research",
      "portfolio_analysis",
      "institutional_sector_analysis",
      "current_public_information",
      "unsupported",
    ])
    .default("financial_research"),
  mode: z.enum(["auto", "general", "research"]).default("auto"),
  configuration_error: z.string().nullable().optional(),
  configuration_error_code: z
    .enum([
      "remote_llm_disabled",
      "ollama_service_not_running",
      "ollama_model_missing",
      "ollama_timeout",
      "ollama_loading",
      "ollama_invalid_response",
    ])
    .nullable()
    .optional(),
  privacy: z
    .string()
    .default("No private workspace data was sent to an external model."),
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
export type PortfolioOverlap = z.infer<typeof portfolioOverlapSchema>;
export type SectorIntelligence = z.infer<typeof sectorIntelligenceSchema>;
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
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      ...options,
      headers: { "Content-Type": "application/json", ...options?.headers },
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError")
      throw error;
    throw new ApiError(
      "Backend unavailable. Start the Python API and retry; your saved work is safe.",
      0,
    );
  }
  if (!response.ok)
    throw new ApiError(
      response.status === 422
        ? "Please check the information you entered."
        : response.status === 500
          ? `The API returned HTTP 500 for /api${path}. The backend is running but this request failed.`
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
