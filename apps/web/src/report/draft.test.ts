// Feature: report-assistant, Properties P1, P3–P7, P9, P10 (design §5).
import { afterEach, describe, expect, it, vi } from "vitest";

import { check, fc } from "@/test/fc";

import { CHANNELS, fieldList, formChannels } from "./channels";
import {
  buildDraft,
  copyAll,
  mappingFor,
  medicineValue,
  outcomeOptions,
  type DraftInput,
} from "./draft";
import { MAPPINGS } from "./mapping";

const forms = CHANNELS.filter((c) =>
  ["online", "pdf", "document", "guidance"].includes(c.kind),
);
const text = fc.string({ maxLength: 40 });
const inputArb: fc.Arbitrary<DraftInput> = fc.record({
  channel: fc.constantFrom(...forms),
  demo: fc.boolean(),
  hcp: fc.boolean(),
  medicine: fc.record({ box: text, ingredient: text }),
  event: text,
  onset: fc.option(
    fc
      .tuple(
        fc.integer({ min: 1990, max: 2026 }),
        fc.integer({ min: 1, max: 12 }),
      )
      .map(([y, m]) => `${y}-${String(m).padStart(2, "0")}`),
    { nil: null },
  ),
  outcome: fc.record({
    option: fc.option(fc.integer({ min: 0, max: 7 }), { nil: null }),
    text,
  }),
  others: fc.array(fc.record({ label: text, ticked: fc.boolean() }), {
    maxLength: 6,
  }),
});
const janus = (k: string) => `[${k}]`;
const DEMO = "Demo · synthetic patient — do not submit";

afterEach(() => vi.unstubAllGlobals());

