// Feature: zombie-alert, Properties P1–P9 (design §5).
import { describe, expect, it } from "vitest";

import type { NoteOut } from "@/api/contracts";
import * as D from "@/api/decode";
import istanbul from "@/demo/fixtures/istanbul.json";
import { DEMO_CHANGE, DEMO_NOTICE } from "@/demo/zombie";
import { Doc, SafeStorage, type StorageLike } from "@/store/storage";
import { validateZombie, zombieDoc } from "@/store/zombie";
import { check, fc } from "@/test/fc";

import {
  changeKey,
  checkBody,
  diffNote,
  EMPTY,
  isDue,
  LIMIT,
  matchChanges,
  MAX_SEEN,
  MAX_SENTENCES,
  nextSince,
  watchNote,
  withoutEvidence,
  type ChangeLike,
  type ZombieDoc,
} from "./zombie";

const recorded = D.decode(D.noteOut, istanbul.notes.en);
if (!recorded.ok) throw new Error("fixture");
const NOTE: NoteOut = recorded.value;

const POOL = ["dataset:pipc", "rule:pipc:5", "paper:a:1", "paper:b:2", "x:y"];
const STATUS = [
  "ok",
  "corrected",
  "expression_of_concern",
  "retracted",
  "unknown",
] as const;

const idsArb = fc.uniqueArray(fc.constantFrom(...POOL), { maxLength: 4 });
const sentenceArb = (id: string) =>
  fc.record({
    type: fc.constant("sentence" as const),
    id: fc.constant(id),
    template: fc.constant("t"),
    kind: fc.constant("claim" as const),
    text: fc.string({ maxLength: 20 }),
    evidence_ids: idsArb,
    numbers: fc.constant([] as string[]),
  });
const noteArb: fc.Arbitrary<NoteOut> = fc
  .uniqueArray(fc.string({ minLength: 1, maxLength: 6 }), { maxLength: 8 })
  .chain((ids) => fc.tuple(...ids.map(sentenceArb)))
  .map((blocks) => ({
    ...NOTE,
    removals: [],
    documents: [
      {
        language: "en" as const,
        sections: [{ id: "findings" as const, heading: null, blocks }],
      },
    ],
  }));
const changeArb: fc.Arbitrary<ChangeLike> = fc.record({
  evidence_id: fc.oneof(fc.constantFrom(...POOL), fc.string()),
  title: fc.option(fc.string(), { nil: null }),
  doi: fc.option(fc.string(), { nil: null }),
  to_status: fc.constantFrom(...STATUS),
  observed_on: fc.constantFrom("2026-11-01", "2026-11-09"),
});
const docArb: fc.Arbitrary<ZombieDoc> = fc
  .tuple(noteArb, fc.array(fc.string(), { maxLength: 5 }))
  .map(([n, seen]) => ({
    ...EMPTY,
    note: watchNote(n, "2026-11-01"),
    seen,
  }));

