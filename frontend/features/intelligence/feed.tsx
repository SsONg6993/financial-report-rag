"use client";

import Link from "next/link";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { z } from "zod";
import { ErrorState, Loading, Section } from "@/components/research-ui";
import { intelligenceFeedSchema, institutionalActivitySchema, publicSourcesSchema } from "./api";

const filters = [
  ["all", "All"], ["investors", "Investors"], ["institutions", "Institutions"],
  ["companies", "Companies"], ["insiders", "Insiders"],
  ["public_updates", "Public Updates"], ["my_watchlist", "My Watchlist"],
] as const;

export function IntelligenceFeed() {
  const [filter, setFilter] = useState<(typeof filters)[number][0]>("all");
  const q = useQuery({
    queryKey: ["intelligence", "feed", filter],
    queryFn: ({ signal }) => api(`/intelligence/feed?category=${filter}`, intelligenceFeedSchema, { signal }),
    refetchInterval: 120_000,
  });
  return <Section title="Intelligence Feed">
    <p className="muted mb-4 text-sm">Public disclosures and official updates matched to your follows and watchlist. Dates are source dates, not trade timestamps.</p>
    <OfficialSources />
    <div className="mb-5 flex flex-wrap gap-2" role="group" aria-label="Filter intelligence feed">
      {filters.map(([id, label]) => <button key={id} type="button" onClick={() => setFilter(id)} aria-pressed={filter === id}
        className={`pill cursor-pointer ${filter === id ? "border-primary text-primary" : ""}`}>{label}</button>)}
    </div>
    {q.isPending ? <Loading /> : q.isError ? <ErrorState retry={() => q.refetch()} /> : <>
      <div className="grid-cards">
        {q.data.events.map((event) => <article className="panel" key={event.id}>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="pill">{event.source_type}</span>
            {event.freshness_state === "stale" && <span className="source">Stale source period</span>}
            {event.priority !== "digest" && <span className="source">{event.priority === "critical" ? "Watchlist alert" : "Relevant"}</span>}
          </div>
          <h3 className="mt-4 text-lg">{event.headline}</h3>
          <p className="muted mt-2 text-sm">{event.why_shown}</p>
          <p className="source">Published/filed {event.published_at.slice(0, 10)}{event.reporting_period ? ` · Reporting period ${event.reporting_period}` : ""}</p>
          <div className="mt-3 flex flex-wrap gap-4 text-sm">
            <a href={event.source_url} target="_blank" rel="noopener noreferrer" className="text-primary">Original source ↗</a>
            {event.ticker && <Link href={`/research/${event.ticker}`} className="text-primary">Research {event.ticker} →</Link>}
          </div>
        </article>)}
      </div>
      {!q.data.events.length && <div className="empty">No matching dated events are cached yet. Follow investors or add companies to your watchlist; this does not imply no real-world activity.</div>}
      <p className="source mt-5">{q.data.coverage}</p>
    </>}
  </Section>;
}

function OfficialSources() {
  const cache = useQueryClient();
  const [open, setOpen] = useState(false);
  const q = useQuery({ queryKey: ["intelligence", "sources"],
    queryFn: ({ signal }) => api("/intelligence/sources", publicSourcesSchema, { signal }), enabled: open });
  const toggle = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      api(`/intelligence/sources/${id}/follow`, z.object({ source_id: z.string(), followed: z.boolean() }),
        { method: "PUT", body: JSON.stringify({ enabled }) }),
    onSuccess: () => { cache.invalidateQueries({ queryKey: ["intelligence", "sources"] });
      cache.invalidateQueries({ queryKey: ["intelligence", "feed"] }); },
  });
  return <details className="panel mb-5" onToggle={(event) => setOpen(event.currentTarget.open)}>
    <summary className="cursor-pointer text-sm font-medium">Follow official public sources</summary>
    {q.isPending ? <Loading /> : q.isError ? <ErrorState retry={() => q.refetch()} /> : <div className="mt-4 flex flex-wrap gap-3">
      {q.data.sources.map((source) => <div className="rounded-xl border border-border p-3 text-sm" key={source.id}>
        <a className="text-primary" href={source.source_url} target="_blank" rel="noopener noreferrer">{source.name} ↗</a>
        <p className="source">{source.error || (source.checked_at ? `Checked ${source.checked_at.slice(0, 10)}` : "Awaiting source check")}</p>
        <button type="button" className="pill mt-2 cursor-pointer" disabled={toggle.isPending}
          onClick={() => toggle.mutate({ id: source.id, enabled: !source.followed })}>{source.followed ? "Following" : "Follow source"}</button>
      </div>)}
      {toggle.isError && <p role="alert" className="source">Could not update source follow. Please retry.</p>}
    </div>}
  </details>;
}

export function InstitutionalActivity({ ticker }: { ticker: string }) {
  const q = useQuery({
    queryKey: ["intelligence", "company", ticker],
    queryFn: ({ signal }) => api(`/intelligence/company/${ticker}`, institutionalActivitySchema, { signal }),
  });
  return <Section title="Tracked Institutional Activity">
    {q.isPending ? <Loading /> : q.isError ? <ErrorState retry={() => q.refetch()} /> : <>
      {q.data.counts && <p className="muted mb-4 text-sm">Comparable reporting period: {Object.entries(q.data.counts).map(([kind, count]) => `${kind.toLowerCase()} ${count}`).join(" · ")}. {q.data.convergence ? "Multiple tracked managers reported changes; this is not a buy/sell signal." : "No comparable multi-manager change detected."}</p>}
      <div className="grid-cards">{q.data.tracked_managers.map((row) => <article className="panel" key={row.manager_id}>
        <Link href={`/discover/${row.manager_id}`} className="font-semibold text-primary">{row.manager}</Link>
        <p className="mt-2 text-sm">{row.activity.replaceAll("_", " ")} · {row.reported_shares.toLocaleString()} reported shares</p>
        <p className="source">Period {row.reporting_period} · Filed {row.filing_date}</p>
        <a href={row.source_url} target="_blank" rel="noopener noreferrer" className="text-sm text-primary">Original filing ↗</a>
      </article>)}</div>
      {!q.data.tracked_managers.length && <div className="empty">No cached tracked-manager filing reports this ticker.</div>}
      <p className="source mt-5">{q.data.coverage}</p>
    </>}
  </Section>;
}
