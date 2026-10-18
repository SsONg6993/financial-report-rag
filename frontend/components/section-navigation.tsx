import Link from "next/link";

type SectionItem = {
  href: string;
  label: string;
  description: string;
};

export function SectionNavigation({
  active,
  ariaLabel,
  items,
}: {
  active: string;
  ariaLabel: string;
  items: SectionItem[];
}) {
  return (
    <nav className="section-navigation" aria-label={ariaLabel}>
      {items.map((item) => (
        <Link
          key={item.href}
          href={item.href}
          aria-current={active === item.href ? "page" : undefined}
        >
          <span>{item.label}</span>
          <small>{item.description}</small>
        </Link>
      ))}
    </nav>
  );
}

export const exploreNavigation = [
  {
    href: "/explore",
    label: "Investors & disclosures",
    description: "Portfolios, overlap, and public filings",
  },
  {
    href: "/research",
    label: "Company research",
    description: "Financial evidence and thesis work",
  },
];

export const intelligenceNavigation = [
  {
    href: "/intelligence",
    label: "Intelligence feed",
    description: "Saved-entity public updates",
  },
  {
    href: "/market-pulse",
    label: "Market Pulse",
    description: "Source-backed market context",
  },
];
