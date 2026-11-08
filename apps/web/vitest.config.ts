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
  },
});
