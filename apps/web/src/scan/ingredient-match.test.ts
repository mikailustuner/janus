// Feature: ocr-first, Properties P1–P4, P6: matching on the device is invariant to letter case
// and diacritics; a tolerant candidate is never farther from a held name than the cap; noise
// never produces a far match; salt words never make a candidate next to an ingredient;
// combination labels give every ingredient (Req 3).
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { check, fc } from "@/test/fc";

import {
  buildIndex,
  distanceCap,
  editDistance,
  fold,
  matchIngredients,
  skeleton,
} from "./ingredient-match";

const names = JSON.parse(
  readFileSync(
    join(import.meta.dirname, "../vocabulary/ingredient-names.json"),
    "utf8",
  ),
) as Record<string, string[]>;
const index = buildIndex(names);
const keysOf = (...lines: string[]) =>
  matchIngredients(lines, index).map((c) => c.key);
const key = (en: string) => {
  const k = Object.keys(names).find((x) => names[x]![0] === en);
  if (!k) throw new Error(en);
  return k;
};
// Two keys with one English name are one ingredient on the device: the first key stands for both.
const held = Object.entries(names).flatMap(([, list]) =>
  list.map((name) => ({ key: key(list[0]!), name })),
);
const heldName = fc.constantFrom(...held);
/** A name's skeletons, word by word. */
const skeletons = (k: string) =>
  names[k]!.map((n) =>
    (fold(n).match(/[a-z0-9]+/g) ?? []).map(skeleton).join(" "),
  );

describe("folding", () => {
  it("removes case and the diacritics of the five languages", () => {
    expect(fold("İBUPROFEN")).toBe("ibuprofen");
    expect(fold("ISIRGAN")).toBe("isirgan");
    expect(fold("ısırgan")).toBe("isirgan");
    expect(fold("Acetylsalicylsäure")).toBe("acetylsalicylsaure");
    expect(fold("Weißdorn")).toBe("weissdorn");
    expect(fold("CODEÍNA")).toBe("codeina");
    expect(fold("oméprazole")).toBe("omeprazole");
    expect(fold("hidroklorür")).toBe("hidroklorur");
  });

  it("gives one skeleton to an INN written in different languages", () => {
    const same = [
      ["amlodipine", "amlodipin", "amlodipina", "amlodipino", "amlodipinum"],
      ["hydrochlorothiazide", "hidroklorotiyazid", "hidroclorotiazida"],
      ["dexamethasone", "deksametazon", "dexametasona", "Dexamethason"],
      ["quetiapine", "ketiapin", "quetiapina"],
      ["cetirizine", "setirizin", "cetirizina"],
      ["spironolactone", "spironolakton", "espironolactona"],
      ["naproxen", "naproksen", "naproxène", "naproxeno"],
      ["atorvastatin", "atorwastatyna", "atorvastatine"],
      ["lamotrigine", "lamotrijin", "lamotrigina"],
    ];
    for (const group of same)
      expect(new Set(group.map((w) => skeleton(fold(w)))).size, group[0]).toBe(
        1,
      );
  });
});

describe("P1 case and diacritics", () => {
  it("a held name is found in upper case, lower case and without its marks", () => {
    check(
      fc.property(heldName, ({ key: k, name }) => {
        const plain = name.normalize("NFD").replace(/[̀-ͯ]/g, "");
        for (const text of [
          name,
          name.toUpperCase(),
          name.toLowerCase(),
          name.toLocaleUpperCase("tr"),
          plain,
        ]) {
          const found = matchIngredients([`Zzq 10 mg ${text} 28`], index);
          expect(
            found.map((c) => c.key),
            text,
          ).toContain(k);
          expect(found.find((c) => c.key === k)!.strength).not.toBe("close");
        }
      }),
    );
  });

  it("any text gives the same candidates in any letter case", () => {
    const letter = fc.constantFrom(
      ..."abcdefghijklmnoprstuvyzçğıöşüäßéèêàñóíáú -'".split(""),
    );
    check(
      fc.property(
        fc.array(
          fc.oneof(
            heldName.map((h) => h.name),
            fc.string({ unit: letter, maxLength: 14 }),
          ),
          {
            maxLength: 6,
          },
        ),
        (parts) => {
          const text = parts.join(" ");
          const base = keysOf(text);
          expect(keysOf(text.toUpperCase())).toEqual(base);
          expect(keysOf(text.toLowerCase())).toEqual(base);
          expect(keysOf(text.toLocaleUpperCase("tr"))).toEqual(base);
        },
      ),
    );
  });
});

