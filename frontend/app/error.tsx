"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/button";

export default function ErrorBoundary({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("ThesisLens route error", error);
  }, [error]);
  return (
    <div className="page">
      <div className="empty mx-auto mt-16 max-w-xl text-left" role="alert">
        <p className="eyebrow">This view could not finish loading</p>
        <h1 className="mt-3">Your saved research is unchanged.</h1>
        <p className="muted mt-3">
          Retry the view. If the problem continues, open Status to distinguish
          a Backend, provider, or local AI issue.
        </p>
        <Button className="mt-6" onClick={reset}>
          Retry this view
        </Button>
      </div>
    </div>
  );
}
