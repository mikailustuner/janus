// The recorded API answers (`src/**/*.recorded.json`) are the demo-mode data of the site and are
// re-recorded with every pipeline release. This is the only test that reads them: each file decodes
// with the production decoder and holds the minimum the demo needs. Behaviour tests use the
// synthetic fixtures in `src/test/fixtures` and never assert on recorded content.
import { describe, expect, it } from "vitest";

import { decode } from "@/api/decode";
import {
  drugOut,
  drugsOut,
  evidenceOut,
  reasonKey,
  systemOut,
  type ModelKitFixture,
} from "@/modelkit/model";
import { reasonCodesOf, type ModelKitSet } from "@/test/fixtures/modelkit";

import {
  defaultRequest,
  job,
  serverCompounds,
  type SimulationFixture,
} from "@/simulation/client";
import { catalogueOut, PRESENT_CODES, seanceOut } from "@/seance/model";
import type { SeanceFixture } from "@/seance/client";
import { cardsOut, exportOut, overviewOut, validationOut } from "@/light/model";
import {
  cascadeOut,
  catalogue as tmCatalogue,
  substanceOut,
} from "@/timemachine/model";
import type { Locale } from "@/api/contracts";
import { demoItems, type Fixture } from "@/demo/client";
import cologne from "@/demo/fixtures/cologne.json";
import istanbul from "@/demo/fixtures/istanbul.json";
import ohio from "@/demo/fixtures/ohio.json";
import { routing } from "@/i18n/routing";
import { demoInfo } from "@/plaininfo/client";
import { ingredient } from "@/plaininfo/model";
import { infoQuery } from "@/plaininfo/query";
import { violations } from "@/test/plaininfo-words";
import type { Loaded, Vocabulary, VocabularyIndex } from "@/vocabulary";
import vocabIndex from "@/vocabulary/index.json";
import { COLOGNE_PASSPORT, RECORDED } from "@/demo/passport-cologne";
import { COLOGNE_PRODUCTS } from "@/demo/passport-products";
import { fromRecorded } from "@/passport/client";
import { fromListItem, presenceOut } from "@/passport/model";
import type { PassportItem } from "@/passport/model";
import { mergeLists } from "@/passport/merge";
import {
  buildProductsRequest,
  fromRecordedProducts,
  LISTABLE,
  productsOut,
} from "@/passport/products";
import { buildPresenceRequests } from "@/passport/request";
import { openOutcomes } from "@/open/model";
import { dataQualityReport } from "@/research/dataQuality";
import { onsetTable } from "@/research/onset";

import simulate from "@/simulation/simulate.recorded.json";
import plainInfo from "@/demo/plain-info.recorded.json";
import timemachine from "@/timemachine/fixture.recorded.json";
import light from "@/light/fixture.recorded.json";
import seance from "@/seance/fixture.recorded.json";
import openData from "@/open/fixture.recorded.json";
import dataQuality from "@/research/data-quality.recorded.json";
import faersOnset from "@/research/faers-onset.recorded.json";
import modelkit from "@/modelkit/modelkit.recorded.json";
import modelkitM0 from "@/modelkit/modelkit.m0.recorded.json";

describe.each([
  ["modelkit.recorded.json", modelkit],
  ["modelkit.m0.recorded.json", modelkitM0],
])("%s", (_name, file) => {
  const fx = file as unknown as ModelKitFixture;
  const drugs = decode(drugsOut, fx.drugs);
  const drugKeys = Object.keys(fx.drug);
  const val = <T>(r: { ok: boolean; value?: T }): T => {
    if (!r.ok) throw new Error("does not decode");
    return r.value as T;
  };

  it("decodes with the production decoders", () => {
    expect(drugs.ok).toBe(true);
    expect(decode(systemOut, fx.validation).ok).toBe(true);
    for (const k of drugKeys)
      expect(decode(drugOut, fx.drug[k]).ok, `drug ${k}`).toBe(true);
    for (const k of Object.keys(fx.evidence))
      expect(decode(evidenceOut, fx.evidence[k]).ok, `evidence ${k}`).toBe(
        true,
      );
  });

  it("holds the minimum the demo needs: a drug list, a drug with a parameter set", () => {
    expect(val(drugs).drugs.length).toBeGreaterThanOrEqual(1);
    const withSet = drugKeys.filter(
      (k) => val(decode(drugOut, fx.drug[k])).parameter_set !== null,
    );
    expect(withSet.length).toBeGreaterThanOrEqual(1);
  });

  it("uses only reason codes the interface has a message for", () => {
    const set = {
      drug: Object.fromEntries(
        drugKeys.map((k) => [k, val(decode(drugOut, fx.drug[k]))]),
      ),
      evidence: Object.fromEntries(
        Object.keys(fx.evidence).map((k) => [
          k,
          val(decode(evidenceOut, fx.evidence[k])),
        ]),
      ),
      validation: val(decode(systemOut, fx.validation)),
    } as unknown as ModelKitSet;
    expect([...reasonCodesOf(set)].filter((c) => !reasonKey(c))).toEqual([]);
  });
});

