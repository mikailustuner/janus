// Records the séance answers for demo mode and the tests from the real local API (séance design
// §7, experience Req 4.4): the catalogue and the two headline pairs (St John's wort / wound,
// vinegar / infection, design §4.5). The API must run with the Canon package, the FAERS counts
// and an integrity load that includes the séance papers. The answers hold no personal data.
//   JANUS_API=http://127.0.0.1:8012 node scripts/record-seance.mjs
import { writeFileSync } from "node:fs";
import { join } from "node:path";

const api = (process.env.JANUS_API ?? "http://127.0.0.1:8000").replace(
  /\/$/,
  "",
);
const PAIRS = [
  { substance: "st_johns_wort", condition: "wound" },
  { substance: "vinegar", condition: "infection" },
];

async function call(path, body) {
  const res = await fetch(`${api}${path}`, {
    method: body ? "POST" : "GET",
    headers: body ? { "content-type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
    signal: AbortSignal.timeout(15_000),
  });
  if (!res.ok) throw new Error(`${path}: HTTP ${res.status}`);
  return res.json();
}

const catalogue = await call("/seance/catalogue");
const pairs = [];
for (const p of PAIRS) {
  const answer = await call("/seance/pair", p);
  if (!answer.headline.eligible)
    throw new Error(`${p.substance}/${p.condition} is not headline-eligible`);
  pairs.push({ request: p, answer });
}
const out = {
  recorded: new Date().toISOString().slice(0, 10),
  catalogue,
  pairs,
};
writeFileSync(
  join(import.meta.dirname, "..", "src", "seance", "fixture.recorded.json"),
  JSON.stringify(out, null, 2) + "\n",
);
console.log(
  `recorded the catalogue (${catalogue.pairs.length} pairs) and ${pairs.length} answers`,
);
