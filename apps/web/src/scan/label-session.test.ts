// Feature: ocr-first, Property P5: a label result never confirms or sends anything by itself.
// Only a choice of the user gives a request, and the request is the English name of the chosen
// ingredient, the chosen NDC or exactly the chosen adjacent words — never label text the user
// did not choose (Req 2.3–2.5; experience Req 11.2, P22).
import { describe, expect, it } from "vitest";

import { startDemo, exitDemo } from "@/demo/session";
import { setPending, type Pending } from "@/flow/pending";
import { deleteEverything } from "@/store/hooks";
import { check, fc } from "@/test/fc";

import type { IngredientCandidate } from "./ingredient-match";
import {
  dispatchLabel,
  labelResult,
  labelState,
  outboundOf,
  reduce,
  type Choice,
  type LabelAction,
  type LabelResult,
  type LabelState,
} from "./label-session";

const ENGLISH = { Q1: "amlodipine", Q2: "valsartan", Q3: "metformin" };
const candidate = fc.record<IngredientCandidate>({
  key: fc.constantFrom("Q1", "Q2", "Q3", "Q404", "toString", "__proto__"),
  strength: fc.constantFrom("exact", "variant", "close"),
  distance: fc.integer({ min: 0, max: 2 }),
  written: fc.constantFrom("ZZJANE DOE", "Amlodipin besilat", "DR ZZSMITH"),
});
const result = fc.record<LabelResult>({
  candidates: fc.array(candidate, { maxLength: 5 }),
  ndcs: fc.array(fc.constantFrom("0295-2680-01", "12345-678-90"), {
    maxLength: 2,
  }),
  words: fc.array(
    fc.constantFrom("PATIENT", "ZZJANE", "DOE", "Amlodipin", "besilat", "x"),
    { maxLength: 8 },
  ),
});
const action: fc.Arbitrary<LabelAction> = fc.oneof(
  fc.constant({ type: "start" as const }),
  fc.record({
    type: fc.constant("progress" as const),
    progress: fc.double({ min: 0, max: 1, noNaN: true }),
    turned: fc.boolean(),
  }),
  result.map((r) => ({ type: "read" as const, result: r })),
  fc.constant({ type: "failed" as const }),
  fc.constant({ type: "clear" as const }),
);
const choice: fc.Arbitrary<Choice> = fc.oneof(
  fc.record({
    kind: fc.constant("ingredient" as const),
    index: fc.oneof(fc.integer({ min: -2, max: 6 }), fc.double()),
  }),
  fc.record({
    kind: fc.constant("ndc" as const),
    index: fc.integer({ min: -2, max: 3 }),
  }),
  fc.record({
    kind: fc.constant("words" as const),
    selected: fc.array(fc.integer({ min: -1, max: 9 }), { maxLength: 4 }),
  }),
);
const run = (actions: readonly LabelAction[]) =>
  actions.reduce<LabelState>(reduce, { kind: "idle" });

describe("P5 a candidate is never confirmed without the user", () => {
  it("no state after any reading holds a choice or a request", () => {
    check(
      fc.property(fc.array(action, { maxLength: 12 }), (actions) => {
        const state = run(actions);
        const text = JSON.stringify(state);
        expect(text).not.toMatch(/chosen|selected|confirmed|outbound|query/);
        expect(Object.keys(state).sort()).toEqual(
          state.kind === "done"
            ? ["kind", "result"]
            : state.kind === "busy"
              ? ["kind", "progress", "turned"]
              : ["kind"],
        );
      }),
    );
  });

  it("a request needs a valid choice in a finished reading and is only what was chosen", () => {
    check(
      fc.property(fc.array(action, { maxLength: 8 }), choice, (actions, ch) => {
        const state = run(actions);
        const out = outboundOf(state, ch, ENGLISH);
        if (state.kind !== "done") {
          expect(out).toBeNull();
          return;
        }
        const r = state.result;
        if (ch.kind === "ingredient") {
          const c = r.candidates[ch.index];
          const name = c && (ENGLISH as Record<string, string>)[c.key];
          if (!c || !["Q1", "Q2", "Q3"].includes(c.key)) {
            expect(out).toBeNull();
            return;
          }
          // The request is the held English name, never the printed text.
          expect(out).toEqual({ kind: "search", query: name, key: c.key });
        } else if (ch.kind === "ndc") {
          expect(out).toEqual(
            r.ndcs[ch.index] ? { kind: "ndc", ndc: r.ndcs[ch.index] } : null,
          );
        } else if (out) {
          expect(out.kind).toBe("search");
          if (out.kind !== "search") return;
          expect(out.key).toBeNull();
          const sorted = [...new Set(ch.selected)].sort((a, b) => a - b);
          expect(out.query).toBe(
            sorted
              .map((i) => r.words[i])
              .join(" ")
              .trim(),
          );
        }
      }),
    );
  });

  it("a reading without words is 'nothing recognised'; a reading is only taken while busy", () => {
    const empty: LabelResult = { candidates: [], ndcs: [], words: [] };
    const some: LabelResult = { candidates: [], ndcs: [], words: ["Zzq"] };
    expect(run([{ type: "start" }, { type: "read", result: empty }])).toEqual({
      kind: "none",
    });
    expect(run([{ type: "start" }, { type: "read", result: some }])).toEqual({
      kind: "done",
      result: some,
    });
    expect(run([{ type: "read", result: some }])).toEqual({ kind: "idle" });
    expect(run([{ type: "start" }, { type: "failed" }])).toEqual({
      kind: "failed",
    });
    expect(
      run([
        { type: "start" },
        { type: "read", result: some },
        { type: "clear" },
      ]),
    ).toEqual({ kind: "idle" });
  });

  it("builds the result from the recognised lines: candidates, NDC shapes, words", () => {
    const r = labelResult(
      {
        confidence: 90,
        lines: [
          { text: "PATIENT ZZJANE DOE", words: ["PATIENT", "ZZJANE", "DOE"] },
          { text: "NDC 0295-2680-01", words: ["NDC", "0295-2680-01"] },
        ],
      },
      (lines) => [
        { key: "Q1", strength: "exact", distance: 0, written: lines[0]! },
      ],
    );
    expect(r.ndcs).toEqual(["0295-2680-01"]);
    expect(r.words).toEqual([
      "PATIENT",
      "ZZJANE",
      "DOE",
      "NDC",
      "0295-2680-01",
    ]);
    expect(r.candidates).toHaveLength(1);
  });

  it("is cleared by 'delete everything on this device' and when the demo starts (Req 6.2)", async () => {
    const some: LabelResult = {
      candidates: [],
      ndcs: [],
      words: ["PATIENT", "ZZJANE", "DOE"],
    };
    const fill = () => {
      dispatchLabel({ type: "start" });
      dispatchLabel({ type: "read", result: some });
      expect(labelState().kind).toBe("done");
    };
    fill();
    setPending({ prefer: "Q1" } as Pending);
    await deleteEverything();
    expect(labelState()).toEqual({ kind: "idle" });
    fill();
    startDemo("istanbul");
    expect(labelState()).toEqual({ kind: "idle" });
    exitDemo();
  });
});
