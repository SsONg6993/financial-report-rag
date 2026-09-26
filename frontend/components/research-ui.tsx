"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ArrowDownRight,
  ArrowRight,
  ArrowUpRight,
  CircleMinus,
  Clock3,
  Info,
  LogOut,
  Search,
  Sparkles,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { write, type Evidence } from "@/lib/api";

export function SearchBox() {
  const router = useRouter();
  const [error, setError] = useState("");
  function search(form: FormData) {
    const q = String(form.get("query") ?? "").trim();
    const aliases: Record<string, string> = {
      apple: "AAPL",
      nvidia: "NVDA",
      alphabet: "GOOGL",
      google: "GOOGL",
      microsoft: "MSFT",
    };
    const investors: Record<string, string> = {
      berkshire: "berkshire",
      buffett: "berkshire",
      pershing: "pershing",
      ackman: "pershing",
      burry: "scion",
      scion: "scion",
      ark: "ark",
      cathie: "ark",
      appaloosa: "appaloosa",
      tepper: "appaloosa",
      bridgewater: "bridgewater",
      duquesne: "duquesne",
      druckenmiller: "duquesne",
      soros: "soros",
      tiger: "tiger",
      coatue: "coatue",
    };
    const investor = Object.keys(investors).find((k) =>
      q.toLowerCase().includes(k),
    );
    if (investor) {
      router.push("/discover/" + investors[investor]);
      return;
    }
    const ticker = aliases[q.toLowerCase()] ?? q.toUpperCase();
    if (!/^[A-Z0-9.-]{1,12}$/.test(ticker)) {
      setError("Try a ticker such as AAPL, or an investor such as Berkshire.");
      return;
    }
    setError("");
    router.push("/research/" + ticker);
  }
  return (
    <form action={search} className="mt-7 max-w-2xl">
      <label htmlFor="company-search" className="sr-only">
        Search companies, investors, or tickers
      </label>
      <div className="flex items-center gap-2 rounded-2xl border border-input bg-card/90 p-2 shadow-[0_18px_50px_rgba(0,0,0,.2)] transition focus-within:border-primary/70 focus-within:ring-4 focus-within:ring-primary/10">
        <Search
          className="ml-2 shrink-0 text-muted-foreground"
          size={20}
          aria-hidden
        />
        <input
          id="company-search"
          name="query"
          autoComplete="off"
          spellCheck={false}
          required
          placeholder="Search companies, investors, or tickers…"
          className="w-full !border-0 !bg-transparent !p-2 !shadow-none"
        />
        <Button type="submit">Explore</Button>
      </div>
      {error && (
        <p role="alert" className="mt-2 text-sm text-destructive">
          {error}
        </p>
      )}
      <div className="mt-3 flex flex-wrap gap-2 text-xs muted">
        Try{" "}
        {["AAPL", "NVDA", "Berkshire", "Pershing"].map((x) => (
          <Link
            key={x}
            href={
              x === "Berkshire"
                ? "/discover/berkshire"
                : x === "Pershing"
                  ? "/discover/pershing"
                  : "/research/" + x
            }
            className="rounded-full border border-border bg-card/70 px-3 py-1.5 transition hover:border-primary/40 hover:text-primary"
          >
            {x}
          </Link>
        ))}
      </div>
    </form>
  );
}
export function Section({
  title,
  aside,
  children,
}: {
  title: string;
  aside?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section>
      <div className="section-head">
        <h2>{title}</h2>
        {aside}
      </div>
      {children}
    </section>
  );
}
export function Sources({ evidence }: { evidence: Evidence[] }) {
  return (
    <div className="space-y-2">
      {evidence.map((e, i) => (
        <div className="source" key={i}>
          <p className="line-clamp-4">{e.text}</p>
          <span>
            {e.period} {e.source_type}{" "}
          </span>
          {/^https:\/\//.test(e.source_url) && (
            <a href={e.source_url} target="_blank" rel="noopener noreferrer">
              Original source ↗
            </a>
          )}
        </div>
      ))}
    </div>
  );
}
export function Help({ label, text }: { label: string; text: string }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          aria-label={label}
          className="inline-flex min-h-8 min-w-8 items-center justify-center align-middle text-muted-foreground"
        >
          <Info size={15} />
        </button>
      </TooltipTrigger>
      <TooltipContent className="max-w-xs p-3">{text}</TooltipContent>
    </Tooltip>
  );
}
export function Loading() {
  return (
    <div role="status" aria-label="Loading research" className="mt-8 space-y-6">
      <div className="panel space-y-4">
        <Skeleton className="h-4 w-28" />
        <Skeleton className="h-10 w-2/3" />
        <Skeleton className="h-5 w-full max-w-xl" />
      </div>
      <div className="grid-cards">
        {[1, 2, 3].map((x) => (
          <div key={x} className="panel space-y-4">
            <Skeleton className="h-5 w-2/3" />
            <Skeleton className="h-24 w-full" />
          </div>
        ))}
      </div>
    </div>
  );
}
export function ErrorState({ retry }: { retry: () => void }) {
  return (
    <div role="alert" className="empty mt-8">
      <h2>Research is temporarily unavailable</h2>
      <p className="mt-2 mb-4">
        Your saved work is safe. Check that the Python research service is
        running, then try again.
      </p>
      <Button onClick={retry}>Try again</Button>
    </div>
  );
}
export function MutationError({ error }: { error: Error | null }) {
  return error ? (
    <p role="alert" className="text-sm text-destructive mt-2">
      {error.message}
    </p>
  ) : null;
}
export function WatchButton({
  ticker,
  enabled,
}: {
  ticker: string;
  enabled: boolean;
}) {
  const cache = useQueryClient();
  const mutation = useMutation({
    mutationFn: () =>
      write("/company/" + ticker + "/watch", { enabled: !enabled }),
    onSuccess: () => {
      cache.invalidateQueries({ queryKey: ["home"] });
      cache.invalidateQueries({ queryKey: ["company", ticker] });
    },
  });
  return (
    <>
      <Button
        variant="outline"
        disabled={mutation.isPending}
        onClick={() => mutation.mutate()}
      >
        {enabled ? "Watching" : "Add to Watchlist"}
      </Button>
      <MutationError error={mutation.error} />
    </>
  );
}
export function ResearchLink({ ticker }: { ticker: string }) {
  return (
    <Button asChild>
      <Link href={"/research/" + ticker}>
        Research <ArrowRight size={14} aria-hidden />
      </Link>
    </Button>
  );
}
export function Freshness({
  type,
  period,
  filed,
  freshness,
}: {
  type: string;
  period?: string | null;
  filed?: string | null;
  freshness?: string;
}) {
  return (
    <div className="mt-3 space-y-2">
      <div className="flex flex-wrap gap-2">
        <span className="pill">{type}</span>
        {period && <span className="pill">Period {period}</span>}
      </div>
      <p className="source !mt-0 inline-flex items-center gap-1.5">
        <Clock3 size={13} aria-hidden />
        {filed ? "Filed / updated " + filed : "Filing date unavailable"}
        {freshness && " · " + freshness}
      </p>
    </div>
  );
}

export function formatDate(value?: string | null) {
  if (!value) return "Date unavailable";
  const parsed = new Date(value.length === 10 ? value + "T00:00:00" : value);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(parsed);
}

export function ActivityBadge({ activity }: { activity?: string | null }) {
  const normalized = (activity ?? "unchanged").toLowerCase();
  const config = normalized.includes("new")
    ? { label: "New", className: "status-new", Icon: Sparkles }
    : normalized.includes("increase") || normalized.includes("add")
      ? {
          label: "Increased",
          className: "status-increased",
          Icon: ArrowUpRight,
        }
      : normalized.includes("reduce") || normalized.includes("decrease")
        ? {
            label: "Reduced",
            className: "status-reduced",
            Icon: ArrowDownRight,
          }
        : normalized.includes("exit") || normalized.includes("sold")
          ? { label: "Exited", className: "status-exited", Icon: LogOut }
          : {
              label: activity || "Unchanged",
              className: "status-neutral",
              Icon: CircleMinus,
            };
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium ${config.className}`}
    >
      <config.Icon size={13} aria-hidden />
      {config.label}
    </span>
  );
}
