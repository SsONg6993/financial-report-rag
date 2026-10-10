"use client";

import Link from "next/link";
import { useDeferredValue, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Search, SlidersHorizontal } from "lucide-react";
import { z } from "zod";
import { ErrorState, Loading, Section } from "@/components/research-ui";
import { api } from "@/lib/api";
import {
  intelligenceFeedSchema,
  institutionalActivitySchema,
  publicSourcesSchema,
} from "./api";

const filters = [
  ["all", "All"],
  ["investors", "Investors"],
  ["companies", "Companies"],
  ["insiders", "Insiders"],
  ["public_updates", "Public updates"],
  ["my_watchlist", "My watchlist"],
] as const;
const dateRanges = [
  [0, "Any date"],
  [7, "7 days"],
  [30, "30 days"],
  [90, "90 days"],
] as const;

function displayFact(value: unknown) {
  if (typeof value === "number")
    return value.toLocaleString("en-US", { maximumFractionDigits: 2 });
  return typeof value === "string" ? value.replaceAll("_", " ") : null;
}

export function IntelligenceFeed({
  variant = "full",
}: {
  variant?: "full" | "preview";
}) {
  const [filter, setFilter] = useState<(typeof filters)[number][0]>("all");
  const [query, setQuery] = useState("");
  const [days, setDays] = useState(0);
  const deferredQuery = useDeferredValue(query.trim().toLowerCase());
  const feed = useQuery({
    queryKey: ["intelligence", "feed", filter],
    queryFn: ({ signal }) =>
      api(
        `/intelligence/feed?category=${filter}&limit=100`,
        intelligenceFeedSchema,
        { signal },
      ),
    refetchInterval: 120_000,
  });
  const events = useMemo(() => {
    const cutoff = days ? Date.now() - days * 86_400_000 : 0;
    return (feed.data?.events ?? [])
      .filter((event) => {
        const searchable =
          `${event.headline} ${event.entity_name} ${event.ticker ?? ""} ${event.source_type} ${event.why_shown}`.toLowerCase();
        return (
          (!deferredQuery || searchable.includes(deferredQuery)) &&
          (!cutoff || Date.parse(event.published_at) >= cutoff)
        );
      })
      .slice(0, variant === "preview" ? 5 : 100);
  }, [days, deferredQuery, feed.data?.events, variant]);

  return (
    <Section
      title={
        variant === "preview"
          ? "Top Intelligence Highlights"
          : "Intelligence Feed"
      }
      aside={
        variant === "preview" ? (
          <Link href="/intelligence" className="text-sm text-primary">
            Open full feed →
          </Link>
        ) : undefined
      }
    >
      <p className="muted mb-4 max-w-3xl text-sm">
        Ranked, dated public disclosures and official updates matched to your
        follows and watchlist. A filing is not a real-time trade or a statement
        of intent.
      </p>
      {variant === "full" && (
        <>
          <OfficialSources />
          <div className="panel mb-5 grid gap-3 md:grid-cols-[minmax(14rem,1fr)_auto]">
            <label className="relative block">
              <span className="sr-only">Search intelligence</span>
              <Search
                className="pointer-events-none absolute left-3 top-3 text-muted-foreground"
                size={17}
                aria-hidden
              />
              <input
                className="w-full pl-10"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search company, manager, or source…"
              />
            </label>
            <label className="flex items-center gap-2 text-sm">
              <SlidersHorizontal size={16} aria-hidden />
              <span className="sr-only">Date range</span>
              <select
                value={days}
                onChange={(event) => setDays(Number(event.target.value))}
              >
                {dateRanges.map(([value, label]) => (
                  <option value={value} key={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <div
              className="flex flex-wrap gap-2 md:col-span-2"
              role="group"
              aria-label="Filter intelligence feed"
            >
              {filters.map(([id, label]) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => setFilter(id)}
                  aria-pressed={filter === id}
                  className={`pill cursor-pointer ${filter === id ? "border-primary text-primary" : ""}`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
        </>
      )}
      {feed.isPending ? (
        <Loading />
      ) : feed.isError ? (
        <ErrorState retry={() => feed.refetch()} />
      ) : (
        <>
          <div className="space-y-3">
            {events.map((event) => {
              const sector =
                typeof event.facts.sector === "string"
                  ? event.facts.sector
                  : null;
              const facts = Object.entries(event.facts)
                .map(([key, value]) => [key, displayFact(value)] as const)
                .filter(([, value]) => value)
                .slice(0, 8);
              return (
                <article className="panel" key={event.id}>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="pill">{event.source_type}</span>
                    {event.ticker && (
                      <span className="pill">{event.ticker}</span>
                    )}
                    {sector && <span className="pill">{sector}</span>}
                    {event.priority !== "digest" && (
                      <span className="pill border-primary/50 text-primary">
                        {event.priority === "critical"
                          ? "Watchlist priority"
                          : "Relevant"}
                      </span>
                    )}
                    {event.freshness_state === "stale" && (
                      <span className="pill border-amber-400/50 text-amber-300">
                        Older source period
                      </span>
                    )}
                  </div>
                  <h3 className="mt-3 text-base leading-snug sm:text-lg">
                    {event.headline}
                  </h3>
                  <p className="muted mt-1 text-sm">{event.why_shown}</p>
                  <p className="source">
                    Published/filed{" "}
                    <time dateTime={event.published_at}>
                      {event.published_at.slice(0, 10)}
                    </time>
                    {event.reporting_period
                      ? ` · Reporting period ${event.reporting_period}`
                      : ""}
                  </p>
                  <div className="mt-3 flex flex-wrap gap-4 text-sm">
                    <a
                      href={event.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-primary"
                    >
                      Original source ↗
                    </a>
                    {event.ticker && (
                      <Link
                        href={`/research/${event.ticker}`}
                        className="text-primary"
                      >
                        Research {event.ticker} →
                      </Link>
                    )}
                  </div>
                  {variant === "full" && facts.length > 0 && (
                    <details className="mt-3 text-sm">
                      <summary>Disclosure details</summary>
                      <dl className="mt-3 grid gap-2 sm:grid-cols-2">
                        {facts.map(([key, value]) => (
                          <div key={key}>
                            <dt className="source !mt-0">
                              {key.replaceAll("_", " ")}
                            </dt>
                            <dd>{value}</dd>
                          </div>
                        ))}
                      </dl>
                    </details>
                  )}
                </article>
              );
            })}
          </div>
          {!events.length && (
            <div className="empty">
              No matching dated events are cached for these filters. This does
              not imply no real-world activity.
            </div>
          )}
          <p className="source mt-5">{feed.data.coverage}</p>
        </>
      )}
    </Section>
  );
}

function OfficialSources() {
  const cache = useQueryClient();
  const [open, setOpen] = useState(false);
  const sources = useQuery({
    queryKey: ["intelligence", "sources"],
    queryFn: ({ signal }) =>
      api("/intelligence/sources", publicSourcesSchema, { signal }),
    enabled: open,
  });
  const toggle = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      api(
        `/intelligence/sources/${id}/follow`,
        z.object({ source_id: z.string(), followed: z.boolean() }),
        { method: "PUT", body: JSON.stringify({ enabled }) },
      ),
    onSuccess: () => {
      cache.invalidateQueries({ queryKey: ["intelligence", "sources"] });
      cache.invalidateQueries({ queryKey: ["intelligence", "feed"] });
    },
  });
  return (
    <details
      className="panel mb-5"
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary>Official public sources</summary>
      {sources.isPending ? (
        <Loading />
      ) : sources.isError ? (
        <ErrorState retry={() => sources.refetch()} />
      ) : (
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          {sources.data.sources.map((source) => (
            <div
              className="rounded-xl border border-border p-3 text-sm"
              key={source.id}
            >
              <a
                className="text-primary"
                href={source.source_url}
                target="_blank"
                rel="noopener noreferrer"
              >
                {source.name} ↗
              </a>
              <p className="source">
                {source.error ||
                  (source.checked_at
                    ? `Checked ${source.checked_at.slice(0, 10)}`
                    : "Awaiting source check")}
              </p>
              <button
                type="button"
                className="pill mt-2 cursor-pointer"
                disabled={toggle.isPending}
                onClick={() =>
                  toggle.mutate({ id: source.id, enabled: !source.followed })
                }
              >
                {source.followed ? "Following" : "Follow source"}
              </button>
            </div>
          ))}
        </div>
      )}
    </details>
  );
}

export function InstitutionalActivity({ ticker }: { ticker: string }) {
  const activity = useQuery({
    queryKey: ["intelligence", "company", ticker],
    queryFn: ({ signal }) =>
      api(`/intelligence/company/${ticker}`, institutionalActivitySchema, {
        signal,
      }),
  });
  return (
    <Section title="Institutional Ownership">
      {activity.isPending ? (
        <Loading />
      ) : activity.isError ? (
        <ErrorState retry={() => activity.refetch()} />
      ) : (
        <>
          {activity.data.counts && (
            <p className="muted mb-4 text-sm">
              Comparable reporting period:{" "}
              {Object.entries(activity.data.counts)
                .map(([kind, count]) => `${kind.toLowerCase()} ${count}`)
                .join(" · ")}
              . Reported changes are not trade signals.
            </p>
          )}
          <div className="space-y-3">
            {activity.data.tracked_managers.map((row) => (
              <article
                className="panel flex flex-col justify-between gap-3 sm:flex-row sm:items-center"
                key={row.manager_id}
              >
                <div>
                  <Link
                    href={`/discover/${row.manager_id}`}
                    className="font-semibold text-primary"
                  >
                    {row.manager}
                  </Link>
                  <p className="mt-1 text-sm">
                    {row.activity.replaceAll("_", " ")} ·{" "}
                    {row.reported_shares.toLocaleString()} reported shares
                  </p>
                  <p className="source">
                    Period {row.reporting_period} · Filed {row.filing_date}
                  </p>
                </div>
                <a
                  href={row.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-primary"
                >
                  Original filing ↗
                </a>
              </article>
            ))}
          </div>
          {!activity.data.tracked_managers.length && (
            <div className="empty">
              No cached tracked-manager filing reports this ticker.
            </div>
          )}
          <p className="source mt-5">{activity.data.coverage}</p>
        </>
      )}
    </Section>
  );
}
