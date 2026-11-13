// Feature: experience §10.2–10.3. The doctor note renders to a real PDF in both paper sizes, with
// and without the demo label and the QR code; the paper rule and the side-by-side contract checks.
import path from "node:path";

import { describe, expect, it } from "vitest";

import type { NoteOut } from "@/api/contracts";
import { NOTES } from "@/test/results";

import { layout, paperFor } from "./layout";
import { renderNotePdf, type PdfLabels } from "./pdf";

const ORIGIN = path.resolve(import.meta.dirname, "../../public");
const note: NoteOut = NOTES[0]!.en!;

const labels = (over: Partial<PdfLabels> = {}): PdfLabels => ({
  demo: null,
  pageOf: (p, n) => `page ${p} of ${n}`,
  versions: "versions",
  qr: null,
  ...over,
});

async function head(blob: Blob): Promise<string> {
  return new TextDecoder().decode(
    new Uint8Array(await blob.arrayBuffer()).slice(0, 5),
  );
}

describe("doctor note PDF", () => {
  it("renders A4 without a demo label and Letter with the demo label and a QR code", async () => {
    const plain = await renderNotePdf(
      layout(note, [], false),
      labels(),
      "A4",
      ORIGIN,
    );
    const demo = await renderNotePdf(
      layout(note, [], true),
      labels({ demo: "Demo", qr: { path: "M0 0h10v10H0z", side: 10 } }),
      "LETTER",
      ORIGIN,
    );
    for (const b of [plain, demo]) {
      expect(await head(b)).toBe("%PDF-");
      expect(b.size).toBeGreaterThan(1000);
    }
  }, 60_000);
});

describe("paper size", () => {
  it("is Letter only for English with region US", () => {
    expect(paperFor("en", "US")).toBe("LETTER");
    expect(paperFor("en", "TR")).toBe("A4");
    expect(paperFor("tr", "US")).toBe("A4");
  });
});

describe("side-by-side contract", () => {
  const second = NOTES[0]!.tr!.documents[0]!;
  const two = (d: NoteOut["documents"][number]): NoteOut => ({
    ...note,
    documents: [note.documents[0]!, d],
  });

  it("pairs two documents with the same sections", () => {
    expect(layout(two(second), [], false).sideBySide).not.toBeNull();
  });

  it("refuses documents whose sections or blocks differ", () => {
    const fewer = { ...second, sections: second.sections.slice(1) };
    expect(() => layout(two(fewer), [], false)).toThrow();
    const renamed = {
      ...second,
      sections: second.sections.map((s, i) =>
        i === 0 ? { ...s, id: "other" } : s,
      ),
    } as typeof second;
    expect(() => layout(two(renamed), [], false)).toThrow();
    const withBlocks = second.sections.findIndex((s) => s.blocks.length > 0);
    const missing = {
      ...second,
      sections: second.sections.map((s, i) =>
        i === withBlocks
          ? {
              ...s,
              blocks: s.blocks.map((b, j) =>
                j === 0 ? { ...b, id: "zz" } : b,
              ),
            }
          : s,
      ),
    } as typeof second;
    expect(() => layout(two(missing), [], false)).toThrow();
  });
});