describe("P2 the tolerance has a strict cap", () => {
  it("is 0 for short names and never more than 2", () => {
    for (let n = 0; n < 40; n++) {
      expect(distanceCap(n)).toBeLessThanOrEqual(2);
      if (n < 6) expect(distanceCap(n)).toBe(0);
    }
  });

  it("every candidate is within the cap of a held name of its ingredient", () => {
    const noisy = fc
      .tuple(
        heldName,
        fc.array(
          fc.tuple(fc.nat(30), fc.constantFrom(..."abcdefghilmnorstuxyz01 ")),
          { maxLength: 5 },
        ),
        fc.boolean(),
      )
      .map(([h, edits, insert]) => {
        let s = h.name;
        for (const [at, ch] of edits) {
          const i = at % (s.length + 1);
          s = s.slice(0, i) + ch + s.slice(insert ? i : i + 1);
        }
        return s;
      });
    check(
      fc.property(fc.array(noisy, { minLength: 1, maxLength: 4 }), (parts) => {
        for (const c of matchIngredients([parts.join(" ")], index)) {
          expect(c.distance).toBeLessThanOrEqual(2);
          if (c.strength !== "close") continue;
          // The printed word (or the stem of a compound) is within the cap of one of the
          // ingredient's own single-word names.
          const printed = (c.written.match(/[\p{L}\p{N}]+/gu) ?? []).map((w) =>
            skeleton(
              fold(w).replace(/0/g, "o").replace(/1/g, "l").replace(/5/g, "s"),
            ),
          );
          // A digit read as its look-alike letter: the repaired words equal a held name.
          const repaired = skeletons(c.key).some((s) =>
            ` ${printed.join(" ")} `.includes(` ${s} `),
          );
          // A name split in two by the recogniser: the two words together are a held name.
          const raw = (c.written.match(/[\p{L}\p{N}]+/gu) ?? []).map(fold);
          const split = raw.some(
            (w, n) =>
              n + 1 < raw.length &&
              skeletons(c.key).includes(skeleton(w + raw[n + 1]!)),
          );
          const near = printed.some((word) => {
            return skeletons(c.key).some((s) => {
              const cap = distanceCap(s.length);
              if (cap === 0) return s === word;
              for (let cut = word.length; cut >= s.length - cap; cut--)
                if (editDistance(word.slice(0, cut), s, cap) <= cap)
                  return true;
              return false;
            });
          });
          expect(repaired || split || near, `${c.written} → ${c.key}`).toBe(
            true,
          );
        }
      }),
    );
  });

  it("noise around a far word never makes it a match", () => {
    // Words more than two edits from every held name, with arbitrary symbols added around them.
    const far = fc.constantFrom(
      "Zentavorlu",
      "Draluvor",
      "Kliquimex",
      "PATIENT",
      "ZZJANE",
      "pharmacy",
      "Filmtabletten",
      "comprimidos",
      "saklayınız",
    );
    const symbols = fc.string({
      unit: fc.constantFrom(..." .,:;-_/|()[]*#'\"0123456789".split("")),
      maxLength: 6,
    });
    check(
      fc.property(
        fc.array(fc.tuple(symbols, far, symbols), {
          minLength: 1,
          maxLength: 5,
        }),
        (parts) => {
          expect(keysOf(parts.map((p) => p.join("")).join(" "))).toEqual([]);
        },
      ),
    );
  });

  it("an edit distance over the cap is reported as over the cap", () => {
    check(
      fc.property(
        fc.stringMatching(/^[a-z]{0,12}$/),
        fc.stringMatching(/^[a-z]{0,12}$/),
        fc.integer({ min: 0, max: 2 }),
        (a, b, cap) => {
          const d = editDistance(a, b, cap);
          expect(d).toBe(editDistance(b, a, cap));
          expect(d).toBeLessThanOrEqual(cap + 1);
          if (a === b) expect(d).toBe(0);
          else expect(d).toBeGreaterThan(0);
          expect(d).toBeGreaterThanOrEqual(
            Math.min(cap + 1, Math.abs(a.length - b.length)),
          );
        },
      ),
    );
  });
});

