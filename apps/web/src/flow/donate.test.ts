// Feature: experience, Property P28 (donation request) and Property P14 (demo isolation, complete):
// a model-based run of demo actions makes no network request, writes nothing to the person's
// list or tokens, and cannot reach a write or loop route (Req 4.3, 4.4, 4.7, 20.2, 20.3, 20.8).
import { describe, expect, it } from "vitest";

import { evidenceBody, pairBody } from "@/api/builders";
import { AGE_BANDS } from "@/api/builders";
import { DemoClient, type Fixture } from "@/demo/client";
import { demoGtin13, detectDemo } from "@/demo/codes";
import cologne from "@/demo/fixtures/cologne.json";
import istanbul from "@/demo/fixtures/istanbul.json";
import ohio from "@/demo/fixtures/ohio.json";
import { readFragment } from "@/doctor/doctor";
import { makeQr } from "@/note/qr";
import { list } from "@/store/list";
import { tokens } from "@/store/tokens";
import { qid } from "@/test/arbitraries";
import { check, fc } from "@/test/fc";

import { donationRequest, type DonationForm } from "./donate";
import { parseLocator } from "./locator";

const formArb = fc.record({
  event: fc.option(
    fc.constantFrom("cough", "rash", "peripheral_oedema", "BAD KEY"),
    { nil: null },
  ),
  direction: fc.constantFrom("adverse" as const, "benefit" as const),
  ingredients: fc.array(qid, { maxLength: 25 }),
  ageBand: fc.option(
    fc.oneof(fc.constantFrom(...AGE_BANDS), fc.integer({ min: 0, max: 120 })),
    { nil: null },
  ),
  sex: fc.constantFrom("female" as const, "male" as const, null),
  region: fc.option(
    fc.constantFrom("TR" as const, "EU" as const, "US" as const),
    { nil: null },
  ),
  consent: fc.boolean(),
});

describe("P28 donation request", () => {
  it("exists only with consent, outside demo, with exactly the allowed fields", () => {
    check(
      fc.property(
        formArb,
        fc.uniqueArray(qid, { maxLength: 30 }),
        fc.boolean(),
        (form: DonationForm, listKeys, demo) => {
          const r = donationRequest(
            {
              ...form,
              ingredients: [...form.ingredients, ...listKeys.slice(0, 3)],
            },
            listKeys,
            demo,
          );
          if (demo) {
            expect(r).toEqual({ ok: false, reason: "demo" });
            return;
          }
          if (!form.consent) {
            expect(r).toEqual({ ok: false, reason: "consent" });
            return;
          }
          if (!r.ok) return;
          const b = r.body;
          expect(
            Object.keys(b).every((k) =>
              [
                "consent",
                "age_band",
                "sex",
                "region",
                "ingredients",
                "event",
                "direction",
              ].includes(k),
            ),
          ).toBe(true);
          expect(b.consent).toEqual({ version: "2026-11-v1", explicit: true });
          expect((AGE_BANDS as readonly number[]).includes(b.age_band)).toBe(
            true,
          );
          expect(b.age_band).toBeGreaterThanOrEqual(20);
          expect(["TR", "EU", "US"]).toContain(b.region);
          expect(b.ingredients.length).toBeGreaterThanOrEqual(1);
          expect(b.ingredients.length).toBeLessThanOrEqual(20);
          expect(new Set(b.ingredients).size).toBe(b.ingredients.length);
          for (const k of b.ingredients) expect(listKeys).toContain(k);
        },
      ),
    );
  });
});

const FIXTURES = { istanbul, cologne, ohio } as unknown as Record<
  string,
  Fixture
>;

describe("P14 demo isolation", () => {
  type Model = { patient: keyof typeof FIXTURES };
  type Real = { client: DemoClient; fetches: number };

  const commands = [
    fc.constantFrom("istanbul", "cologne", "ohio").map((p) => ({
      check: () => true,
      run: async (m: Model, r: Real) => {
        m.patient = p as Model["patient"];
        r.client = new DemoClient(FIXTURES[p]!);
      },
      toString: () => `pick ${p}`,
    })),
    fc.integer({ min: 1, max: 9 }).map((n) => ({
      check: () => true,
      run: async (_m: Model, r: Real) => {
        const ref = detectDemo(`(01)0${demoGtin13(n)}(21)DEMO1`);
        expect(ref).not.toBeNull();
        await r.client.resolveScan({ content: `(01)0${demoGtin13(n)}` });
      },
      toString: () => `scan demo code ${n}`,
    })),
    fc.constant({
      check: () => true,
      run: async (_m: Model, r: Real) => {
        const e = await r.client.evaluate(r.client.recordedEvaluateIn());
        expect(e.ok).toBe(true);
        if (!e.ok) return;
        for (const f of e.data.findings) {
          await r.client.resolveEvidence(
            evidenceBody([
              ...new Set([
                ...f.evidence_ids,
                ...f.excluded_evidence.map((x) => x.id),
              ]),
            ]),
          );
          const l = parseLocator(f.faers_locator);
          if (l)
            await r.client.memoryPair(pairBody(l.ingredient, l.event, "ALL"));
        }
        await r.client.memorySnapshot();
      },
      toString: () => "evaluate, open findings and memory",
    }),
    fc.constantFrom("en", "tr", "de").map((lang) => ({
      check: () => true,
      run: async (m: Model, r: Real) => {
        const n = await r.client.noteDocument({
          evaluation: r.client.recordedEvaluateIn(),
          languages: [lang],
        } as never);
        expect(n.ok).toBe(true);
        // the demo QR opens the demo doctor page; nothing is sent there
        const qr = makeQr(`https://janus.example/o#demo-${m.patient}`);
        expect(qr).not.toBeNull();
        expect(readFragment(`#demo-${m.patient}`).kind).toBe("demo");
      },
      toString: () => `note ${lang} + demo QR`,
    })),
    fc.constant({
      check: () => true,
      run: async (_m: Model, r: Real) => {
        expect(
          donationRequest(
            {
              event: "cough",
              direction: "adverse",
              ingredients: ["Q1"],
              ageBand: 70,
              sex: null,
              region: "TR",
              consent: true,
            },
            ["Q1"],
            true,
          ),
        ).toEqual({ ok: false, reason: "demo" });
        for (const m of [
          "noteToken",
          "withdraw",
          "outcomeForm",
          "outcomes",
          "contribute",
          "deleteContribution",
        ])
          expect(
            (r.client as unknown as Record<string, unknown>)[m],
          ).toBeUndefined();
      },
      toString: () => "donate / withdraw (unreachable)",
    }),
  ];

  it("makes no request and writes nothing to the person's list or tokens", async () => {
    const listBefore = JSON.stringify(list.get());
    const tokensBefore = JSON.stringify(tokens.get());
    const realFetch = globalThis.fetch;
    let fetches = 0;
    globalThis.fetch = (async () => {
      fetches++;
      throw new Error("no network in demo");
    }) as typeof fetch;
    try {
      await check(
        fc.asyncProperty(
          fc.commands(commands, { maxCommands: 12 }),
          async (cmds) => {
            const model: Model = { patient: "istanbul" };
            const real: Real = {
              client: new DemoClient(FIXTURES.istanbul!),
              fetches: 0,
            };
            await fc.asyncModelRun(() => ({ model, real }), cmds as never);
          },
        ),
        { numRuns: 40 },
      );
    } finally {
      globalThis.fetch = realFetch;
    }
    expect(fetches).toBe(0);
    expect(JSON.stringify(list.get())).toBe(listBefore);
    expect(JSON.stringify(tokens.get())).toBe(tokensBefore);
  });
});
