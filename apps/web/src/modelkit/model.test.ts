// Feature: model-kit Req 6. The decoders accept the answers (synthetic, src/test/fixtures/modelkit.ts;
// the recorded files are checked in src/test/recorded-contract.test.ts); the view model (hash key,
// status badge, log-log chart maths) and the reason-code coverage hold in five languages.
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { decode } from "@/api/decode";
import { routing } from "@/i18n/routing";

import { KEYS, modelKitSet, reasonCodesOf } from "@/test/fixtures/modelkit";

import {
  bandPolygon,
  demoModelKit,
  drugOut,
  drugsPath,
  drugsOut,
  EVIDENCE_PARAMS,
  evidenceOut,
  inBand,
  shortStudy,
  keyFromHash,
  logAxis,
  logPos,
  NO_QUERY,
  PAGE_SIZE,
  pageOfDrugs,
  PARAM_NAMES,
  paramKey,
  REASON_CODES,
  reasonKey,
  SP_CLASSES,
  SP_GRADES,
  statusBadge,
  systemOut,
  TARGETS,
} from "./model";

type Tree = { [k: string]: string | Tree };
const set = modelKitSet();
const fx = set.raw;
const root = (p: string) => join(import.meta.dirname, "../../../..", p);
const catalogue = (l: string) =>
  JSON.parse(
    readFileSync(join(import.meta.dirname, `../../messages/${l}.json`), "utf8"),
  ) as Tree;
const has = (t: Tree, path: string) =>
  path
    .split(".")
    .reduce<string | Tree | undefined>(
      (n, k) => (typeof n === "object" ? n[k] : undefined),
      t,
    ) !== undefined;

describe("decoders accept the answers", () => {
  it("drugs, system report, every drug and every evidence list", () => {
    expect(decode(drugsOut, fx.drugs).ok).toBe(true);
    expect(decode(systemOut, fx.validation).ok).toBe(true);
    for (const k of Object.keys(fx.drug))
      expect(decode(drugOut, fx.drug[k]).ok, k).toBe(true);
    for (const k of Object.keys(fx.evidence))
      expect(decode(evidenceOut, fx.evidence[k]).ok, k).toBe(true);
  });
  it("the set has one drug of every status and a drug with a set and with none", () => {
    const d = Object.values(set.drug).map((x) => x.summary);
    for (const st of ["validated", "not_validated", "failed"])
      expect(
        d.some((x) => x.status === st),
        st,
      ).toBe(true);
    expect(d.some((x) => x.has_set)).toBe(true);
    expect(d.some((x) => !x.has_set)).toBe(true);
    expect(d.length).toBeGreaterThan(PAGE_SIZE);
  });
  it("a changed enum is a contract error", () => {
    const bad = structuredClone(fx.drugs) as { drugs: { status: string }[] };
    bad.drugs[0]!.status = "recommended";
    expect(decode(drugsOut, bad).ok).toBe(false);
  });
  it("the demo client answers from the file and 404s an unknown key", async () => {
    const c = demoModelKit(fx);
    expect((await c.drugs(NO_QUERY)).ok).toBe(true);
    expect((await c.drug(KEYS.validated)).ok).toBe(true);
    const r = await c.drug("nope");
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.error.messageKey).toBe("ModelKit.errors.unknown");
    expect(c.downloads).toBe(false);
  });
});

describe("list paging and search", () => {
  it("the live path carries only what differs from the defaults", () => {
    expect(drugsPath(NO_QUERY)).toBe(`modelkit/drugs?limit=${PAGE_SIZE}`);
    expect(
      drugsPath({
        q: "  Tra ",
        status: "failed",
        hasSet: true,
        offset: 25,
        limit: 25,
      }),
    ).toBe(
      "modelkit/drugs?q=tra&status=failed&has_set=true&limit=25&offset=25",
    );
  });
  it("the demo page applies the same filters as the API and counts the whole list", () => {
    const all = decode(drugsOut, fx.drugs);
    expect(all.ok).toBe(true);
    if (!all.ok) return;
    const whole = pageOfDrugs(all.value, NO_QUERY);
    expect(whole.total).toBe(all.value.drugs.length);
    expect(whole.drugs.length).toBe(Math.min(PAGE_SIZE, whole.total));
    expect(whole.counts.all).toBe(whole.total);
    const second = pageOfDrugs(all.value, { ...NO_QUERY, offset: PAGE_SIZE });
    expect(second.drugs.map((d) => d.key)).toEqual(
      all.value.drugs.slice(PAGE_SIZE, 2 * PAGE_SIZE).map((d) => d.key),
    );
    const first = all.value.drugs[0]!;
    const found = pageOfDrugs(all.value, {
      ...NO_QUERY,
      q: first.key.slice(0, 5).toUpperCase(),
    });
    expect(found.drugs.some((d) => d.key === first.key)).toBe(true);
    expect(found.counts).toEqual(whole.counts); // counts ignore the filters
    for (const st of ["validated", "not_validated", "failed"] as const) {
      const kept = pageOfDrugs(all.value, {
        ...NO_QUERY,
        status: st,
        limit: 1000,
      }).drugs;
      expect(kept.length, st).toBeGreaterThan(0);
      expect(kept.every((d) => d.status === st)).toBe(true);
    }
    const withSet = pageOfDrugs(all.value, {
      ...NO_QUERY,
      hasSet: true,
      limit: 1000,
    }).drugs;
    expect(withSet.length).toBeGreaterThan(0);
    expect(withSet.length).toBeLessThan(whole.total);
    expect(withSet.every((d) => d.has_set)).toBe(true);
  });
});

