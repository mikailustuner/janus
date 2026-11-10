/**
 * Synthetic label images for the label-recognition evaluation (ocr-first spec, Req 5). Draws
 * label-like text with headless Chromium in several fonts, sizes, rotations, colours and
 * languages and writes PNG files plus a manifest. Nothing is downloaded: every image is rendered
 * text, every brand name is an invented word. These are not photos of real boxes.
 *
 *   node apps/web/scripts/ocr-eval-fixtures.mjs        write apps/web/.ocr-eval/{*.png,cases.json}
 *
 * The case list is deterministic (a seeded generator); the pixels depend on the fonts installed
 * on the machine, so the recognised text is committed (src/scan/eval/ocr-text.json), not the
 * images.
 */
import { mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

import { chromium } from "@playwright/test";

import { parseCsv } from "./gen-vocabulary.mjs";

const here = fileURLToPath(new URL(".", import.meta.url));
const repoRoot = join(here, "../../..");
const outDir = join(here, "../.ocr-eval");

/** mulberry32: a small seeded generator, so the case list never changes between runs. */
function rng(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const HELD_LANGS = ["en", "tr", "de", "fr", "es"];

/** English INN → the salt printed with it on the synthetic label (null: none). */
const INGREDIENTS = {
  amlodipine: "besilate",
  paracetamol: null,
  ibuprofen: null,
  metformin: "hydrochloride",
  omeprazole: null,
  atorvastatin: "calcium",
  ramipril: null,
  furosemide: null,
  simvastatin: null,
  pantoprazole: "sodium",
  bisoprolol: "fumarate",
  losartan: "potassium",
  sertraline: "hydrochloride",
  diclofenac: "sodium",
  metoprolol: "succinate",
  lansoprazole: null,
  tamsulosin: "hydrochloride",
  valsartan: null,
  hydrochlorothiazide: null,
  donepezil: "hydrochloride",
  citalopram: null,
  gabapentin: null,
  tramadol: "hydrochloride",
  prednisolone: null,
  codeine: "phosphate",
  enalapril: "maleate",
  lisinopril: null,
  indapamide: null,
  candesartan: null,
  esomeprazole: "magnesium",
  rosuvastatin: "calcium",
  allopurinol: null,
  cetirizine: "dihydrochloride",
  loratadine: null,
  naproxen: "sodium",
  spironolactone: null,
  carvedilol: null,
  nifedipine: null,
  verapamil: "hydrochloride",
  digoxin: null,
  quetiapine: "fumarate",
  risperidone: null,
  venlafaxine: "hydrochloride",
  pregabalin: null,
  carbamazepine: null,
  lamotrigine: null,
  dexamethasone: null,
  betahistine: "dihydrochloride",
  domperidone: null,
  metoclopramide: "hydrochloride",
};

const SALTS = {
  besilate: {
    en: "besilate",
    tr: "besilat",
    de: "besilat",
    fr: "bésilate",
    es: "besilato",
  },
  hydrochloride: {
    en: "hydrochloride",
    tr: "hidroklorür",
    de: "hydrochlorid",
    fr: "chlorhydrate",
    es: "hidrocloruro",
  },
  dihydrochloride: {
    en: "dihydrochloride",
    tr: "dihidroklorür",
    de: "dihydrochlorid",
    fr: "dichlorhydrate",
    es: "dihidrocloruro",
  },
  fumarate: {
    en: "fumarate",
    tr: "fumarat",
    de: "fumarat",
    fr: "fumarate",
    es: "fumarato",
  },
  succinate: {
    en: "succinate",
    tr: "süksinat",
    de: "succinat",
    fr: "succinate",
    es: "succinato",
  },
  maleate: {
    en: "maleate",
    tr: "maleat",
    de: "maleat",
    fr: "maléate",
    es: "maleato",
  },
  phosphate: {
    en: "phosphate",
    tr: "fosfat",
    de: "phosphat",
    fr: "phosphate",
    es: "fosfato",
  },
  sodium: {
    en: "sodium",
    tr: "sodyum",
    de: "Natrium",
    fr: "sodique",
    es: "sódico",
    metal: true,
  },
  calcium: {
    en: "calcium",
    tr: "kalsiyum",
    de: "Calcium",
    fr: "calcique",
    es: "cálcico",
    metal: true,
  },
  potassium: {
    en: "potassium",
    tr: "potasyum",
    de: "Kalium",
    fr: "potassique",
    es: "potásico",
    metal: true,
  },
  magnesium: {
    en: "magnesium",
    tr: "magnezyum",
    de: "Magnesium",
    fr: "magnésique",
    es: "magnésico",
    metal: true,
  },
};

/** How the ingredient is written with its salt, in the label's language. */
function withSalt(name, salt, lang) {
  if (!salt) return name;
  const s = SALTS[salt];
  if (lang === "en" || lang === "tr") return `${name} ${s[lang]}`;
  if (lang === "de") return s.metal ? `${name}-${s.de}` : `${name}${s.de}`;
  if (s.metal) {
    const word =
      lang === "es" && name.endsWith("a") ? s.es.replace(/o$/, "a") : s[lang];
    return `${name} ${word}`;
  }
  const de = lang === "fr" && /^[aeiouéèh]/i.test(name) ? "d'" : "de ";
  return `${s[lang]} ${de}${name}`;
}

/**
 * Names in other Latin-script languages and Latin, for boxes from countries whose language
 * Janus does not hold. Written from general knowledge as test inputs, not a source Janus holds.
 */
const OTHER = {
  it: {
    amlodipine: "amlodipina",
    paracetamol: "paracetamolo",
    ibuprofen: "ibuprofene",
    metformin: "metformina",
    omeprazole: "omeprazolo",
    atorvastatin: "atorvastatina",
    furosemide: "furosemide",
    simvastatin: "simvastatina",
    pantoprazole: "pantoprazolo",
    bisoprolol: "bisoprololo",
    sertraline: "sertralina",
    diclofenac: "diclofenac",
    lansoprazole: "lansoprazolo",
    tamsulosin: "tamsulosina",
    ramipril: "ramipril",
  },
  pt: {
    amlodipine: "amlodipina",
    paracetamol: "paracetamol",
    ibuprofen: "ibuprofeno",
    metformin: "metformina",
    omeprazole: "omeprazol",
    atorvastatin: "atorvastatina",
    furosemide: "furosemida",
    simvastatin: "sinvastatina",
    pantoprazole: "pantoprazol",
    bisoprolol: "bisoprolol",
    sertraline: "sertralina",
    diclofenac: "diclofenac",
    lansoprazole: "lansoprazol",
    tamsulosin: "tansulosina",
    ramipril: "ramipril",
  },
  nl: {
    amlodipine: "amlodipine",
    paracetamol: "paracetamol",
    ibuprofen: "ibuprofen",
    metformin: "metformine",
    omeprazole: "omeprazol",
    atorvastatin: "atorvastatine",
    furosemide: "furosemide",
    simvastatin: "simvastatine",
    pantoprazole: "pantoprazol",
    bisoprolol: "bisoprolol",
    sertraline: "sertraline",
    diclofenac: "diclofenac",
    lansoprazole: "lansoprazol",
    tamsulosin: "tamsulosine",
    ramipril: "ramipril",
  },
  pl: {
    amlodipine: "amlodypina",
    paracetamol: "paracetamol",
    ibuprofen: "ibuprofen",
    metformin: "metformina",
    omeprazole: "omeprazol",
    atorvastatin: "atorwastatyna",
    furosemide: "furosemid",
    simvastatin: "symwastatyna",
    pantoprazole: "pantoprazol",
    bisoprolol: "bizoprolol",
    sertraline: "sertralina",
    diclofenac: "diklofenak",
    lansoprazole: "lanzoprazol",
    tamsulosin: "tamsulozyna",
    ramipril: "ramipryl",
  },
  la: {
    amlodipine: "amlodipinum",
    paracetamol: "paracetamolum",
    ibuprofen: "ibuprofenum",
    metformin: "metforminum",
    omeprazole: "omeprazolum",
    atorvastatin: "atorvastatinum",
    furosemide: "furosemidum",
    simvastatin: "simvastatinum",
    pantoprazole: "pantoprazolum",
    bisoprolol: "bisoprololum",
    sertraline: "sertralinum",
    diclofenac: "diclofenacum",
    lansoprazole: "lansoprazolum",
    tamsulosin: "tamsulosinum",
    ramipril: "ramiprilum",
  },
};

/** Ingredients the on-device list does not hold: no candidate is expected for them. */
const NOT_HELD = [
  "amoxicillin",
  "warfarin",
  "levothyroxine",
  "ciprofloxacin",
  "clopidogrel",
  "salbutamol",
  "memantine",
  "finasteride",
];

const COMBINATIONS = [
  ["amlodipine", "valsartan"],
  ["amlodipine", "valsartan", "hydrochlorothiazide"],
  ["losartan", "hydrochlorothiazide"],
  ["paracetamol", "codeine"],
  ["bisoprolol", "hydrochlorothiazide"],
  ["candesartan", "hydrochlorothiazide"],
  ["enalapril", "hydrochlorothiazide"],
  ["tramadol", "paracetamol"],
  ["ramipril", "amlodipine"],
  ["atorvastatin", "amlodipine"],
];

/** Label furniture per language: form, count, "each tablet contains", a storage line. */
const WORDS = {
  en: {
    form: "film-coated tablets",
    count: "28 tablets",
    contains: "Each tablet contains",
    keep: "Keep out of the sight and reach of children.",
    use: "Oral use",
  },
  tr: {
    form: "film kaplı tablet",
    count: "28 tablet",
    contains: "Her tablet içerir:",
    keep: "Çocukların göremeyeceği yerlerde saklayınız.",
    use: "Ağızdan alınır",
  },
  de: {
    form: "Filmtabletten",
    count: "28 Filmtabletten",
    contains: "Jede Tablette enthält",
    keep: "Arzneimittel für Kinder unzugänglich aufbewahren.",
    use: "Zum Einnehmen",
  },
  fr: {
    form: "comprimés pelliculés",
    count: "28 comprimés",
    contains: "Chaque comprimé contient",
    keep: "Tenir hors de la vue et de la portée des enfants.",
    use: "Voie orale",
  },
  es: {
    form: "comprimidos recubiertos con película",
    count: "28 comprimidos",
    contains: "Cada comprimido contiene",
    keep: "Mantener fuera de la vista y del alcance de los niños.",
    use: "Vía oral",
  },
  it: {
    form: "compresse rivestite con film",
    count: "28 compresse",
    contains: "Ogni compressa contiene",
    keep: "Tenere fuori dalla vista e dalla portata dei bambini.",
    use: "Uso orale",
  },
  pt: {
    form: "comprimidos revestidos por película",
    count: "28 comprimidos",
    contains: "Cada comprimido contém",
    keep: "Manter fora da vista e do alcance das crianças.",
    use: "Via oral",
  },
  nl: {
    form: "filmomhulde tabletten",
    count: "28 tabletten",
    contains: "Elke tablet bevat",
    keep: "Buiten het zicht en bereik van kinderen houden.",
    use: "Oraal gebruik",
  },
  pl: {
    form: "tabletki powlekane",
    count: "28 tabletek",
    contains: "Każda tabletka zawiera",
    keep: "Przechowywać w miejscu niewidocznym dla dzieci.",
    use: "Podanie doustne",
  },
  la: {
    form: "compressi obducti",
    count: "28 compressi",
    contains: "Compositio:",
    keep: "Keep out of the sight and reach of children.",
    use: "Oral use",
  },
};

const FONTS = [
  "DejaVu Sans",
  "DejaVu Serif",
  "Lato",
  "C059",
  "FreeSans",
  "DejaVu Sans Condensed",
  "DejaVu Sans Mono",
];
const SIZES = [13, 18, 26]; // CSS px of the ingredient line; the image is rendered at 2×
const ROTATIONS = [0, 0, 0, 2, -4, 7, 90, 270, 180];
// The last four imitate a phone photo a little: a slanted box face, sensor noise, strong JPEG
// compression, and a picture taken from too far (half the resolution).
const STYLES = [
  "plain",
  "plain",
  "inverse",
  "band",
  "grey",
  "blur",
  "perspective",
  "noise",
  "jpeg",
  "lowres",
];
const CASES = ["asis", "upper", "title"];
const DOSES = [5, 10, 20, 25, 40, 50, 100, 500];

const SYLL = [
  "zen",
  "ta",
  "vor",
  "lu",
  "mex",
  "qui",
  "dra",
  "nol",
  "bex",
  "ty",
  "ro",
  "fa",
  "kli",
  "su",
  "vel",
];

function brand(rand) {
  const n = 2 + Math.floor(rand() * 2);
  let s = "";
  for (let i = 0; i < n; i++) s += SYLL[Math.floor(rand() * SYLL.length)];
  return s[0].toUpperCase() + s.slice(1);
}

function recase(s, how) {
  if (how === "upper") return s.toLocaleUpperCase("en");
  if (how === "title")
    return s.replace(/(^|[\s-])(\p{L})/gu, (_, a, b) => a + b.toUpperCase());
  return s;
}

function buildCases() {
  const rows = parseCsv(
    readFileSync(
      join(repoRoot, "apps/api/janus/notes/glossary/ingredients.csv"),
      "utf8",
    ),
  ).filter((r) => r.status === "accepted");
  // Two rows with one English name: the first stands for both, as on the device.
  const byEn = new Map();
  for (const r of rows) if (!byEn.has(r.en)) byEn.set(r.en, r);
  const rand = rng(20261110);
  const pick = (list, i) => list[i % list.length];
  const cases = [];
  let n = 0;
  const push = (group, lang, written, expected) => {
    const i = n++;
    // Other-language boxes are read with the English model only; held languages are read with
    // their own interface language two times out of three, else with another one.
    const locale =
      group === "other" || !HELD_LANGS.includes(lang)
        ? "en"
        : i % 3 === 2
          ? pick(HELD_LANGS, i)
          : lang;
    const how = pick(CASES, Math.floor(rand() * 3));
    cases.push({
      id: `${group}-${String(i).padStart(3, "0")}`,
      group,
      lang,
      locale,
      font: pick(FONTS, Math.floor(rand() * FONTS.length)),
      size: pick(SIZES, Math.floor(rand() * SIZES.length)),
      rotation: pick(ROTATIONS, Math.floor(rand() * ROTATIONS.length)),
      style: pick(STYLES, Math.floor(rand() * STYLES.length)),
      brand: brand(rand),
      dose: pick(DOSES, Math.floor(rand() * DOSES.length)),
      written: written.map((w) => recase(w, how)),
      // Every second label repeats the ingredient in a "contains" line, as many boxes do.
      repeat: i % 2 === 0,
      expected,
    });
  };

  // A. One ingredient, in each language Janus holds a name for.
  for (const [en, salt] of Object.entries(INGREDIENTS)) {
    const row = byEn.get(en);
    if (!row) throw new Error(`not in the glossary: ${en}`);
    for (const lang of HELD_LANGS)
      if (row[lang])
        push("held", lang, [withSalt(row[lang], salt, lang)], [row.key]);
  }
  // B. One ingredient, in a language Janus holds no name for.
  for (const [lang, names] of Object.entries(OTHER))
    for (const [en, name] of Object.entries(names))
      push("other", lang, [name], [byEn.get(en).key]);
  // C. Combination products: every ingredient is expected.
  COMBINATIONS.forEach((combo, i) => {
    for (const lang of [pick(HELD_LANGS, i), pick(HELD_LANGS, i + 2)]) {
      const rowsOf = combo.map((en) => byEn.get(en));
      push(
        "combination",
        lang,
        rowsOf.map((r, k) =>
          withSalt(r[lang] || r.en, INGREDIENTS[combo[k]], lang),
        ),
        rowsOf.map((r) => r.key),
      );
    }
  });
  // D. Nothing the device list holds: an invented brand, or an ingredient outside the list.
  for (let i = 0; i < 16; i++) push("none", pick(HELD_LANGS, i), [], []);
  NOT_HELD.forEach((en, i) => {
    if (byEn.has(en)) throw new Error(`held after all: ${en}`);
    push("not_held", pick(HELD_LANGS, i), [en], []);
  });
  return cases;
}

const esc = (s) =>
  s.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" })[c]);

function html(c) {
  const w = WORDS[c.lang];
  const look = {
    plain: "background:#fff;color:#111",
    inverse: "background:#16305c;color:#fff",
    band: "background:#f3e6c4;color:#1d2b4f",
    grey: "background:#ececec;color:#6a6a6a",
    blur: "background:#fff;color:#111;filter:blur(0.6px)",
    perspective: "background:#fff;color:#111",
    noise: "background:#fff;color:#111",
    jpeg: "background:#f7f7f2;color:#222",
    lowres: "background:#fff;color:#111",
  }[c.style];
  const slant =
    c.style === "perspective"
      ? "perspective(900px) rotateY(24deg) rotateX(8deg) "
      : "";
  const grain =
    c.style === "noise"
      ? `<div style="position:absolute;inset:0;opacity:.45;mix-blend-mode:multiply;background:url(&quot;data:image/svg+xml,${encodeURIComponent(
          "<svg xmlns='http://www.w3.org/2000/svg' width='300' height='300'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' seed='7'/></filter><rect width='300' height='300' filter='url(#n)'/></svg>",
        )}&quot;)"></div>`
      : "";
  const big = Math.round(c.size * 1.8);
  const lines = [
    `<div style="font-size:${big}px;font-weight:700">${esc(c.brand)} ${c.dose} mg</div>`,
    ...c.written.map(
      (t) => `<div style="font-size:${c.size}px">${esc(t)}</div>`,
    ),
    `<div style="font-size:${c.size}px">${esc(w.form)}</div>`,
    ...(c.repeat
      ? [
          `<div style="font-size:${Math.round(c.size * 0.85)}px">${esc(w.contains)} ${c.dose} mg ${esc(c.written.join(" / "))}</div>`,
        ]
      : []),
    `<div style="font-size:${c.size}px">${esc(w.count)} · ${esc(w.use)}</div>`,
    `<div style="font-size:${Math.round(c.size * 0.85)}px">${esc(w.keep)}</div>`,
  ];
  return `<!doctype html><meta charset="utf-8"><body style="margin:0;background:#8a8f98">
<div id="label" style="position:absolute;left:50%;top:50%;transform:translate(-50%,-50%) ${slant}rotate(${c.rotation}deg);
width:${Math.max(360, c.size * 30)}px;padding:${c.size * 1.2}px;line-height:1.45;font-family:'${c.font}';${look}">
${lines.join("\n")}${grain}</div></body>`;
}

async function main() {
  const cases = buildCases();
  rmSync(outDir, { recursive: true, force: true });
  mkdirSync(outDir, { recursive: true });
  const browser = await chromium.launch();
  const sharp = await browser.newPage({
    viewport: { width: 1200, height: 1200 },
    deviceScaleFactor: 2,
  });
  const coarse = await browser.newPage({
    viewport: { width: 1200, height: 1200 },
    deviceScaleFactor: 1,
  });
  for (const c of cases) {
    const page = c.style === "lowres" ? coarse : sharp;
    await page.setContent(html(c));
    const box = await page.locator("#label").boundingBox();
    const pad = 24;
    c.file = `${c.id}.${c.style === "jpeg" ? "jpg" : "png"}`;
    await page.screenshot({
      path: join(outDir, c.file),
      ...(c.style === "jpeg" ? { type: "jpeg", quality: 30 } : {}),
      clip: {
        x: Math.max(0, box.x - pad),
        y: Math.max(0, box.y - pad),
        width: Math.min(1200, box.width + 2 * pad),
        height: Math.min(1200, box.height + 2 * pad),
      },
    });
  }
  await browser.close();
  writeFileSync(
    join(outDir, "cases.json"),
    JSON.stringify(cases, null, 1) + "\n",
  );
  console.log(`${cases.length} label images written to ${outDir}`);
}

if (process.argv[1] === fileURLToPath(import.meta.url)) await main();
