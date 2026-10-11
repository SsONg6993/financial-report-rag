"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { z } from "zod";
import { api } from "@/lib/api";

const recordSchema = z.object({
  asset_name: z.string(),
  transaction_type: z.string(),
  amount_range: z.string(),
  transaction_date: z.string(),
  filing_date: z.string(),
  source_url: z.string(),
  page: z.number().nullable().optional(),
  source_text: z.string().optional().default(""),
  confidence: z.string().optional().default("unknown"),
});

const extractionSchema = z.object({
  status: z.string(),
  method: z.string(),
  text_layer_status: z.string(),
  ocr_used: z.boolean(),
  pages_total: z.number(),
  pages_with_text: z.number(),
  pages_with_tables: z.number(),
  raw_fragment_count: z.number(),
  candidate_count: z.number(),
  verified_count: z.number(),
  rejected_count: z.number(),
  deduplicated_count: z.number(),
  coverage_rate: z.number(),
  confidence: z.string(),
  rejection_reasons: z.record(z.string(), z.number()),
});

const schema = z.array(
  z.object({
    person: z.string(),
    disclosure_type: z.string(),
    filing_date: z.string(),
    source_document_date: z.string(),
    certification_date: z.string().optional().default(""),
    source_url: z.string(),
    notes: z.union([z.string(), z.array(z.string())]),
    records: z.array(recordSchema),
    extraction: extractionSchema,
  }),
);

type Disclosure = z.infer<typeof schema>[number];

function asDate(value: string) {
  if (!value) return "";
  const parsed = new Date(value);
  return Number.isNaN(parsed.valueOf())
    ? value
    : new Intl.DateTimeFormat("en", { dateStyle: "medium" }).format(parsed);
}

function label(value: string) {
  return value.replaceAll("_", " ");
}

