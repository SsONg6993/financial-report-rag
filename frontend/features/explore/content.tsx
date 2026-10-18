"use client";

import dynamic from "next/dynamic";
import { useEffect, useRef, useState } from "react";

const PortfolioNetwork = dynamic(
  () =>
    import("@/features/portfolio-network/portfolio-network").then(
      (module) => module.PortfolioNetwork,
    ),
  { loading: () => <SectionSkeleton label="Loading portfolio network" /> },
);
const InvestorList = dynamic(
  () =>
    import("@/features/discover/investors").then(
      (module) => module.InvestorList,
    ),
  { loading: () => <SectionSkeleton label="Loading investor directory" /> },
);
const PublicOfficials = dynamic(
  () =>
    import("@/features/discover/public-officials").then(
      (module) => module.PublicOfficials,
    ),
  { loading: () => <SectionSkeleton label="Loading public disclosures" /> },
);

function SectionSkeleton({ label }: { label: string }) {
  return (
    <section className="mt-10" aria-label={label} aria-busy="true">
      <div className="h-7 w-64 animate-pulse rounded bg-surface motion-reduce:animate-none" />
      <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {[0, 1, 2].map((item) => (
          <div
            className="h-40 animate-pulse rounded-2xl border border-border bg-surface/60 motion-reduce:animate-none"
            key={item}
          />
        ))}
      </div>
    </section>
  );
}

function DeferredPublicOfficials() {
  const anchor = useRef<HTMLDivElement>(null);
  const [ready, setReady] = useState(false);
  useEffect(() => {
    const element = anchor.current;
    if (!element || ready) return;
    const observer = new IntersectionObserver(
      ([entry]) => entry.isIntersecting && setReady(true),
      { rootMargin: "600px" },
    );
    observer.observe(element);
    const timeout = window.setTimeout(() => setReady(true), 2000);
    return () => {
      observer.disconnect();
      window.clearTimeout(timeout);
    };
  }, [ready]);
  return (
    <div ref={anchor}>
      {ready ? (
        <PublicOfficials />
      ) : (
        <SectionSkeleton label="Public disclosures will load when visible" />
      )}
    </div>
  );
}

export function ExploreContent() {
  return (
    <>
      <PortfolioNetwork />
      <InvestorList />
      <DeferredPublicOfficials />
    </>
  );
}
