"use client";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { api, homeSchema, percent } from "@/lib/api";
import {
  BellRing,
  Binoculars,
  Building2,
  Eye,
  ShieldAlert,
} from "lucide-react";
import {
  ActivityBadge,
  ErrorState,
  Freshness,
  Loading,
  ResearchLink,
  Section,
  WatchButton,
} from "@/components/research-ui";
export function HomeFeed() {
  const q = useQuery({
    queryKey: ["home"],
    queryFn: ({ signal }) => api("/home/feed", homeSchema, { signal }),
    refetchInterval: 120_000,
  });
  if (q.isPending) return <Loading />;
  if (q.isError) return <ErrorState retry={() => q.refetch()} />;
  const d = q.data;
  return (
    <>
      <Section
        title="Top Investor Activity"
        aside={
          <Link href="/discover" className="text-sm text-primary">
            Explore investors →
          </Link>
        }
      >
        <p className="muted text-sm mb-4">
          Verified changes from the latest available disclosure. These are not
          real-time trades and do not explain an investor’s motivation.
        </p>
        <div className="grid-cards">
          {d.activity.slice(0, 6).map((a, i) => (
            <article className="panel group" key={i}>
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-center gap-3">
                  <span className="icon-shell">
                    <Building2 size={18} aria-hidden />
                  </span>
                  <div>
                    <Link
                      href={"/discover/" + a.institution_id}
                      className="text-sm font-semibold hover:text-primary"
                    >
                      {a.institution}
                    </Link>
                    <p className="source !mt-0">Public portfolio disclosure</p>
                  </div>
                </div>
                <ActivityBadge activity={a.activity} />
              </div>
              <div className="mt-5 flex items-end justify-between gap-3">
                <div>
                  <h3 className="text-xl">{a.ticker || a.issuer}</h3>
                  {a.ticker && a.issuer && (
                    <p className="muted text-sm">{a.issuer}</p>
                  )}
                </div>
                <span className="font-mono text-sm">
                  {a.pct_change === null
                    ? "New / exited position"
                    : percent(a.pct_change)}
                </span>
              </div>
              {a.ticker && (
                <Link
                  className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-primary"
                  href={"/research/" + a.ticker}
                >
                  Open company research →
                </Link>
              )}
              <Freshness
                type={a.source_type}
                period={a.current_period ?? a.reporting_period}
                filed={a.filing_date}
                freshness={a.freshness}
              />
              {a.source_url && (
                <a
                  className="source inline-block"
                  href={a.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  View disclosure ↗
                </a>
              )}
            </article>
          ))}
        </div>
        {!d.activity.length && (
          <div className="empty">
            No comparable disclosures loaded yet. Start with a featured investor
            below.
          </div>
        )}
      </Section>
      <Section title="Interesting Ideas">
        <p className="muted text-sm mb-4">
          ThesisLens analysis, not the investor’s stated rationale.
        </p>
        <div className="grid-cards">
          {d.ideas.map((i) => (
            <article key={i.ticker} className="panel">
              <div className="flex items-center justify-between gap-3">
                <span className="icon-shell">
                  <Binoculars size={18} aria-hidden />
                </span>
                <span className="pill">Research starting point</span>
              </div>
              <h3 className="mt-4 text-2xl">{i.ticker}</h3>
              <p className="mt-1 text-sm font-medium">Why it’s on the radar</p>
              <ul className="mt-4 space-y-2 text-sm muted">
                {i.reasons.slice(0, 2).map((r) => (
                  <li className="flex gap-2" key={r}>
                    <Eye
                      className="mt-0.5 shrink-0 text-primary"
                      size={15}
                      aria-hidden
                    />
                    {r}
                  </li>
                ))}
              </ul>
              <p className="mt-4 flex gap-2 rounded-xl bg-muted/35 p-3 text-xs muted">
                <ShieldAlert
                  className="shrink-0 text-amber-300"
                  size={15}
                  aria-hidden
                />
                Disclosure timing may differ from the investor’s current
                position.
              </p>
              <p className="source">
                Period {i.period} ·{" "}
                <a
                  href={i.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Disclosure ↗
                </a>
              </p>
              <div className="mt-5 flex flex-wrap gap-2">
                <ResearchLink ticker={i.ticker} />
                <WatchButton ticker={i.ticker} enabled={i.watchlisted} />
              </div>
            </article>
          ))}
        </div>
        {!d.ideas.length && (
          <div className="empty">
            Verified ticker mappings and evidence will populate ideas here.
            Nothing is fabricated.
          </div>
        )}
      </Section>
      <Section title="My Watchlist">
        <div className="grid-cards">
          {d.watchlist.map((w) => (
            <Link
              className="panel group hover:border-primary/40"
              href={"/research/" + w.ticker}
              key={w.ticker}
            >
              <div className="flex items-center justify-between gap-3">
                <span className="icon-shell">
                  <BellRing size={18} aria-hidden />
                </span>
                <span className="pill">
                  {w.attention ? `${w.attention} to review` : "Up to date"}
                </span>
              </div>
              <h3 className="mt-4 text-xl">{w.ticker}</h3>
              <p className="muted mt-3">
                {w.tracked
                  ? w.tracked +
                    " ideas tracked · " +
                    w.attention +
                    " need review"
                  : w.available
                    ? "Explore financial changes and ideas to track"
                    : "Company evidence not yet available"}
              </p>
              <span className="text-primary text-sm">Continue research →</span>
            </Link>
          ))}
        </div>
        {!d.watchlist.length && (
          <div className="empty">
            Save a company from Research to follow its evidence—even before
            tracking a thesis.
          </div>
        )}
      </Section>
      <p className="source mt-8">
        Feed assembled {d.as_of.slice(0, 10)} · Source dates govern freshness,
        not the time this page loaded.
      </p>
    </>
  );
}
