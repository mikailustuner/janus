// Records the Cologne demo list's product lists from the local API (medication-passport design
// §15, DP33): for every box that can be checked and every listable source, the first rows of
// `POST /passport/products`. The queries follow src/passport/products.ts (a vitest check keeps
// both equal). Names come from the open-licence sources only (BDPM, AEMPS Nomenclátor, openFDA
// NDC), exactly as published; each answer carries its source and data date.
//   JANUS_API=http://127.0.0.1:8011 node scripts/record-passport-products.mjs
import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const dir = join(import.meta.dirname, "..", "src", "demo");
const api = (process.env.JANUS_API ?? "http://127.0.0.1:8000").replace(
  /\/$/,
  "",
);
const read = (f) => JSON.parse(readFileSync(join(dir, f), "utf8"));
const TARGETS = read(
  "../passport/fixtures/schema-literals.json",
).listable_source_id;
const ROWS = 8;

const sendable = (i) =>
  !i.homeopathic &&
  i.ingredients.length > 0 &&
  i.ingredients.every((g) => g.key);
const queries = new Map();
for (const item of read("passport-cologne.json").items.filter(sendable)) {
  const keys = [...new Set(item.ingredients.map((g) => g.key))].sort();
  const ingredients = keys.map((key) => {
    const lines = item.ingredients.filter((g) => g.key === key);
    const s = lines.length === 1 ? lines[0].strength : null;
    return s ? { key, strength: s } : { key };
  });
  const q = item.doseForm
    ? { ingredients, dose_form: item.doseForm.group }
    : { ingredients };
  queries.set(JSON.stringify(q), q);
}

const answers = [];
let dataset = null;
for (const q of queries.values())
  for (const target of TARGETS) {
    const request = { ...q, target, offset: 0, limit: ROWS };
    const res = await fetch(`${api}/passport/products`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(request),
      signal: AbortSignal.timeout(20_000),
    });
    if (!res.ok) throw new Error(`${target}: products answered ${res.status}`);
    const response = await res.json();
    dataset ??= response.dataset_version;
    if (response.dataset_version !== dataset)
      throw new Error("the dataset changed while recording");
    answers.push({ request, response });
  }
const out = {
  recorded: {
    date: new Date().toISOString().slice(0, 10),
    dataset_version: dataset,
  },
  answers,
};
writeFileSync(
  join(dir, "passport-products.recorded.json"),
  JSON.stringify(out, null, 1) + "\n",
);
console.log(`recorded ${answers.length} answers`);
