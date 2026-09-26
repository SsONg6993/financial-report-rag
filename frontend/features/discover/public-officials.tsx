"use client";
import { useQuery } from "@tanstack/react-query";
import { z } from "zod";
import { api } from "@/lib/api";
const schema = z.array(
  z.object({
    person: z.string(),
    disclosure_type: z.string(),
    filing_date: z.string(),
    source_document_date: z.string(),
    source_url: z.string(),
    notes: z.union([z.string(), z.array(z.string())]),
    records: z.array(
      z.object({
        asset_name: z.string(),
        transaction_type: z.string(),
        amount_range: z.string(),
        transaction_date: z.string(),
        filing_date: z.string(),
        source_url: z.string(),
      }),
    ),
  }),
);
export function PublicOfficials() {
  const q = useQuery({
    queryKey: ["public-officials"],
    queryFn: ({ signal }) => api("/public-officials", schema, { signal }),
  });
  return (
    <details className="panel mt-8">
      <summary className="font-semibold">
        Public officials · a separate disclosure system
      </summary>
      <p className="muted text-sm mt-4">
        Official OGE disclosures are range-based, not institutional portfolios.
        No exact values or portfolio weights are inferred.
      </p>
      {q.isPending ? (
        <p className="muted mt-3" role="status">
          Checking cached disclosures…
        </p>
      ) : q.isError ? (
        <p className="empty mt-4" role="alert">
          Official disclosure data is unavailable. Institutional research
          remains available.
        </p>
      ) : !q.data.length ? (
        <p className="empty mt-4">
          No verified public-official disclosure cached. Use the internal
          importer to load an official OGE document.
        </p>
      ) : (
        q.data.map((d, i) => (
          <article key={i} className="border-t border-border mt-5 pt-5">
            <h3>{d.person}</h3>
            <p className="source">
              {d.disclosure_type} · Filing date {d.filing_date || "unknown"} ·
              Source document date {d.source_document_date || "unknown"}
            </p>
            <a
              className="source inline-block"
              href={d.source_url}
              target="_blank"
              rel="noopener noreferrer"
            >
              Official document ↗
            </a>
            {d.records.map((r, j) => (
              <p className="text-sm mt-3" key={j}>
                {r.asset_name} · {r.transaction_type} · {r.amount_range} ·{" "}
                {r.transaction_date}
              </p>
            ))}
            {!d.records.length && (
              <p className="empty mt-4">
                No transaction rows passed the parser’s quality checks. Review
                the original document; unverified rows are not presented as
                facts.
              </p>
            )}
            <p className="source">
              {Array.isArray(d.notes) ? d.notes.join(" ") : d.notes}
            </p>
          </article>
        ))
      )}
    </details>
  );
}
