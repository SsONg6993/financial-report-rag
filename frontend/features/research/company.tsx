"use client";
import Link from "next/link";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import {
  api,
  companySchema,
  disclosureSchema,
  money,
  percent,
  thesisSchema,
  write,
  type Suggestion,
  type Thesis,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  ArrowRight,
  Banknote,
  BarChart3,
  Binoculars,
  Building2,
  CalendarDays,
  CircleAlert,
  FileSearch,
  Gauge,
  ShieldAlert,
  Sparkles,
  TrendingUp,
} from "lucide-react";
import {
  ErrorState,
  Freshness,
  Help,
  Loading,
  MutationError,
  Section,
  Sources,
  WatchButton,
} from "@/components/research-ui";

function SuggestedCard({
  suggestion,
  ticker,
  tracked,
}: {
  suggestion: Suggestion;
  ticker: string;
  tracked: Thesis[];
}) {
  const cache = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [ignored, setIgnoredState] = useState(false);
  const [text, setText] = useState(suggestion.text);
  const alreadyTracked = tracked.some((t) => t.text === text);
  const ignore = useMutation({
    mutationFn: () =>
      write(
        "/company/" +
          ticker +
          "/suggestions/" +
          encodeURIComponent(suggestion.id) +
          "/ignore",
        { enabled: true },
      ),
    onSuccess: () => {
      setIgnoredState(true);
      cache.invalidateQueries({ queryKey: ["company", ticker] });
    },
  });
  const setIgnored = (_value: boolean) => ignore.mutate();
  const m = useMutation({
    mutationFn: () =>
      api("/theses", thesisSchema, {
        method: "POST",
        body: JSON.stringify({
          ticker,
          text,
          rule: text === suggestion.text ? suggestion.rule : null,
        }),
      }),
    onSuccess: () => cache.invalidateQueries({ queryKey: ["company", ticker] }),
  });
  if (ignored) return null;
  if (ignore.error)
    return (
      <div role="alert" className="panel">
        <p>{ignore.error.message}</p>
        <Button onClick={() => ignore.reset()}>Return to suggestion</Button>
      </div>
    );
  return (
    <article className="panel flex flex-col" data-testid="suggested-thesis">
      <div className="flex justify-between gap-2">
        <span className="pill">{suggestion.category}</span>
        <span className="text-xs muted">{suggestion.period}</span>
      </div>
      {editing ? (
        <label className="mt-4 text-sm">
          Edit tracking idea
          <textarea
            aria-label="Edit tracking idea"
            value={text}
            onChange={(e) => setText(e.target.value)}
            maxLength={2000}
          />
          <span className="source">
            Editing the claim removes its automatic numeric rule. Semantic
            evaluation may be uncertain.
          </span>
        </label>
      ) : (
        <h3 className="mt-4 leading-snug">{suggestion.text}</h3>
      )}
      <p className="muted text-sm mt-3">{suggestion.why_it_matters}</p>
      <details className="mt-4 text-sm">
        <summary className="text-primary">Evidence & test conditions</summary>
        <Sources evidence={suggestion.evidence} />
        <p className="mt-4">
          <strong>Supports it:</strong> {suggestion.support_condition}
        </p>
        <p className="mt-2">
          <strong>Invalidates it:</strong> {suggestion.invalidate_condition}
        </p>
        <p className="source">{suggestion.generator}</p>
      </details>
      <div className="flex flex-wrap gap-2 mt-auto pt-6">
        <Button
          disabled={
            m.isPending || m.isSuccess || alreadyTracked || !text.trim()
          }
          onClick={() => m.mutate()}
        >
          {m.isSuccess || alreadyTracked
            ? "Tracked"
            : m.isPending
              ? "Saving…"
              : "Track idea"}
        </Button>
        <Button variant="outline" onClick={() => setEditing(!editing)}>
          {editing ? "Done editing" : "Edit"}
        </Button>
        <Button variant="ghost" onClick={() => setIgnored(true)}>
          Ignore
        </Button>
      </div>
      <MutationError error={m.error} />
    </article>
  );
}
function TrackedCard({ thesis }: { thesis: Thesis }) {
  const cache = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(thesis.text);
  const evaluation = useMutation({
    mutationFn: () =>
      api("/theses/" + thesis.id + "/evaluate", thesisSchema, {
        method: "POST",
      }),
    onSuccess: () =>
      cache.invalidateQueries({ queryKey: ["company", thesis.ticker] }),
  });
  const edit = useMutation({
    mutationFn: () =>
      api("/theses/" + thesis.id, thesisSchema, {
        method: "PUT",
        body: JSON.stringify({
          ticker: thesis.ticker,
          text,
          rule: text === thesis.text ? thesis.rule : null,
        }),
      }),
    onSuccess: () => {
      setEditing(false);
      cache.invalidateQueries({ queryKey: ["company", thesis.ticker] });
    },
  });
  return (
    <article className="panel" data-testid="tracked-thesis">
      <div className="flex flex-wrap justify-between gap-3">
        <h3 className="max-w-2xl leading-snug">{thesis.text}</h3>
        <span className="pill">{thesis.status.replaceAll("_", " ")}</span>
      </div>
      <p className="muted text-sm mt-4">
        {thesis.explanation ??
          "Evaluate this thesis against available dated evidence."}
      </p>
      <div className="flex flex-wrap gap-2 mt-5">
        <Button
          disabled={evaluation.isPending}
          onClick={() => evaluation.mutate()}
        >
          {evaluation.isPending ? "Evaluating…" : "Evaluate evidence"}
        </Button>
        <Button variant="outline" onClick={() => setEditing(!editing)}>
          Edit idea
        </Button>
      </div>
      {editing && (
        <form
          className="mt-4"
          onSubmit={(e) => {
            e.preventDefault();
            edit.mutate();
          }}
        >
          <label className="text-sm">
            Idea to test
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              required
              maxLength={2000}
            />
          </label>
          <Button type="submit" disabled={edit.isPending}>
            Save changes
          </Button>
        </form>
      )}
      <MutationError error={evaluation.error || edit.error} />
      <div className="grid gap-6 md:grid-cols-2 mt-5">
        {thesis.supporting_evidence.length > 0 && (
          <div>
            <p className="eyebrow">Supporting evidence</p>
            <Sources evidence={thesis.supporting_evidence} />
          </div>
        )}
        {thesis.contradicting_evidence.length > 0 && (
          <div>
            <p className="eyebrow">Contradicting evidence</p>
            <Sources evidence={thesis.contradicting_evidence} />
          </div>
        )}
      </div>
      {thesis.history.length > 0 && (
        <ol
          aria-label="Thesis timeline"
          className="flex flex-wrap gap-6 mt-6 border-t border-border pt-4"
        >
          {thesis.history.map((h, i) => (
            <li key={i} className="border-l-2 border-primary/30 pl-3">
              <p className="text-xs muted">
                {h.period ?? h.evaluated_at.slice(0, 10)}
              </p>
              <p className="text-sm font-semibold">{h.status}</p>
              <p className="text-xs muted">
                Evaluated {h.evaluated_at.slice(0, 10)}
              </p>
            </li>
          ))}
        </ol>
      )}
    </article>
  );
}
function CustomThesis({
  ticker,
  templates,
}: {
  ticker: string;
  templates: Record<string, string[]>;
}) {
  const cache = useQueryClient();
  const [category, setCategory] = useState("Growth");
  const [text, setText] = useState("");
  const m = useMutation({
    mutationFn: () =>
      api("/theses", thesisSchema, {
        method: "POST",
        body: JSON.stringify({ ticker, text, rule: null }),
      }),
    onSuccess: () => {
      setText("");
      cache.invalidateQueries({ queryKey: ["company", ticker] });
    },
  });
  return (
    <details className="panel mt-5">
      <summary className="font-semibold">Create your own tracking idea</summary>
      <form
        className="mt-5"
        onSubmit={(e) => {
          e.preventDefault();
          m.mutate();
        }}
      >
        <label className="block text-sm">
          Research category
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="block mt-2 w-full max-w-sm"
          >
            {Object.keys(templates).map((t) => (
              <option key={t}>{t}</option>
            ))}
          </select>
        </label>
        <div className="mt-3 text-sm muted">
          {(templates[category] ?? []).map((x) => (
            <p key={x}>{x}</p>
          ))}
        </div>
        <label className="block mt-4 text-sm">
          Your testable assumption
          <textarea
            required
            value={text}
            onChange={(e) => setText(e.target.value)}
            maxLength={2000}
          />
        </label>
        <Button type="submit" disabled={m.isPending || !text.trim()}>
          Track custom idea
        </Button>
        <MutationError error={m.error} />
      </form>
    </details>
  );
}
function Disclosures({
  ticker,
  kind,
}: {
  ticker: string;
  kind: "insiders" | "ownership";
}) {
  const q = useQuery({
    queryKey: [kind, ticker],
    queryFn: ({ signal }) =>
      api("/" + kind + "/" + ticker, disclosureSchema, { signal }),
    refetchInterval: 120_000,
  });
  return (
    <details className="panel">
      <summary className="font-semibold">
        {kind === "insiders"
          ? "Insider activity · SEC Form 4"
          : "Major ownership · Schedule 13D/G"}
      </summary>
      {q.isPending ? (
        <Loading />
      ) : q.isError ? (
        <ErrorState retry={() => q.refetch()} />
      ) : (
        <div className="mt-4 space-y-4">
          {q.data.records.slice(0, 6).map((r) => (
            <article key={r.id} className="border-b border-border pb-4">
              <span className="pill">{r.activity}</span>
              <h3 className="mt-2">{r.insider ?? r.filer}</h3>
              <p className="text-sm muted">
                {r.role ?? r.form}
                {r.shares != null
                  ? " · " + r.shares.toLocaleString("en-US") + " shares"
                  : ""}
                {r.price != null ? " at " + money(r.price) : ""}
                {r.ownership_percentage != null
                  ? " · " + r.ownership_percentage + "% disclosed ownership"
                  : ""}
              </p>
              <p className="text-sm muted mt-2">{r.context}</p>
              <Freshness
                type={r.source_type}
                period={r.reporting_period}
                filed={r.filing_date}
              />
              <a className="source inline-block" href={r.source_url}>
                Original filing ↗
              </a>
            </article>
          ))}
          {!q.data.records.length && (
            <p className="empty">
              {q.data.available
                ? "No normalized records in the limited recent filing coverage."
                : "Data unavailable or not yet cached. Refresh is attempted independently of company research."}
            </p>
          )}
          {q.data.refresh.error && (
            <p className="source">{q.data.refresh.error}</p>
          )}
        </div>
      )}
    </details>
  );
}
export function CompanyResearch({ ticker }: { ticker: string }) {
  const q = useQuery({
    queryKey: ["company", ticker],
    queryFn: ({ signal }) =>
      api("/company/" + ticker, companySchema, { signal }),
    refetchInterval: 60_000,
  });
  if (q.isPending) return <Loading />;
  if (q.isError) return <ErrorState retry={() => q.refetch()} />;
  const c = q.data;
  const a = c.annual;
  const context = c.financial_context;
  const quarterly = context?.kind === "quarterly";
  const revenue = context?.metrics.find((m) => m.metric === "revenue");
  const comparableRevenue =
    revenue?.value != null && revenue.previous != null &&
    revenue.value > 0 && revenue.previous > 0 ? revenue : null;
  const income = context?.metrics.find((m) => m.metric === "net_income");
  const fcfMargin =
    !quarterly && a?.revenue && a.free_cash_flow != null
      ? a.free_cash_flow / a.revenue
      : null;
  const metrics = [
    {
      label: "Revenue growth",
      value: quarterly ? revenue?.yoy : a?.revenue_growth,
      Icon: TrendingUp,
    },
    {
      label: "Net margin",
      value: quarterly
        ? revenue?.value &&
          income?.value != null &&
          income.start === revenue.start
          ? income.value / revenue.value
          : null
        : a?.net_margin,
      Icon: Gauge,
    },
    { label: "FCF margin", value: fcfMargin, Icon: Banknote },
  ];
  return (
    <>
      <Link href="/research" className="text-sm muted">
        ← Find a company
      </Link>
      <section className="hero mt-5 !py-9">
        <div className="flex flex-wrap items-start justify-between gap-7">
          <div className="max-w-3xl">
            <div className="flex items-center gap-3">
              <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border border-primary/30 bg-primary/10 font-mono text-sm font-bold text-primary" aria-label={`${ticker} monogram`}>
                {ticker.slice(0, 2)}
              </span>
              <p className="eyebrow">Company research · {ticker}</p>
            </div>
            <h1 className="mt-4">{c.name}</h1>
            <p className="source mt-2">
              {ticker}{c.identity?.exchange ? ` · ${c.identity.exchange}` : ""}
              {" · "}{c.refresh.error ? "Saved evidence · source refresh failed" : c.available ? "Verified research available" : c.availability_status === "loading" ? "Loading official sources" : "Financial evidence unavailable"}
              {c.identity?.source_url && <> · <a href={c.identity.source_url} target="_blank" rel="noopener noreferrer">SEC identity source ↗</a></>}
            </p>
            <p className="muted mt-3 max-w-2xl">
              {c.radar[0]?.text ??
                "A clean workspace for testing the business evidence behind this company."}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <WatchButton ticker={ticker} enabled={c.watchlisted} />
            <Button asChild>
              <a href="#ideas-to-track">
                View ideas <ArrowRight size={15} aria-hidden />
              </a>
            </Button>
          </div>
        </div>
        <div className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {[
            ["Price", money(c.market?.price)],
            ["Market cap", money(c.market?.market_cap)],
            [
              `Revenue · ${context?.period ?? `Latest annual · FY${a?.fiscal_year ?? "?"}`}`,
              money(context ? revenue?.value : a?.revenue),
            ],
            [
              "Trailing P/E",
              c.market?.trailing_pe?.toFixed(1) ?? "Unavailable",
            ],
          ].map(([label, value]) => (
            <div
              className="rounded-xl border border-border/70 bg-background/30 p-4"
              key={label}
            >
              <p className="source !mt-0">{label}</p>
              <p className="metric mt-2">{value}</p>
            </div>
          ))}
        </div>
        <p className="source mt-5 inline-flex items-center gap-1.5">
          <CalendarDays size={13} aria-hidden />
          {c.market?.status ?? "unavailable"} · Quote updated{" "}
          {c.market?.quote_as_of || c.market_as_of || "date unavailable"}
          {c.market?.provider && ` · ${c.market.provider}`}
        </p>
        <p className="source">
          Previous close: {money(c.market?.previous_close)}
          {c.market?.status === "cached" &&
            " · Showing the last successful saved quote; the current source check has not supplied a fresh value."}
          {c.market?.source_url && (
            <>
              {" "}
              ·{" "}
              <a
                href={c.market.source_url}
                target="_blank"
                rel="noopener noreferrer"
              >
                Quote source ↗
              </a>
            </>
          )}
        </p>
      </section>
      {!c.available && (
        <div className="empty mt-6">
          <FileSearch
            className="mx-auto mb-3 text-primary"
            size={28}
            aria-hidden
          />
          <h2>Research is still taking shape</h2>
          <p className="mt-3">
            {c.availability_status === "loading"
              ? "Official filings are being checked. This page will remain available while the background refresh runs."
              : c.availability_status === "provider_error"
                ? "The source check failed. No verified financial data is being invented; try again after the provider recovers."
                : c.availability_status === "unknown_symbol"
                  ? "This ticker is not in the current SEC company directory. Check the symbol or use the company search above."
                : "No supported filing facts are saved for this symbol yet. This is not a claim that the company has no filings."}
          </p>
          <Button className="mt-4" onClick={() => q.refetch()}>
            Check again
          </Button>
        </div>
      )}
      {c.refresh.error && (
        <div className="empty mt-4 text-left">
          <h3>Using the latest saved evidence</h3>
          <p className="mt-2">
            A source refresh failed, but cached facts remain usable where
            available.
          </p>
          <p className="source">{c.refresh.error}</p>
        </div>
      )}
      <Section title="Business & filing evidence">
        <div className="grid gap-4 lg:grid-cols-[1.2fr_1fr]">
          <article className="panel">
            <h3>Business overview</h3>
            {c.overview ? (
              <>
                <p className="muted mt-3 text-sm leading-6">{c.overview.text}</p>
                <p className="source mt-3">SEC filing excerpt · {c.overview.period || "Period not listed"} · <a href={c.overview.source_url} target="_blank" rel="noopener noreferrer">Read source ↗</a></p>
              </>
            ) : (
              <p className="muted mt-3 text-sm">A sourced business overview is not cached. Open the original filing rather than relying on an unsourced summary.</p>
            )}
          </article>
          <article className="panel">
            <h3>Recent SEC filings</h3>
            {c.filing_timeline.length ? (
              <ul className="mt-3 space-y-3">
                {c.filing_timeline.slice(0, 4).map((filing) => (
                  <li key={filing.source_url} className="border-b border-border/60 pb-3 last:border-0">
                    <a className="font-medium text-primary" href={filing.source_url} target="_blank" rel="noopener noreferrer">{filing.form} ↗</a>
                    <p className="source !mt-1">Period {filing.report_date || "unavailable"} · Filed {filing.filing_date}</p>
                  </li>
                ))}
              </ul>
            ) : <p className="muted mt-3 text-sm">No verified filing timeline is cached yet.</p>}
          </article>
        </div>
      </Section>
      <Section title="Why It Matters">
        <div className="grid-cards">
          <article className="panel">
            <span className="icon-shell">
              <Binoculars size={18} aria-hidden />
            </span>
            <h3 className="mt-4">Investor attention</h3>
            <p className="muted mt-2 text-sm">
              {c.radar[0]?.text ??
                "No verified institutional or insider signal is assumed."}
            </p>
          </article>
          {c.metric_context.map((metric) => (
            <article className="panel" key={metric.metric}>
              <div className="flex items-center justify-between gap-2">
                <span className="icon-shell">
                  <TrendingUp size={18} aria-hidden />
                </span>
                <span className="pill">{metric.status}</span>
              </div>
              <h3 className="mt-4">{metric.label}</h3>
              <p className="metric mt-2">
                {["free_cash_flow", "revenue", "net_income"].includes(
                  metric.metric,
                )
                  ? money(metric.current)
                  : percent(metric.current)}
              </p>
              <p className="source">
                {metric.current_period} · Previous{" "}
                {metric.previous_period ?? "unavailable"}:{" "}
                {["free_cash_flow", "revenue", "net_income"].includes(
                  metric.metric,
                )
                  ? money(metric.previous)
                  : percent(metric.previous)}
              </p>
              <p className="mt-3 text-sm font-medium text-primary">
                {metric.delta == null
                  ? "Comparable value unavailable"
                  : `${metric.delta > 0 ? "↑" : metric.delta < 0 ? "↓" : "→"} ${["free_cash_flow", "revenue", "net_income"].includes(metric.metric) ? (metric.relative_change == null ? money(metric.delta) : percent(metric.relative_change)) : `${(metric.delta * 100).toFixed(1)} percentage points`}`}
              </p>
              <p className="muted mt-2 text-sm">{metric.meaning}</p>
              {metric.metric === "free_cash_flow" && (
                <Help
                  label="What is FCF?"
                  text="Free cash flow is cash generated from operations after capital spending. A negative value means spending exceeded operating cash generation."
                />
              )}
              {metric.source_url && (
                <p className="source">
                  <a href={metric.source_url}>Current evidence ↗</a>
                  {metric.previous_source_url && (
                    <>
                      {" "}
                      ·{" "}
                      <a href={metric.previous_source_url}>
                        Previous evidence ↗
                      </a>
                    </>
                  )}
                </p>
              )}
            </article>
          ))}
          {!c.metric_context.length && (
            <div className="empty">
              Comparable financial periods are not available yet. No growth or
              cash-generation rating is inferred.
            </div>
          )}
        </div>
      </Section>
      <Section
        title="Financial Snapshot"
        aside={
          context?.period || a?.fiscal_year ? (
            <span className="pill">
              {context?.period ?? `Latest annual · FY${a?.fiscal_year}`} · SEC
              facts
            </span>
          ) : undefined
        }
      >
        {context && (
          <div className="panel mb-5">
            <h3>Numbers That Matter</h3>
            {comparableRevenue && (
              <div className="mt-4 rounded-xl border border-border/70 bg-background/30 p-4" role="img" aria-label={`Revenue comparison: ${comparableRevenue.period} ${money(comparableRevenue.value)}, previous ${comparableRevenue.previous_period} ${money(comparableRevenue.previous)}`}>
                <p className="text-sm font-medium">Comparable revenue</p>
                {[
                  { period: comparableRevenue.previous_period ?? "Prior period", value: comparableRevenue.previous ?? 0, color: "bg-sky-500" },
                  { period: comparableRevenue.period, value: comparableRevenue.value ?? 0, color: "bg-primary" },
                ].map((bar) => (
                  <div key={bar.period} className="mt-3 grid grid-cols-[minmax(5rem,8rem)_1fr_auto] items-center gap-3 text-xs">
                    <span className="truncate">{bar.period}</span>
                    <span className="h-2 overflow-hidden rounded-full bg-muted"><span className={`block h-full rounded-full ${bar.color}`} style={{ width: `${Math.max(2, bar.value / Math.max(comparableRevenue.value ?? 0, comparableRevenue.previous ?? 0) * 100)}%` }} /></span>
                    <span className="font-mono">{money(bar.value)}</span>
                  </div>
                ))}
                <a className="source mt-3 block" href={comparableRevenue.source_url} target="_blank" rel="noopener noreferrer">SEC facts ↗</a>
              </div>
            )}
            <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {context.metrics.map((m) => (
                <div
                  key={m.metric}
                  className="rounded-xl border border-border p-4"
                >
                  <p>{m.label}</p>
                  <p className="mt-2 font-semibold text-primary">{m.period}</p>
                  <p className="metric mt-2">
                    {m.metric === "revenue_growth"
                      ? percent(m.value)
                      : m.metric === "eps" && m.value != null
                        ? `$${m.value.toFixed(2)}`
                        : money(m.value)}
                  </p>
                  <p className="source">
                    {m.metric === "revenue_growth" && m.value != null
                      ? `YoY · ${m.previous_period ?? "prior year"}`
                      : m.yoy != null
                        ? `${percent(m.yoy)} YoY · ${m.previous_period}`
                        : "Comparable growth unavailable"}
                  </p>
                  {m.previous != null && (
                    <p className="source">
                      Previous {m.previous_period}:{" "}
                      {m.metric === "eps"
                        ? `$${m.previous.toFixed(2)}`
                        : money(m.previous)}
                    </p>
                  )}
                  {m.source_url && (
                    <a className="source" href={m.source_url}>
                      SEC facts ↗
                    </a>
                  )}
                </div>
              ))}
            </div>
            {quarterly && a?.fiscal_year && (
              <details className="mt-5">
                <summary>
                  Annual context · Latest annual · FY{a.fiscal_year}
                </summary>
                <p className="source">
                  Revenue: {money(a.revenue)} · Revenue growth:{" "}
                  {percent(a.revenue_growth)} · Free cash flow:{" "}
                  {money(a.free_cash_flow)}
                </p>
                {a.source_url && (
                  <a className="source" href={a.source_url}>
                    Annual SEC facts ↗
                  </a>
                )}
              </details>
            )}
          </div>
        )}
        <div className="panel">
          <div className="flex items-center gap-3">
            <span className="icon-shell">
              <BarChart3 size={18} aria-hidden />
            </span>
            <div>
              <h3>Financial pulse</h3>
              <p className="source !mt-0">
                {context?.period ?? "Latest annual"} · FCF margin unavailable
                when cash flow and revenue durations differ
              </p>
            </div>
          </div>
          <div className="mt-7 grid gap-6 md:grid-cols-3">
            {metrics.map(({ label, value, Icon }) => (
              <div key={label}>
                <div className="flex items-center justify-between gap-3 text-sm">
                  <span className="flex items-center gap-2 muted">
                    <Icon size={15} aria-hidden />
                    {label}
                  </span>
                  <strong className="font-mono">{percent(value)}</strong>
                </div>
                <div className="metric-track">
                  <div
                    className={`metric-fill ${value != null && value < 0 ? "!bg-amber-400" : ""}`}
                    style={{
                      width:
                        value == null
                          ? "0%"
                          : `${Math.min(100, Math.abs(value) * 200)}%`,
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
          <div className="mt-7 flex flex-wrap gap-4 text-xs muted">
            {a?.source_url && (
              <a href={a.source_url}>Financial facts source ↗</a>
            )}
            <span>
              Bars are scaled for quick comparison; labels show the actual
              values.
            </span>
          </div>
        </div>
        <div className="mt-6">
          <div className="section-head !mt-0">
            <h3 className="text-xl">What’s New</h3>
          </div>
          <div className="grid-cards">
            {c.changes.map((change, index) => (
              <article className="panel" key={index}>
                <span className="pill">{change.category}</span>
                <h3 className="mt-4 leading-snug">{change.text}</h3>
                <p className="source">
                  {change.comparison ??
                    "Observed filing-language comparison, not a claim that the underlying risk is new."}
                </p>
                <details className="mt-4 text-sm">
                  <summary className="cursor-pointer text-primary">
                    Compare source evidence
                  </summary>
                  <Sources
                    evidence={
                      change.evidence ??
                      [change.previous, change.current].filter(
                        (item) => item !== undefined,
                      )
                    }
                  />
                </details>
              </article>
            ))}
          </div>
          {!c.changes.length && (
            <div className="empty">
              <Sparkles
                className="mx-auto mb-3 text-primary"
                size={24}
                aria-hidden
              />
              <h3>No verified change to highlight</h3>
              <p className="mt-2">
                Comparable filings are needed before a material change can be
                shown. Missing data is never estimated.
              </p>
            </div>
          )}
        </div>
      </Section>
      <section id="ideas-to-track" className="scroll-mt-24">
        <div className="section-head">
          <h2>What To Watch</h2>
        </div>
        <div className="grid gap-6 lg:grid-cols-2">
          <div>
            <div className="mb-4 flex items-center gap-2">
              <Sparkles className="text-primary" size={20} aria-hidden />
              <h3 className="text-xl">Ideas to Track</h3>
              <Help
                label="What is a thesis?"
                text="A thesis is a testable idea about how a business may develop. Track evidence that supports or challenges it."
              />
            </div>
            <p className="muted mb-4 text-sm">
              Evidence-backed questions to investigate—not recommendations.
              {quarterly &&
                " Annual financial ideas retain their original fiscal-year labels; they are background context, not latest-quarter metrics."}
            </p>
            <div className="space-y-4">
              {c.suggestions.map((suggestion) => (
                <SuggestedCard
                  key={suggestion.id}
                  suggestion={suggestion}
                  ticker={ticker}
                  tracked={c.theses}
                />
              ))}
            </div>
            {!c.suggestions.length && (
              <div className="empty">
                <h3>No sourced ideas yet</h3>
                <p className="mt-2">
                  Ideas appear after enough verified financial or filing
                  evidence is available.
                </p>
              </div>
            )}
          </div>
          <div>
            <div className="mb-4 flex items-center gap-2">
              <CircleAlert className="text-amber-300" size={20} aria-hidden />
              <h3 className="text-xl">Key Risks</h3>
            </div>
            <p className="muted mb-4 text-sm">
              Read the source language and decide what could challenge the idea.
            </p>
            <div className="space-y-4">
              {c.risk_cards.map((risk, index) => (
                <article className="panel" key={index}>
                  <span className="icon-shell">
                    <ShieldAlert size={18} aria-hidden />
                  </span>
                  <h3 className="mt-4">{risk.title}</h3>
                  <p className="muted mt-3 text-sm leading-6">{risk.summary}</p>
                  <p className="mt-3 text-sm">
                    <strong>Why it matters:</strong> {risk.why_it_matters}
                  </p>
                  <p className="source">
                    ThesisLens analysis · Evidence{" "}
                    {risk.period || "date unavailable"}
                  </p>
                  {risk.source_url && (
                    <p className="source">
                      <a
                        href={risk.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        View source ↗
                      </a>
                    </p>
                  )}
                  <details className="mt-4 text-sm">
                    <summary className="text-primary">
                      View original SEC evidence
                    </summary>
                    <p className="source whitespace-pre-wrap leading-6">
                      {risk.evidence.text}
                    </p>
                  </details>
                </article>
              ))}
            </div>
            {!c.risk_cards.length && (
              <div className="empty">
                <h3>Risk evidence not cached yet</h3>
                <p className="mt-2">
                  This does not mean the company has no risks. Review the
                  original filings before reaching a conclusion.
                </p>
              </div>
            )}
          </div>
        </div>
      </section>
      <details className="panel mt-10">
        <summary className="cursor-pointer font-semibold">
          Advanced tracking, disclosures, and source details
        </summary>
        <div className="mt-7 space-y-8">
          <div>
            <div className="flex items-center gap-2">
              <h3>My tracked ideas</h3>
              <Help
                label="What does weakening mean?"
                text="New evidence conflicts with an assumption you track. It does not automatically mean the stock should be sold."
              />
            </div>
            <div className="mt-4 space-y-4">
              {c.theses.map((thesis) => (
                <TrackedCard key={thesis.id} thesis={thesis} />
              ))}
            </div>
            {!c.theses.length && (
              <div className="empty mt-4">
                Track an idea above to start a dated evidence timeline.
              </div>
            )}
            <CustomThesis ticker={ticker} templates={c.templates} />
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <Disclosures ticker={ticker} kind="insiders" />
            <Disclosures ticker={ticker} kind="ownership" />
          </div>
          <div className="rounded-xl border border-border p-4">
            <p className="font-medium">Valuation context</p>
            <p className="muted mt-2 text-sm">
              Trailing P/E: {c.market?.trailing_pe?.toFixed(1) ?? "Unavailable"}
              . A multiple is context, not fair value.
            </p>
          </div>
          {c.warnings.length > 0 && (
            <div>
              <p className="font-medium">Source notes and limitations</p>
              {c.warnings.map((warning, index) => (
                <p className="source" key={index}>
                  {warning}
                </p>
              ))}
            </div>
          )}
        </div>
      </details>
    </>
  );
}
