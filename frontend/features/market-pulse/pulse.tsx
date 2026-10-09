"use client";

import Link from "next/link";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  ArrowRight,
  Clock3,
  FileCheck2,
  Globe2,
  Layers3,
  Radio,
  RefreshCw,
} from "lucide-react";
import { api, percent, money } from "@/lib/api";
import { ErrorState, Loading, Section } from "@/components/research-ui";
import { z } from "zod";
import {
  pulseSchema,
  pulseDetailSchema,
  supportedWatchlistEvents,
  type PulseEvent,
  type PulseImpact,
} from "./api";

function usePulse() {
  return useQuery({
    queryKey: ["market-pulse"],
    queryFn: ({ signal }) => api("/market-pulse", pulseSchema, { signal }),
    staleTime: 60_000,
    refetchInterval: 30_000,
  });
}
const title = (text: string) => text.replaceAll("_", " ").toLowerCase();
const date = (text: string | null) =>
  text
    ? text.replace("T", " ").slice(0, 16) + " UTC"
    : "Not specified by source";

function EventCard({ event }: { event: PulseEvent }) {
  const supported = event.impacts.filter((i) => i.impact_type !== "UNCLEAR");
  return (
    <article className="panel flex min-w-0 flex-col" data-testid="pulse-event">
      <div className="flex flex-wrap gap-2">
        <span className="pill">{event.category}</span>
        <span className="pill">{event.freshness}</span>
      </div>
      <h3 className="mt-4 leading-snug">
        <Link href={`/market-pulse/${event.id}`}>{event.headline}</Link>
      </h3>
      <p className="source">
        FACT · {event.source} · Published {date(event.published_at)}
      </p>
      <p className="source">Event time: {date(event.event_time)}</p>
      <p className="muted mt-3 text-sm leading-6">{event.what_happened}</p>
      <div className="mt-4 rounded-xl border border-border bg-background/40 p-3">
        <p className="eyebrow">Economic mechanism · analysis</p>
        <p className="mt-2 text-sm leading-6">{event.why_it_matters}</p>
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        {supported.slice(0, 4).map((i) => (
          <span className="pill" key={i.ticker}>
            {i.ticker} · {title(i.impact_type)}
            {i.watched ? " · watchlist" : ""}
          </span>
        ))}
      </div>
      {!supported.length && (
        <p className="source mt-4">
          Company relevance unclear · no supported exposure established.
        </p>
      )}
      <Link
        href={`/market-pulse/${event.id}`}
        className="mt-auto flex items-center gap-2 pt-5 text-sm font-medium text-primary"
      >
        View impact & evidence <ArrowRight size={15} aria-hidden />
      </Link>
    </article>
  );
}

export function MarketPulsePreview() {
  const q = usePulse();
  if (q.isPending)
    return (
      <Section title="Market Pulse">
        <p className="muted text-sm" role="status">
          Checking cached primary-source events…
        </p>
      </Section>
    );
  return (
    <Section
      title="Market Pulse"
      aside={
        <Link className="text-primary text-sm" href="/market-pulse">
          View Market Pulse →
        </Link>
      }
    >
      {q.isError ? (
        <p className="empty" role="alert">
          {q.error.message}
        </p>
      ) : (
        <>
          <p className="muted text-sm mb-4">
            Events → exposure → evidence. Analysis, not price predictions.
          </p>
          <div className="grid-cards">
            {q.data.events
              .filter((e) => e.recent)
              .slice(0, 3)
              .map((event) => (
                <EventCard key={event.id} event={event} />
              ))}
          </div>
          {!q.data.events.some((e) => e.recent) && (
            <p className="empty">
              {q.data.status === "source_unavailable"
                ? "Market Pulse sources are unavailable and no successful cached events exist."
                : "No recent sourced events cached yet. Older coverage is not presented as latest."}
            </p>
          )}
        </>
      )}
    </Section>
  );
}