describe("report draft", () => {
  it("P1: every native label is in the channel's verified field list", () => {
    check(
      fc.property(inputArb, (input) => {
        const d = buildDraft(input);
        const fl = fieldList(input.channel);
        for (const r of d.rows) {
          if (r.label === null) continue;
          expect(fl).not.toBeNull();
          expect(fl!.source.fields).toContain(r.label);
          expect(["verified", "derived"]).toContain(fl!.source.fieldsStatus);
        }
        if (!fl) expect(d.rows.every((r) => r.label === null)).toBe(true);
      }),
    );
  });

  it("P3: building a draft sends and stores nothing", () => {
    const spy = vi.fn(() => {
      throw new Error("network or storage used");
    });
    vi.stubGlobal("fetch", spy);
    vi.stubGlobal("XMLHttpRequest", spy);
    vi.stubGlobal("navigator", { sendBeacon: spy });
    vi.stubGlobal("localStorage", { setItem: spy, getItem: spy });
    vi.stubGlobal("sessionStorage", { setItem: spy, getItem: spy });
    check(
      fc.property(inputArb, (input) => {
        copyAll(buildDraft(input), DEMO, janus);
      }),
    );
    expect(spy).not.toHaveBeenCalled();
  });

  it("P4: the demo line is there iff it is a demo", () => {
    check(
      fc.property(inputArb, (input) => {
        const d = buildDraft(input);
        const t = copyAll(d, DEMO, janus);
        expect(d.demo).toBe(input.demo);
        expect(t.startsWith(DEMO)).toBe(input.demo);
        if (!input.demo) expect(t.includes(DEMO)).toBe(false);
      }),
    );
  });

  it("P5: other medicines are exactly the ticked ones, in list order", () => {
    check(
      fc.property(inputArb, (input) => {
        const row = buildDraft(input).rows.find((r) => r.key === "others");
        const ticked = input.others
          .filter((o) => o.ticked && o.label.trim())
          .map((o) => o.label.trim());
        if (ticked.length === 0) expect(row).toBeUndefined();
        else expect(row!.value).toBe(ticked.join("; "));
      }),
    );
  });

  it("P6: copy-all is the rows in form order", () => {
    check(
      fc.property(inputArb, (input) => {
        const d = buildDraft(input);
        const lines = copyAll(d, DEMO, janus).split("\n");
        const body = input.demo ? lines.slice(1) : lines;
        const expected = d.rows.map(
          (r) => `${r.label ?? janus(r.key)}: ${r.value}`,
        );
        if (d.rows.length) expect(body).toEqual(expected);
        const fl = d.fieldList
          ? CHANNELS.find((c) => c.id === d.fieldList)!.fields
          : [];
        const idx = d.rows
          .filter((r) => r.label)
          .map((r) => fl.indexOf(r.label!));
        expect([...idx].sort((a, b) => a - b)).toEqual(idx);
        // Janus-labelled rows come after the mapped ones.
        const firstJanus = d.rows.findIndex((r) => r.label === null);
        if (firstJanus >= 0)
          expect(d.rows.slice(firstJanus).every((r) => r.label === null)).toBe(
            true,
          );
      }),
    );
  });

  it("P7: an outcome option is the channel's own; no options where none were read", () => {
    check(
      fc.property(inputArb, (input) => {
        const opts = outcomeOptions(input.channel, input.hcp);
        const row = buildDraft(input).rows.find((r) => r.key === "outcome");
        if (opts.length) {
          const chosen =
            input.outcome.option !== null
              ? opts[input.outcome.option]
              : undefined;
          if (chosen) expect(row!.value).toBe(chosen);
          else expect(row).toBeUndefined();
          const src = fieldList(input.channel)!.source;
          for (const o of opts) expect(src.outcomeOptions).toContain(o);
        } else if (input.outcome.text.trim())
          expect(row!.value).toBe(input.outcome.text.trim());
      }),
    );
    expect(outcomeOptions(formChannels("TR")[0]!, false)).toHaveLength(6);
    for (const k of ["US", "DE", "FR", "ES", "EU"] as const)
      for (const c of formChannels(k))
        expect(outcomeOptions(c, false), c.id).toEqual([]);
  });

  it("P9: in the doctor view only channels for health professionals get native labels", () => {
    check(
      fc.property(inputArb, (input) => {
        const d = buildDraft({ ...input, hcp: true });
        if (!input.channel.audience.includes("hcp"))
          expect(d.rows.every((r) => r.label === null)).toBe(true);
      }),
    );
    const us = formChannels("US")[0]!;
    expect(mappingFor(us, false)).not.toBeNull();
    expect(mappingFor(us, true)).toBeNull();
  });

  it("P10: missing required fields are recorded ones the draft does not fill", () => {
    check(
      fc.property(inputArb, (input) => {
        const d = buildDraft(input);
        const fl = d.fieldList
          ? CHANNELS.find((c) => c.id === d.fieldList)!
          : null;
        const filled = new Set(d.rows.map((r) => r.label));
        for (const r of d.missingRequired) {
          expect(fl!.required).toContain(r);
          expect(filled.has(r)).toBe(false);
        }
        if (!fl) expect(d.missingRequired).toEqual([]);
      }),
    );
  });

  it("names the medicine as on the box, with its ingredient", () => {
    expect(medicineValue("ATOR 20 mg", "atorvastatin")).toBe(
      "ATOR 20 mg (atorvastatin)",
    );
    expect(medicineValue("", "atorvastatin")).toBe("atorvastatin");
    expect(medicineValue("Atorvastatin", "atorvastatin")).toBe("Atorvastatin");
  });

  it("maps a TÜFAM draft field by field", () => {
    const d = buildDraft({
      channel: formChannels("TR")[0]!,
      demo: false,
      hcp: false,
      medicine: { box: "ATOR 20 mg", ingredient: "atorvastatin" },
      event: "Kas ağrısı",
      onset: "2026-10",
      outcome: { option: 1, text: "" },
      others: [
        { label: "PAROL", ticked: true },
        { label: "NORVASC", ticked: false },
      ],
    });
    expect(d.rows.map((r) => [r.label, r.value])).toEqual([
      ["Reaksiyonlar/belirtiler > Reaksiyon/belirti", "Kas ağrısı"],
      ["Reaksiyonlar/belirtiler > Başlangıç tarihi", "Ekim 2026"],
      ["Reaksiyonlar/belirtiler > Sonuç", "İyileşiyor/düzeliyor"],
      ["İlaçlar > İlaç adı", "ATOR 20 mg (atorvastatin)"],
      ["İlaçlar > İlaç adı", "PAROL"],
    ]);
    expect(d.missingRequired).toContain(
      "Ne olduğunu tanımlayın > Vaka anlatımı",
    );
    expect(Object.keys(MAPPINGS)).toContain(d.fieldList);
  });
});
