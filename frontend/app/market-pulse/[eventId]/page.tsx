import { MarketPulseDetail } from "@/features/market-pulse/pulse";
export default async function Page({
  params,
}: {
  params: Promise<{ eventId: string }>;
}) {
  const { eventId } = await params;
  return (
    <div className="page">
      <MarketPulseDetail eventId={eventId} />
    </div>
  );
}
