import path from "node:path";

import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: {
    alias: { "@": path.resolve(import.meta.dirname, "src") },
  },
  test: {
    include: ["src/**/*.test.{ts,tsx}"],
    environment: "node",
    // Property tests over recorded fixtures run 300 cases in CI (FC_PROFILE=ci).
    testTimeout: 60_000,
    // `pnpm test:coverage` (CI): line floors for the core modules (docs/testing.md, "Coverage").
    // UI components are covered by the Playwright checks, not here.
    coverage: {
      provider: "v8",
      include: [
        "src/cascade-map/**/*.{ts,tsx}",
        "src/modelkit/**/*.{ts,tsx}",
        "src/note/**/*.{ts,tsx}",
      ],
      exclude: ["**/*.test.{ts,tsx}"],
      reporter: ["text-summary", "json-summary"],
      thresholds: {
        "src/cascade-map/**": { lines: 90 },
        "src/modelkit/**": { lines: 90 },
        "src/note/**": { lines: 90 },
      },
    },
  },
});