describe("names across languages, salts and combinations", () => {
  it("finds INN variants: paracetamol and acetaminophen are one ingredient", () => {
    const k = key("paracetamol");
    for (const text of [
      "Paracetamol 500 mg",
      "ACETAMINOPHEN 500 MG",
      "paracétamol",
      "Paracetamolo 500 mg compresse",
      "parasetamol 500 mg tablet",
      "Paracetamolum",
    ])
      expect(keysOf(text), text).toEqual([k]);
  });

  it("finds a name in a language Janus holds no name for", () => {
    expect(keysOf("amlodypina 5 mg tabletki")).toEqual([key("amlodipine")]);
    expect(keysOf("Omeprazolo 20 mg capsule")).toEqual([key("omeprazole")]);
    expect(keysOf("sinvastatina 20 mg")).toEqual([key("simvastatin")]);
  });

  it("ignores salt words for matching and keeps them in the printed text", () => {
    const cases: [string, string, string][] = [
      ["Amlodipine besilate 5 mg", "amlodipine", "Amlodipine besilate"],
      ["METFORMIN HİDROKLORÜR 850 mg", "metformin", "METFORMIN HİDROKLORÜR"],
      ["Metoprololsuccinat 47,5 mg", "metoprolol", "Metoprololsuccinat"],
      ["Diclofenac-Natrium 50 mg", "diclofenac", "Diclofenac-Natrium"],
      [
        "chlorhydrate de metformine 500 mg",
        "metformin",
        "chlorhydrate de metformine",
      ],
      ["bésilate d'amlodipine", "amlodipine", "bésilate d'amlodipine"],
      ["atorvastatina cálcica 20 mg", "atorvastatin", "atorvastatina cálcica"],
      ["losartan potassium 50 mg", "losartan", "losartan potassium"],
    ];
    for (const [text, en, printed] of cases) {
      const found = matchIngredients([text], index);
      expect(
        found.map((c) => c.key),
        text,
      ).toEqual([key(en)]);
      expect(found[0]!.written).toBe(printed);
    }
  });

  it("a held name made of salt words is still found", () => {
    expect(keysOf("Calcium carbonate 500 mg")).toEqual([
      key("calcium carbonate"),
    ]);
    expect(keysOf("magnesium citrate")).toEqual([key("magnesium citrate")]);
  });

  it("finds every ingredient of a combination label, each once", () => {
    expect(
      keysOf(
        "Zentavor 5 mg/160 mg/12,5 mg",
        "amlodipine besilate / valsartan / hydrochlorothiazide",
        "Each tablet contains amlodipine, valsartan and hydrochlorothiazide",
      ),
    ).toEqual([
      key("amlodipine"),
      key("valsartan"),
      key("hydrochlorothiazide"),
    ]);
  });

  it("a misread letter gives a close candidate, a far word gives none", () => {
    const a = matchIngredients(["AMLODIP1NE 5 mg"], index);
    expect(a.map((c) => [c.key, c.strength])).toEqual([
      [key("amlodipine"), "close"],
    ]);
    const b = matchIngredients(["hydrochlorothiazlde"], index);
    expect(b.map((c) => [c.key, c.strength, c.distance])).toEqual([
      [key("hydrochlorothiazide"), "close", 1],
    ]);
    expect(keysOf("amlxxxpine")).toEqual([]);
    expect(keysOf("Keep out of the sight and reach of children.")).toEqual([]);
  });

  it("an exact name is never replaced by a similar one", () => {
    const found = matchIngredients(["prednisone 5 mg"], index);
    expect(found[0]!.key).toBe(key("prednisone"));
    expect(found[0]!.strength).toBe("exact");
    expect(found.map((c) => c.key)).not.toContain(key("prednisolone"));
  });

  it("label words in the five languages give no candidate", () => {
    const text = `film-coated tablets oral use each tablet contains keep out of the sight and reach
      of children store below prescription only medicine batch expiry
      film kaplı tablet ağızdan alınır her tablet içerir çocukların göremeyeceği yerlerde saklayınız
      reçete ile satılır son kullanma tarihi parti no kullanma talimatı
      Filmtabletten zum Einnehmen jede Tablette enthält Arzneimittel für Kinder unzugänglich
      aufbewahren verschreibungspflichtig verwendbar bis Packungsbeilage beachten
      comprimés pelliculés voie orale chaque comprimé contient tenir hors de la vue et de la portée
      des enfants médicament soumis à prescription médicale lot péremption notice
      comprimidos recubiertos con película vía oral cada comprimido contiene mantener fuera de la
      vista y del alcance de los niños con receta médica lote caducidad prospecto
      PATIENT DOCTOR PHARMACY TAKE ONE TABLET DAILY REFILLS QUANTITY`;
    expect(matchIngredients(text.split("\n"), index)).toEqual([]);
  });
});

