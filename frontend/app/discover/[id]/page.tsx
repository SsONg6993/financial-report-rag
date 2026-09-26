import { InvestorProfile } from "@/features/discover/investors";
export default async function Investor({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <div className="page">
      <InvestorProfile id={id} />
    </div>
  );
}
