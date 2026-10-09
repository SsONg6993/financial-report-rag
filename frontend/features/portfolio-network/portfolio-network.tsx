"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";
import { useQuery } from "@tanstack/react-query";
import { Maximize2, Minus, Pause, Play, Plus } from "lucide-react";
import { z } from "zod";
import {
  ErrorState,
  Loading,
  Section,
  formatDate,
} from "@/components/research-ui";
import {
  api,
  investorSchema,
  money,
  percent,
  portfolioOverlapSchema,
  type PortfolioOverlap,
} from "@/lib/api";
import { networkLayout, nextPlaybackPeriod, type Point } from "./layout";
import styles from "./portfolio-network.module.css";

type Hover =
  { kind: "institution"; id: string } | { kind: "security"; id: string } | null;
interface View {
  x: number;
  y: number;
  width: number;
  height: number;
}
const BASE_VIEW: View = { x: 0, y: 0, width: 920, height: 560 };

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => word[0])
    .join("")
    .toUpperCase();
}

function NetworkCanvas({
  data,
  reducedMotion,
}: {
  data: PortfolioOverlap;
  reducedMotion: boolean;
}) {
  const router = useRouter();
  const [view, setView] = useState<View>(BASE_VIEW);
  const [hover, setHover] = useState<Hover>(null);
  const [drag, setDrag] = useState<{ x: number; y: number; view: View } | null>(
    null,
  );
  const previous = useRef<PortfolioOverlap | null>(null);
  const [departing, setDeparting] = useState<{
    data: PortfolioOverlap;
    layout: ReturnType<typeof networkLayout>;
  } | null>(null);
  const layout = useMemo(() => networkLayout(data), [data]);
  const currentIds = useMemo(
    () => new Set(data.network.securities.map((row) => row.id)),
    [data],
  );

  useEffect(() => {
    const old = previous.current;
    previous.current = data;
    if (!old || reducedMotion) return;
    const removed = old.network.securities.filter(
      (row) => !currentIds.has(row.id),
    );
    if (!removed.length) return;
    const oldData = {
      ...old,
      network: {
        ...old.network,
        securities: removed,
        edges: old.network.edges.filter((edge) =>
          removed.some((row) => row.id === edge.security_id),
        ),
      },
    };
    setDeparting({ data: oldData, layout: networkLayout(old) });
    const timer = window.setTimeout(() => setDeparting(null), 450);
    return () => window.clearTimeout(timer);
  }, [currentIds, data, reducedMotion]);

  function zoom(factor: number): void {
    setView((old) => {
      const width = Math.min(1200, Math.max(420, old.width * factor));
      const height = width * (560 / 920);
      return {
        x: old.x + (old.width - width) / 2,
        y: old.y + (old.height - height) / 2,
        width,
        height,
      };
    });
  }
  function activate(path: string): void {
    router.push(path);
  }
  function keyActivate(event: KeyboardEvent<SVGGElement>, path: string): void {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      activate(path);
    }
  }
  const hoveredInstitution =
    hover?.kind === "institution"
      ? data.institutions.find((row) => row.id === hover.id)
      : null;
  const hoveredSecurity =
    hover?.kind === "security"
      ? data.network.securities.find((row) => row.id === hover.id)
      : null;

  return (
    <div className={styles.shell} data-testid="portfolio-network-canvas">
      <div className={styles.controls} aria-label="Network zoom controls">
        <button
          className={styles.control}
          aria-label="Zoom in"
          onClick={() => zoom(0.82)}
        >
          <Plus size={17} aria-hidden />
        </button>
        <button
          className={styles.control}
          aria-label="Zoom out"
          onClick={() => zoom(1.18)}
        >
          <Minus size={17} aria-hidden />
        </button>
        <button
          className={styles.control}
          aria-label="Reset view"
          onClick={() => setView(BASE_VIEW)}
        >
          <Maximize2 size={16} aria-hidden />
        </button>
      </div>
      <svg
        className={styles.canvas}
        viewBox={`${view.x} ${view.y} ${view.width} ${view.height}`}
        role="img"
        aria-label="Interactive network of selected institutions and their verified disclosed holdings"
        onWheel={(event) => {
          event.preventDefault();
          zoom(event.deltaY > 0 ? 1.08 : 0.92);
        }}
        onPointerDown={(event) =>
          setDrag({ x: event.clientX, y: event.clientY, view })
        }
        onPointerMove={(event) => {
          if (!drag) return;
          const scale = view.width / event.currentTarget.clientWidth;
          setView({
            ...drag.view,
            x: drag.view.x - (event.clientX - drag.x) * scale,
            y: drag.view.y - (event.clientY - drag.y) * scale,
          });
        }}
        onPointerUp={() => setDrag(null)}
        onPointerLeave={() => setDrag(null)}
      >
        {data.network.edges.map((edge) => {
          const from = layout.institutions.get(edge.institution_id);
          const to = layout.securities.get(edge.security_id);
          const security = data.network.securities.find(
            (row) => row.id === edge.security_id,
          );
          if (!from || !to) return null;
          return (
            <line
              key={`${edge.institution_id}:${edge.security_id}`}
              x1={from.x + 62}
              y1={from.y}
              x2={to.x}
              y2={to.y}
              strokeWidth={1 + Math.min(5, edge.weight * 18)}
              className={`${styles.edge} ${security && security.owner_count > 1 ? styles.edgeShared : ""}`}
            />
          );
        })}
        {departing?.data.network.securities.map((security) => {
          const point = departing.layout.securities.get(security.id);
          if (!point) return null;
          return (
            <g
              key={`exit:${security.id}`}
              className={styles.exiting}
              transform={`translate(${point.x} ${point.y})`}
            >
              <circle r="18" className={styles.security} />
            </g>
          );
        })}
        {data.institutions.map((institution) => {
          const point = layout.institutions.get(institution.id) as Point;
          return (
            <g
              key={institution.id}
              className={styles.node}
              role="link"
              tabIndex={0}
              aria-label={`Open ${institution.name} portfolio`}
              transform={`translate(${point.x} ${point.y})`}
              onMouseEnter={() =>
                setHover({ kind: "institution", id: institution.id })
              }
              onMouseLeave={() => setHover(null)}
              onFocus={() =>
                setHover({ kind: "institution", id: institution.id })
              }
              onBlur={() => setHover(null)}
              onClick={() => activate(`/discover/${institution.id}`)}
              onKeyDown={(event) =>
                keyActivate(event, `/discover/${institution.id}`)
              }
            >
              <rect
                x="-62"
                y="-25"
                width="124"
                height="50"
                rx="14"
                className={styles.institution}
              />
              <text textAnchor="middle" y="-2" className={styles.label}>
                {initials(institution.name)}
              </text>
              <text textAnchor="middle" y="13" className={styles.subLabel}>
                {institution.holding_count} holdings
              </text>
            </g>
          );
        })}
        {data.network.securities.map((security) => {
          const point = layout.securities.get(security.id) as Point;
          const radius = 13 + Math.min(12, security.owner_count * 3);
          return (
            <g
              key={security.id}
              className={`${styles.node} ${styles.entering}`}
              role={security.ticker ? "link" : undefined}
              tabIndex={security.ticker ? 0 : undefined}
              aria-label={security.ticker ? `Open research for ${security.ticker}` : undefined}
              transform={`translate(${point.x} ${point.y})`}
              onMouseEnter={() =>
                setHover({ kind: "security", id: security.id })
              }
              onMouseLeave={() => setHover(null)}
              onFocus={() => setHover({ kind: "security", id: security.id })}
              onBlur={() => setHover(null)}
              onClick={() =>
                security.ticker && activate(`/research/${security.ticker}`)
              }
              onKeyDown={(event) =>
                security.ticker &&
                keyActivate(event, `/research/${security.ticker}`)
              }
            >
              <circle
                r={radius}
                className={`${styles.security} ${security.owner_count > 1 ? styles.securityShared : ""}`}
              />
              <text textAnchor="middle" y="4" className={styles.label}>
                {security.ticker || "—"}
              </text>
              {security.owner_count > 1 && (
                <text
                  textAnchor="middle"
                  y={radius + 13}
                  className={styles.subLabel}
                >
                  {security.owner_count} owners
                </text>
              )}
            </g>
          );
        })}
      </svg>
      {(hoveredInstitution || hoveredSecurity) && (
        <div className={styles.tooltip} role="status">
          {hoveredInstitution && (
            <>
              <strong>{hoveredInstitution.name}</strong>
              <p className="mt-1 text-xs muted">
                {hoveredInstitution.source_type} · period{" "}
                {hoveredInstitution.reporting_period || "unavailable"} · filed{" "}
                {formatDate(hoveredInstitution.filing_date)}
              </p>
              {hoveredInstitution.source_url && (
                <p className="source">
                  <a href={hoveredInstitution.source_url}>Original source ↗</a>
                </p>
              )}
            </>
          )}
          {hoveredSecurity && (
            <>
              <strong>
                {hoveredSecurity.ticker || hoveredSecurity.issuer}
              </strong>
              <p className="mt-1 text-xs muted">
                {hoveredSecurity.issuer} · {hoveredSecurity.security_class}
                {hoveredSecurity.put_call
                  ? ` · ${hoveredSecurity.put_call}`
                  : ""}
              </p>
              {hoveredSecurity.owners.map((owner) => (
                <p key={owner.institution_id} className="mt-1 text-xs">
                  <span className="font-medium">
                    {
                      data.institutions.find(
                        (row) => row.id === owner.institution_id,
                      )?.name
                    }
                  </span>{" "}
                  · {percent(owner.weight)} · {owner.shares.toLocaleString()}{" "}
                  shares · {money(owner.reported_value)}
                </p>
              ))}
            </>
          )}
        </div>
      )}
    </div>
  );
}

