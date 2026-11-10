// Feature: medication-passport, Properties P1, P2, P18, P20, P21 and the contract mirror
// (tasks 9.1–9.5). Validates Req 1.2–1.6, 4.3, 6.7, 9.1, 11.1, 11.2.
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { check, fc } from "@/test/fc";

import { listArb } from "./arbitraries";
import { duplicateGroups, isChecked } from "./duplicates";
import { strengthFromEntry } from "./entry";
import { itemIdentity, itemKeys } from "./identity";
import { memoryKeys, memoryRequests } from "./memory-keys";
import { addItem, earlierMonth, mergeLists } from "./merge";
import * as M from "./model";
import {
  buildPresenceRequests,
  fanBack,
  notSentReason,
  type BuiltRequests,
} from "./request";

const fixture = (name: string): unknown =>
  JSON.parse(readFileSync(join(import.meta.dirname, "fixtures", name), "utf8"));

const shuffled = <T>(xs: readonly T[]) =>
  fc.shuffledSubarray([...xs], { minLength: xs.length, maxLength: xs.length });

describe("contract mirror (types of schemas.py)", () => {
  const lit = fixture("schema-literals.json") as Record<string, unknown>;
  it("has the closed sets and limits of the server", () => {
    expect({
      status: [...M.STATUSES],
      result: [...M.RESULTS],
      cmp_reason: [...M.CMP_REASONS],
      notice: [...M.NOTICES],
      source_id: [...M.SOURCE_IDS],
      form_group: [...M.FORM_GROUPS],
      countable_groups: [...M.COUNTABLE_GROUPS],
      region: [...M.SOURCE_REGIONS],
      country: [...M.SOURCE_COUNTRIES],
      unavailable_reason: [...M.UNAVAILABLE_REASONS],
      attribution: [...M.ATTRIBUTIONS],
      unit: [...M.UNITS],
      basis: [...M.BASES],
      key_pattern: M.KEY.source,
      amount_pattern: M.AMOUNT.source,
      max_items: M.MAX_ITEMS,
      max_ingredients: M.MAX_INGREDIENTS,
      max_keys: M.MAX_KEYS,
    }).toEqual(
      Object.fromEntries(
        Object.entries(lit).filter(
          ([k]) =>
            ![
              "source_status",
              "not_compared_groups",
              "disclaimer",
              // the product list's sets are checked in products.test.tsx
              "listable_source_id",
              "level",
              "level_reason",
              "marketed",
              "listing_notice",
              "max_page",
              "max_offset",
            ].includes(k),
        ),
      ),
    );
    expect(lit.source_status).toEqual(["loaded", "source_unavailable"]);
  });
});

describe("P1 merge", () => {
  const normal = (l: M.PassportItem[]) => mergeLists(l, []);

  it("is commutative and associative", () => {
    check(
      fc.property(listArb("a"), listArb("b"), listArb("c"), (a, b, c) => {
        expect(mergeLists(a, b)).toEqual(mergeLists(b, a));
        expect(mergeLists(mergeLists(a, b), c)).toEqual(
          mergeLists(a, mergeLists(b, c)),
        );
      }),
    );
  });

  it("does not depend on the order in which items were added", () => {
    check(
      fc.property(
        listArb("a").chain((l) => fc.tuple(fc.constant(l), shuffled(l))),
        ([l, s]) => {
          expect(normal(s)).toEqual(normal(l));
        },
      ),
    );
  });

  it("is idempotent but for box counts, and keeps one item per identity", () => {
    check(
      fc.property(listArb("a"), (raw) => {
        const a = normal(raw);
        const ids = a.map(itemIdentity);
        expect(new Set(ids).size).toBe(ids.length);
        const aa = mergeLists(a, a);
        expect(aa.map((i) => ({ ...i, boxes: i.boxes / 2 }))).toEqual(a);
      }),
    );
  });

  it("adding an item already present changes only its box count", () => {
    check(
      fc.property(
        listArb("a")
          .map((l) => mergeLists(l, []))
          .filter((l) => l.length > 0)
          .chain((l) =>
            fc.tuple(fc.constant(l), fc.nat({ max: l.length - 1 })),
          ),
        ([a, n]) => {
          const x = a[n]!;
          const after = addItem(a, x);
          expect(after).toEqual(
            a.map((i) => (i === x ? { ...i, boxes: i.boxes * 2 } : i)),
          );
        },
      ),
    );
  });

  it("sums box counts and keeps the earliest known start month", () => {
    check(
      fc.property(listArb("a"), listArb("b"), (a, b) => {
        const merged = mergeLists(a, b);
        const all = [...a, ...b];
        expect(merged.reduce((s, i) => s + i.boxes, 0)).toBe(
          all.reduce((s, i) => s + i.boxes, 0),
        );
        for (const m of merged) {
          const same = all.filter((i) => itemIdentity(i) === itemIdentity(m));
          expect(m.started).toBe(
            same.reduce<string | null>(
              (s, i) => earlierMonth(s, i.started),
              null,
            ),
          );
        }
      }),
    );
  });
});

