import { AskResearch } from "@/features/ask/ask";
export default function Ask() {
  return (
    <div className="page">
      <div className="hero !py-10">
        <p className="eyebrow">Evidence-aware research companion</p>
        <h1 className="mt-3">Ask a better question.</h1>
        <p className="muted mt-4 max-w-2xl">
          Explore disclosures, compare evidence, and test your assumptions.
          Answers separate reported facts from interpretation.
        </p>
      </div>
      <AskResearch />
    </div>
  );
}
