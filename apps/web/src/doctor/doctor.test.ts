// Feature: experience, Properties P26 (doctor page transport) and P27 (outcome answers).
import { describe, expect, it } from "vitest";

import * as D from "@/api/decode";
import istanbul from "@/demo/fixtures/istanbul.json";
import { check, fc } from "@/test/fc";

import {
  buildAnswers,
  canSend,
  doctorSession,
  NEEDS_MEDICINE,
  readFragment,
  type Answer,
} from "./doctor";

const form = (() => {
  const r = D.decode(D.outcomeFormOut, istanbul.doctorForm);
  if (!r.ok) throw new Error(r.path);
  return r.value;
})();

const tokenArb = fc.stringMatching(/^[A-Za-z0-9_-]{40,200}$/);
const fragmentArb = fc.oneof(
  tokenArb,
  fc.constantFrom(
    "demo-istanbul",
    "demo-ohio",
    "demo-cologne",
    "demo-x",
    "",
    "short",
  ),
  fc.string({ maxLength: 50 }),
);

describe("P26 doctor page transport", () => {
  it("sends the token only as {token} in a JSON body to the two outcome routes", async () => {
    await check(
      fc.asyncProperty(fragmentArb, async (frag) => {
        const calls: { url: string; init: RequestInit }[] = [];
        const fakeFetch = async (url: string, init: RequestInit) => {
          calls.push({ url, init });
          return new Response(
            JSON.stringify(
              url.endsWith("/form") ? istanbul.doctorForm : { stored: 1 },
            ),
          );
        };
        const s = doctorSession(`#${frag}`, fakeFetch);
        await s.form();
        await s.send([{ ref: 0, assessment: "confirmed" }]);
        const kind = readFragment(frag).kind;
        if (kind !== "token") {
          expect(calls).toEqual([]);
          return;
        }
        expect(calls.map((c) => c.url)).toEqual([
          "/api/outcomes/form",
          "/api/outcomes",
        ]);
        for (const c of calls) {
          expect(c.url).not.toContain(frag);
          expect(c.url).not.toContain("?");
          const body = JSON.parse(String(c.init.body));
          expect(body.token).toBe(frag);
          expect(c.init.credentials).toBe("omit");
          expect(c.init.referrerPolicy).toBe("no-referrer");
        }
        expect(Object.keys(JSON.parse(String(calls[0]!.init.body)))).toEqual([
          "token",
        ]);
      }),
    );
    expect(readFragment("#demo-istanbul")).toEqual({
      kind: "demo",
      patient: "istanbul",
    });
  });
});

describe("P27 outcome answers and the Send rule", () => {
  const answerArb = fc.record(
    {
      assessment: fc.constantFrom(
        "confirmed" as const,
        "not_a_cascade" as const,
      ),
      action: fc.constantFrom(
        "dose_changed" as const,
        "medicine_changed" as const,
        "stopped" as const,
        "no_change" as const,
      ),
      actionOn: fc.constantFrom("index" as const, "marker" as const),
    },
    { requiredKeys: [] },
  );
  it("leaves out unanswered findings, requires action_on exactly for dose/medicine/stop, enables Send iff ≥ 1 answer", () => {
    check(
      fc.property(
        fc.dictionary(
          fc.constantFrom(...form.findings.map((f) => String(f.ref))),
          answerArb,
        ),
        (dict) => {
          const state: Record<number, Answer> = Object.fromEntries(
            Object.entries(dict).map(([k, v]) => [Number(k), v]),
          );
          const built = buildAnswers(form, state);
          const incomplete = Object.values(state).some(
            (a) =>
              a.assessment &&
              a.action &&
              NEEDS_MEDICINE.has(a.action) &&
              !a.actionOn,
          );
          if (incomplete) {
            expect(built).toBeNull();
            expect(canSend(form, state)).toBe(false);
            return;
          }
          expect(built).not.toBeNull();
          const answered = Object.entries(state).filter(
            ([, a]) => a.assessment,
          ).length;
          expect(built!).toHaveLength(answered);
          expect(new Set(built!.map((a) => a.ref)).size).toBe(built!.length);
          for (const a of built!) {
            expect(a.ref).toBeLessThan(form.findings.length);
            expect("action_on" in a).toBe(
              !!a.action && NEEDS_MEDICINE.has(a.action),
            );
          }
          expect(canSend(form, state)).toBe(answered > 0);
        },
      ),
    );
  });
});
