import { SearchBox } from "@/components/research-ui";
import Link from "next/link";
export default function Research() {
  return (
    <div className="page">
      <div className="hero">
        <p className="eyebrow">Build conviction with evidence</p>
        <h1 className="mt-3">
          Research a business.
          <br />
          Test the assumptions.
        </h1>
        <p className="muted mt-4">
          Start with the financial facts, then turn an idea into an assumption
          you can test over time.
        </p>
        <SearchBox />
      </div>
      <div className="grid-cards mt-8">
        {[
          ["AAPL", "Apple"],
          ["NVDA", "NVIDIA"],
          ["GOOGL", "Alphabet"],
        ].map(([t, n]) => (
          <Link
            key={t}
            href={"/research/" + t}
            className="panel hover:border-primary/40"
          >
            <span className="eyebrow">Explore company evidence</span>
            <h2 className="mt-3">{t}</h2>
            <p className="muted mt-2">{n}</p>
            <p className="text-primary text-sm mt-4">Open Research →</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
