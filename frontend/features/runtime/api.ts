import { z } from "zod";

export const runtimeStatusSchema = z.object({
  status: z.enum(["ready", "degraded"]),
  service: z.string(),
  api_version: z.string(),
  build_commit: z.string(),
  checked_at: z.string(),
  backend: z.object({ status: z.string() }),
  database: z.object({ status: z.string(), accessible: z.boolean() }),
  cache: z.object({ status: z.string(), accessible: z.boolean() }),
  market_pulse: z.object({ status: z.string(), detail: z.string() }),
  ollama: z.object({
    status: z.string(),
    model: z.string(),
    model_available: z.boolean(),
    detail: z.string(),
  }),
});