describe("P2 duplicate groups", () => {
  it("groups two distinct items iff both are checked and share a key; changes nothing", () => {
    check(
      fc.property(listArb("a"), (raw) => {
        const list = mergeLists(raw, []);
        const before = structuredClone(list);
        const groups = duplicateGroups(list);
        expect(list).toEqual(before);
        for (const x of list)
          for (const y of list) {
            if (x.id === y.id) continue;
            const shared = itemKeys(x).filter((k) => itemKeys(y).includes(k));
            const together = groups.some(
              (g) => g.items.includes(x.id) && g.items.includes(y.id),
            );
            expect(together).toBe(
              isChecked(x) && isChecked(y) && shared.length > 0,
            );
          }
        for (const g of groups)
          expect(g.items).toEqual(
            list
              .filter((i) => isChecked(i) && itemKeys(i).includes(g.key))
              .map((i) => i.id)
              .sort(),
          );
      }),
    );
  });

  it("never makes a group from a key repeated inside one item", () => {
    const item: M.PassportItem = {
      id: "x",
      demo: false,
      origin: { region: "TR", country: "TR" },
      source: { source_id: "titck", snapshot_date: "2026-11-06" },
      code: null,
      boxName: "Two salt lines",
      ingredients: ["5000", "40000"].map((amount) => ({
        key: "Q1",
        label: "x",
        status: "mapped" as const,
        strength: { amount, unit: "ug" as const, basis: "unit" as const },
        strengthOrigin: "source" as const,
      })),
      doseForm: null,
      homeopathic: false,
      boxes: 1,
      started: null,
    };
    expect(duplicateGroups([item])).toEqual([]);
    expect(
      duplicateGroups([item, { ...item, id: "y", boxName: "Other" }]),
    ).toEqual([{ key: "Q1", items: ["x", "y"] }]);
    expect(
      duplicateGroups([
        item,
        { ...item, id: "y", boxName: "H", homeopathic: true },
      ]),
    ).toEqual([]);
  });
});

/** Every string value and every key of a JSON value. */
function strings(v: unknown): string[] {
  if (typeof v === "string") return [v];
  if (Array.isArray(v)) return v.flatMap(strings);
  if (v && typeof v === "object")
    return Object.entries(v).flatMap(([k, x]) => [k, ...strings(x)]);
  return [];
}

const ALLOWED_FIELDS = [
  "items",
  "ingredients",
  "key",
  "strength",
  "amount",
  "unit",
  "basis",
  "dose_form",
];

/** A response the server could give to `body` (only the shape matters for the fan-back). */
function fakeOut(body: M.PresenceIn): M.PresenceOut {
  return {
    dataset_version: "0".repeat(64),
    form_table_version: "1".repeat(64),
    sources: [],
    items: body.items.map((it, i) => ({
      item: i,
      keys: it.ingredients.map((g) => g.key).sort(),
      unknown_keys: [],
      answers: [],
    })),
    notices: ["presence_is_lower_bound"],
    disclaimer: "x",
  };
}

