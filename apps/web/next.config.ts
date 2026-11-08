import path from "node:path";

import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

// Monorepo root, so standalone output traces workspace dependencies correctly.
const workspaceRoot = path.resolve(process.cwd(), "../..");

// Same-origin API (experience DP15): the browser only ever talks to its own origin under /api.
// A build argument of the web image; the default is the local API.
const apiOrigin = (
  process.env.JANUS_API_ORIGIN || "http://127.0.0.1:8000"
).replace(/\/$/, "");

const dev = process.env.NODE_ENV === "development";

// A build version for the service worker's cache name (DP22).
const build =
  process.env.JANUS_BUILD_ID ||
  new Date().toISOString().replace(/\D/g, "").slice(0, 14);

// DP31: connect, image, font and worker sources limited to the own origin. Inline scripts are
// needed by the App Router payload on static pages; wasm for the barcode reader. React needs
// eval only in development (debugging call stacks).
const csp = [
  "default-src 'self'",
  "connect-src 'self'",
  "img-src 'self' data: blob:",
  "worker-src 'self' blob:",
  `script-src 'self' 'unsafe-inline' 'wasm-unsafe-eval'${dev ? " 'unsafe-eval'" : ""}`,
  "style-src 'self' 'unsafe-inline'",
  "font-src 'self'",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
].join("; ");

const securityHeaders = [
  { key: "Content-Security-Policy", value: csp },
  { key: "Referrer-Policy", value: "no-referrer" },
  {
    key: "Permissions-Policy",
    value: "camera=(self), microphone=(), geolocation=()",
  },
  { key: "X-Content-Type-Options", value: "nosniff" },
];

const nextConfig: NextConfig = {
  output: "standalone",
  outputFileTracingRoot: workspaceRoot,
  poweredByHeader: false,
  agentRules: false,
  env: { NEXT_PUBLIC_JANUS_BUILD: build },
  devIndicators: false,
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    root: workspaceRoot,
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${apiOrigin}/:path*` }];
  },
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

const withNextIntl = createNextIntlPlugin();

export default withNextIntl(nextConfig);
