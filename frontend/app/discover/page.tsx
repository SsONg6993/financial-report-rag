import { InvestorList } from "@/features/discover/investors";
import { PublicOfficials } from "@/features/discover/public-officials";
export default function Discover() {
  return (
    <div className="page">
      <div className="hero !py-10">
        <p className="eyebrow">Public portfolios, made clearer</p>
        <h1 className="mt-3">Discover investors worth studying.</h1>
        <p className="muted mt-4 max-w-2xl">
          Compare the latest disclosed holdings, see meaningful changes, and
          choose which companies deserve your own research.
        </p>
      </div>
      <InvestorList />
      <PublicOfficials />
    </div>
  );
}