export function PortfolioNetwork() {
  const investors = useQuery({
    queryKey: ["investors"],
    queryFn: ({ signal }) =>
      api("/investors", z.array(investorSchema), { signal }),
  });
  const [selected, setSelected] = useState<string[]>([]);
  const [period, setPeriod] = useState<string | null>(null);
  const [playing, setPlaying] = useState(false);
  const [reducedMotion, setReducedMotion] = useState(false);

  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReducedMotion(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);
  useEffect(() => {
    if (!selected.length && investors.data)
      setSelected(
        investors.data
          .filter((row) => row.available)
          .slice(0, 3)
          .map((row) => row.id),
      );
  }, [investors.data, selected.length]);
  const query = new URLSearchParams();
  selected.forEach((id) => query.append("investors", id));
  if (period) query.set("period", period);
  const overlap = useQuery({
    queryKey: ["portfolio-overlap", { selected, period }],
    queryFn: ({ signal }) =>
      api(`/portfolio-overlap?${query.toString()}`, portfolioOverlapSchema, {
        signal,
      }),
    enabled: selected.length >= 2,
    staleTime: 60_000,
  });
  useEffect(() => {
    if (!playing || reducedMotion || !overlap.data?.periods.length) return;
    const timer = window.setInterval(
      () =>
        setPeriod((current) =>
          nextPlaybackPeriod(overlap.data?.periods ?? [], current),
        ),
      1800,
    );
    return () => window.clearInterval(timer);
  }, [playing, reducedMotion, overlap.data?.periods]);
  function toggle(id: string): void {
    setPlaying(false);
    setPeriod(null);
    setSelected((old) =>
      old.includes(id)
        ? old.filter((item) => item !== id)
        : old.length < 5
          ? [...old, id]
          : old,
    );
  }

  if (investors.isPending) return <Loading />;
  if (investors.isError)
    return <ErrorState retry={() => investors.refetch()} />;
  return (
    <Section
      title="Institutional Portfolio Network"
      aside={<span className="pill">Verified stored disclosures</span>}
    >
      <div className="panel mb-4">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="font-medium">Select 2–5 institutions</p>
            <p className="source !mt-1">
              Shared ownership describes disclosed securities—not shared intent.
            </p>
          </div>
          <div
            className="flex flex-wrap gap-2"
            aria-label="Institution selection"
          >
            {investors.data
              .filter((row) => row.available)
              .map((investor) => (
                <button
                  key={investor.id}
                  type="button"
                  aria-pressed={selected.includes(investor.id)}
                  onClick={() => toggle(investor.id)}
                  className={`min-h-11 rounded-xl border px-3 text-sm transition ${selected.includes(investor.id) ? "border-primary bg-primary/15 text-primary" : "border-border bg-background/40 muted"}`}
                >
                  {investor.name}
                </button>
              ))}
          </div>
        </div>
        {selected.length < 2 && (
          <p className="mt-4 text-sm text-amber-300" role="status">
            Select at least two institutions to compare.
          </p>
        )}
      </div>
      {overlap.isPending && selected.length >= 2 ? (
        <Loading />
      ) : overlap.isError ? (
        <ErrorState retry={() => overlap.refetch()} />
      ) : (
        overlap.data && (
          <>
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <label className="text-sm">
                Reporting date
                <select
                  className="ml-2 min-h-11"
                  aria-label="Reporting date"
                  value={period ?? ""}
                  onChange={(event) => {
                    setPlaying(false);
                    setPeriod(event.target.value || null);
                  }}
                >
                  <option value="">Latest available per institution</option>
                  {overlap.data.periods.map((item) => (
                    <option value={item} key={item}>
                      {item}
                    </option>
                  ))}
                </select>
              </label>
              <button
                type="button"
                className="flex min-h-11 items-center gap-2 rounded-xl border border-border px-4 text-sm disabled:opacity-50"
                disabled={reducedMotion || overlap.data.periods.length < 2}
                onClick={() => setPlaying((old) => !old)}
                aria-label={
                  playing
                    ? "Pause historical playback"
                    : "Play historical timeline"
                }
              >
                {playing ? (
                  <Pause size={16} aria-hidden />
                ) : (
                  <Play size={16} aria-hidden />
                )}
                {reducedMotion
                  ? "Playback disabled for reduced motion"
                  : playing
                    ? "Pause"
                    : "Play history"}
              </button>
            </div>
            <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
              {[
                ["Common to all", overlap.data.summary.common_count.toString()],
                ["Shared by 2+", overlap.data.summary.shared_count.toString()],
                [
                  "Combined universe",
                  overlap.data.summary.union_count.toString(),
                ],
                ["Jaccard", percent(overlap.data.summary.jaccard)],
                [
                  "Weight overlap",
                  percent(overlap.data.summary.weight_overlap),
                ],
              ].map(([label, value]) => (
                <div className="panel !p-4" key={label}>
                  <p className="source !mt-0">{label}</p>
                  <p className="metric mt-1">{value}</p>
                </div>
              ))}
            </div>
            <NetworkCanvas data={overlap.data} reducedMotion={reducedMotion} />
            {overlap.data.network.truncated && (
              <p className="source">
                Network limited to {overlap.data.network.security_limit}{" "}
                highest-overlap/highest-weight securities for readability.
                Metrics use all verified mapped holdings.
              </p>
            )}
            <div className="mt-5 grid gap-4 lg:grid-cols-2">
              <article className="panel">
                <h3>Comparison coverage</h3>
                <div className="mt-4 space-y-3">
                  {overlap.data.institutions.map((row) => (
                    <div
                      key={row.id}
                      className="flex items-start justify-between gap-4 border-b border-border/60 pb-3"
                    >
                      <div>
                        <Link
                          className="font-medium text-primary"
                          href={`/discover/${row.id}`}
                        >
                          {row.name}
                        </Link>
                        <p className="source !mt-1">
                          {row.source_type || "No eligible snapshot"} ·{" "}
                          {row.reporting_period || "Unavailable"}
                        </p>
                      </div>
                      <div className="text-right text-sm">
                        <strong>{row.holding_count}</strong> holdings
                        <br />
                        <span className="muted">
                          {row.unique_count} unique · {row.mapped_count} mapped
                          {row.unmapped_count
                            ? ` · ${row.unmapped_count} unmapped`
                            : ""}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </article>
              <article className="panel">
                <h3>Pairwise similarity</h3>
                <div className="table-wrap mt-3">
                  <table>
                    <thead>
                      <tr>
                        <th>Pair</th>
                        <th>Shared</th>
                        <th>Jaccard</th>
                        <th>Weight overlap</th>
                      </tr>
                    </thead>
                    <tbody>
                      {overlap.data.pairwise.map((row) => (
                        <tr key={`${row.left}:${row.right}`}>
                          <td>
                            {row.left} / {row.right}
                          </td>
                          <td>{row.shared_count}</td>
                          <td>{percent(row.jaccard)}</td>
                          <td>{percent(row.weight_overlap)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </article>
            </div>
            <article className="panel mt-4">
              <h3>Shared and unique holdings</h3>
              <div className="mt-4 grid gap-5 lg:grid-cols-2">
                <div>
                  <p className="eyebrow">
                    Shared by two or more selected institutions
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {overlap.data.securities
                      .filter((row) => row.owner_count > 1)
                      .map((row) =>
                        row.ticker ? (
                          <Link
                            key={row.id}
                            href={`/research/${row.ticker}`}
                            className="pill"
                          >
                            {row.ticker} · {row.owner_count}
                          </Link>
                        ) : (
                          <span key={row.id} className="pill">
                            {row.issuer} · {row.owner_count}
                          </span>
                        ),
                      )}
                    {!overlap.data.securities.some(
                      (row) => row.owner_count > 1,
                    ) && (
                      <p className="muted text-sm">
                        No class-aware shared holding is available for this
                        selection.
                      </p>
                    )}
                  </div>
                </div>
                <div>
                  <p className="eyebrow">Unique to one selected institution</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {overlap.data.securities
                      .filter((row) => row.owner_count === 1)
                      .slice(0, 20)
                      .map((row) =>
                        row.ticker ? (
                          <Link
                            key={row.id}
                            href={`/research/${row.ticker}`}
                            className="pill"
                          >
                            {row.ticker} · {row.owners[0]?.institution_id}
                          </Link>
                        ) : (
                          <span key={row.id} className="pill">
                            {row.issuer} · {row.owners[0]?.institution_id}
                          </span>
                        ),
                      )}
                    {!overlap.data.securities.some(
                      (row) => row.owner_count === 1,
                    ) && (
                      <p className="muted text-sm">
                        No mapped holding is unique in this selection.
                      </p>
                    )}
                  </div>
                </div>
              </div>
            </article>
            <details className="panel mt-4">
              <summary className="font-medium">
                Definitions, source coverage, and position changes
              </summary>
              <div className="mt-4 space-y-2">
                {overlap.data.coverage_notes.map((note) => (
                  <p key={note} className="source">
                    {note}
                  </p>
                ))}
                <p className="source">
                  <strong>Jaccard:</strong> securities common to every selected
                  institution ÷ the union of their mapped securities.{" "}
                  <strong>Weight overlap:</strong> sum of the minimum disclosed
                  weight across every selected institution for those common
                  securities.
                </p>
              </div>
              {overlap.data.changes.length > 0 ? (
                <div className="table-wrap mt-5">
                  <table>
                    <thead>
                      <tr>
                        <th>Institution</th>
                        <th>Security</th>
                        <th>Change</th>
                        <th>Period</th>
                        <th>Source</th>
                      </tr>
                    </thead>
                    <tbody>
                      {overlap.data.changes
                        .slice(0, 30)
                        .map((change, index) => (
                          <tr
                            key={`${change.institution_id}:${change.cusip}:${index}`}
                          >
                            <td>{change.institution_id}</td>
                            <td>{change.ticker || change.issuer}</td>
                            <td>{change.activity}</td>
                            <td>{change.reporting_period}</td>
                            <td>
                              {change.source_url && (
                                <a href={change.source_url}>Filing ↗</a>
                              )}
                            </td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="empty mt-4">
                  No comparable prior stored period is available for the
                  selected snapshots. No changes are inferred.
                </p>
              )}
            </details>
          </>
        )
      )}
    </Section>
  );
}
