import type { PortfolioOverlap } from "@/lib/api";

export interface Point {
  x: number;
  y: number;
}

export function networkLayout(data: PortfolioOverlap): {
  institutions: Map<string, Point>;
  securities: Map<string, Point>;
} {
  const institutions = new Map<string, Point>();
  const securities = new Map<string, Point>();
  const institutionStep = 460 / Math.max(data.institutions.length - 1, 1);
  data.institutions.forEach((institution, index) => {
    institutions.set(institution.id, {
      x: 105,
      y: data.institutions.length === 1 ? 280 : 50 + index * institutionStep,
    });
  });
  const columns =
    data.network.securities.length > 26
      ? 3
      : data.network.securities.length > 12
        ? 2
        : 1;
  const rows = Math.ceil(data.network.securities.length / columns);
  data.network.securities.forEach((security, index) => {
    const column = Math.floor(index / rows);
    const row = index % rows;
    securities.set(security.id, {
      x: 480 + column * 200,
      y: rows === 1 ? 280 : 42 + row * (476 / Math.max(rows - 1, 1)),
    });
  });
  return { institutions, securities };
}

export function nextPlaybackPeriod(
  periods: string[],
  current: string | null,
): string | null {
  if (!periods.length) return null;
  const chronological = [...periods].reverse();
  const index = current ? chronological.indexOf(current) : -1;
  return chronological[(index + 1) % chronological.length];
}
