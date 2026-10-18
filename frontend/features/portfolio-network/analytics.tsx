"use client";

import { money, percent, type PortfolioOverlap } from "@/lib/api";
import { useMemo, useState, type CSSProperties } from "react";

const COLORS = ["#35d6ee", "#668cff", "#9b7cff", "#45c7a4", "#f4bd62"];

function institutionName(data: PortfolioOverlap, id: string): string {
  return data.institutions.find((row) => row.id === id)?.name ?? id;
}

export function SimilarityHeatmap({ data }: { data: PortfolioOverlap }) {
  const pair = (left: string, right: string) =>
    data.pairwise.find(
      (row) =>
        (row.left === left && row.right === right) ||
        (row.left === right && row.right === left),
    );

  return (
    <article className="panel">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="eyebrow">Pairwise overlap</p>
          <h3 className="mt-1">Jaccard similarity heatmap</h3>
        </div>
        <span className="source !mt-0">Darker = more similar</span>
      </div>
      <div className="mt-4 overflow-x-auto">
        <table
          className="heatmap"
          aria-label="Pairwise Jaccard similarity heatmap"
        >
          <thead>
            <tr>
              <th scope="col">Institution</th>
              {data.institutions.map((row) => (
                <th scope="col" key={row.id}>
                  {row.name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.institutions.map((left) => (
              <tr key={left.id}>
                <th scope="row">{left.name}</th>
                {data.institutions.map((right) => {
                  const item = pair(left.id, right.id);
                  const self = left.id === right.id;
                  const value = self && left.available ? 1 : item?.jaccard;
                  const comparable = self ? left.available : item?.comparable;
                  return (
                    <td key={right.id}>
                      <span
                        className={`heat-cell ${!comparable ? "heat-cell-missing" : ""}`}
                        style={
                          comparable
                            ? ({ "--heat": value ?? 0 } as CSSProperties)
                            : undefined
                        }
                        title={
                          !comparable
                            ? "No comparable stored disclosure"
                            : `${institutionName(data, left.id)} / ${institutionName(data, right.id)}: ${percent(value ?? 0)}`
                        }
                      >
                        {comparable ? percent(value ?? 0) : "N/A"}
                      </span>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="source">
        N/A means a disclosure was unavailable. A visible 0% is a genuine zero
        across mapped, class-aware identifiers.
      </p>
    </article>
  );
}

export function AllocationDonuts({ data }: { data: PortfolioOverlap }) {
  return (
    <article className="panel">
      <p className="eyebrow">Concentration</p>
      <h3 className="mt-1">Top disclosed allocations</h3>
      <div className="mt-5 grid gap-5 sm:grid-cols-2">
        {data.institutions
          .filter((row) => row.available)
          .map((institution) => {
            const holdings = data.securities
              .map((security) => ({
                security,
                owner: security.owners.find(
                  (row) => row.institution_id === institution.id,
                ),
              }))
              .filter((row) => row.owner)
              .sort((a, b) => (b.owner?.weight ?? 0) - (a.owner?.weight ?? 0))
              .slice(0, 5);
            let cursor = 0;
            const segments = holdings.map((row, index) => {
              const start = cursor;
              cursor += Math.max(0, (row.owner?.weight ?? 0) * 100);
              return `${COLORS[index]} ${start}% ${cursor}%`;
            });
            if (cursor < 100) segments.push(`#20384d ${cursor}% 100%`);
            return (
              <div key={institution.id} className="allocation-mini">
                <div
                  className="allocation-ring"
                  role="img"
                  aria-label={`${institution.name} top five allocation ${cursor.toFixed(1)} percent`}
                  style={{
                    background: `conic-gradient(${segments.join(",")})`,
                  }}
                >
                  <span>
                    {cursor.toFixed(0)}%<small>top 5</small>
                  </span>
                </div>
                <div className="min-w-0">
                  <strong>{institution.name}</strong>
                  {holdings.slice(0, 3).map((row, index) => (
                    <p className="source !mt-1 truncate" key={row.security.id}>
                      <i style={{ background: COLORS[index] }} />{" "}
                      {row.security.ticker || row.security.issuer} ·{" "}
                      {percent(row.owner?.weight ?? 0)}
                    </p>
                  ))}
                </div>
              </div>
            );
          })}
      </div>
    </article>
  );
}

export function HistoricalEvolution({ data }: { data: PortfolioOverlap }) {
  const availableInstitutions = data.institutions.filter((row) =>
    data.history.some((item) => item.institution_id === row.id),
  );
  const [institutionId, setInstitutionId] = useState(
    availableInstitutions[0]?.id ?? "",
  );
  const rows = useMemo(
    () =>
      data.history
        .filter((row) => row.institution_id === institutionId)
        .sort((a, b) => a.reporting_period.localeCompare(b.reporting_period)),
    [data.history, institutionId],
  );
  const periods = useMemo(
    () => [...new Set(data.history.map((row) => row.reporting_period))].sort(),
    [data.history],
  );
  const [selectedPeriod, setSelectedPeriod] = useState<string | null>(null);
  const selected =
    rows.find((row) => row.reporting_period === selectedPeriod) ?? rows.at(-1);
  const width = 720;
  const height = 250;
  const x = (period: string) =>
    periods.length < 2
      ? width / 2
      : 58 + (periods.indexOf(period) / (periods.length - 1)) * (width - 88);
  const y = (value: number) =>
    height - 48 - Math.min(1, Math.max(0, value)) * (height - 76);
  const selectedName =
    availableInstitutions.find((row) => row.id === institutionId)?.name ??
    institutionId;

  return (
    <article className="panel lg:col-span-2">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="eyebrow">Stored disclosure history</p>
          <h3 className="mt-1">Historical disclosed concentration</h3>
        </div>
        <span className="source !mt-0">
          No interpolation across missing periods
        </span>
      </div>
      {periods.length && availableInstitutions.length ? (
        <>
          <div
            className="mt-4 flex flex-wrap gap-2"
            aria-label="Historical investor selection"
          >
            {availableInstitutions.map((institution) => (
              <button
                type="button"
                key={institution.id}
                aria-pressed={institutionId === institution.id}
                className={`min-h-10 rounded-xl border px-3 text-sm ${institutionId === institution.id ? "border-primary bg-primary/15 text-primary" : "border-border muted"}`}
                onClick={() => {
                  setInstitutionId(institution.id);
                  setSelectedPeriod(null);
                }}
              >
                {institution.name}
              </button>
            ))}
          </div>
          <div className="mt-4 overflow-x-auto">
            <svg
              className="history-chart"
              viewBox={`0 0 ${width} ${height}`}
              role="img"
              aria-label={`${selectedName} historical top-five disclosed portfolio concentration`}
            >
              {[0, 0.25, 0.5, 0.75, 1].map((tick) => (
                <g key={tick}>
                  <line
                    x1="58"
                    x2={width - 30}
                    y1={y(tick)}
                    y2={y(tick)}
                    className="history-grid"
                  />
                  <text
                    x="50"
                    y={y(tick) + 4}
                    textAnchor="end"
                    className="history-label"
                  >
                    {percent(tick)}
                  </text>
                </g>
              ))}
              {periods.map((period) => (
                <text
                  key={period}
                  x={x(period)}
                  y={height - 18}
                  textAnchor="middle"
                  className="history-label"
                >
                  {period.slice(0, 7)}
                </text>
              ))}
              {rows.slice(1).map((row, index) => {
                const previous = rows[index];
                const adjacent =
                  periods.indexOf(row.reporting_period) -
                    periods.indexOf(previous.reporting_period) ===
                  1;
                return adjacent ? (
                  <line
                    key={`${previous.reporting_period}:${row.reporting_period}`}
                    x1={x(previous.reporting_period)}
                    y1={y(previous.top_five_weight)}
                    x2={x(row.reporting_period)}
                    y2={y(row.top_five_weight)}
                    className="history-line"
                  />
                ) : null;
              })}
              {rows.map((row) => (
                <g key={row.reporting_period} className="history-point">
                  <circle
                    cx={x(row.reporting_period)}
                    cy={y(row.top_five_weight)}
                    r={
                      selected?.reporting_period === row.reporting_period
                        ? 7
                        : 5
                    }
                    onClick={() => setSelectedPeriod(row.reporting_period)}
                  >
                    <title>
                      {selectedName} · {row.reporting_period} ·{" "}
                      {percent(row.top_five_weight)} ·{" "}
                      {money(row.disclosed_value_total)}
                    </title>
                  </circle>
                </g>
              ))}
            </svg>
            <div
              className="mt-2 flex flex-wrap gap-2"
              aria-label="Historical period selection"
            >
              {rows.map((row) => (
                <button
                  type="button"
                  key={row.reporting_period}
                  aria-pressed={
                    selected?.reporting_period === row.reporting_period
                  }
                  className="pill"
                  onClick={() => setSelectedPeriod(row.reporting_period)}
                >
                  {row.reporting_period}
                </button>
              ))}
            </div>
          </div>
          {selected && (
            <div className="history-detail mt-5">
              <div>
                <p className="eyebrow">Selected disclosure</p>
                <h3 className="mt-1">
                  {selectedName} · {selected.reporting_period}
                </h3>
                <p className="source">
                  Filed/updated {selected.filing_date} · {selected.source_type}{" "}
                  · <a href={selected.source_url}>Original source ↗</a>
                </p>
              </div>
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
                {selected.top_holdings.map((holding) => (
                  <div
                    className="rounded-xl border border-border p-3"
                    key={`${holding.cusip}:${holding.security_class}`}
                  >
                    <strong>{holding.ticker || holding.issuer}</strong>
                    <p className="source !mt-1">{holding.issuer}</p>
                    <p className="mt-2 font-mono text-sm">
                      {percent(holding.weight)}
                    </p>
                  </div>
                ))}
              </div>
              {!selected.top_holdings.length && (
                <p className="empty mt-3">
                  No mapped holdings are available for this stored period.
                </p>
              )}
            </div>
          )}
        </>
      ) : (
        <p className="empty mt-4">
          No stored historical disclosures are available for this selection.
        </p>
      )}
    </article>
  );
}