describe("view model", () => {
  it("reads a drug key from the fragment, nothing else", () => {
    expect(keyFromHash("#sunitinib")).toBe("sunitinib");
    expect(keyFromHash("tramadol")).toBe("tramadol");
    for (const bad of [
      "",
      "#",
      "#Sun",
      "#1abc",
      "#a-b",
      "#../x",
      `#${"a".repeat(33)}`,
    ])
      expect(keyFromHash(bad), bad).toBeNull();
    expect(keyFromHash(`#${"a".repeat(32)}`)).not.toBeNull();
  });
  it("maps a status to its message and a tone that is never risk red", () => {
    expect(statusBadge("failed")).toEqual({
      labelKey: "ModelKit.status.failed",
      tone: "failed",
    });
    expect(statusBadge("validated").tone).toBe("validated");
  });
  it("builds a log axis of whole decades and a valid 2-fold band", () => {
    const a = logAxis([3.7, 52, 800]);
    expect(a.min).toBe(1);
    expect(a.max).toBe(1000);
    expect(a.ticks).toEqual([1, 10, 100, 1000]);
    expect(logAxis([5]).max / logAxis([5]).min).toBeGreaterThanOrEqual(10);
    expect(logPos(a, 1)).toBe(0);
    expect(logPos(a, 1000)).toBe(1);
    expect(logPos(a, 10)).toBeCloseTo(1 / 3, 10);
    expect(logPos(a, 1e9)).toBe(1);
    expect(logPos(a, -1)).toBe(0);
    const band = bandPolygon(a);
    expect(band).toHaveLength(6);
    for (const [x, y] of band) {
      expect(x).toBeGreaterThanOrEqual(a.min);
      expect(y).toBeLessThanOrEqual(a.max);
      expect(y / x).toBeLessThanOrEqual(2 + 1e-9);
      expect(y / x).toBeGreaterThanOrEqual(0.5 - 1e-9);
    }
  });
  it("inBand is inclusive at 2-fold and matches the flag of every point", () => {
    expect(inBand({ observed: 10, predicted: 20 })).toBe(true);
    expect(inBand({ observed: 10, predicted: 5 })).toBe(true);
    expect(inBand({ observed: 10, predicted: 4.9 })).toBe(false);
    const points = Object.values(set.drug).flatMap((d) => d.validation.points);
    expect(points.some((p) => p.within_2_fold)).toBe(true);
    expect(points.some((p) => !p.within_2_fold)).toBe(true);
    expect(points.some((p) => p.predicted / p.observed === 2)).toBe(true); // on the edge
    for (const p of points)
      expect(inBand(p), p.evidence_id).toBe(p.within_2_fold);
  });
  it("shortStudy cuts long internal ids and keeps short ones", () => {
    expect(shortStudy("NCT02404805")).toBe("NCT02404805");
    expect(shortStudy("485bc9db-8665-9f5a-e063-6394a90a7921")).toBe(
      "485bc9db…",
    );
    expect(shortStudy("FDA review WINHZLLDWRZWRT")).toBe("FDA review WINH…");
  });
  it("labels apparent parameters CL/F and V/F", () => {
    expect(paramKey("cl", true)).toBe("ModelKit.param.clApparent");
    expect(paramKey("cl", false)).toBe("ModelKit.param.cl");
    expect(paramKey("ka", true)).toBe("ModelKit.param.ka");
    expect(paramKey("zzz", false)).toBeNull();
  });
});

describe("reason codes", () => {
  const seen = reasonCodesOf(set);
  const py = readFileSync(root("apps/api/janus/modelkit/reasons.py"), "utf8");
  const api = new Set(
    [...py.matchAll(/^\s{4}"([a-z0-9_]+)":/gm)].map((m) => m[1]!),
  );

  it("every code of the synthetic answers is known", () => {
    expect(seen.size).toBeGreaterThan(10);
    expect([...seen].filter((c) => !reasonKey(c))).toEqual([]);
  });
  it("every code of the API glossary is known, and none is invented", () => {
    expect(api.size).toBeGreaterThan(40);
    expect([...api].filter((c) => !reasonKey(c))).toEqual([]);
    expect(REASON_CODES.filter((c) => c !== "not_used" && !api.has(c))).toEqual(
      [],
    );
  });
  it.each(routing.locales)("%s has a message for each code and label", (l) => {
    const c = catalogue(l);
    const missing = [
      ...REASON_CODES.map((x) => `ModelKit.reasons.${x}`),
      ...EVIDENCE_PARAMS.map((x) => `ModelKit.evParam.${x}`),
      ...PARAM_NAMES.map((x) => `ModelKit.param.${x}`),
      "ModelKit.param.clApparent",
      "ModelKit.param.vApparent",
      "ModelKit.param.fApparent",
      "ModelKit.models.one_compartment",
      "ModelKit.models.two_compartment",
      "ModelKit.errors.unavailable",
      "ModelKit.errors.unknown",
      "ModelKit.errors.invalidKey",
      ...SP_CLASSES.map((x) => `ModelKit.sp.class.${x}`),
      ...SP_GRADES.map((x) => `ModelKit.sp.grade.${x}`),
      ...["auc", "cmax"].map((x) => `ModelKit.sp.measure.${x}`),
      ...["auc", "cmax", "cl", "conc"].map(
        (x) => `ModelKit.sp.atlasMeasure.${x}`,
      ),
      ...TARGETS.map((x) => `ModelKit.dl.${x}`),
    ].filter((k) => !has(c, k));
    expect(missing).toEqual([]);
  });
  it("non-English text is not an English copy", () => {
    const en = catalogue("en");
    for (const l of routing.locales.filter((x) => x !== "en")) {
      const c = catalogue(l);
      for (const k of ["researchUse", "expertReview", "intro", "title"])
        expect((c.ModelKit as Tree)[k], `${l} ${k}`).not.toBe(
          (en.ModelKit as Tree)[k],
        );
    }
  });
});