describe("P18 request content", () => {
  const big = {
    keys: fc.integer({ min: 1, max: 160 }).map((n) => `Q${n}`),
    names: fc.string({ minLength: 1, maxLength: 8 }).map((s) => `ZZBOX${s}`),
    max: 140,
  };
  const lists = fc.oneof(listArb("s"), listArb("b", big));

  it("holds only keys, codes and form groups, within the limits", () => {
    check(
      fc.property(lists, (raw) => {
        const list = mergeLists(raw, []);
        const built = buildPresenceRequests(list);
        const text = JSON.stringify(built.bodies);
        for (const item of list) {
          expect(text).not.toContain(item.boxName);
          expect(text).not.toContain(`"${item.id}"`);
        }
        for (const s of strings(built.bodies))
          expect(
            ALLOWED_FIELDS.includes(s) ||
              M.KEY.test(s) ||
              M.AMOUNT.test(s) ||
              (M.UNITS as readonly string[]).includes(s) ||
              (M.BASES as readonly string[]).includes(s) ||
              (M.FORM_GROUPS as readonly string[]).includes(s),
            s,
          ).toBe(true);
        for (const body of built.bodies) {
          expect(body.items.length).toBeGreaterThanOrEqual(1);
          expect(body.items.length).toBeLessThanOrEqual(M.MAX_ITEMS);
          const keys = new Set(
            body.items.flatMap((i) => i.ingredients.map((g) => g.key)),
          );
          expect(keys.size).toBeLessThanOrEqual(M.MAX_KEYS);
          for (const it of body.items) {
            const k = it.ingredients.map((g) => g.key);
            expect(k.length).toBeGreaterThanOrEqual(1);
            expect(k.length).toBeLessThanOrEqual(M.MAX_INGREDIENTS);
            expect(new Set(k).size).toBe(k.length);
            expect(k).toEqual([...k].sort());
          }
          // identical queries are sent once
          const q = body.items.map((i) => JSON.stringify(i));
          expect(new Set(q).size).toBe(q.length);
        }
      }),
    );
  });

  it("covers exactly the sendable items and fans every answer back", () => {
    check(
      fc.property(lists, (raw) => {
        const list = mergeLists(raw, []);
        const built: BuiltRequests = buildPresenceRequests(list);
        const answers = fanBack(built, built.bodies.map(fakeOut));
        for (const item of list) {
          const reason = notSentReason(item);
          expect(built.notSent.get(item.id) ?? null).toBe(reason);
          if (reason) expect(answers.has(item.id)).toBe(false);
          else expect(answers.get(item.id)?.item.keys).toEqual(itemKeys(item));
        }
      }),
    );
  });

  it("leaves out homeopathic, keyless and partly recognised items", () => {
    check(
      fc.property(listArb("a"), (raw) => {
        for (const item of raw) {
          const r = notSentReason(item);
          if (item.homeopathic) expect(r).toBe("homeopathic");
          else if (itemKeys(item).length === 0) expect(r).toBe("no_key");
          else if (item.ingredients.some((i) => !i.key))
            expect(r).toBe("partial");
          else expect(r).toBeNull();
        }
      }),
    );
  });
});

