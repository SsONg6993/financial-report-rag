"use client";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import {
  api,
  investorSchema,
  money,
  percent,
  write,
  type Investor,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  Building2,
  CalendarDays,
  ChartNoAxesColumnIncreasing,
  ExternalLink,
  Layers3,
} from "lucide-react";
import {
  ActivityBadge,
  ErrorState,
  formatDate,
  Freshness,
  Help,
  Loading,
  MutationError,
  ResearchLink,
  Section,
} from "@/components/research-ui";

function Follow({ investor }: { investor: Investor }) {
  const cache = useQueryClient();
  const m = useMutation({
    mutationFn: () =>
      write("/investors/" + investor.id + "/follow", {
        enabled: !investor.followed,
      }),
    onSuccess: () => {
      cache.invalidateQueries({ queryKey: ["investors"] });
      cache.invalidateQueries({ queryKey: ["investor", investor.id] });
      cache.invalidateQueries({ queryKey: ["home"] });
    },
  });
  return (
    <>
      <Button
        variant={investor.followed ? "outline" : "default"}
        disabled={m.isPending}
        onClick={() => m.mutate()}
      >
        {investor.followed ? "Following" : "Follow investor"}
      </Button>
      <MutationError error={m.error} />
    </>
  );
}
export function InvestorList() {
  const q = useQuery({
    queryKey: ["investors"],
    queryFn: ({ signal }) =>
      api("/investors", z.array(investorSchema), { signal }),
  });
  if (q.isPending) return <Loading />;
  if (q.isError) return <ErrorState retry={() => q.refetch()} />;
  return (
    <Section
      title="Featured investors"
      aside={
        <Help
          label="What is a 13F?"
          text="13F filings disclose certain U.S. equity holdings of qualifying managers. They are delayed and do not represent a complete or real-time portfolio."
        />
      }
    >
      <div className="grid-cards">
        {q.data.map((i) => (
          <article key={i.id} className="panel group flex flex-col">
            <div className="flex justify-between gap-2">
              <span className="icon-shell">
                <Building2 size={18} aria-hidden />
              </span>
              <span
                className={
                  i.available
                    ? "status-new rounded-full px-2.5 py-1 text-xs"
                    : "status-neutral rounded-full px-2.5 py-1 text-xs"
                }
              >
                {i.available ? "Latest data ready" : "Awaiting data"}
              </span>
            </div>
            <Link href={"/discover/" + i.id}>
              <h3 className="mt-5 text-xl transition group-hover:text-primary">
                {i.name}
              </h3>
            </Link>
            <p className="text-sm muted min-h-6 mt-1">{i.investor}</p>
            <div className="flex flex-wrap gap-1 mt-4">
              {i.style_tags.map((t) => (
                <span key={t} className="pill">
                  {t}
                </span>
              ))}
            </div>
            <div className="mt-5 rounded-xl border border-border/70 bg-background/35 p-3">
              <div className="flex items-center gap-2 text-xs muted">
                <CalendarDays size={14} aria-hidden />
                <span>
                  {i.source_type === "SEC Form 13F"
                    ? "Quarterly disclosure"
                    : "Daily holdings"}{" "}
                  · {formatDate(i.filing_date)}
                </span>
              </div>
              <div className="mt-3 space-y-2">
                {i.holdings.slice(0, 3).map((holding, index) => (
                  <div
                    className="flex items-center justify-between gap-3 text-sm"
                    key={holding.cusip + index}
                  >
                    <span className="truncate">
                      <span className="mr-2 font-mono text-xs text-primary">
                        {holding.ticker || "—"}
                      </span>
                      {holding.issuer}
                    </span>
                    <span className="shrink-0 font-mono text-xs muted">
                      {percent(holding.weight)}
                    </span>
                  </div>
                ))}
                {!i.holdings.length && (
                  <p className="text-sm muted">
                    Open the profile to check the official source.
                  </p>
                )}
              </div>
            </div>
            <div className="mt-auto flex flex-wrap gap-2 pt-5">
              <Button asChild>
                <Link href={"/discover/" + i.id}>View portfolio</Link>
              </Button>
              <Follow investor={i} />
            </div>
          </article>
        ))}
      </div>
      <p className="source mt-5">
        Style tags are descriptive, not rankings. Individual names describe
        association with the institution, not a claim about who made a specific
        trade.
      </p>
    </Section>
  );
}