function DisclosureCard({ disclosure }: { disclosure: Disclosure }) {
  const [asset, setAsset] = useState("");
  const [type, setType] = useState("");
  const [amount, setAmount] = useState("");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const types = [...new Set(disclosure.records.map((row) => row.transaction_type))];
  const amounts = [...new Set(disclosure.records.map((row) => row.amount_range))];
  const filtered = useMemo(
    () =>
      disclosure.records.filter(
        (row) =>
          row.asset_name.toLowerCase().includes(asset.trim().toLowerCase()) &&
          (!type || row.transaction_type === type) &&
          (!amount || row.amount_range === amount) &&
          (!fromDate || row.transaction_date >= fromDate) &&
          (!toDate || row.transaction_date <= toDate),
      ),
    [amount, asset, disclosure.records, fromDate, toDate, type],
  );
  const coverage = disclosure.extraction.coverage_rate;
  const needsReview =
    disclosure.extraction.status === "review_required" ||
    disclosure.extraction.confidence === "low";

  return (
    <article className="panel mt-5" data-testid="public-disclosure-card">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="eyebrow">{disclosure.disclosure_type}</p>
          <h3 className="mt-2">{disclosure.person}</h3>
          <p className="source">
            Filing date {asDate(disclosure.filing_date) || "not verified"} ·
            Document date {asDate(disclosure.source_document_date) || "unknown"}
          </p>
        </div>
        <span className={needsReview ? "status-reduced" : "status-increased"}>
          {needsReview ? "Review required" : "Verified extraction"}
        </span>
      </div>

      <div className="grid-cards mt-5 !gap-3">
        <div className="rounded-xl border border-border p-4">
          <span className="eyebrow">Verified transactions</span>
          <p className="metric mt-2">
            {disclosure.extraction.verified_count.toLocaleString()}
          </p>
        </div>
        <div className="rounded-xl border border-border p-4">
          <span className="eyebrow">Candidate coverage</span>
          <p className="metric mt-2">{(coverage * 100).toFixed(1)}%</p>
          <p className="source">Confidence {disclosure.extraction.confidence}</p>
        </div>
        <div className="rounded-xl border border-border p-4">
          <span className="eyebrow">Source pages</span>
          <p className="metric mt-2">{disclosure.extraction.pages_total}</p>
          <p className="source">
            Text layer {disclosure.extraction.text_layer_status}
          </p>
        </div>
      </div>

      <p className="muted mt-5 text-sm">
        Amounts are official disclosure ranges—not exact transaction values or
        evidence of current holdings.
      </p>
      <a
        className="source mt-3 inline-block"
        href={disclosure.source_url}
        target="_blank"
        rel="noopener noreferrer"
      >
        Open original official document ↗
      </a>

      {disclosure.records.length ? (
        <>
          <div
            className="disclosure-filters mt-6"
            aria-label="Transaction filters"
          >
            <label>
              <span>Disclosed asset</span>
              <input
                value={asset}
                onChange={(event) => setAsset(event.target.value)}
                placeholder="Filter by asset"
              />
            </label>
            <label>
              <span>Transaction type</span>
              <select
                value={type}
                onChange={(event) => setType(event.target.value)}
              >
                <option value="">All verified types</option>
                {types.map((value) => (
                  <option value={value} key={value}>
                    {value}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>Amount range</span>
              <select
                value={amount}
                onChange={(event) => setAmount(event.target.value)}
              >
                <option value="">All verified ranges</option>
                {amounts.map((value) => (
                  <option value={value} key={value}>
                    {value}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>From</span>
              <input
                type="date"
                value={fromDate}
                onChange={(event) => setFromDate(event.target.value)}
              />
            </label>
            <label>
              <span>To</span>
              <input
                type="date"
                value={toDate}
                onChange={(event) => setToDate(event.target.value)}
              />
            </label>
          </div>
          <p className="source" role="status">
            Showing {filtered.length.toLocaleString()} of{" "}
            {disclosure.records.length.toLocaleString()} verified rows
          </p>
          <div className="table-wrap mt-3">
            <table className="min-w-[760px]">
              <thead>
                <tr>
                  <th>Transaction date</th>
                  <th>Disclosed asset</th>
                  <th>Type</th>
                  <th>Amount range</th>
                  <th>Source</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((row, index) => (
                  <tr
                    key={`${row.transaction_date}-${row.asset_name}-${index}`}
                  >
                    <td>{asDate(row.transaction_date)}</td>
                    <td>{row.asset_name}</td>
                    <td>{row.transaction_type}</td>
                    <td>{row.amount_range}</td>
                    <td>
                      <a
                        className="source"
                        href={`${disclosure.source_url}#page=${row.page ?? 1}`}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        Page {row.page ?? "unknown"} ↗
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : (
        <div className="empty mt-5" role="status">
          <strong>No transactions were verified by the extractor.</strong>
          <p className="mt-2 text-sm">
            This does not mean no transactions occurred. The document needs
            source review because no row safely passed the form-specific checks.
          </p>
        </div>
      )}

      <details className="diagnostic-details mt-5">
        <summary>Technical extraction details</summary>
        <div className="mt-3 text-sm muted">
          <p>
            {disclosure.extraction.candidate_count.toLocaleString()} numbered
            candidates ·{" "}
            {disclosure.extraction.rejected_count.toLocaleString()} unverified ·{" "}
            {disclosure.extraction.deduplicated_count.toLocaleString()} duplicates
            removed
          </p>
          <p className="mt-2">
            Method {label(disclosure.extraction.method)} · OCR{" "}
            {disclosure.extraction.ocr_used ? "used" : "not used"}
          </p>
          {Object.keys(disclosure.extraction.rejection_reasons).length > 0 && (
            <ul className="mt-3 grid gap-1">
              {Object.entries(disclosure.extraction.rejection_reasons).map(
                ([reason, count]) => (
                  <li key={reason}>
                    {label(reason)}: {count.toLocaleString()}
                  </li>
                ),
              )}
            </ul>
          )}
        </div>
      </details>
    </article>
  );
}

export function PublicOfficials() {
  const query = useQuery({
    queryKey: ["public-officials"],
    queryFn: ({ signal }) => api("/public-officials", schema, { signal }),
  });

  return (
    <section className="mt-10" aria-labelledby="public-officials-title">
      <div className="section-head">
        <div>
          <p className="eyebrow">Range-based public disclosures</p>
          <h2 id="public-officials-title">Public Officials</h2>
          <p className="muted mt-2 text-sm">
            OGE reports are validated under their own form schema and remain
            separate from institutional 13F portfolios.
          </p>
        </div>
      </div>
      {query.isPending ? (
        <p className="empty mt-4" role="status">
          Checking cached disclosures…
        </p>
      ) : query.isError ? (
        <p className="empty mt-4" role="alert">
          Official disclosure data is unavailable. Institutional research
          remains available.
        </p>
      ) : !query.data.length ? (
        <p className="empty mt-4">
          No official public-disclosure snapshot is cached. This is not evidence
          that no disclosure exists.
        </p>
      ) : (
        query.data.map((disclosure) => (
          <DisclosureCard
            key={`${disclosure.source_url}-${disclosure.source_document_date}`}
            disclosure={disclosure}
          />
        ))
      )}
    </section>
  );
}
