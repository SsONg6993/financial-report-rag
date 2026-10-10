"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
} from "react";
import type { z } from "zod";
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
import {
  api,
  companyResolveSchema,
  companySearchSchema,
  write,
  type Evidence,
} from "@/lib/api";

const investorTerms: Record<string, string> = {
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

export function SearchBox() {
  const router = useRouter();
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [suggestions, setSuggestions] = useState<
    z.infer<typeof companySearchSchema>["results"]
  >([]);
  const [searching, setSearching] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [directoryStale, setDirectoryStale] = useState(false);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const suggestionButtons = useRef<(HTMLButtonElement | null)[]>([]);

  useEffect(() => {
    if (query.trim().length < 2 || !showSuggestions) {
      return;
    }
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      setSearching(true);
      try {
        const data = await api(
          "/companies/search?q=" + encodeURIComponent(query.trim()),
          companySearchSchema,
          { signal: controller.signal },
        );
        setSuggestions(data.results);
        setDirectoryStale(data.stale);
      } catch {
        if (!controller.signal.aborted) {
          setSuggestions([]);
          setError(
            "Company directory is temporarily unavailable. Your saved research is unaffected.",
          );
        }
      } finally {
        if (!controller.signal.aborted) setSearching(false);
      }
    }, 250);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [query, showSuggestions]);

  async function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const q = query.trim();
    if (!q) return;
    const investor = Object.keys(investorTerms).find(
      (term) => q.toLowerCase() === term,
    );
    if (investor) {
      router.push("/discover/" + investorTerms[investor]);
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      const result = await api(
        "/companies/resolve?q=" + encodeURIComponent(q),
        companyResolveSchema,
      );
      setDirectoryStale(Boolean(result.stale));
      if (result.status === "resolved" && result.company) {
        setShowSuggestions(false);
        router.push("/research/" + result.company.ticker);
      } else {
        setSuggestions(result.matches);
        setShowSuggestions(true);
        setError(result.message ?? "Select a specific company listing.");
      }
    } catch {
      setError(
        "SEC company lookup is unavailable. Retry shortly; saved research is unaffected.",
      );
    } finally {
      setSubmitting(false);
    }
  }
  function choose(ticker: string) {
    setQuery(ticker);
    setError("");
    setShowSuggestions(false);
    router.push("/research/" + ticker);
  }
  function onInputKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown" && suggestions.length) {
      event.preventDefault();
      suggestionButtons.current[0]?.focus();
    }
    if (event.key === "Escape") setShowSuggestions(false);
  }
  return (
    <form onSubmit={search} className="relative mt-7 max-w-2xl" role="search">
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
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            setError("");
            setShowSuggestions(true);
          }}
          onKeyDown={onInputKeyDown}
          aria-describedby={error ? "company-search-error" : undefined}
          autoComplete="off"
          spellCheck={false}
          required
          placeholder="Search companies, investors, or tickers…"
          className="w-full !border-0 !bg-transparent !p-2 !shadow-none"
        />
        <Button type="submit" disabled={submitting}>
          {submitting ? "Finding…" : "Explore"}
        </Button>
      </div>
      {showSuggestions && query.trim().length >= 2 && (
        <div
          className="absolute z-30 mt-2 w-full overflow-hidden rounded-2xl border border-border bg-card p-2 shadow-2xl"
          aria-label="Company suggestions"
        >
          {searching && (
            <p className="px-3 py-2 text-sm muted">
              Searching the SEC directory…
            </p>
          )}
          {!searching && suggestions.length === 0 && !error && (
            <p className="px-3 py-2 text-sm muted">
              No SEC company suggestion yet.
            </p>
          )}
          {suggestions.map((item, index) => (
            <button
              key={item.ticker + item.cik}
              ref={(node) => {
                suggestionButtons.current[index] = node;
              }}
              type="button"
              onClick={() => choose(item.ticker)}
              onKeyDown={(event) => {
                if (event.key === "Escape") setShowSuggestions(false);
                if (event.key === "ArrowDown")
                  suggestionButtons.current[index + 1]?.focus();
                if (event.key === "ArrowUp")
                  suggestionButtons.current[index - 1]?.focus();
              }}
              className="flex w-full items-center justify-between gap-3 rounded-xl px-3 py-2 text-left hover:bg-accent focus-visible:bg-accent"
            >
              <span className="min-w-0">
                <strong className="block truncate text-sm">{item.name}</strong>
                <span className="text-xs muted">
                  {item.exchange || "Exchange not listed"}
                </span>
              </span>
              <span className="rounded-lg border border-border px-2 py-1 text-xs text-primary">
                {item.ticker}
              </span>
            </button>
          ))}
          {directoryStale && (
            <p className="px-3 py-2 text-xs text-amber-300">
              Using the last verified SEC directory; refresh is temporarily
              unavailable.
            </p>
          )}
        </div>
      )}
      {error && (
        <p
          id="company-search-error"
          role="alert"
          className="mt-2 text-sm text-destructive"
        >
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
  id,
  title,
  aside,
  children,
}: {
  id?: string;
  title: string;
  aside?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section id={id} className="scroll-mt-24">
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
export function ErrorState({
  retry,
  error,
}: {
  retry: () => void;
  error?: Error | null;
}) {
  return (
    <div role="alert" className="empty mt-8">
      <h2>Research is temporarily unavailable</h2>
      <p className="mt-2 mb-4">
        {error?.message ??
          "Your saved work is safe. Check that the Python research service is running, then try again."}
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
