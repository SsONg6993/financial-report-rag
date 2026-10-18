export default function Loading() {
  return (
    <div className="page" role="status" aria-label="Loading ThesisLens page">
      <div className="hero !py-10">
        <div className="h-3 w-40 animate-pulse rounded bg-surface motion-reduce:animate-none" />
        <div className="mt-5 h-12 max-w-2xl animate-pulse rounded-xl bg-surface motion-reduce:animate-none" />
        <div className="mt-4 h-5 max-w-xl animate-pulse rounded bg-surface motion-reduce:animate-none" />
      </div>
      <div className="mt-8 grid gap-4 md:grid-cols-3">
        {[0, 1, 2].map((item) => (
          <div
            className="h-48 animate-pulse rounded-2xl border border-border bg-surface/60 motion-reduce:animate-none"
            key={item}
          />
        ))}
      </div>
      <span className="sr-only">Loading…</span>
    </div>
  );
}