export function MarketPulsePage() {
  const q = usePulse();
  const [watchlistOnly, setWatchlistOnly] = useState(false);
  const cache = useQueryClient();
  const refresh = useMutation({
    mutationFn: () =>
      api("/market-pulse/refresh", z.object({ status: z.string() }), {
        method: "POST",
      }),
    onSuccess: () => cache.invalidateQueries({ queryKey: ["market-pulse"] }),
  });
  if (q.isPending) return <Loading />;
  if (q.isError)
    return <ErrorState retry={() => q.refetch()} error={q.error} />;
  const relevant = supportedWatchlistEvents(q.data.events);
  const recent = (watchlistOnly ? relevant : q.data.events).filter(
    (e) => e.recent,
  );
  return (
    <>
      <section className="hero !py-9">
        <div className="flex flex-wrap items-start justify-between gap-5">
          <div className="max-w-2xl">
            <p className="eyebrow flex items-center gap-2">
              <Radio size={17} aria-hidden />
              Market Pulse
            </p>
            <h1 className="mt-3">Events. Exposure. Evidence.</h1>
            <p className="muted mt-4">
              Understand what happened, who may be affected, and why the
              connection needs evidence—not a prediction.
            </p>
          </div>
          <button
            className="nav-link border border-border rounded-xl"
            onClick={() => refresh.mutate()}
            disabled={refresh.isPending}
          >
            <RefreshCw size={15} className="inline mr-2" aria-hidden />
            {refresh.isPending ? "Requesting…" : "Check sources"}
          </button>
        </div>
        <div className="mt-6 flex flex-wrap gap-3">
          <span className="pill">
            <Globe2 size={13} aria-hidden /> Primary sources
          </span>
          <span className="pill">
            <FileCheck2 size={13} aria-hidden /> Evidence-gated company
            relevance
          </span>
          <span className="pill">
            <Clock3 size={13} aria-hidden />
            Source dates, not cache dates
          </span>
        </div>
        {refresh.isSuccess && (
          <p className="source" role="status">
            {refresh.data.status} Cached events remain visible while the update
            runs.
          </p>
        )}
        {refresh.isError && (
          <p role="alert" className="source">
            Source check could not be requested. Cached coverage remains below.
          </p>
        )}
      </section>
      <Section title="News Affecting Your Watchlist">
        <div className="panel flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="font-semibold">
              {q.data.watchlist_event_count} recent events may matter to your
              watchlist
            </p>
            <p className="source">
              Only supported company exposure qualifies. Missing evidence is not
              relevance.
            </p>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={watchlistOnly}
              onChange={(e) => setWatchlistOnly(e.target.checked)}
            />
            Watchlist only
          </label>
        </div>
      </Section>
      <Section
        title={
          watchlistOnly
            ? "Supported watchlist relevance"
            : "Recent events · last 7 days"
        }
      >
        <div className="grid-cards">
          {recent.slice(0, 12).map((event) => (
            <EventCard key={event.id} event={event} />
          ))}
        </div>
        {!recent.length && (
          <div className="empty">
            <Activity className="mx-auto mb-3 text-primary" aria-hidden />
            <h3>
              {watchlistOnly
                ? "No supported watchlist matches yet"
                : q.data.status === "source_unavailable"
                  ? "Market Pulse sources are unavailable"
                  : q.data.status === "empty_cache"
                    ? "No cached market events yet"
                    : "No recent events cached yet"}
            </h3>
            <p className="mt-2">
              {q.data.diagnostic} This is a coverage limit, not a claim that
              nothing happened.
            </p>
          </div>
        )}
      </Section>
      {!watchlistOnly && q.data.events.some((e) => !e.recent) && (
        <details className="panel mt-6">
          <summary>Earlier coverage · not latest</summary>
          <div className="grid-cards mt-5">
            {q.data.events
              .filter((e) => !e.recent)
              .slice(0, 6)
              .map((event) => (
                <EventCard key={event.id} event={event} />
              ))}
          </div>
        </details>
      )}
      <details className="panel mt-6">
        <summary>Source status & coverage</summary>
        <p className="source">{q.data.coverage}</p>
        {q.data.providers.map((p) => (
          <div className="mt-4" key={p.source}>
            <p className="text-sm">
              {p.source} · {p.stale ? "Stale / unavailable" : "Source checked"}
            </p>
            <p className="source">
              Last successful check: {date(p.successful_at)} · Attempt:{" "}
              {date(p.checked_at)}
            </p>
            {p.error && <p className="source">{p.error}</p>}
          </div>
        ))}
      </details>
    </>
  );
}

