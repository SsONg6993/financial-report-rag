import { HomeFeed } from "@/features/home/home-feed";
import { SearchBox } from "@/components/research-ui";
import { MarketPulsePreview } from "@/features/market-pulse/pulse";
export default function Home() {
  return (
    <div className="page">
      <div className="hero">
        <p className="eyebrow">Investor-led company research</p>
        <h1 className="mt-3 max-w-2xl">
          See what changed. Understand why it matters.
        </h1>
        <p className="muted mt-4 max-w-2xl">
          Turn public portfolio disclosures into clear research starting
          points—then test each idea against the business evidence.
        </p>
        <SearchBox />
      </div>
      <HomeFeed />
      <MarketPulsePreview />
    </div>
  );
}
