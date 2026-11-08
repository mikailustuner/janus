/**
 * Records the demo fixtures from the real local API (experience design §13.3, DP11, DP32).
 *
 * Usage (local only, never in CI):
 *   JANUS_RECORD_API=http://127.0.0.1:8010 node apps/web/scripts/record-demo.mjs
 * The API must run with the real dataset, the rule base, the integrity load, the FAERS counts,
 * note keys and an outcome consent version set (see .env.example). Nothing is written to the API's
 * database except what `POST /notes/token` needs to issue a token; the token itself is not stored.
 *
 * Product text is TİTCK, openFDA, BDPM or CIMA text: every product text field is replaced by an
 * invented value from the table below before writing (structure.md: no TİTCK string is committed).
 * Candidate ids stay (opaque within one dataset version). No request value is printed.
 */
import { writeFileSync } from "node:fs";
import { join } from "node:path";
const API = process.env.JANUS_RECORD_API ?? "http://127.0.0.1:8010";
const OUT = join(import.meta.dirname, "../src/demo/fixtures");
const LANGUAGES = ["en", "tr", "de", "fr", "es"];
const OUTCOME_CONSENT_VERSION = "2026-11-v1";
const tr = (query, atc) => ({
  how: "tr_by_code",
  query,
  atc,
});
const PATIENTS = [
  {
    id: "istanbul",
    userRegion: "TR",
    noteLanguage: "tr",
    outcomeRegion: "TR",
    items: [
      {
        // The gate-1 combination box (apps/api/tests/test_cascades_real_artifacts.py).
        plan: { how: "scan", content: "08680199094206", region: "TR" },
        started: "2024-01",
        boxName: "Amlodis Plus 10/20 (demo)",
        invented: {
          product: "Amlodis Plus 10/20 tablet (demo)",
          generic: "amlodipine + lisinopril",
        },
      },
      item(tr("furosemide", "C03CA01"), "2024-06", "Furodem 40 (demo)"),
      item(tr("metformin", "A10BA02"), "2022-05", "Metfordem 1000 (demo)"),
      item(tr("atorvastatin", "C10AA05"), "2023-01", "Atordem 20 (demo)"),
      item(tr("paracetamol", "N02BE01"), "2023-05", "Parademol 500 (demo)"),
      item(tr("omeprazole", "A02BC01"), null, "Omedem 20 (demo)"),
      item(tr("sertraline", "N06AB06"), "2021-03", "Sertradem 50 (demo)"),
      item(tr("lactulose", "A06AD11"), "2024-03", "Laktudem syrup (demo)"),
      item(tr("alprazolam", "N05BA12"), null, "Alpradem 0.5 (demo)"),
    ],
  },
  {
    id: "cologne",
    userRegion: "EU",
    noteLanguage: "de",
    outcomeRegion: "EU",
    items: [
      item(tr("ramipril", "C09AA05"), "2024-02", "Ramidem 5 (demo)"),
      {
        plan: { how: "de_box", gtin: "4001234567891", query: "Ambroxol" },
        started: "2024-05",
        boxName: "Hustendem Saft (Demo)",
        invented: { product: "Hustendem Saft (Demo)", generic: null },
      },
      {
        plan: { how: "de_box", gtin: "4009876543211", query: "Ibuprofen" },
        started: "2025-01",
        boxName: "Ibudem 400 (Demo)",
        invented: { product: "Ibudem 400 (Demo)", generic: null },
      },
      item(tr("pantoprazole", "A02BC02"), "2025-03", "Pantodem 40 (demo)"),
    ],
  },
  {
    id: "ohio",
    userRegion: "US",
    noteLanguage: "en",
    outcomeRegion: "US",
    items: [
      item(
        { how: "us_by_ndc", query: "donepezil" },
        "2024-04",
        "Donedem 10 mg vial (demo)",
      ),
      item(
        { how: "us_by_ndc", query: "oxybutynin" },
        "2024-09",
        "Oxydem 5 mg vial (demo)",
      ),
      item(
        { how: "us_by_ndc", query: "gabapentin" },
        "2025-02",
        "Gabadem 300 mg vial (demo)",
      ),
      item(
        { how: "us_by_ndc", query: "furosemide" },
        "2025-06",
        "Furodem US 20 mg vial (demo)",
      ),
    ],
  },
];
function item(plan, started, boxName) {
  const generic = "query" in plan ? plan.query : null;
  return { plan, started, boxName, invented: { product: boxName, generic } };
}
async function post(path, body) {
  const res = await fetch(API + path, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(60_000),
  });
  return { status: res.status, json: await res.json() };
}
async function ok(path, body) {
  const { status, json } = await post(path, body);
  if (status !== 200 && status !== 201)
    throw new Error(`${path}: ${status} ${String(json.error)}`);
  return json;
}
async function get(path) {
  const res = await fetch(API + path, { signal: AbortSignal.timeout(30_000) });
  if (!res.ok) throw new Error(`${path}: ${res.status}`);
  return await res.json();
}
/** Resolves one item; returns the recorded resolution and the chosen candidate index. */
async function resolve(plan) {
  switch (plan.how) {
    case "scan": {
      const resolution = await ok("/resolve/scan", {
        content: plan.content,
        region: plan.region,
      });
      return { resolution, pick: 0, route: "scan" };
    }
    case "tr_by_code": {
      const search = await ok("/resolve/search", {
        query: plan.query,
        region: "TR",
      });
      const ids = new Set();
      for (const c of search.candidates)
        for (const a of c.atc_codes ?? [])
          if (a.code === plan.atc && typeof a.product === "string")
            ids.add(a.product);
      if (ids.size === 0) throw new Error(`no TR product for ${plan.atc}`);
      const resolution = await ok("/resolve/products", {
        candidate_ids: [...ids],
      });
      const pick = resolution.candidates.findIndex(
        (c) =>
          c.kind === "product" &&
          c.published_atc === plan.atc &&
          c.ingredients?.length === 1 &&
          c.ingredients[0]?.status === "mapped",
      );
      if (pick < 0)
        throw new Error(`no single-ingredient TR product for ${plan.atc}`);
      return { resolution, pick, route: "products" };
    }
    case "us_by_ndc": {
      const search = await ok("/resolve/search", {
        query: plan.query,
        region: "US",
        limit: 10,
      });
      const product = search.candidates.find(
        (c) =>
          c.kind === "product" &&
          !c.homeopathic &&
          !c.name_only &&
          c.ingredients?.length === 1 &&
          c.packages.length > 0,
      );
      if (!product) throw new Error(`no US product for the query`);
      const ndc = product.packages[0].ndc_published;
      const resolution = await ok("/resolve/ndc", { ndc });
      const pick = resolution.candidates.findIndex(
        (c) => c.candidate_id === product.candidate_id,
      );
      return { resolution, pick: Math.max(pick, 0), route: "ndc" };
    }
    case "de_box": {
      const scan = await ok("/resolve/scan", { content: plan.gtin });
      const notice = scan.notices.find(
        (n) => n.code === "no_open_product_database",
      );
      if (!notice)
        throw new Error("expected no_open_product_database for a DE box");
      const resolution = await ok("/resolve/search", {
        query: plan.query,
        region: "EU",
      });
      const pick = resolution.candidates.findIndex(
        (c) => c.kind === "ingredient",
      );
      if (pick < 0) throw new Error("no ingredient candidate");
      return { resolution, pick, route: "search", scan };
    }
  }
}
/** Replaces every product text field with the invented value (§13.3). */
function scrub(resolution, pick, invented) {
  const scrubCandidate = (c) => {
    if (c.kind !== "product") return c;
    return {
      ...c,
      product_name: invented.product,
      brand_name: invented.product,
      generic_name: invented.generic,
      ingredient_text: invented.generic,
      dosage_form: null,
      product_type: null,
      routes: [],
      status_published: [],
      packages: c.packages.map((_, i) => ({
        ndc_published: `0295-268${i}-01`,
        ndc11: `02952680${i}01`.padEnd(11, "0").slice(0, 11),
      })),
      ingredients: (c.ingredients ?? []).map((ing) => ({
        ...ing,
        published_name: ing.ingredient_key?.label_en ?? "ingredient",
        strength: null,
      })),
    };
  };
  // Demo items are confirmed already: only the chosen candidate is kept (design §13.3).
  const out = {
    ...resolution,
    candidates: [scrubCandidate(resolution.candidates[pick])],
  };
  if (out.scan) out.scan = { ...out.scan, gtin: "00000000000000" };
  return out;
}
function demoGtin13(n) {
  const body = "295268" + String(n).padStart(6, "0");
  let sum = 0;
  for (let i = 0; i < 12; i++) sum += Number(body[i]) * (i % 2 === 0 ? 1 : 3);
  return body + String((10 - (sum % 10)) % 10);
}
function parseLocator(locator) {
  return Object.fromEntries(
    locator
      .replace(/^faers:/, "")
      .split(";")
      .map((p) => p.split("=")),
  );
}
async function record(patient, codeOffset) {
  const items = [];
  const evalItems = [];
  let dataset = null;
  for (const [i, it] of patient.items.entries()) {
    const { resolution, pick, route, scan } = await resolve(it.plan);
    if (dataset && resolution.dataset_version !== dataset)
      throw new Error("dataset changed");
    dataset = resolution.dataset_version;
    const cand = resolution.candidates[pick];
    const evalItem =
      cand.kind === "product"
        ? { product: cand.candidate_id }
        : { ingredient: cand.ingredient_key.qid };
    if (it.started) evalItem.started = it.started;
    evalItems.push(evalItem);
    const demoCode = demoGtin13(codeOffset + i + 1);
    const sourceKey =
      it.plan.how === "us_by_ndc"
        ? { kind: "ndc", ndc: `0295-268${i}-01` }
        : it.plan.how === "de_box"
          ? {
              kind: "search",
              query: it.plan.query,
              region: "EU",
              pick: { kind: "ingredient", qid: cand.ingredient_key.qid },
            }
          : { kind: "scan", content: `(01)0${demoCode}` };
    items.push({
      demoCode,
      route,
      sourceKey,
      boxName: it.boxName,
      started: it.started,
      choices: [],
      resolution: scrub(resolution, pick, it.invented),
      // The DE box scan that led to name search (no candidates; the GTIN is not kept).
      scanResolution: scan
        ? { ...scan, scan: { ...scan.scan, gtin: "04000000000000" } }
        : null,
    });
  }
  const evaluateIn = { dataset_version: dataset, items: evalItems };
  const evaluation = await ok("/cascades/evaluate", evaluateIn);
  const findings = evaluation.findings;
  const evidence = {};
  for (const f of findings) {
    const ids = [
      ...new Set([...f.evidence_ids, ...f.excluded_evidence.map((e) => e.id)]),
    ];
    evidence[f.finding_id] = await ok("/evidence/resolve", {
      evidence_ids: ids,
    });
  }
  const snapshot = await get("/memory/snapshot");
  const pairs = {};
  for (const f of findings) {
    const loc = f.faers_locator;
    if (!loc || pairs[loc]) continue;
    const p = parseLocator(loc);
    pairs[loc] = await ok("/memory/pair", {
      ingredient: p.ingredient,
      event: { key: p.event },
      region: p.region ?? "ALL",
      scope: p.scope ?? "suspect",
    });
  }
  const keys = [
    ...new Set(
      items.flatMap((it) => {
        const res = it.resolution;
        const c = res.candidates[0];
        if (c.kind === "ingredient") return [c.ingredient_key.qid];
        return (c.ingredients ?? [])
          .filter((g) => g.status === "mapped" && g.ingredient_key)
          .map((g) => g.ingredient_key.qid);
      }),
    ),
  ].sort();
  const combination = await ok("/memory/combination", {
    ingredients: keys.slice(0, 20),
  });
  const regions = await ok("/memory/regions", {
    ingredients: keys.slice(0, 20),
  });
  const events = [
    ...new Set(
      findings
        .map((f) => f.faers_locator)
        .filter((l) => !!l)
        .map((l) => parseLocator(l).event),
    ),
  ];
  const shared = {};
  for (const event of events) {
    for (const layer of ["contributions", "outcomes"]) {
      const { status, json } = await post("/memory/shared", {
        layer,
        ingredients: keys.slice(0, 20),
        event,
        direction: "adverse",
      });
      shared[`${layer}:${event}`] =
        status === 200 ? json : { error_status: status, ...json };
    }
  }
  const pins = {
    rule_base_version: evaluation.rule_base_version,
    integrity_version: evaluation.integrity_version,
    counts_build_id: snapshot.build_id,
  };
  const notes = {};
  for (const lang of LANGUAGES) {
    notes[lang] = await ok("/notes/document", {
      evaluation: evaluateIn,
      pins,
      languages: [lang],
      region: patient.userRegion,
    });
  }
  let doctorForm = null;
  if (findings.length > 0) {
    const token = await ok("/notes/token", {
      note: {
        evaluation: evaluateIn,
        pins,
        languages: [patient.noteLanguage],
        region: patient.userRegion,
      },
      consent_version: OUTCOME_CONSENT_VERSION,
      outcome_region: patient.outcomeRegion,
    });
    doctorForm = await ok("/outcomes/form", { token: token.token });
    // The token and qr_url are dropped here and never written (§13.3).
  }
  const versions = notes.en.versions;
  return {
    patient: patient.id,
    userRegion: patient.userRegion,
    noteLanguage: patient.noteLanguage,
    recorded: {
      date: new Date().toISOString().slice(0, 10),
      dataset_version: dataset,
      rule_base_version: evaluation.rule_base_version,
      integrity_version: evaluation.integrity_version,
      counts_build_id: snapshot.build_id,
      glossary_version: versions.glossary_version,
    },
    items,
    evaluation,
    evidence,
    memory: { snapshot, pairs, combination, regions, shared },
    notes,
    doctorForm,
  };
}
let offset = 0;
for (const patient of PATIENTS) {
  const fixture = await record(patient, offset);
  offset += 10;
  writeFileSync(
    join(OUT, `${patient.id}.json`),
    JSON.stringify(fixture, null, 1) + "\n",
  );
  const ev = fixture.evaluation;
  const summary = ev.findings.map(
    (f) =>
      `${f.rule_id} ${f.status} ${f.timing} months=${f.months_between} form_confirmed=${f.form_confirmed}`,
  );
  // Counts and rule ids only (no product text, no request values).
  console.log(
    `${patient.id}: ${summary.length} findings [${summary.join("; ")}], ${ev.item_warnings.length} warnings, rules ${ev.rules.checked}/${ev.rules.total}`,
  );
}
