"use client";

import { useQuery } from "@tanstack/react-query";
import { Activity, CheckCircle2, CircleAlert, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { runtimeStatusSchema } from "./api";

const labels: Record<string, string> = {
  ready: "Ready",
  stale_cache: "Stale cache",
  source_unavailable: "Source unavailable",
  empty_cache: "Empty cache",
  service_unavailable: "Service unavailable",
  model_missing: "Model missing",
  loading: "Loading",
  invalid_response: "Invalid response",
  configuration_mismatch: "Configuration mismatch",
  unavailable: "Unavailable",
  degraded: "Degraded",
  error: "Error",
};

function StatusCard({
  title,
  status,
  detail,
}: {
  title: string;
  status: string;
  detail: string;
}) {
  const healthy = status === "ready";
  const Icon = healthy ? CheckCircle2 : CircleAlert;
  return (
    <article
      className="panel"
      data-testid={`runtime-${title.toLowerCase().replaceAll(" ", "-")}`}
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="eyebrow">{title}</p>
          <h2 className="mt-2 text-xl">{labels[status] ?? status}</h2>
        </div>
        <span
          className={`icon-shell ${healthy ? "text-emerald-300" : "text-amber-300"}`}
        >
          <Icon size={19} aria-hidden />
        </span>
      </div>
      <p className="mt-4 text-sm muted">{detail}</p>
    </article>
  );
}

export function RuntimeStatus() {
  const query = useQuery({
    queryKey: ["runtime-status"],
    queryFn: ({ signal }) => api("/readiness", runtimeStatusSchema, { signal }),
    retry: false,
  });
  const expectedCommit = process.env.NEXT_PUBLIC_THESISLENS_BUILD_COMMIT;
  const mismatch = Boolean(
    query.data &&
    expectedCommit &&
    expectedCommit !== "unknown" &&
    query.data.build_commit !== expectedCommit,
  );
  return (
    <div className="page">
      <section className="hero">
        <p className="eyebrow inline-flex items-center gap-2">
          <Activity size={15} aria-hidden /> Local runtime
        </p>
        <h1 className="mt-3">System status</h1>
        <p className="mt-3 max-w-2xl muted">
          Local-only service diagnostics. No credentials, environment values, or
          personal data are displayed.
        </p>
        <Button
          className="mt-6"
          variant="outline"
          onClick={() => query.refetch()}
          disabled={query.isFetching}
        >
          <RefreshCw
            size={15}
            aria-hidden
            className={query.isFetching ? "animate-spin" : ""}
          />
          {query.isFetching ? "Checking…" : "Refresh status"}
        </Button>
      </section>
      {query.isPending && (
        <div className="empty mt-8" role="status">
          Checking local services…
        </div>
      )}
      {query.isError && (
        <div className="empty mt-8" role="alert">
          <h2>Backend offline</h2>
          <p className="mt-2">{query.error.message}</p>
          <p className="mt-3 text-sm">
            Run <code>.\start-thesislens.ps1</code> from the project folder,
            then refresh.
          </p>
        </div>
      )}
      {query.data && (
        <>
          {mismatch && (
            <div
              className="mt-8 rounded-2xl border border-amber-400/40 bg-amber-400/10 p-5"
              role="alert"
            >
              <strong>Backend version mismatch</strong>
              <p className="mt-1 text-sm muted">
                The frontend and Backend were started from different commits.
                Run the stop script, then the start script.
              </p>
            </div>
          )}
          <div className="grid-cards mt-8">
            <StatusCard
              title="Backend"
              status={mismatch ? "degraded" : query.data.backend.status}
              detail={`API ${query.data.api_version} · build ${query.data.build_commit.slice(0, 12)}`}
            />
            <StatusCard
              title="Market Pulse"
              status={query.data.market_pulse.status}
              detail={query.data.market_pulse.detail}
            />
            <StatusCard
              title="General AI"
              status={query.data.ollama.status}
              detail={`${query.data.ollama.model} · ${query.data.ollama.detail}`}
            />
            <StatusCard
              title="Frontend"
              status="ready"
              detail="This status page is loaded and interactive."
            />
          </div>
          <section className="panel mt-8">
            <h2>Troubleshooting</h2>
            <ul className="mt-4 list-disc space-y-2 pl-5 text-sm muted">
              <li>
                Run <code>.\status-thesislens.ps1</code> for a safe local
                summary.
              </li>
              <li>
                Use <code>.\stop-thesislens.ps1</code> only for processes
                started and tracked by ThesisLens.
              </li>
              <li>A missing Ollama model is never downloaded automatically.</li>
              <li>
                Logs rotate under <code>.runtime\logs</code> and do not contain
                configuration secrets.
              </li>
            </ul>
          </section>
        </>
      )}
    </div>
  );
}