describe("P20 memory keys", () => {
  it("are the sorted distinct checked keys; order, counts and repeats change nothing", () => {
    check(
      fc.property(
        listArb("a").chain((l) => fc.tuple(fc.constant(l), shuffled(l))),
        ([l, s]) => {
          const keys = memoryKeys(l);
          expect(keys).toEqual([...new Set(keys)].sort());
          expect(keys).toEqual(
            [...new Set(l.filter(isChecked).flatMap(itemKeys))].sort(),
          );
          const doubled = [...s, ...s].map((i) => ({
            ...i,
            boxes: i.boxes + 1,
          }));
          expect(memoryKeys(doubled)).toEqual(keys);
          expect(memoryRequests(doubled)).toEqual(memoryRequests(l));
        },
      ),
    );
  });

  it("builds no request above 20 keys without the user's selection", () => {
    const big = {
      keys: fc.integer({ min: 1, max: 60 }).map((n) => `Q${n}`),
      max: 40,
    };
    check(
      fc.property(
        listArb("a", big),
        fc.array(fc.integer({ min: 1, max: 60 })),
        (l, pick) => {
          const keys = memoryKeys(l);
          const r = memoryRequests(l);
          if (keys.length > 20) {
            expect(r).toEqual({ kind: "needs_selection", keys });
            const chosen = [...new Set(pick.map((n) => `Q${n}`))].filter((k) =>
              keys.includes(k),
            );
            const s = memoryRequests(
              l,
              pick.map((n) => `Q${n}`),
            );
            if (chosen.length >= 1 && chosen.length <= 20) {
              expect(s.kind).toBe("ready");
              if (s.kind === "ready") expect(s.keys).toEqual(chosen.sort());
            } else expect(s.kind).toBe("needs_selection");
          } else if (keys.length === 0) expect(r).toEqual({ kind: "none" });
          else {
            expect(r.kind).toBe("ready");
            if (r.kind !== "ready") return;
            expect(r.regions).toEqual({ ingredients: keys });
            expect(r.combination).toEqual(
              keys.length >= 2 ? { ingredients: keys, scope: "any" } : null,
            );
          }
        },
      ),
    );
  });
});

describe("P21 entry parity with the Python rule", () => {
  const cases = fixture("entry-cases.json") as {
    amount: string;
    unit: string;
    basis: string;
    code: M.StrengthCode | null;
  }[];
  it("gives the code of entry_code for each of the 500 shared cases", () => {
    expect(cases.length).toBe(500);
    for (const c of cases)
      expect(
        strengthFromEntry(c.amount, c.unit, c.basis),
        JSON.stringify(c),
      ).toEqual(c.code);
  });
  it("converts exactly and refuses ambiguous thousands groups", () => {
    check(
      fc.property(fc.integer({ min: 1, max: 999_999 }), (mg) => {
        expect(strengthFromEntry(String(mg), "mg", "unit")).toEqual({
          amount: String(mg * 1000),
          unit: "ug",
          basis: "unit",
        });
      }),
    );
    expect(strengthFromEntry("1,000", "mg", "unit")).toBeNull();
    expect(strengthFromEntry("1.000", "mg", "unit")).toBeNull();
    expect(strengthFromEntry("0,125", "mg", "unit")?.amount).toBe("125");
    expect(strengthFromEntry("2,5", "mg", "mL")).toEqual({
      amount: "2500",
      unit: "ug",
      basis: "mL",
    });
  });
});

describe("fromListItem (experience store → Passport item)", () => {
  it("keeps the region, the source and date, the keys and the strength codes", async () => {
    const { demoItems } = await import("@/demo/client");
    const ist = (await import("@/demo/fixtures/istanbul.json")).default;
    const col = (await import("@/demo/fixtures/cologne.json")).default;
    for (const f of [ist, col]) {
      const items = demoItems(f as never).map((i) =>
        M.fromListItem(i, (k, p) => k ?? p, true),
      );
      for (const [i, item] of items.entries()) {
        const c = demoItems(f as never)[i]!.candidate;
        expect(item.demo).toBe(true);
        if (c.kind === "ingredient") {
          expect(item.source).toEqual({ entered_by_name: true });
          expect(itemKeys(item)).toEqual([c.ingredient_key.qid]);
        } else {
          expect(item.origin.region).toBe(c.region);
          expect(item.source).toEqual({
            source_id: c.source.source_id,
            snapshot_date: c.source.snapshot_date,
          });
        }
      }
      if (f === ist)
        expect(items.some((i) => itemKeys(i).length === 2)).toBe(true);
    }
  });
});
