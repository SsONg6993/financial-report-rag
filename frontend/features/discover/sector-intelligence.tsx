"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ExternalLink, Info, TrendingDown, TrendingUp } from "lucide-react";
import {
  api,
  money,
  percent,
  sectorIntelligenceSchema,
} from "@/lib/api";
import {
  ErrorState,
  formatDate,
  Loading,
  Section,
} from "@/components/research-ui";

export function SectorIntelligence({ investorId }: { investorId: string }) {
  const [period, setPeriod] = useState("");
  const [sector, setSector] = useState("");
  const params = new URLSearchParams({ investors: investorId });
  if (period) params.set("period", period);
  if (sector) params.set("sector", sector);
  const query = useQuery({
    queryKey: ["sector-intelligence", investorId, period, sector],
    queryFn: ({ signal }) =>
      api(`/sector-intelligence?${params}`, sectorIntelligenceSchema, { signal }),
  });
  if (query.isPending)
    return (
      <Section title="Institutional Sector Intelligence">
        <Loading />
      </Section>
    );
  if (query.isError)
    return (
      <Section title="Institutional Sector Intelligence">
        <ErrorState retry={() => query.refetch()} />
      </Section>
    );
  const analysis = query.data.institutions[0];
  if (!analysis)
    return (
      <Section title="Institutional Sector Intelligence">
        <div className="empty">
          <h3>No sector analysis available</h3>
          <p className="mt-2">
            A verified saved disclosure is required. Unknown classifications
            are not inferred from issuer names.
          </p>
        </div>
      </Section>
    );
  const sectors = Array.from(
    new Set([
      ...analysis.allocation.map((row) => row.sector),
      ...(sector ? [sector] : []),
    ]),
  );
  const maxWeight = Math.max(
    ...analysis.allocation.map((row) => row.weight),
    0.01,
  );
  return (
    <Section title="Institutional Sector Intelligence">
      <div className="panel">
        <div className="flex flex-wrap items-end justify-between gap-4 border-b border-border/70 pb-5">
          <div>
            <p className="eyebrow">Verified historical allocation</p>
            <h3 className="mt-2">Sector allocation</h3>
            <p className="source">
              {analysis.name} · reporting period{" "}
              {formatDate(analysis.reporting_period)} · filed{" "}
              {formatDate(analysis.filing_date)}
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <label className="text-sm">
              Reporting period
              <select
                aria-label="Reporting period filter"
                className="mt-2 block min-h-10 rounded-lg border border-border bg-background px-3"
                value={period}
                onChange={(event) => setPeriod(event.target.value)}
              >
                <option value="">Latest saved</option>
                {analysis.available_periods.map((value) => (
                  <option value={value} key={value}>
                    {value}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-sm">
              Sector
              <select
                aria-label="Sector filter"
                className="mt-2 block min-h-10 max-w-56 rounded-lg border border-border bg-background px-3"
                value={sector}
                onChange={(event) => setSector(event.target.value)}
              >
                <option value="">All sectors</option>
                {sectors.map((value) => (
                  <option value={value} key={value}>
                    {value}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </div>

        <div className="mt-5 grid gap-3 sm:grid-cols-3">
          <div className="rounded-xl border border-border/70 bg-background/35 p-4">
            <p className="source !mt-0">Classified value coverage</p>
            <p className="metric mt-1">
              {percent(analysis.coverage.classified_value_percentage)}
            </p>
          </div>
          <div className="rounded-xl border border-border/70 bg-background/35 p-4">
            <p className="source !mt-0">Unknown classification</p>
            <p className="metric mt-1">
              {percent(analysis.coverage.unknown_value_percentage)}
            </p>
          </div>
          <div className="rounded-xl border border-border/70 bg-background/35 p-4">
            <p className="source !mt-0">Largest disclosed sector</p>
            <p className="mt-1 font-semibold">
              {analysis.concentration.largest_sector || "Unavailable"}
            </p>
          </div>
        </div>

        <div className="mt-7 space-y-4" aria-label="Sector allocation chart">
          {analysis.allocation.map((row) => {
            const change = analysis.sector_changes.find(
              (item) => item.sector === row.sector,
            );
            return (
              <button
                type="button"
                className="block w-full rounded-xl border border-border/70 bg-background/25 p-4 text-left transition hover:border-primary/40"
                aria-pressed={sector === row.sector}
                onClick={() => setSector(sector === row.sector ? "" : row.sector)}
                key={row.sector}
              >
                <span className="flex flex-wrap items-center justify-between gap-2 text-sm">
                  <strong>{row.sector}</strong>
                  <span className="font-mono">
                    {percent(row.weight)} · {money(row.reported_value)}
                  </span>
                </span>
                <span className="mt-3 block h-2 overflow-hidden rounded-full bg-muted/30">
                  <span
                    className="block h-full rounded-full bg-primary transition-[width] motion-reduce:transition-none"
                    style={{ width: `${(row.weight / maxWeight) * 100}%` }}
                  />
                </span>
                <span className="source">
                  {row.holding_count} reported holding
                  {row.holding_count === 1 ? "" : "s"}
                  {change && analysis.comparison.available
                    ? ` · ${change.weight_change >= 0 ? "+" : ""}${percent(change.weight_change)} weight change`
                    : " · no comparable prior period"}
                </span>
              </button>
            );
          })}
        </div>

        <div className="mt-7 overflow-x-auto">
          <table className="w-full min-w-[680px] text-left text-sm">
            <thead className="border-b border-border text-xs uppercase tracking-wider muted">
              <tr>
                <th className="py-3 pr-4">Sector</th>
                <th className="py-3 pr-4">Weight</th>
                <th className="py-3 pr-4">Reported value</th>
                <th className="py-3 pr-4">Share increases</th>
                <th className="py-3">Share reductions</th>
              </tr>
            </thead>
            <tbody>
              {analysis.sector_changes.map((row) => (
                <tr className="border-b border-border/60" key={row.sector}>
                  <td className="py-3 pr-4 font-medium">{row.sector}</td>
                  <td className="py-3 pr-4 font-mono">
                    {percent(row.weight_after)}
                  </td>
                  <td className="py-3 pr-4 font-mono">
                    {money(row.reported_value_after)}
                  </td>
                  <td className="py-3 pr-4">
                    <span className="inline-flex items-center gap-1 text-emerald-400">
                      <TrendingUp size={14} aria-hidden />
                      {row.position_activity.NEW +
                        row.position_activity.INCREASED}
                    </span>
                  </td>
                  <td className="py-3">
                    <span className="inline-flex items-center gap-1 text-rose-400">
                      <TrendingDown size={14} aria-hidden />
                      {row.position_activity.REDUCED +
                        row.position_activity.EXITED}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="mt-6 rounded-xl border border-border/70 bg-background/35 p-4 text-sm muted">
          <p className="flex items-start gap-2">
            <Info className="mt-0.5 shrink-0 text-primary" size={16} aria-hidden />
            <span>{analysis.comparison.weight_change_note}</span>
          </p>
          <p className="mt-2">{analysis.comparison.share_change_note}</p>
          <p className="mt-2">{query.data.interpretation_policy}</p>
          {query.data.coverage_notes.map((note) => (
            <p className="mt-2" key={note}>
              {note}
            </p>
          ))}
        </div>
        <div className="mt-5 flex flex-wrap gap-4 text-sm">
          <a
            className="inline-flex items-center gap-1.5 text-primary"
            href={analysis.source_url}
            target="_blank"
            rel="noopener noreferrer"
          >
            Original disclosure <ExternalLink size={14} aria-hidden />
          </a>
          <a
            className="inline-flex items-center gap-1.5 text-primary"
            href={analysis.taxonomy_source_url}
            target="_blank"
            rel="noopener noreferrer"
          >
            Classification taxonomy <ExternalLink size={14} aria-hidden />
          </a>
        </div>
        <p className="source">
          {analysis.taxonomy}. Unknown identifiers remain visible and count
          against coverage.
        </p>
      </div>
    </Section>
  );
}