describe("names in five further languages (text only; these were not used to write the rules)", () => {
  // Written from general knowledge as test inputs, not from a source Janus holds.
  const EN =
    "amlodipine paracetamol ibuprofen metformin omeprazole atorvastatin furosemide simvastatin pantoprazole bisoprolol sertraline diclofenac lansoprazole tamsulosin ramipril".split(
      " ",
    );
  const FURTHER: Record<string, string> = {
    cs: "amlodipin paracetamol ibuprofen metformin omeprazol atorvastatin furosemid simvastatin pantoprazol bisoprolol sertralin diklofenak lansoprazol tamsulosin ramipril",
    ro: "amlodipină paracetamol ibuprofen metformină omeprazol atorvastatină furosemid simvastatină pantoprazol bisoprolol sertralină diclofenac lansoprazol tamsulosină ramipril",
    hu: "amlodipin paracetamol ibuprofén metformin omeprazol atorvasztatin furoszemid szimvasztatin pantoprazol bizoprolol szertralin diklofenák lanzoprazol tamszulozin ramipril",
    sv: "amlodipin paracetamol ibuprofen metformin omeprazol atorvastatin furosemid simvastatin pantoprazol bisoprolol sertralin diklofenak lansoprazol tamsulosin ramipril",
    lt: "amlodipinas paracetamolis ibuprofenas metforminas omeprazolas atorvastatinas furozemidas simvastatinas pantoprazolas bisoprololis sertralinas diklofenakas lansoprazolas tamsulozinas ramiprilis",
  };

  it("finds the ingredient, and never a wrong one", () => {
    const found: Record<string, number> = {};
    for (const [lang, list] of Object.entries(FURTHER)) {
      found[lang] = 0;
      list.split(" ").forEach((name, i) => {
        const keys = keysOf(`Zzq 10 mg ${name} 30`);
        if (keys.length === 0) return;
        expect(keys, `${lang} ${name}`).toEqual([key(EN[i]!)]);
        found[lang]!++;
      });
    }
    // Lithuanian endings (-as, -is) are outside the spelling rules: some names are only reached
    // by the tolerant comparison, and short ones not at all.
    expect(found).toEqual({ cs: 15, ro: 15, hu: 15, sv: 15, lt: 14 });
  });
});