function AllocationChart({ investor }: { investor: Investor }) {
  const colors = ["#35d6ee", "#5b8cff", "#8b7cf6", "#36cfa0", "#f4b860"];
  const top = investor.holdings.slice(0, 5);
  const total = top.reduce((sum, holding) => sum + holding.weight, 0);
  let cursor = 0;
  const segments = top.map((holding, index) => {
    const start = cursor;
    cursor += Math.max(0, holding.weight * 100);
    return `${colors[index]} ${start}% ${cursor}%`;
  });
  if (cursor < 100) segments.push(`#17263a ${cursor}% 100%`);
  return (
    <div className="panel grid items-center gap-7 sm:grid-cols-[180px_1fr]">
      <div
        className="chart-donut mx-auto"
        role="img"
        aria-label="Allocation chart for the top disclosed holdings"
        style={{ background: `conic-gradient(${segments.join(",")})` }}
      >
        <div>
          <span className="metric">{percent(total)}</span>
          <span className="source !mt-0">top five</span>
        </div>
      </div>
      <div className="space-y-3">
        {top.map((holding, index) => (
          <div
            className="flex items-center justify-between gap-3 text-sm"
            key={holding.cusip + index}
          >
            <span className="flex min-w-0 items-center gap-2">
              <i
                className="h-2.5 w-2.5 shrink-0 rounded-full"
                style={{ background: colors[index] }}
              />{" "}
              <span className="truncate">
                {holding.ticker || holding.issuer}
              </span>
            </span>
            <strong className="font-mono">{percent(holding.weight)}</strong>
          </div>
        ))}
        {cursor < 100 && (
          <div className="flex items-center justify-between gap-3 text-sm muted">
            <span className="flex items-center gap-2">
              <i className="h-2.5 w-2.5 rounded-full bg-[#17263a]" />
              Other holdings
            </span>
            <span className="font-mono">{percent(1 - total)}</span>
          </div>
        )}
      </div>
    </div>
  );
}
export function InvestorProfile({ id }: { id: string }) {
  const q = useQuery({
    queryKey: ["investor", id],
    queryFn: ({ signal }) =>
      api("/investors/" + id, investorSchema, { signal }),
    refetchInterval: 60_000,
  });
  if (q.isPending) return <Loading />;
  if (q.isError) return <ErrorState retry={() => q.refetch()} />;
  const i = q.data;
  const changes = i.changes.filter((c) => c.activity !== "UNCHANGED");
  return (
    <>
      <Link href="/discover" className="text-sm muted">
        ← All investors
      </Link>
      <div className="hero mt-5 !py-9">
        <div className="flex flex-wrap items-start justify-between gap-7">
          <div className="max-w-3xl">
            <p className="eyebrow">
              {i.source_type === "SEC Form 13F"
                ? "Quarterly institutional disclosure"
                : "Daily fund holdings"}
            </p>
            <h1 className="mt-3">{i.name}</h1>
            <p className="muted mt-2 text-base">{i.investor}</p>
            <div className="mt-5 flex flex-wrap gap-2">
              {i.style_tags.map((tag) => (
                <span className="pill" key={tag}>
                  {tag}
                </span>
              ))}
            </div>
          </div>
          <Follow investor={i} />
        </div>
        <div className="mt-8 grid gap-3 sm:grid-cols-3">
          <div className="rounded-xl border border-border/70 bg-background/30 p-4">
            <p className="source !mt-0">Portfolio source</p>
            <p className="mt-1 font-medium">{i.source_type}</p>
          </div>
          <div className="rounded-xl border border-border/70 bg-background/30 p-4">
            <p className="source !mt-0">Holdings date</p>
            <p className="mt-1 font-medium">
              {formatDate(i.filing_date || i.latest_period)}
            </p>
          </div>
          <div className="rounded-xl border border-border/70 bg-background/30 p-4">
            <p className="source !mt-0">Verified positions</p>
            <p className="mt-1 font-medium">{i.holdings.length} holdings</p>
          </div>
        </div>
        <div className="mt-5 flex flex-wrap items-center gap-4">
          {i.source_url && (
            <a
              className="inline-flex items-center gap-1.5 text-sm font-medium text-primary"
              href={i.source_url}
              target="_blank"
              rel="noopener noreferrer"
            >
              Open official source <ExternalLink size={14} aria-hidden />
            </a>
          )}
          {i.freshness && <span className="source !mt-0">{i.freshness}</span>}
        </div>
      </div>
      {i.refresh.error && (
        <div className="empty mt-5 text-left">
          <h2>
            {i.available
              ? "Showing the latest saved snapshot"
              : "The source is temporarily unavailable"}
          </h2>
          <p className="mt-2">
            {i.available
              ? "A fresh source check failed, so the last verified portfolio remains visible."
              : "No verified portfolio has been saved yet."}
          </p>
          <p className="source">{i.refresh.error}</p>
        </div>
      )}
      {!i.available && (
        <div className="empty mt-6">
          <Layers3
            className="mx-auto mb-3 text-primary"
            size={28}
            aria-hidden
          />
          <h2>No verified portfolio yet</h2>
          <p className="mx-auto mt-2 max-w-lg">
            We’ll keep this profile intact while the official source is
            unavailable. You can follow it now and check again later.
          </p>
          <Button
            className="mt-4"
            variant="outline"
            onClick={() => q.refetch()}
          >
            Check official source again
          </Button>
        </div>
      )}
      {i.holdings.length > 0 && (
        <Section title="Top Holdings">
          <div className="panel space-y-2">
            {i.holdings.slice(0, 10).map((holding, index) => (
              <div
                className="holding-row"
                key={holding.cusip + holding.put_call + index}
              >
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-muted/60 font-mono text-xs muted">
                  {index + 1}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-baseline justify-between gap-4">
                    <p className="truncate font-medium">
                      {holding.ticker || holding.issuer}
                    </p>
                    <span className="shrink-0 font-mono text-sm">
                      {percent(holding.weight)}
                    </span>
                  </div>
                  <p className="truncate text-xs muted">
                    {holding.issuer} · {money(holding.reported_value)}
                  </p>
                  <div className="weight-track">
                    <div
                      className="weight-fill"
                      style={{
                        width: `${Math.min(100, holding.weight * 100)}%`,
                      }}
                    />
                  </div>
                </div>
                {holding.ticker && !holding.put_call && (
                  <Button variant="ghost" size="sm" asChild>
                    <Link href={`/research/${holding.ticker}`}>Research</Link>
                  </Button>
                )}
              </div>
            ))}
          </div>
        </Section>
      )}
      <Section title="Recent Changes">
        <p className="text-sm muted mb-4">
          Changes compare successful snapshots; they are not trade execution
          dates.
        </p>
        <div className="grid-cards">
          {changes.slice(0, 8).map((c, index) => (
            <article key={index} className="panel">
              <div className="flex items-center justify-between gap-3">
                <ActivityBadge activity={c.activity} />
                <ChartNoAxesColumnIncreasing
                  className="text-primary"
                  size={20}
                  aria-hidden
                />
              </div>
              <h3 className="mt-3">{c.ticker || c.issuer}</h3>
              <p className="metric mt-2">
                {c.pct_change == null ? "New / exited" : percent(c.pct_change)}
              </p>
              <p className="source">
                Through {formatDate(i.filing_date || i.latest_period)}
              </p>
              {c.ticker && (
                <div className="mt-4">
                  <ResearchLink ticker={c.ticker} />
                </div>
              )}
            </article>
          ))}
        </div>
        {!changes.length && (
          <div className="empty">
            <h3>No comparison available yet</h3>
            <p className="mt-2">
              A second successful snapshot is needed before ThesisLens can show
              an actual change.
            </p>
          </div>
        )}
      </Section>
      {i.holdings.length > 0 && (
        <Section title="Portfolio Allocation">
          <AllocationChart investor={i} />
        </Section>
      )}
      <Section title="Companies Worth Exploring">
        <p className="muted text-sm mb-4">
          Start with a large disclosed position, then verify the business for
          yourself.
        </p>
        <div className="grid-cards">
          {i.holdings
            .filter((h) => h.ticker && !h.put_call)
            .slice(0, 3)
            .map((h) => (
              <article className="panel" key={h.ticker}>
                <span className="icon-shell">
                  <Building2 size={18} aria-hidden />
                </span>
                <h3 className="mt-4">{h.ticker}</h3>
                <p className="muted mt-3 mb-4">
                  {h.issuer} represents {percent(h.weight)} of this disclosed
                  portfolio.
                </p>
                <ResearchLink ticker={h.ticker} />
              </article>
            ))}
        </div>
      </Section>
      <details className="panel mt-8">
        <summary className="cursor-pointer font-medium">
          Source notes and disclosure history
        </summary>
        <p className="mt-4 text-sm muted">{i.rationale}</p>
        <div className="mt-5 space-y-4">
          {i.timeline.map((entry) => (
            <div className="timeline-item" key={entry.period}>
              <p className="font-medium">{entry.period}</p>
              <p className="source !mt-1">
                Filed {formatDate(entry.filing_date)} ·{" "}
                <a href={entry.source_url}>Original disclosure ↗</a>
              </p>
            </div>
          ))}
          {i.notes.map((note) => (
            <p key={note} className="source">
              {note}
            </p>
          ))}
        </div>
      </details>
    </>
  );
}
