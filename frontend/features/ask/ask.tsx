"use client";
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { api, answerSchema } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { MutationError, Sources } from "@/components/research-ui";
import {
  ArrowUp,
  BookOpenCheck,
  MessageCircleQuestion,
  Search,
  ShieldCheck,
} from "lucide-react";
const examples = [
  "Why did Berkshire reduce AAPL?",
  "Which investors I follow disclose GOOGL?",
  "What changed in AAPL’s latest quarter?",
  "What idea should I track for NVDA?",
];
export function AskResearch() {
  const [question, setQuestion] = useState("");
  const m = useMutation({
    mutationFn: () =>
      api("/ask", answerSchema, {
        method: "POST",
        body: JSON.stringify({ question, ticker: "AAPL" }),
      }),
  });
  return (
    <>
      <form
        className="panel mt-8 !p-3 sm:!p-5"
        onSubmit={(e) => {
          e.preventDefault();
          m.mutate();
        }}
      >
        <div className="flex gap-3">
          <span className="icon-shell mt-1 hidden shrink-0 sm:inline-flex">
            <MessageCircleQuestion size={18} aria-hidden />
          </span>
          <div className="min-w-0 flex-1">
            <label htmlFor="question" className="font-semibold">
              What would you like to investigate?
            </label>
            <textarea
              id="question"
              name="question"
              autoComplete="off"
              className="mt-3 !min-h-28 resize-y !border-0 !bg-background/55"
              minLength={3}
              maxLength={2000}
              required
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Ask about a company, investor disclosure, or idea to track…"
            />
          </div>
        </div>
        <div className="mt-3 flex flex-wrap items-center justify-between gap-3 border-t border-border/70 pt-3">
          <p className="flex items-center gap-1.5 text-xs muted">
            <ShieldCheck size={14} className="text-primary" aria-hidden />
            Grounded in dated local evidence.
          </p>
          <Button
            type="submit"
            disabled={m.isPending || question.trim().length < 3}
          >
            {m.isPending ? (
              "Reviewing sources…"
            ) : (
              <>
                Ask ThesisLens <ArrowUp size={15} aria-hidden />
              </>
            )}
          </Button>
        </div>
        <MutationError error={m.error} />
      </form>
      <div className="mt-5 grid gap-2 sm:grid-cols-2">
        {examples.map((x) => (
          <button
            key={x}
            className="flex min-h-14 items-center gap-3 rounded-xl border border-border bg-card/65 px-4 py-3 text-left text-sm transition hover:border-primary/40 hover:bg-card"
            onClick={() => setQuestion(x)}
          >
            <Search size={15} className="shrink-0 text-primary" aria-hidden />
            {x}
          </button>
        ))}
      </div>
      {m.data && (
        <article className="panel mt-8" aria-live="polite">
          <div className="flex items-center gap-3">
            <span className="icon-shell">
              <BookOpenCheck size={18} aria-hidden />
            </span>
            <div>
              <p className="eyebrow">Research response</p>
              <h2 className="mt-1">What the evidence supports</h2>
            </div>
          </div>
          <p className="whitespace-pre-wrap mt-5 leading-7">{m.data.answer}</p>
          <details className="mt-5">
            <summary className="text-sm text-primary">
              Sources &amp; evidence ({m.data.evidence.length})
            </summary>
            <Sources evidence={m.data.evidence} />
          </details>
          <p className="source">{m.data.source}</p>
        </article>
      )}
    </>
  );
}
