import { CompanyResearch } from "@/features/research/company";
import { PulseResearchContext } from "@/features/market-pulse/pulse";
import { InstitutionalActivity } from "@/features/intelligence/feed";
export default async function Research({
  params,
  searchParams,
}: {
  params: Promise<{ ticker: string }>;
  searchParams: Promise<{ event?: string | string[] }>;
}) {
  const { ticker } = await params;
  const { event } = await searchParams;
  return (
    <div className="page">
      {typeof event === "string" && /^[a-f0-9]{20}$/.test(event) && (
        <PulseResearchContext eventId={event} ticker={ticker.toUpperCase()} />
      )}
      <CompanyResearch ticker={ticker.toUpperCase()} />
      <InstitutionalActivity ticker={ticker.toUpperCase()} />
    </div>
  );
}
