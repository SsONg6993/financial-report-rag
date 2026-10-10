import { IntelligenceFeed } from "@/features/intelligence/feed";

export default function IntelligencePage() {
  return (
    <div className="page">
      <div className="hero !py-10">
        <p className="eyebrow">Public-source monitoring</p>
        <h1 className="mt-3">Intelligence Feed</h1>
        <p className="muted mt-3 max-w-2xl">
          Search and filter dated disclosures, official updates, and
          watchlist-relevant events. Relevance reflects your saved follows—not
          investment merit.
        </p>
      </div>
      <IntelligenceFeed />
    </div>
  );
}
