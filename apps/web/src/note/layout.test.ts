// Feature: experience, Properties P4 (product-name slots) and P24 (note layout).
import { describe, expect, it } from "vitest";

import { noteBody } from "@/api/builders";
import type { NoteOut } from "@/api/contracts";
import { SECTION_ORDER } from "@/api/decode";
import { sentinelBoxName, walk } from "@/test/arbitraries";
import { check, fc } from "@/test/fc";
import { NOTES, RESULTS } from "@/test/results";

import { layout, pdfFileName } from "./layout";

const noteArb = fc.record({
  notes: fc.constantFrom(...NOTES),
  a: fc.constantFrom("en", "tr", "de", "fr", "es"),
  b: fc.option(fc.constantFrom("en", "tr", "de", "fr", "es"), { nil: null }),
  shuffle: fc.boolean(),
});

function compose({
  notes,
  a,
  b,
  shuffle,
}: {
  notes: Record<string, NoteOut>;
  a: string;
  b: string | null;
  shuffle: boolean;
}): NoteOut {
  const first = notes[a]!;
  const docs = [
    first.documents[0]!,
    ...(b && b !== a ? [notes[b]!.documents[0]!] : []),
  ];
  // The API's section order is kept by the layout even if a document arrives in another order.
  return {
    ...first,
    documents: docs.map((d) => ({
      ...d,
      sections: shuffle ? [...d.sections].reverse() : d.sections,
    })),
  };
}

describe("P24 note layout", () => {
  it("keeps the section order, every sentence verbatim, headings and the side-by-side pairs", () => {
    check(
      fc.property(
        noteArb,
        fc.array(sentinelBoxName, { minLength: 9, maxLength: 9 }),
        (x, boxes) => {
          const note = compose(x);
          const l = layout(note, boxes, true);
          expect(l.demo).toBe(true);
          l.documents.forEach((d, k) => {
            const ids = d.sections.map((s) => s.id);
            expect(ids).toEqual(
              [...ids].sort(
                (p, q) => SECTION_ORDER.indexOf(p) - SECTION_ORDER.indexOf(q),
              ),
            );
            const src = note.documents[k]!;
            const texts = src.sections.flatMap((s) =>
              s.blocks.flatMap((b) =>
                b.type === "sentence"
                  ? [b.text]
                  : b.type === "stat"
                    ? b.sentences.map((z) => z.text)
                    : [],
              ),
            );
            const laid = d.sections.flatMap((s) =>
              s.blocks.flatMap((b) =>
                b.kind === "sentence"
                  ? [b.text]
                  : b.kind === "stat"
                    ? b.sentences.map((z) => z.text)
                    : [],
              ),
            );
            expect(laid.sort()).toEqual(texts.sort());
            for (const s of src.sections)
              if (s.heading)
                expect(d.sections.find((z) => z.id === s.id)!.heading).toBe(
                  s.heading.text,
                );
            expect(d.disclaimer).toBeTruthy();
          });
          if (note.documents.length === 2) {
            expect(l.sideBySide).not.toBeNull();
            for (const sec of l.sideBySide!)
              for (const [p, q] of sec.rows) expect(p.id).toBe(q.id);
          } else expect(l.sideBySide).toBeNull();
        },
      ),
    );
  });
  it("refuses a second document whose blocks have no partner", () => {
    const n = NOTES[0]!;
    const broken: NoteOut = {
      ...n.en!,
      documents: [
        n.en!.documents[0]!,
        {
          ...n.tr!.documents[0]!,
          sections: n.tr!.documents[0]!.sections.slice(1),
        },
      ],
    };
    expect(() => layout(broken, [], false)).toThrow();
    expect(pdfFileName("2026-11")).toBe("janus-note-2026-11.pdf");
  });
});

describe("P4 product-name slots", () => {
  it("fill every medicine row from the list item of the same index; no later body has a box name", () => {
    check(
      fc.property(
        noteArb,
        fc.array(sentinelBoxName, { minLength: 9, maxLength: 9 }),
        (x, boxes) => {
          const note = compose({ ...x, b: null });
          const l = layout(note, boxes, false);
          const rows = l.documents[0]!.sections.flatMap((s) => s.blocks).filter(
            (b) => b.kind === "medicine",
          );
          expect(rows.length).toBeGreaterThan(0);
          for (const r of rows)
            if (r.kind === "medicine")
              expect(r.productName).toBe(boxes[r.item] ?? null);
          const ev = RESULTS[0]!;
          const body = noteBody(
            {
              dataset_version: ev.dataset_version,
              items: [{ ingredient: "Q1" }],
            },
            {},
            ["en"],
            "TR",
            null,
          );
          const { strings } = walk(body);
          for (const s of strings)
            for (const b of boxes) expect(s.includes(b)).toBe(false);
        },
      ),
    );
  });
});
