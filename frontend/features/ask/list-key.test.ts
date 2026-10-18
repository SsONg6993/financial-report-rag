import { describe, expect, it } from "vitest";
import { staticListKey } from "./list-key";

describe("staticListKey", () => {
  it("keeps duplicate disclosure descriptions as distinct rendered items", () => {
    const description =
      "Berkshire Hathaway · Unknown · LENNAR CORP: increased reported shares";
    const keys = [description, description].map((item, index) =>
      staticListKey("accumulation", item, index),
    );

    expect(new Set(keys).size).toBe(2);
    expect(keys).toEqual([
      staticListKey("accumulation", description, 0),
      staticListKey("accumulation", description, 1),
    ]);
  });
});
