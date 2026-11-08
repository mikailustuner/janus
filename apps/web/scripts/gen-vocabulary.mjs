/**
 * Generates the client's clinical vocabulary from the API's reviewed files (experience design
 * §8.3, DP17): cascade names, Janus event labels and safety-line keys, reviewed ingredient names
 * and the note's name tags, in five languages. Only `accepted` glossary rows and `active` event
 * rows are used. A vitest parity test regenerates in memory and compares with the committed
 * files (P13).
 *
 *   node apps/web/scripts/gen-vocabulary.mjs          write src/vocabulary/*.json
 */
import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

export const LOCALES = ["en", "tr", "de", "fr", "es"];
const SENTENCE_IDS = [
  "abrupt_stop",
  "name.not_translated",
  "name.not_reviewed",
  "name.combination_code",
  "not_checked.homeopathic_product",
  "not_checked.ambiguous",
  "not_checked.no_ingredient_key",
  "not_checked.possible_unsplit_combination",
  "not_checked.no_ingredient_atc",
  "not_checked.no_ingredient_atc_for_route",
];

/** RFC 4180 CSV: quoted fields, doubled quotes, CRLF or LF. */
export function parseCsv(text) {
  const rows = [];
  let row = [];
  let field = "";
  let quoted = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (quoted) {
      if (c === '"' && text[i + 1] === '"') {
        field += '"';
        i++;
      } else if (c === '"') quoted = false;
      else field += c;
    } else if (c === '"') quoted = true;
    else if (c === ",") {
      row.push(field);
      field = "";
    } else if (c === "\n" || c === "\r") {
      if (c === "\r" && text[i + 1] === "\n") i++;
      row.push(field);
      rows.push(row);
      row = [];
      field = "";
    } else field += c;
  }
  if (field !== "" || row.length > 0) {
    row.push(field);
    rows.push(row);
  }
  const [header, ...body] = rows.filter((r) => r.some((f) => f !== ""));
  return body.map((r) =>
    Object.fromEntries(header.map((h, i) => [h, r[i] ?? ""])),
  );
}

const sha256 = (text) => createHash("sha256").update(text).digest("hex");

/** Returns `{ "<file>.json": object }` for src/vocabulary. */
export function generate(repoRoot) {
  const read = (p) => readFileSync(join(repoRoot, p), "utf8");
  const files = {
    ingredients: "apps/api/janus/notes/glossary/ingredients.csv",
    cascades: "apps/api/janus/notes/glossary/cascades.csv",
    sentences: "apps/api/janus/notes/glossary/sentences.csv",
    events: "apps/api/janus/memory/memory_events.csv",
    pipc: "data/pipc.csv",
  };
  const text = Object.fromEntries(
    Object.entries(files).map(([k, p]) => [k, read(p)]),
  );
  const ingredients = parseCsv(text.ingredients).filter(
    (r) => r.status === "accepted",
  );
  const cascades = new Map(
    parseCsv(text.cascades)
      .filter((r) => r.status === "accepted")
      .map((r) => [r.position, r]),
  );
  const sentences = new Map(
    parseCsv(text.sentences)
      .filter((r) => r.status === "accepted")
      .map((r) => [r.id, r]),
  );
  const events = parseCsv(text.events).filter((r) => r.status === "active");
  const pipc = parseCsv(text.pipc);

  const out = {};
  for (const lang of LOCALES) {
    const vocab = { events: {}, cascades: {}, ingredients: {}, sentences: {} };
    for (const e of events) {
      vocab.events[e.key] = {
        label: e[`label_${lang}`] || e.label_en,
        safety_line: e.safety_line || null,
        direction: e.direction,
        pipc_positions: e.pipc_positions
          ? e.pipc_positions.split(";").filter(Boolean).map(Number)
          : [],
      };
    }
    for (const row of pipc) {
      const accepted = cascades.get(row.position);
      vocab.cascades[row.position] =
        lang === "en" || !accepted
          ? {
              drug_a: row.drug_a,
              adverse_event: row.adverse_event,
              drug_b: row.drug_b,
              translated: lang === "en",
            }
          : {
              drug_a: accepted[`drug_a_${lang}`],
              adverse_event: accepted[`adverse_event_${lang}`],
              drug_b: accepted[`drug_b_${lang}`],
              translated: true,
            };
    }
    for (const r of ingredients) {
      if (!r[lang]) continue;
      vocab.ingredients[r.key] =
        lang === "en" && r.en_alt ? `${r.en} (${r.en_alt})` : r[lang];
    }
    for (const id of SENTENCE_IDS) {
      const s = sentences.get(id);
      if (!s || !s[lang])
        throw new Error(`sentence ${id} has no accepted ${lang} text`);
      vocab.sentences[id] = s[lang];
    }
    out[`${lang}.json`] = vocab;
  }
  out["index.json"] = {
    sources: Object.fromEntries(
      Object.entries(files).map(([k, p]) => [p, sha256(text[k])]),
    ),
    english_names: Object.fromEntries(ingredients.map((r) => [r.key, r.en])),
  };
  return out;
}

export function serialise(value) {
  return JSON.stringify(value, null, 1) + "\n";
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const here = fileURLToPath(new URL(".", import.meta.url));
  const repoRoot = join(here, "../../..");
  const outDir = join(here, "../src/vocabulary");
  for (const [name, value] of Object.entries(generate(repoRoot)))
    writeFileSync(join(outDir, name), serialise(value));
  console.log("vocabulary written");
}
