// Feature: ocr-first, Property P8: the photo is read turned only when the upright reading names
// nothing and is not confident; a useful reading is always the one returned (Req 4.3).
import { describe, expect, it } from "vitest";

import { check, fc } from "@/test/fc";

import { readLabel, RETRY_BELOW, type Pass, type Turns } from "./ocr-passes";

const pass = fc.record({
  confidence: fc.integer({ min: 0, max: 100 }),
  useful: fc.boolean(),
});

describe("P8 which reading is used", () => {
  it("reads upright first, turns only when needed, and returns a useful reading if there is one", async () => {
    await check(
      fc.asyncProperty(fc.tuple(pass, pass, pass, pass), async (passes) => {
        const asked: Turns[] = [];
        const made = new Map<Pass, { turns: Turns; useful: boolean }>();
        const got = await readLabel(
          async (turns) => {
            asked.push(turns);
            const p: Pass = {
              confidence: passes[turns]!.confidence,
              lines: [],
            };
            made.set(p, { turns, useful: passes[turns]!.useful });
            return p;
          },
          (p) => made.get(p)!.useful,
        );
        const upright = passes[0]!;
        expect(asked[0]).toBe(0);
        expect(new Set(asked).size).toBe(asked.length);
        if (upright.useful || upright.confidence >= RETRY_BELOW) {
          expect(asked).toEqual([0]);
          expect(made.get(got)!.turns).toBe(0);
          return;
        }
        const firstUseful = ([1, 3, 2] as const).find((t) => passes[t]!.useful);
        if (firstUseful !== undefined) {
          expect(made.get(got)!.turns).toBe(firstUseful);
          expect(asked.at(-1)).toBe(firstUseful);
        } else {
          expect(asked).toEqual([0, 1, 3, 2]);
          expect(got.confidence).toBe(
            Math.max(...passes.map((p) => p.confidence)),
          );
        }
      }),
    );
  });
});
