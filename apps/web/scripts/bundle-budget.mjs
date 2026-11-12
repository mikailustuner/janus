/**
 * Bundle budget (experience design §16, Req 25.2): sums the gzip size of the JavaScript each route
 * loads before interaction (the script tags of its prerendered HTML) on the production build, and
 * the lazy parts (barcode reader, OCR, PDF) separately. Fails when a value is over its budget.
 *
 *   pnpm build && node apps/web/scripts/bundle-budget.mjs
 */
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { gzipSync } from "node:zlib";

const web = join(fileURLToPath(new URL(".", import.meta.url)), "..");
const next = join(web, ".next");
const KB = 1024;

// Budgets recorded in task 21 (design §16, DP38): measured on 2026-11-08 + 10 %. The design's
// first ceilings (190 KB per route, 110 KB for /o, 6 MB OCR) were set before measuring; the
// Next.js 16 / React 19 runtime alone is about 160 KB gzip, and tessdata_fast tur is 4.5 MB.
export const BUDGET = {
  route: 243 * KB, // first-load JS per route, gzip (measured max 220.3 KB, /en/note)
  doctor: 202 * KB, // the doctor page /o, gzip (measured 183.1 KB; form ready in 2.15 s, C5)
  zxing: 1042 * KB, // reader JS + wasm (measured 947 KB)
  tesseract: 9197 * KB, // worker + core + the largest language, tur (measured 8361 KB)
  pdf: 909 * KB, // PDF chunk + embedded fonts (measured 826 KB)
};

const gz = (file) => gzipSync(readFileSync(file)).length;
const html = (route) => {
  const p = join(next, "server/app", `${route}.html`);
  return existsSync(p) ? readFileSync(p, "utf8") : null;
};
const scripts = (doc) => [
  ...new Set(
    [...doc.matchAll(/<script[^>]+src="(\/_next\/static\/[^"]+\.js)"/g)].map(
      (m) => m[1],
    ),
  ),
];

const ROUTES = [
  "en",
  "en/scan",
  "en/confirm",
  "en/medicines",
  "en/timeline",
  "en/results",
  "en/results/finding",
  "en/memory",
  "en/note",
  "en/note/withdraw",
  "en/donate",
  "en/privacy",
  "en/settings",
  "en/demo",
  "en/research",
  "en/research/seance",
  "o",
];

const rows = [];
let failed = false;
for (const route of ROUTES) {
  const doc = html(route);
  if (!doc) {
    rows.push([route, "not prerendered"]);
    continue;
  }
  const size = scripts(doc).reduce(
    (sum, src) => sum + gz(join(next, src.replace("/_next/", ""))),
    0,
  );
  const limit = route === "o" ? BUDGET.doctor : BUDGET.route;
  if (size > limit) failed = true;
  rows.push([
    `/${route}`,
    `${(size / KB).toFixed(1)} KB`,
    size > limit ? `OVER ${(limit / KB).toFixed(0)} KB` : "ok",
  ]);
}

function chunksWith(marker) {
  const dir = join(next, "static/chunks");
  const out = [];
  const walk = (d) => {
    for (const f of readdirSync(d)) {
      const p = join(d, f);
      if (statSync(p).isDirectory()) walk(p);
      else if (f.endsWith(".js") && readFileSync(p, "utf8").includes(marker))
        out.push(p);
    }
  };
  walk(dir);
  return out;
}
const sum = (files, fn = gz) => files.reduce((s, f) => s + fn(f), 0);
const raw = (f) => statSync(f).size;

const vendor = join(web, "public/vendor");
const lazy = {
  zxing:
    sum(chunksWith("zxing_reader.wasm")) +
    raw(join(vendor, "zxing/zxing_reader.wasm")),
  tesseract:
    raw(join(vendor, "tesseract/worker.min.js")) +
    raw(join(vendor, "tesseract/core/tesseract-core-simd-lstm.wasm.js")) +
    Math.max(
      ...["eng", "tur", "deu", "fra", "spa", "por"].map((l) =>
        raw(join(vendor, `tesseract/lang/${l}.traineddata`)),
      ),
    ),
  pdf:
    sum(chunksWith("registerHyphenationCallback")) +
    sum(
      [
        "AtkinsonHyperlegibleNext-Regular",
        "AtkinsonHyperlegibleNext-Bold",
        "Fraunces-SemiBold",
        "IBMPlexMono-Regular",
        "NotoSans-Fallback",
      ].map((f) => join(web, "public/fonts", `${f}.ttf`)),
      raw,
    ),
};
for (const [k, v] of Object.entries(lazy)) {
  const over = v > BUDGET[k];
  if (over) failed = true;
  rows.push([
    `lazy: ${k}`,
    `${(v / KB).toFixed(0)} KB`,
    over ? `OVER ${(BUDGET[k] / KB).toFixed(0)} KB` : "ok",
  ]);
}

for (const r of rows) console.log(r.join("  "));
if (failed) {
  console.error("bundle budget exceeded");
  process.exit(1);
}