describe("zombie-alert pure logic", () => {
  it("P1: the check body is a date and the limit, with no id or text", () => {
    check(
      fc.property(
        docArb,
        fc.option(fc.constant("2026-11-05"), { nil: null }),
        (doc, since) => {
          const body = checkBody({ ...doc, since });
          if (!doc.note!.ids.length) {
            expect(body).toBeNull();
            return;
          }
          expect(Object.keys(body!).sort()).toEqual(["limit", "since"]);
          expect(body!.limit).toBe(LIMIT);
          expect(body!.since).toBe(since ?? "2026-10-25"); // a week before the note (A6)
          const raw = JSON.stringify(body);
          for (const id of doc.note!.ids) expect(raw).not.toContain(id);
        },
      ),
    );
    const real = { ...EMPTY, note: watchNote(NOTE, "2026-11-08") };
    const raw = JSON.stringify(checkBody(real));
    for (const id of real.note.ids) expect(raw).not.toContain(id);
    for (const s of real.note.sentences) expect(raw).not.toContain(s.text);
    for (const it of istanbul.items) expect(raw).not.toContain(it.boxName);
  });

  it("P2, P3: alert iff a cited id changed to retracted with an unseen key", () => {
    check(
      fc.property(docArb, fc.array(changeArb, { maxLength: 8 }), (doc, cs) => {
        const { alerts } = matchChanges(doc, cs);
        const cited = new Set(doc.note!.ids);
        for (const a of alerts) expect(cited.has(a.evidenceId)).toBe(true);
        const expected = new Set(
          cs
            .filter(
              (c) =>
                cited.has(c.evidence_id) &&
                c.to_status === "retracted" &&
                !doc.seen.includes(changeKey(c)),
            )
            .map(changeKey),
        );
        expect(new Set(alerts.map((a) => a.key))).toEqual(expected);
        expect(alerts.length).toBe(expected.size);
      }),
    );
  });

  it("P4: the same change never alerts twice; seen grows", () => {
    check(
      fc.property(docArb, fc.array(changeArb, { maxLength: 8 }), (doc, cs) => {
        const first = matchChanges(doc, [...cs, ...cs]);
        const next = { ...doc, seen: first.seen };
        expect(matchChanges(next, cs).alerts).toEqual([]);
        expect(matchChanges(next, [...cs].reverse()).alerts).toEqual([]);
        for (const k of doc.seen.slice(-MAX_SEEN))
          expect(first.seen).toContain(k);
      }),
    );
  });

  it("P5: a truncated answer moves since to its oldest date only", () => {
    check(
      fc.property(
        fc.array(changeArb, { minLength: 1, maxLength: 5 }),
        fc.boolean(),
        (cs, full) => {
          const list = full
            ? Array.from({ length: LIMIT }, (_, i) => cs[i % cs.length]!)
            : cs.slice(0, LIMIT - 1);
          const next = nextSince({ as_of: "2026-11-10", changes: list });
          if (!full) expect(next).toBe("2026-11-10");
          else expect(next).toBe(list.map((c) => c.observed_on).sort()[0]);
        },
      ),
    );
  });

  it("P6: any stored value validates or is rejected, never throws; failing storage keeps working", () => {
    check(
      fc.property(fc.jsonValue(), (v) => {
        expect(() => validateZombie(v)).not.toThrow();
      }),
    );
    check(
      fc.property(docArb, (doc) => {
        expect(validateZombie(JSON.parse(JSON.stringify(doc)))).toEqual(doc);
        expect(validateZombie({ ...doc, v: 2 })).toBeNull();
      }),
    );
    const throwing: StorageLike = {
      getItem: () => {
        throw new Error("SecurityError");
      },
      setItem: () => {
        throw new DOMException("full", "QuotaExceededError");
      },
      removeItem: () => {
        throw new Error("SecurityError");
      },
      length: 0,
      key: () => null,
    };
    const d: Doc<ZombieDoc> = zombieDoc(new SafeStorage(() => throwing));
    expect(d.get()).toEqual(EMPTY);
    d.update((z) => ({ ...z, notify: true }));
    expect(d.get().notify).toBe(true);
    const corrupt = new SafeStorage(() => ({
      ...throwing,
      getItem: () => "{not json",
      setItem: () => {},
      removeItem: () => {},
    }));
    expect(zombieDoc(corrupt).get()).toEqual(EMPTY);
  });

  it("P7: diff lists exactly the sentences that cited a changed id", () => {
    check(
      fc.property(noteArb, noteArb, idsArb, (a, b, changed) => {
        const before = watchNote(a, "2026-11-01").sentences;
        const after = new Map(
          b.documents[0]!.sections[0]!.blocks.map((s) => [
            (s as { id: string }).id,
            s as { text: string; evidence_ids: string[] },
          ]),
        );
        const d = diffNote(before, b, changed);
        const listed = [...d.removed, ...d.changed.map((c) => c.before)];
        for (const s of listed)
          expect(s.ids.some((i) => changed.includes(i))).toBe(true);
        for (const s of d.removed) expect(after.has(s.id)).toBe(false);
        for (const c of d.changed) {
          expect(after.has(c.before.id)).toBe(true);
          expect(
            c.after.text !== c.before.text ||
              c.after.ids.join() !== c.before.ids.join(),
          ).toBe(true);
        }
        for (const s of before)
          if (s.ids.some((i) => changed.includes(i)) && !after.has(s.id))
            expect(d.removed).toContainEqual(s);
      }),
    );
  });

  it("P8: withoutEvidence keeps only citable ids and drops emptied sentences", () => {
    check(
      fc.property(noteArb, idsArb, (n, gone) => {
        const out = withoutEvidence(n, gone);
        const before = n.documents[0]!.sections[0]!.blocks as {
          id: string;
          evidence_ids: string[];
        }[];
        const after = out.documents[0]!.sections[0]!.blocks as {
          id: string;
          evidence_ids: string[];
        }[];
        for (const s of after)
          for (const id of s.evidence_ids) expect(gone).not.toContain(id);
        const dropped = before.filter(
          (s) =>
            s.evidence_ids.length &&
            s.evidence_ids.every((i) => gone.includes(i)),
        );
        expect(after.length).toBe(before.length - dropped.length);
        expect(out.removals.map((r) => r.sentence_id)).toEqual(
          dropped.map((s) => s.id),
        );
        for (const s of after) expect(before.map((b) => b.id)).toContain(s.id);
      }),
    );
  });

  it("P9: bounds and distinct cited ids", () => {
    check(
      fc.property(noteArb, (n) => {
        const w = watchNote(n, "2026-11-01");
        expect(new Set(w.ids).size).toBe(w.ids.length);
        expect(w.sentences.length).toBeLessThanOrEqual(MAX_SENTENCES);
      }),
    );
    const many = Array.from({ length: MAX_SEEN + 50 }, (_, i) => `k${i}`);
    const doc = { ...EMPTY, note: watchNote(NOTE, "2026-11-01"), seen: many };
    const r = matchChanges(doc, [DEMO_CHANGE]);
    expect(r.seen.length).toBe(MAX_SEEN);
    expect(r.seen.at(-1)).toBe(changeKey(DEMO_CHANGE));
  });

  it("demo: one alert, then the recorded note loses exactly the supporting line", () => {
    const doc = { ...EMPTY, note: watchNote(NOTE, "2026-11-08") };
    expect(doc.note.ids).toContain(DEMO_CHANGE.evidence_id);
    const first = matchChanges(doc, [DEMO_CHANGE], true);
    expect(first.alerts).toHaveLength(1);
    expect(
      matchChanges({ ...doc, seen: first.seen }, [DEMO_CHANGE], true).alerts,
    ).toEqual([]);
    const after = withoutEvidence(NOTE, [DEMO_CHANGE.evidence_id]);
    expect(D.decode(D.noteOut, after).ok).toBe(true);
    const d = diffNote(doc.note.sentences, after, [DEMO_CHANGE.evidence_id]);
    expect(d.removed.map((s) => s.id)).toEqual([
      "pipc:5:Q411347:Q388801:supporting",
    ]);
    expect(d.changed).toEqual([]);
    expect(DEMO_NOTICE.doi!.startsWith("10.5555/")).toBe(true);
  });

  it("isDue", () => {
    expect(isDue(null, 0, 1)).toBe(true);
    expect(isDue(1000, 1500, 1000)).toBe(false);
    expect(isDue(1000, 2000, 1000)).toBe(true);
    expect(isDue(5000, 1000, 1000)).toBe(true); // clock went back
  });
});
