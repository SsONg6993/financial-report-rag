export type VisualAsset = {
  src: string;
  source: string;
  creator: string;
  license: string;
  alt: string;
};

const commons = (file: string) =>
  `https://commons.wikimedia.org/wiki/Special:Redirect/file/${encodeURIComponent(file)}`;

export const investorVisuals: Record<string, VisualAsset> = {
  berkshire: {
    src: commons("Warren Buffett in 2010 (cropped).jpg"),
    source:
      "https://commons.wikimedia.org/wiki/File:Warren_Buffett_in_2010_(cropped).jpg",
    creator: "United States federal government",
    license: "Public domain (U.S. federal government work)",
    alt: "Warren Buffett",
  },
  ark: {
    src: commons("Cathie Wood.jpg"),
    source: "https://commons.wikimedia.org/wiki/File:Cathie_Wood.jpg",
    creator: "Steve Jurvetson",
    license: "CC BY 2.0",
    alt: "Cathie Wood",
  },
  pershing: {
    src: commons("Bill Ackman (26410186110) (cropped).jpg"),
    source:
      "https://commons.wikimedia.org/wiki/File:Bill_Ackman_(26410186110)_(cropped).jpg",
    creator: "Senate Democrats",
    license: "CC BY 2.0",
    alt: "Bill Ackman",
  },
};

export const companyVisuals: Record<string, VisualAsset> = {
  AAPL: {
    src: commons("Apple Logo.svg"),
    source: "https://commons.wikimedia.org/wiki/File:Apple_Logo.svg",
    creator: "Apple Inc.",
    license: "Public domain; trademarked",
    alt: "Apple logo",
  },
  META: {
    src: commons("Meta Platforms Inc. logo.svg"),
    source:
      "https://commons.wikimedia.org/wiki/File:Meta_Platforms_Inc._logo.svg",
    creator: "Meta Platforms",
    license: "Public domain simple logo; trademarked",
    alt: "Meta logo",
  },
  GOOGL: {
    src: commons("Google 2015 logo.svg"),
    source: "https://commons.wikimedia.org/wiki/File:Google_2015_logo.svg",
    creator: "Google LLC",
    license: "Public domain simple logo; trademarked",
    alt: "Google logo",
  },
  GOOG: {
    src: commons("Google 2015 logo.svg"),
    source: "https://commons.wikimedia.org/wiki/File:Google_2015_logo.svg",
    creator: "Google LLC",
    license: "Public domain simple logo; trademarked",
    alt: "Google logo",
  },
  KO: {
    src: commons("Coca-Cola logo.svg"),
    source: "https://commons.wikimedia.org/wiki/File:Coca-Cola_logo.svg",
    creator: "The Coca-Cola Company",
    license: "Public domain; trademarked",
    alt: "Coca-Cola logo",
  },
  MSFT: {
    src: commons("Microsoft logo.svg"),
    source: "https://commons.wikimedia.org/wiki/File:Microsoft_logo.svg",
    creator: "Microsoft Corporation",
    license: "Public domain simple logo; trademarked",
    alt: "Microsoft logo",
  },
  NVDA: {
    src: commons("NVIDIA logo.svg"),
    source: "https://commons.wikimedia.org/wiki/File:NVIDIA_logo.svg",
    creator: "NVIDIA Corporation",
    license: "Apache License 2.0; trademarked",
    alt: "NVIDIA logo",
  },
  TSLA: {
    src: commons("Tesla Motors.svg"),
    source: "https://commons.wikimedia.org/wiki/File:Tesla_Motors.svg",
    creator: "Tesla, Inc.",
    license: "Public domain simple logo; trademarked",
    alt: "Tesla logo",
  },
};

export function visualForEntity(
  kind: "investor" | "company",
  id: string,
): VisualAsset | undefined {
  return kind === "investor"
    ? investorVisuals[id.toLowerCase()]
    : companyVisuals[id.toUpperCase()];
}

export function entityInitials(value: string): string {
  const parts = value.split(/[\s—-]+/).filter(Boolean);
  if (parts.length === 1) return parts[0].slice(0, 3).toUpperCase();
  return parts
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
}
