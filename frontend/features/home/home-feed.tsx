"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowUpRight, Building2, CircleAlert } from "lucide-react";
import { api, homeSchema, money, percent } from "@/lib/api";
import {
  ActivityBadge,
  ErrorState,
  Freshness,
  Loading,
  Section,
} from "@/components/research-ui";

export function HomeFeed({ highlights }: { highlights: ReactNode }) {
  const feed = useQuery({
    queryKey: ["home"],
    queryFn: ({ signal }) => api("/home/feed", homeSchema, { signal }),
    refetchInterval: 120_000,
  });
  if (feed.isPending) return <Loading />;
  if (feed.isError) return <ErrorState retry={() => feed.refetch()} />;
  const data = feed.data;
  const quotes = data.market_overview.filter((quote) => quote.available);
  return (
    <>
      <Section
        title="Market Overview"
        aside={
          <Link href="/market-pulse" className="text-sm text-primary">
            Market Pulse →
          </Link>
        }
      >
        {quotes.length ? (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {quotes.slice(0, 4).map((quote) => (
              <Link
                href={`/research/${quote.ticker}`}
                className="panel group"
                key={quote.ticker}
              >
                <div className="flex items-center justify-between">
                  <strong>{quote.ticker}</strong>
                  <ArrowUpRight
                    size={16}
                    className="text-primary"
                    aria-hidden
                  />
                </div>
                <p className="metric mt-3">{money(quote.price)}</p>
                <p
                  className={`mt-1 text-sm ${quote.change != null && quote.change < 0 ? "text-amber-300" : "text-primary"}`}
                >
                  {quote.change == null
                    ? "Daily change unavailable"
                    : `${quote.change >= 0 ? "+" : ""}${percent(quote.change)}`}
                </p>
                <p className="source">
                  {quote.status} ·{" "}
                  {quote.quote_as_of?.slice(0, 10) ?? "date unavailable"}
                </p>
              </Link>
            ))}
          </div>
        ) : (
          <div className="empty text-left">
            <h3>Saved market quotes are not available</h3>
            <p className="mt-2">
              Company filings and institutional disclosures remain usable.
              Quotes appear only after a configured provider returns dated data.
            </p>
          </div>
        )}
      </Section>
      <Section
        title="My Watchlist"
        aside={
          <Link href="/research" className="text-sm text-primary">
            Research a company →
          </Link>
        }
      >
        {data.watchlist.length ? (
          <div className="overflow-x-auto">
            <table>
              <thead>
                <tr>
                  <th scope="col">Company</th>
                  <th scope="col">Tracked ideas</th>
                  <th scope="col">Status</th>
                  <th scope="col">
                    <span className="sr-only">Open</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.watchlist.map((item) => (
                  <tr key={item.ticker}>
                    <th scope="row">{item.ticker}</th>
                    <td>{item.tracked}</td>
                    <td>
                      {item.attention
                        ? `${item.attention} need review`
                        : item.available
                          ? "Evidence available"
                          : "Awaiting evidence"}
                    </td>
                    <td>
                      <Link
                        href={`/research/${item.ticker}`}
                        className="text-primary"
                      >
                        Open →
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="empty">
            No companies saved yet. Add one from Research to monitor its
            evidence.
          </div>
        )}
      </Section>
      {highlights}
      <Section
        title="Institutional Activity"
        aside={
          <Link href="/discover" className="text-sm text-primary">
            Compare investors →
          </Link>
        }
      >
        <p className="muted mb-4 text-sm">
          Latest comparable saved disclosures. 13F reports are delayed and
          incomplete.
        </p>
        {data.activity.length ? (
          <div className="space-y-3">
            {data.activity.slice(0, 4).map((item, index) => (
              <article
                className="panel flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"
                key={`${item.institution_id}-${item.ticker}-${index}`}
              >
                <div className="flex items-start gap-3">
                  <span className="icon-shell">
                    <Building2 size={17} aria-hidden />
                  </span>
                  <div>
                    <Link
                      href={`/discover/${item.institution_id}`}
                      className="font-semibold hover:text-primary"
                    >
                      {item.institution}
                    </Link>
                    <p className="muted text-sm">
                      {item.ticker || item.issuer} ·{" "}
                      {item.pct_change == null
                        ? "new or exited position"
                        : percent(item.pct_change)}
                    </p>
                    <Freshness
                      type={item.source_type}
                      period={item.current_period ?? item.reporting_period}
                      filed={item.filing_date}
                      freshness={item.freshness}
                    />
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <ActivityBadge activity={item.activity} />
                  {item.ticker && (
                    <Link
                      href={`/research/${item.ticker}`}
                      className="text-sm text-primary"
                    >
                      Research →
                    </Link>
                  )}
                </div>
              </article>
            ))}
          </div>
        ) : (
          <div className="empty">
            No comparable saved institutional changes are available yet.
          </div>
        )}
      </Section>
      <Section title="Quick Research">
        <div className="panel grid gap-5 md:grid-cols-[1fr_auto] md:items-center">
          <div>
            <h3>Start with a company, investor, or question</h3>
            <p className="muted mt-2 text-sm">
              Research uses verified filings and saved public disclosures;
              General mode uses your local Ollama configuration.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link href="/research" className="pill border-primary text-primary">
              Company research
            </Link>
            <Link href="/discover" className="pill">
              Investor research
            </Link>
            <Link href="/ask" className="pill">
              Ask ThesisLens
            </Link>
          </div>
        </div>
        {!data.watchlist.length && (
          <p className="mt-3 flex items-center gap-2 text-sm muted">
            <CircleAlert size={15} aria-hidden />
            Add a watchlist company to personalize market and intelligence
            highlights.
          </p>
        )}
      </Section>
      <p className="source mt-8">
        Dashboard assembled {data.as_of.slice(0, 10)} · Source dates govern
        freshness.
      </p>
    </>
  );
}