function ImpactCard({
  impact,
  event,
}: {
  impact: PulseImpact;
  event: PulseEvent;
}) {
  return (
    <article className="panel min-w-0" data-testid="pulse-impact">
      <div className="flex flex-wrap justify-between gap-3">
        <div>
          <p className="eyebrow">
            {impact.ticker}
            {impact.watched ? " · watchlist" : ""}
          </p>
          <h3 className="mt-1">{impact.company}</h3>
        </div>
        <span className="pill capitalize">{title(impact.impact_type)}</span>
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        <span className="pill capitalize">{title(impact.horizon)}</span>
        <span className="pill capitalize">
          {title(impact.evidence_strength)} exposure evidence
        </span>
      </div>
      <p className="mt-4 text-sm leading-6">{impact.explanation}</p>
      {impact.mechanism.length > 0 && (
        <div className="mt-4 rounded-xl border border-border p-4">
          <p className="eyebrow flex items-center gap-2">
            <Layers3 size={14} aria-hidden />
            Economic mechanism · analysis
          </p>
          <ol className="mt-3 space-y-2">
            {impact.mechanism.map((step, i) => (
              <li key={i} className="flex gap-3 text-sm">
                <span className="text-primary">{i + 1}</span>
                {step}
              </li>
            ))}
          </ol>
        </div>
      )}
      <p className="source mt-4">Confidence: {impact.confidence}</p>
      <details className="mt-4">
        <summary className="text-primary text-sm">
          View company exposure & supporting evidence
        </summary>
        <p className="mt-3 text-sm">{impact.company_exposure}</p>
        {impact.evidence_refs.map((r, i) => (
          <div className="mt-3 text-sm" key={i}>
            <p className="source">
              {r.source} · Evidence date {r.date ?? "unavailable"}
            </p>
            <p className="muted leading-6">{r.text}</p>
            <a
              href={r.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="source"
            >
              Evidence source ↗
            </a>
          </div>
        ))}
        {!impact.evidence_refs.length && (
          <p className="source">
            Insufficient company evidence. No exposure is invented.
          </p>
        )}
      </details>
      {impact.portfolio_context.length > 0 && (
        <details className="mt-4">
          <summary className="text-primary text-sm">
            Followed public portfolio context
          </summary>
          {impact.portfolio_context.map((p) => (
            <p key={p.investor_id} className="source">
              <Link href={`/discover/${p.investor_id}`}>{p.investor}</Link> ·{" "}
              {p.source_type} · Reporting period {p.reporting_period} · Filed{" "}
              {p.filing_date}
              <br />
              {p.note} · <a href={p.source_url}>Disclosure ↗</a>
            </p>
          ))}
        </details>
      )}
      {impact.judgment && (
        <p className="source">
          {impact.judgment.source} · {impact.judgment.sufficiency} · semantic
          support check, not market certainty
        </p>
      )}
      <Link
        className="mt-5 inline-flex min-h-11 items-center gap-2 text-sm font-medium text-primary"
        href={`/research/${encodeURIComponent(impact.ticker)}?event=${encodeURIComponent(event.id)}`}
      >
        Research {impact.ticker}
        <ArrowRight size={15} aria-hidden />
      </Link>
    </article>
  );
}

export function MarketPulseDetail({ eventId }: { eventId: string }) {
  const q = useQuery({
    queryKey: ["market-pulse", eventId],
    queryFn: ({ signal }) =>
      api(`/market-pulse/${encodeURIComponent(eventId)}`, pulseDetailSchema, {
        signal,
      }),
    staleTime: 60_000,
    retry: 1,
  });
  if (q.isPending) return <Loading />;
  if (q.isError)
    return (
      <>
        <Link href="/market-pulse" className="text-primary">
          ← Market Pulse
        </Link>
        <ErrorState retry={() => q.refetch()} />
      </>
    );
  const e = q.data;
  return (
    <>
      <Link href="/market-pulse" className="text-sm text-primary">
        ← Market Pulse
      </Link>
      <section className="hero mt-5 !py-9">
        <div className="flex flex-wrap gap-2">
          <span className="pill">{e.category}</span>
          <span className="pill">{e.freshness}</span>
        </div>
        <h1 className="mt-4 max-w-4xl">{e.headline}</h1>
        <p className="source mt-4">
          {e.source} · Source time {date(e.published_at)} · Event time{" "}
          {date(e.event_time)}
        </p>
        <a
          href={e.source_url}
          className="source"
          target="_blank"
          rel="noopener noreferrer"
        >
          Original primary source ↗
        </a>
      </section>
      <div className="grid-cards mt-6">
        {[
          ["What happened · Fact", e.what_happened],
          ["Why it matters · Analysis", e.why_it_matters],
          ["What to watch", e.what_to_watch],
        ].map(([heading, text]) => (
          <section className="panel" key={heading}>
            <h2 className="text-xl">{heading}</h2>
            <p className="mt-3 text-sm leading-6 muted">{text}</p>
          </section>
        ))}
      </div>
      <p className="source">
        {e.generator} · Potential relationships, not guaranteed outcomes.
      </p>
      <Section title="Potentially affected companies">
        <div className="grid gap-4 lg:grid-cols-2">
          {e.impacts.map((i) => (
            <ImpactCard key={i.ticker} impact={i} event={e} />
          ))}
        </div>
        {!e.impacts.length && (
          <p className="empty">
            No supported company exposure established in cached coverage.
          </p>
        )}
      </Section>
      <details className="panel mt-6">
        <summary>Observed market reaction · observation, not causality</summary>
        <p className="source">{e.reaction_note}</p>
        {e.reactions.map((r) => (
          <p key={r.ticker} className="source">
            {r.ticker} · Reference: {money(r.reference_price)} · 1-day:{" "}
            {percent(r.day_1_return)} · 5-day: {percent(r.day_5_return)}
            <br />
            {r.label}
          </p>
        ))}
      </details>
      {e.related_sources.length > 0 && (
        <details className="panel mt-6">
          <summary>Related source coverage</summary>
          {e.related_sources.map((r, i) => (
            <p className="source" key={i}>
              <a href={r.source_url}>
                {r.source}: {r.text}
              </a>{" "}
              · {date(r.date)}
            </p>
          ))}
        </details>
      )}
    </>
  );
}

export function PulseResearchContext({
  eventId,
  ticker,
}: {
  eventId: string;
  ticker: string;
}) {
  const q = useQuery({
    queryKey: ["market-pulse", eventId],
    queryFn: ({ signal }) =>
      api(`/market-pulse/${encodeURIComponent(eventId)}`, pulseDetailSchema, {
        signal,
      }),
    staleTime: 60_000,
    retry: false,
  });
  const impact = q.data?.impacts.find((i) => i.ticker === ticker);
  return (
    <aside className="panel mb-6" aria-label="Market Pulse research context">
      <p className="eyebrow">Opened from Market Pulse</p>
      {q.data ? (
        <>
          <Link
            className="text-primary mt-2 inline-block"
            href={`/market-pulse/${eventId}`}
          >
            {q.data.headline}
          </Link>
          <p className="source">
            Why this event could matter:{" "}
            {impact?.explanation ??
              "Company-specific relevance remains unclear in available evidence."}
          </p>
          <p className="source">What to watch: {q.data.what_to_watch}</p>
        </>
      ) : (
        <p className="source">
          {q.isError
            ? "Event context unavailable or expired. Company Research remains available below."
            : "Loading dated event context…"}
        </p>
      )}
    </aside>
  );
}
