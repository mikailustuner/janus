// Records the demo patients' presence answers from the local API (medication-passport design
// §9, Req 12.2, DP26). Cologne's boxes are src/demo/passport-cologne.json; Istanbul's and Ohio's
// are their recorded fixture items. The queries follow src/passport/request.ts (a vitest check
// keeps both equal); the answers hold counts and codes only, nothing from a product name.
//   JANUS_API=http://127.0.0.1:8011 node scripts/record-passport.mjs
import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const dir = join(import.meta.dirname, "..", "src", "demo");
const api = (process.env.JANUS_API ?? "http://127.0.0.1:8000").replace(
  /\/$/,
  "",
);
const read = (f) => JSON.parse(readFileSync(join(dir, f), "utf8"));
const GROUPS = read("../passport/fixtures/schema-literals.json").form_group;

/** Fixture items as the fields the query needs: keys, strength codes, form group. */
function fromFixture(f) {
  return f.items.map((it) => {
    const c = it.resolution.candidates[0];
    if (c.kind === "ingredient")
      return {
        homeopathic: false,
        doseForm: null,
        ingredients: [{ key: c.ingredient_key.qid, strength: null }],
      };
    return {
      homeopathic: c.homeopathic,
      doseForm: GROUPS.includes(c.dose_form_group)
        ? { group: c.dose_form_group }
        : null,
      ingredients: c.ingredients.map((g) => ({
        key:
          g.status === "mapped"
            ? (g.ingredient_key?.qid ?? null)
            : (it.choices.find((ch) => ch.position === g.position)
                ?.ingredient ?? null),
        strength: g.strength_code ?? null,
      })),
    };
  });
}

function request(items) {
  const sendable = (i) =>
    !i.homeopathic &&
    i.ingredients.length > 0 &&
    i.ingredients.every((g) => g.key);
  const queries = new Map();
  for (const item of items.filter(sendable)) {
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
  return { items: [...queries.values()] };
}

const patients = {
  cologne: read("passport-cologne.json").items,
  istanbul: fromFixture(read("fixtures/istanbul.json")),
  ohio: fromFixture(read("fixtures/ohio.json")),
};
for (const [patient, items] of Object.entries(patients)) {
  const body = request(items);
  const res = await fetch(`${api}/passport/presence`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(20_000),
  });
  if (!res.ok) throw new Error(`${patient}: presence answered ${res.status}`);
  const response = await res.json();
  const out = {
    recorded: {
      date: new Date().toISOString().slice(0, 10),
      dataset_version: response.dataset_version,
      form_table_version: response.form_table_version,
    },
    request: body,
    response,
  };
  writeFileSync(
    join(dir, `passport-${patient}.recorded.json`),
    JSON.stringify(out, null, 1) + "\n",
  );
  console.log(
    `${patient}: ${response.items.length} items, dataset ${response.dataset_version.slice(0, 8)}`,
  );
}
