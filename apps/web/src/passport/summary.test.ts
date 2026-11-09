// Feature: experience, Property P31: the passport summary counts `present` answers over the
// answers whose source was checked; it never claims more listings than checked sources, and there
// is no summary when no source was checked (Req 29.2).
import { describe, expect, it } from "vitest";

import { check, fc } from "@/test/fc";

import { STATUSES } from "./model";
import { presenceSummary } from "./summary";

const answers = fc.array(fc.record({ status: fc.constantFrom(...STATUSES) }), {
  minLength: 5,
  maxLength: 5,
});

describe("presence summary (P31)", () => {
  it("listed ≤ checked ≤ 5, counted from the statuses", () => {
    check(
      fc.property(answers, (a) => {
        const s = presenceSummary({ answers: a } as never);
        const checked = a.filter(
          (x) => x.status !== "source_unavailable",
        ).length;
        if (checked === 0) {
          expect(s).toBeNull();
          return;
        }
        expect(s).not.toBeNull();
        expect(s!.checked).toBe(checked);
        expect(s!.listed).toBe(a.filter((x) => x.status === "present").length);
        expect(s!.listed).toBeLessThanOrEqual(s!.checked);
        expect(s!.checked).toBeLessThanOrEqual(5);
      }),
    );
  });
});
