import { expect, it } from "vitest";
import { homeSchema, investorSchema, companySchema } from "./api";
const live = process.env.LIVE_API === "true";
for (const [path, schema] of [
  ["/home/feed", homeSchema],
  ["/investors/berkshire", investorSchema],
  ["/company/AAPL", companySchema],
  ["/company/NVDA", companySchema],
] as const) {
  it.skipIf(!live)(`validates real cached API response ${path}`, async () => {
    const r = await fetch("http://127.0.0.1:8000/api" + path);
    expect(r.ok).toBe(true);
    const result = schema.safeParse(await r.json());
    expect(result.error?.issues).toBeUndefined();
  });
}
