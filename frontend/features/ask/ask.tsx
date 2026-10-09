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
  Sparkles,
} from "lucide-react";
type AskMode = "auto" | "general" | "research";
const examples = [
  "How do you think medical AI will develop in the future?",
  "Which recent news may affect my watchlist?",
  "Why did Berkshire reduce AAPL?",
  "Which investors I follow disclose GOOGL?",
  "What changed in AAPL’s latest quarter?",
  "What idea should I track for NVDA?",
];
const generalErrorTitle = (code?: string | null) => {
  if (code === "ollama_service_not_running")
    return "Ollama service is not running";
  if (code === "ollama_model_missing") return "Ollama model is missing";
  if (code === "ollama_timeout") return "Ollama response timed out";
  if (code === "remote_llm_disabled") return "Remote LLM access is disabled";
  return "General AI configuration error";
};
export function AskResearch() {
  const [question, setQuestion] = useState("");
  const [mode, setMode] = useState<AskMode>("auto");
  const m = useMutation({
    mutationFn: () =>
      api("/ask", answerSchema, {
        method: "POST",
        body: JSON.stringify({ question, mode }),
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
        <fieldset className="mb-4 flex flex-wrap items-center gap-2 border-b border-border/70 pb-4">
          <legend className="mb-2 w-full text-xs font-semibold uppercase tracking-[0.12em] muted">
            Answer mode
          </legend>
          {(["auto", "general", "research"] as AskMode[]).map((item) => (
            <button
              key={item}
              type="button"
              aria-pressed={mode === item}
              className={`min-h-10 rounded-xl border px-4 text-sm capitalize transition ${mode === item ? "border-primary bg-primary/15 text-primary" : "border-border bg-background/40 muted"}`}
              onClick={() => setMode(item)}
            >
              {item}
            </button>
          ))}
          <span className="source !mt-0 sm:ml-2">
            Auto routes locally. General never receives portfolio or filing
            context.
          </span>
        </fieldset>
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
            {mode === "general"
              ? "General AI uses only your question and configured model."
              : "Financial answers stay grounded in dated local evidence."}
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
              <p className="eyebrow">{m.data.intent.replaceAll("_", " ")}</p>
              <h2 className="mt-1">
                {m.data.intent === "general"
                  ? "General AI response"
                  : "What the evidence supports"}
              </h2>
            </div>
          </div>
          {m.data.sections ? (
            <div className="mt-6 space-y-6">
              <section>
                <h3>Short Answer</h3>
                <p className="mt-2 leading-7">{m.data.sections.short_answer}</p>
                <p className="source">
                  Verified evidence · investor rationale is identified only when
                  sourced
                </p>
              </section>
              {[
                ["Why", m.data.sections.why],
                ["Numbers That Matter", m.data.sections.numbers],
                ["What To Watch", m.data.sections.watch],
              ].map(([title, items]) => (
                <section key={String(title)}>
                  <h3>{String(title)}</h3>
                  <div className="mt-2 space-y-2">
                    {(items as string[]).length ? (
                      (items as string[]).map((item, index) => (
                        <p
                          className={`text-sm leading-6 whitespace-pre-line ${title === "Numbers That Matter" ? "rounded-xl border border-border p-4 font-medium" : "muted"}`}
                          key={index}
                        >
                          {item}
                        </p>
                      ))
                    ) : (
                      <p className="text-sm muted">
                        No verified values available for this question.
                      </p>
                    )}
                  </div>
                  {title === "Why" && (
                    <p className="source">
                      ThesisLens analysis · separate from investor-stated
                      rationale
                    </p>
                  )}
                </section>
              ))}
              {m.data.sections.annual_context.length > 0 && (
                <section>
                  <h3>Annual context</h3>
                  <div className="mt-2 space-y-2">
                    {m.data.sections.annual_context.map((item, index) => (
                      <p
                        key={index}
                        className="text-sm muted whitespace-pre-line"
                      >
                        {item}
                      </p>
                    ))}
                  </div>
                </section>
              )}
            </div>
          ) : (
            <p className="whitespace-pre-wrap mt-5 leading-7">
              {m.data.answer}
            </p>
          )}
          {m.data.configuration_error && (
            <div className="empty mt-5 text-left" role="alert">
              <strong>
                {generalErrorTitle(m.data.configuration_error_code)}
              </strong>
              <p className="mt-2 text-sm">{m.data.configuration_error}</p>
            </div>
          )}
          {m.data.evidence.length > 0 && (
            <details className="mt-5">
              <summary className="text-sm text-primary">
                Sources &amp; evidence ({m.data.evidence.length})
              </summary>
              <Sources evidence={m.data.evidence} />
            </details>
          )}
          <p className="mt-5 flex items-start gap-2 text-xs muted">
            <Sparkles
              size={14}
              className="mt-0.5 shrink-0 text-primary"
              aria-hidden
            />
            {m.data.privacy}
          </p>
          <p className="source">{m.data.source}</p>
        </article>
      )}
    </>
  );
}
