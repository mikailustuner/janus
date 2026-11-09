// Records the time-machine answers for demo mode and the tests from the real local API
// (time-machine design §10; experience Req 30): the catalogue, every substance and every cascade.
// The API must run with the time-machine artifact under $JANUS_DATA_DIR/timemachine. The answers
// hold no personal data. Also writes `src/timemachine/index.json`: the substance ids, and per
// cascade its PIPC row and the ingredient keys of its index drugs (from
// data/time_machine/cascades.csv, matched to the vocabulary by English name), used by the links
// and the patient gate without a request.
//   JANUS_API=http://127.0.0.1:8012 node scripts/record-timemachine.mjs
import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";

import { parseCsv } from "../src/report/csv.mjs";

const api = (process.env.JANUS_API ?? "http://127.0.0.1:8000").replace(
  /\/$/,
  "",
);
const root = join(import.meta.dirname, "..");

async function get(path) {
  const res = await fetch(`${api}${path}`, {
    signal: AbortSignal.timeout(15_000),
  });
  if (!res.ok) throw new Error(`${path}: HTTP ${res.status}`);
  return res.json();
}

const catalogue = await get("/timemachine/catalogue");
const substances = {};
for (const id of catalogue.substance_ids)
  substances[id] = await get(`/timemachine/substance/${id}`);
const cascades = {};
for (const id of catalogue.cascade_ids)
  cascades[id] = await get(`/timemachine/cascade/${id}`);

const vocab = JSON.parse(
  readFileSync(join(root, "src/vocabulary/en.json"), "utf8"),
);
const byName = new Map(
  Object.entries(vocab.ingredients).map(([k, v]) => [
    String(v).toLowerCase(),
    k,
  ]),
);
const [head, ...body] = parseCsv(
  readFileSync(join(root, "../../data/time_machine/cascades.csv"), "utf8"),
);
const rows = body
  .filter((r) => r.length === head.length)
  .map((r) => Object.fromEntries(head.map((h, i) => [h, r[i]])));
const index = {
  built_at: catalogue.meta.built_at,
  substances: catalogue.substance_ids,
  cascades: catalogue.cascade_ids.map((id) => {
    const row = rows.find((r) => r.cascade_id === id);
    if (!row) throw new Error(`${id}: not in cascades.csv`);
    const keys = row.index_ingredients.split("|").map((n) => {
      const k = byName.get(n.toLowerCase());
      if (!k)
        throw new Error(`${id}: no vocabulary key for an index ingredient`);
      return k;
    });
    return {
      id,
      pipc_position: cascades[id].cascade.pipc_position,
      index_keys: keys,
    };
  }),
};

const recorded = new Date().toISOString().slice(0, 10);
writeFileSync(
  join(root, "src/timemachine/fixture.recorded.json"),
  JSON.stringify({ recorded, catalogue, substances, cascades }, null, 1) + "\n",
);
writeFileSync(
  join(root, "src/timemachine/index.json"),
  JSON.stringify(index, null, 2) + "\n",
);
console.log(
  `recorded ${catalogue.substance_ids.length} substances, ${catalogue.cascade_ids.length} cascades`,
);