describe("data-quality.recorded.json", () => {
  const r = decode(dataQualityReport, dataQuality.report);

  it("decodes and holds at least one finding with a CSV and a Markdown file", () => {
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.value.findings.length).toBeGreaterThanOrEqual(1);
    expect(dataQuality.csv.length).toBeGreaterThan(0);
    expect(dataQuality.md.length).toBeGreaterThan(0);
  });

  it("carries no TİTCK barcode or GTIN (the page can show the whole file)", () => {
    expect(JSON.stringify(dataQuality)).not.toMatch(/(?<!\d)0?869\d{10}(?!\d)/);
  });
});

describe("faers-onset.recorded.json", () => {
  const r = decode(onsetTable, faersOnset.table);

  it("decodes and holds the 65 PIPC positions with a CSV file", () => {
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.value.rows.map((x) => x.pipc_position)).toEqual(
      Array.from({ length: 65 }, (_, i) => i + 1),
    );
    expect(faersOnset.csv.length).toBeGreaterThan(0);
  });
});

describe("simulate.recorded.json", () => {
  const fx = simulate as unknown as SimulationFixture;
  const compounds = decode(serverCompounds, fx.compounds);

  it("decodes: the compounds list and every recorded job", () => {
    expect(compounds.ok).toBe(true);
    expect(fx.jobs.length).toBeGreaterThanOrEqual(1);
    for (const j of fx.jobs) expect(decode(job, j.job).ok).toBe(true);
  });

  it("holds a done job for the form's default request of each model (the demo offers those)", () => {
    if (!compounds.ok) throw new Error("compounds do not decode");
    for (const kind of ["compartmental", "httk_population"] as const) {
      const want = defaultRequest(compounds.value, kind);
      const hit = fx.jobs.find(
        (j) =>
          JSON.stringify(Object.entries(j.request).sort()) ===
          JSON.stringify(Object.entries(want).sort()),
      );
      expect(hit, kind).toBeTruthy();
      const d = decode(job, hit!.job);
      expect(d.ok && d.value.state === "done" && d.value.result !== null).toBe(
        true,
      );
    }
  });
});

describe("open/fixture.recorded.json", () => {
  const r = decode(openOutcomes, openData.outcomes);

  it("decodes, keeps the release rule (k >= 20, hidden cells never listed) and has a CSV header", () => {
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.value.release_rule.k).toBeGreaterThanOrEqual(20);
    expect(r.value.release_rule.hidden_cells_listed).toBe(false);
    expect(openData.csv.split("\n")[0]).toMatch(/^dataset_version,/);
  });
});

describe("seance/fixture.recorded.json", () => {
  const fx = seance as unknown as SeanceFixture;

  it("decodes: the catalogue and every recorded pair, each pair listed in the catalogue", () => {
    const cat = decode(catalogueOut, fx.catalogue);
    expect(cat.ok).toBe(true);
    expect(fx.pairs.length).toBeGreaterThanOrEqual(1);
    for (const p of fx.pairs) {
      const a = decode(seanceOut, p.answer);
      expect(a.ok).toBe(true);
      if (cat.ok)
        expect(
          cat.value.pairs.some(
            (x) =>
              x.substance === p.request.substance &&
              x.condition === p.request.condition,
          ),
        ).toBe(true);
    }
  });

  it("uses only present-witness caveat codes the screen can word", () => {
    for (const p of fx.pairs) {
      const a = decode(seanceOut, p.answer);
      if (a.ok)
        for (const c of a.value.witnesses.present.codes)
          expect(PRESENT_CODES as readonly string[]).toContain(c);
    }
  });
});

describe("light/fixture.recorded.json", () => {
  it("decodes: overview, every goal's cards, validation and export", () => {
    expect(decode(overviewOut, light.overview).ok).toBe(true);
    expect(Object.keys(light.cards).length).toBeGreaterThanOrEqual(1);
    for (const [goal, v] of Object.entries(light.cards))
      expect(decode(cardsOut, v).ok, goal).toBe(true);
    expect(decode(validationOut, light.validation).ok).toBe(true);
    expect(decode(exportOut, light.export).ok).toBe(true);
  });

  it("holds at least one hypothesis card and one export row", () => {
    const cards = Object.values(light.cards).flatMap(
      (v) => (v as { cards: unknown[] }).cards,
    );
    expect(cards.length).toBeGreaterThanOrEqual(1);
    expect(
      (light.export as { rows: unknown[] }).rows.length,
    ).toBeGreaterThanOrEqual(1);
  });
});

