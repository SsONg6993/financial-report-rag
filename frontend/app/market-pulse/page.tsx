import { MarketPulsePage } from "@/features/market-pulse/pulse";
import {
  intelligenceNavigation,
  SectionNavigation,
} from "@/components/section-navigation";
export default function Page() {
  return (
    <div className="page">
      <SectionNavigation
        active="/market-pulse"
        ariaLabel="Intelligence sections"
        items={intelligenceNavigation}
      />
      <MarketPulsePage />
    </div>
  );
}
