import { describe, expect, it } from "vitest";
import {
  companyVisuals,
  entityInitials,
  investorVisuals,
  visualForEntity,
} from "./visual-assets";

describe("verified visual assets", () => {
  it("resolves assets case-insensitively and preserves explicit fallbacks", () => {
    expect(visualForEntity("investor", "BERKSHIRE")).toBe(
      investorVisuals.berkshire,
    );
    expect(visualForEntity("company", "aapl")).toBe(companyVisuals.AAPL);
    expect(visualForEntity("investor", "unverified-manager")).toBeUndefined();
  });

  it("creates readable monograms when no verified image exists", () => {
    expect(entityInitials("David Tepper")).toBe("DT");
    expect(entityInitials("RKLB")).toBe("RKL");
  });

  it("keeps a source, creator, and license for every remote asset", () => {
    for (const asset of [
      ...Object.values(investorVisuals),
      ...Object.values(companyVisuals),
    ]) {
      expect(asset.source).toMatch(/^https:\/\/commons\.wikimedia\.org/);
      expect(asset.creator).not.toBe("");
      expect(asset.license).not.toBe("");
    }
  });
});
