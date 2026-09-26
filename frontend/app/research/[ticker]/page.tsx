import { CompanyResearch } from "@/features/research/company";
export default async function Research({
  params,
}: {
  params: Promise<{ ticker: string }>;
}) {
  const { ticker } = await params;
  return (
    <div className="page">
      <CompanyResearch ticker={ticker.toUpperCase()} />
    </div>
  );
}
