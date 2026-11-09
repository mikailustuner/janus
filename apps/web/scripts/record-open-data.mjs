// Records the open outcome dataset for demo mode and the tests from the real local API
// (open-data design §4). The API must run with the database and a noise key. Released cells are
// public aggregates (k = 20, noise, sibling rule); today there are none.
//   JANUS_API=http://127.0.0.1:8012 node scripts/record-open-data.mjs
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
const outcomes = await (await get("/open/outcomes")).json();
const csv = await (await get("/open/outcomes.csv")).text();
writeFileSync(
  join(import.meta.dirname, "../src/open/fixture.recorded.json"),
  JSON.stringify(
    { recorded: new Date().toISOString().slice(0, 10), outcomes, csv },
    null,
    1,
  ) + "\n",
);
console.log(`recorded ${outcomes.cells.length} released cells`);
