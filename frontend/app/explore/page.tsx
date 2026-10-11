import { SearchBox } from "@/components/research-ui";
import {
  exploreNavigation,
  SectionNavigation,
} from "@/components/section-navigation";
import { InvestorList } from "@/features/discover/investors";
import { PublicOfficials } from "@/features/discover/public-officials";
import { PortfolioNetwork } from "@/features/portfolio-network/portfolio-network";

export default function ExplorePage() {
  return (
    <div className="page">
      <div className="hero !py-10">
        <p className="eyebrow">Explore verified public evidence</p>
        <h1 className="mt-3">Investors, portfolios, and businesses.</h1>
        <p className="muted mt-4 max-w-2xl">
          Move from disclosed institutional portfolios to company research
          without confusing delayed filings, public-official reports, or
          current holdings.
        </p>
        <SearchBox />
      </div>
      <SectionNavigation
        active="/explore"
        ariaLabel="Explore sections"
        items={exploreNavigation}
      />
      <PortfolioNetwork />
      <InvestorList />
      <PublicOfficials />
    </div>
  );
}
