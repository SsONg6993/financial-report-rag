import { defineConfig } from "vitest/config";
export default defineConfig({
  test: {
    include: ["lib/**/*.test.ts", "features/**/*.test.ts"],
    environment: "node",
  },
});
