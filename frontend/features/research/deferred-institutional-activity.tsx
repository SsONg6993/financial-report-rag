"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";

const InstitutionalActivity = dynamic(
  () =>
    import("@/features/intelligence/feed").then(
      (module) => module.InstitutionalActivity,
    ),
  {
    loading: () => (
      <div className="panel mt-8 h-40 animate-pulse motion-reduce:animate-none" />
    ),
  },
);

export function DeferredInstitutionalActivity({ ticker }: { ticker: string }) {
  const [ready, setReady] = useState(false);
  useEffect(() => {
    if (ready) return;
    const activate = () => {
      if (
        window.location.hash === "#institutional-ownership" ||
        window.scrollY > 200
      )
        setReady(true);
    };
    activate();
    window.addEventListener("hashchange", activate);
    window.addEventListener("scroll", activate, { passive: true });
    return () => {
      window.removeEventListener("hashchange", activate);
      window.removeEventListener("scroll", activate);
    };
  }, [ready]);
  return (
    <div id="institutional-ownership" className="scroll-mt-24">
      {ready ? (
        <InstitutionalActivity ticker={ticker} />
      ) : (
        <section className="mt-10" aria-busy="true">
          <h2>Institutional activity</h2>
          <p className="source mt-2">
            Saved manager disclosures load when this section approaches view.
          </p>
        </section>
      )}
    </div>
  );
}
