"use client";
import Link from "next/link";
import { useState } from "react";
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
import { EntityAvatar } from "@/components/entity-avatar";
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
import { SectorIntelligence } from "./sector-intelligence";

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
  const [cik, setCik] = useState("");
  const cache = useQueryClient();
  const resolve = useMutation({
    mutationFn: () =>
      api(
        "/investors/resolve",
        z.object({ id: z.string(), name: z.string() }),
        {
          method: "POST",
          body: JSON.stringify({ cik: Number(cik) }),
        },
      ),
    onSuccess: () => {
      setCik("");
      cache.invalidateQueries({ queryKey: ["investors"] });
    },
  });
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
      <form
        className="mb-5 flex flex-wrap items-end gap-3"
        onSubmit={(event) => {
          event.preventDefault();
          resolve.mutate();
        }}
      >
        <label className="text-sm">
          Add verified SEC 13F filer by CIK
          <input
            className="mt-2 block rounded-lg border border-border bg-background px-3 py-2"
            inputMode="numeric"
            pattern="[0-9]+"
            value={cik}
            onChange={(event) => setCik(event.target.value)}
            placeholder="SEC CIK"
            required
            aria-label="SEC CIK"
          />
        </label>
        <Button type="submit" disabled={resolve.isPending}>
          {resolve.isPending ? "Verifying…" : "Verify filer"}
        </Button>
        <span className="source">
          Checked only when requested; original 13F-HR required.
        </span>
      </form>
      <MutationError error={resolve.error} />
      <div className="grid-cards">
        {q.data.map((i) => (
          <article key={i.id} className="panel group flex flex-col">
            <div className="flex justify-between gap-2">
              <EntityAvatar
                kind="investor"
                id={i.id}
                name={i.investor || i.name}
              />
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
            <p className="text-sm muted min-h-6 mt-1">
              {i.investor
                ? `Associated investor · ${i.investor}`
                : "Institutional filer"}
            </p>
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
      <div className="min-w-0 space-y-3">
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
            <EntityAvatar
              kind="investor"
              id={i.id}
              name={i.investor || i.name}
              size="lg"
              className="entity-avatar-lg mb-4"
            />
            <p className="eyebrow">
              {i.source_type === "SEC Form 13F"
                ? "Quarterly institutional disclosure"
                : "Daily fund holdings"}
            </p>
            <h1 className="mt-3">{i.name}</h1>
            <p className="muted mt-2 text-base">
              {i.investor
                ? `Associated investor · ${i.investor}`
                : "Institutional filer"}
            </p>
            <p className="source">
              Reported position changes are attributed to the filing entity, not
              necessarily personal trades by an associated individual.
            </p>
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
          <div className="panel holdings-table">
            <div className="holding-grid holding-header" aria-hidden="true">
              <span>Security</span>
              <span>Reported value</span>
              <span>Portfolio weight</span>
              <span>Research</span>
            </div>
            {i.holdings.slice(0, 10).map((holding, index) => (
              <article
                className="holding-grid"
                key={holding.cusip + holding.put_call + index}
              >
                <div className="holding-main">
                  <EntityAvatar
                    kind="company"
                    id={holding.ticker}
                    name={holding.ticker || holding.issuer}
                    size="sm"
                  />
                  <div className="min-w-0">
                    <p className="flex flex-wrap items-center gap-2 font-semibold">
                      <span>{holding.ticker || "Unmapped security"}</span>
                      {holding.put_call && (
                        <span className="pill">{holding.put_call}</span>
                      )}
                    </p>
                    <p className="text-xs muted break-words">
                      {holding.issuer}
                    </p>
                    <p className="source !mt-1">
                      {holding.security_class || "Class unavailable"} ·{" "}
                      {holding.share_type}
                    </p>
                  </div>
                </div>
                <div className="holding-stat" data-label="Reported value">
                  <strong>{money(holding.reported_value)}</strong>
                  <span>{holding.shares.toLocaleString()} reported shares</span>
                </div>
                <div className="holding-stat" data-label="Portfolio weight">
                  <strong>{percent(holding.weight)}</strong>
                  <div className="weight-track">
                    <div
                      className="weight-fill"
                      style={{
                        width: `${Math.min(100, holding.weight * 100)}%`,
                      }}
                    />
                  </div>
                </div>
                <div className="holding-actions">
                  {holding.ticker_verified && !holding.put_call ? (
                    <Button variant="outline" size="sm" asChild>
                      <Link href={`/research/${holding.ticker}`}>Research</Link>
                    </Button>
                  ) : (
                    <span className="source !mt-0">
                      No verified research mapping
                    </span>
                  )}
                </div>
                <details className="entry-estimate">
                  <summary>
                    Estimated entry price ·{" "}
                    {holding.entry_price_estimate?.label ||
                      "Not reliably estimable"}
                  </summary>
                  {holding.entry_price_estimate?.status ===
                  "indicative_range" ? (
                    <div className="mt-3 grid gap-2 text-sm sm:grid-cols-3">
                      <p>
                        <span className="muted">Possible range</span>
                        <br />
                        <strong>
                          {money(holding.entry_price_estimate.price_low)}–
                          {money(holding.entry_price_estimate.price_high)}
                        </strong>
                      </p>
                      <p>
                        <span className="muted">Daily-close average</span>
                        <br />
                        <strong>
                          {money(
                            holding.entry_price_estimate.estimated_average,
                          )}
                        </strong>
                      </p>
                      <p>
                        <span className="muted">Confidence</span>
                        <br />
                        <strong className="capitalize">
                          {holding.entry_price_estimate.confidence}
                        </strong>
                      </p>
                    </div>
                  ) : (
                    <p className="mt-3 text-sm muted">
                      {holding.entry_price_estimate?.assumptions[0] ||
                        "Insufficient comparable disclosure and price evidence."}
                    </p>
                  )}
                  <p className="source">
                    Actual purchase cost is unknown.{" "}
                    {holding.entry_price_estimate?.method}
                  </p>
                </details>
              </article>
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
      {i.holdings.length > 0 && <SectorIntelligence investorId={i.id} />}
      <Section title="Companies Worth Exploring">
        <p className="muted text-sm mb-4">
          Start with a large disclosed position, then verify the business for
          yourself.
        </p>
        <div className="grid-cards">
          {i.holdings
            .filter((h) => h.ticker_verified && !h.put_call)
            .slice(0, 3)
            .map((h) => (
              <article className="panel" key={h.ticker}>
                <EntityAvatar kind="company" id={h.ticker} name={h.ticker} />
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
