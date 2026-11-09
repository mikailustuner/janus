// Records the two open research datasets for demo mode and the tests from the real local API
// (data-quality design §9, faers-onset-table design §7): the data-quality report (JSON, CSV,
// Markdown) and the FAERS onset table (JSON, CSV). The API must run with both builds under
// $JANUS_DATA_DIR (quality/current, onset_table/current). Both hold codes and counts only: no
// TİTCK row, product name or barcode, no personal data.
//   JANUS_API=http://127.0.0.1:8012 node scripts/record-research.mjs
import { writeFileSync } from "node:fs";
import { join } from "node:path";

const api = (process.env.JANUS_API ?? "http://127.0.0.1:8000").replace(
  /\/$/,
  "",
);
async function get(path) {
  const res = await fetch(`${api}${path}`, {
    signal: AbortSignal.timeout(15_000),
  });
  if (!res.ok) throw new Error(`${path}: HTTP ${res.status}`);
  return res;
}
const recorded = new Date().toISOString().slice(0, 10);
const out = (name, value) =>
  writeFileSync(
    join(import.meta.dirname, "../src/research", name),
    JSON.stringify({ recorded, ...value }, null, 1) + "\n",
  );

const report = await (await get("/open/data-quality")).json();
out("data-quality.recorded.json", {
  report,
  csv: await (await get("/open/data-quality.csv")).text(),
  md: await (await get("/open/data-quality.md")).text(),
});
const table = await (await get("/open/faers-onset")).json();
out("faers-onset.recorded.json", {
  table,
  csv: await (await get("/open/faers-onset.csv")).text(),
});
console.log(
  `recorded ${report.findings.length} findings, ${table.rows.length} onset rows`,
);
