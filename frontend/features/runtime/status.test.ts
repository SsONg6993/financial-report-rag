import { describe, expect, it } from "vitest";
import { runtimeStatusSchema } from "./api";

describe("runtime status contract", () => {
  it("distinguishes optional dependency states", () => {
    const parsed = runtimeStatusSchema.parse({
      status: "ready",
      service: "ThesisLens Backend",
      api_version: "0.1.0",
      build_commit: "abc123",
      checked_at: "2026-10-10T00:00:00Z",
      backend: { status: "ready" },
      database: { status: "ready", accessible: true },
      cache: { status: "ready", accessible: true },
      market_pulse: { status: "stale_cache", detail: "Using cached events." },
      ollama: {
        status: "model_missing",
        model: "qwen3:4b",
        model_available: false,
        detail: "Model is not installed.",
      },
    });
    expect(parsed.market_pulse.status).toBe("stale_cache");
    expect(parsed.ollama.status).toBe("model_missing");
  });
});