describe("timemachine/fixture.recorded.json", () => {
  const fx = timemachine as unknown as {
    catalogue: unknown;
    substances: Record<string, unknown>;
    cascades: Record<string, unknown>;
  };
  const cat = decode(tmCatalogue, fx.catalogue);

  it("decodes: the catalogue, every substance and every cascade, each listed in the catalogue", () => {
    expect(cat.ok).toBe(true);
    if (!cat.ok) return;
    expect(Object.keys(fx.substances).sort()).toEqual(
      [...cat.value.substance_ids].sort(),
    );
    expect(Object.keys(fx.cascades).sort()).toEqual(
      [...cat.value.cascade_ids].sort(),
    );
    for (const [k, v] of Object.entries(fx.substances))
      expect(decode(substanceOut, v).ok, k).toBe(true);
    for (const [k, v] of Object.entries(fx.cascades))
      expect(decode(cascadeOut, v).ok, k).toBe(true);
  });

  it("holds at least one substance and one cascade", () => {
    expect(Object.keys(fx.substances).length).toBeGreaterThanOrEqual(1);
    expect(Object.keys(fx.cascades).length).toBeGreaterThanOrEqual(1);
  });
});

describe("demo/plain-info.recorded.json", () => {
  const LOCALES = routing.locales as readonly Locale[];
  const items = [istanbul, ohio, cologne].flatMap((f) =>
    demoItems(f as unknown as Fixture),
  );
  const vocab = async (l: Locale): Promise<Loaded> => ({
    locale: l,
    vocab: (await import(`@/vocabulary/${l}.json`)).default as Vocabulary,
    index: vocabIndex as VocabularyIndex,
  });

  it("answers every demo medicine in every language, without a product (the demo needs this)", async () => {
    for (const language of LOCALES) {
      const v = await vocab(language);
      for (const item of items) {
        const q = infoQuery(v, item, language, true);
        const r = await demoInfo(q.body!);
        expect(r.ok, `${item.id} ${language}`).toBe(true);
        if (r.ok) expect(r.data.official).toBeNull();
      }
    }
  });

  it("decodes every recorded ingredient answer", () => {
    for (const [language, byCodes] of Object.entries(plainInfo.ingredients))
      for (const [codes, answer] of Object.entries(byCodes))
        expect(decode(ingredient, answer).ok, `${language} ${codes}`).toBe(
          true,
        );
  });

  it("names no dose and no way of taking a medicine in the group texts", () => {
    for (const l of LOCALES)
      for (const answer of Object.values(
        (plainInfo.ingredients as Record<string, Record<string, unknown>>)[l]!,
      )) {
        const { groups } = answer as {
          groups: { name: string; text: string }[];
        };
        for (const g of groups) {
          expect(g.text).not.toMatch(/\d/);
          expect(violations(`${g.name} ${g.text}`, l), g.text).toEqual([]);
        }
      }
  });
});

describe("demo/passport-*.recorded.json (presence answers of the three demo patients)", () => {
  const lists = async () => {
    const out: Record<string, PassportItem[]> = { cologne: COLOGNE_PASSPORT };
    for (const p of ["istanbul", "ohio"]) {
      const f = (await import(`@/demo/fixtures/${p}.json`)).default;
      out[p] = demoItems(f as Fixture).map((i) =>
        fromListItem(i, (_k, l) => l, true),
      );
    }
    return out;
  };

  it("decode, and name their dataset and recording date", () => {
    for (const [p, rec] of Object.entries(RECORDED)) {
      const d = decode(presenceOut, rec.response);
      expect(d.ok, p).toBe(true);
      if (d.ok)
        expect(d.value.dataset_version).toBe(rec.recorded.dataset_version);
      expect(rec.recorded.date).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    }
  });

  it("hold every query the demo lists build (the demo needs this)", async () => {
    for (const [p, list] of Object.entries(await lists())) {
      const rec = RECORDED[p]!;
      const built = buildPresenceRequests(mergeLists(list, []));
      const sorted = (b: { items: unknown[] }) =>
        b.items.map((q) => JSON.stringify(q)).sort();
      expect(built.bodies.flatMap(sorted).sort(), p).toEqual(
        sorted(rec.request),
      );
      for (const b of built.bodies)
        expect(fromRecorded(rec, b), p).not.toBeNull();
    }
  });
});

describe("demo/passport-products.recorded.json", () => {
  it("decodes, from listable sources only, with the query's keys, and dates", () => {
    expect(COLOGNE_PRODUCTS.recorded.date).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    for (const a of COLOGNE_PRODUCTS.answers) {
      const d = decode(productsOut, a.response);
      expect(d.ok).toBe(true);
      if (!d.ok) continue;
      expect(LISTABLE).toContain(d.value.source.source_id);
      expect(d.value.source.source_id).toBe(a.request.target);
      expect(d.value.dataset_version).toBe(
        COLOGNE_PRODUCTS.recorded.dataset_version,
      );
      const keys = a.request.ingredients.map((g) => g.key).sort();
      for (const p of d.value.products)
        expect([...new Set(p.ingredients.map((g) => g.key))].sort()).toEqual(
          keys,
        );
    }
  });

  it("holds the first page of every query the Cologne list builds, for every target", () => {
    for (const item of COLOGNE_PASSPORT)
      for (const target of LISTABLE) {
        const body = buildProductsRequest(item, target);
        if (body)
          expect(
            fromRecordedProducts(COLOGNE_PRODUCTS, body),
            `${item.boxName} ${target}`,
          ).not.toBeNull();
      }
  });
});
