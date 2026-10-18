import { HomeFeed } from "@/features/home/home-feed";
import { IntelligenceFeed } from "@/features/intelligence/feed";
export default function Home() {
  return (
    <div className="page">
      <div className="hero !py-10">
        <p className="eyebrow">Your research workspace</p>
        <h1 className="mt-3 max-w-3xl">
          Evidence first. Decisions remain yours.
        </h1>
        <p className="muted mt-3 max-w-2xl">
          Monitor companies and disclosed institutional portfolios without
          turning delayed filings into invented real-time signals.
        </p>
      </div>
      <HomeFeed highlights={<IntelligenceFeed variant="preview" />} />
    </div>
  );
}
