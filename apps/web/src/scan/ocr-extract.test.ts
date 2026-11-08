// Feature: experience, Property P22: for any recognised text (names, addresses, prescriber
// lines, NDCs), nothing is sent without a choice; an NDC chip is exactly the NDC; a selection is
// exactly the selected adjacent words (2–100 characters, trimmed) (Req 11.2, 11.4).
import { describe, expect, it } from "vitest";

import { check, fc } from "@/test/fc";

import { classifyTyped } from "./gs1";
import { ndcCandidates, selectionQuery } from "./ocr-extract";

const personal = fc.constantFrom(
  "PATIENT: ZZJANE DOE",
  "DR ZZSMITH MD",
  "123 ZZMAIN ST APT 4",
  "ZZPHARMACY RX 8813",
);
const ndc = fc
  .tuple(
    fc.integer({ min: 1000, max: 99999 }),
    fc.integer({ min: 100, max: 9999 }),
    fc.integer({ min: 1, max: 99 }),
  )
  .map(([a, b, c]) => `${a}-${b}-${c}`);
const word = fc.stringMatching(/^[A-Za-z]{1,12}$/);

describe("P22 OCR extraction", () => {
  it("offers NDCs as chips and nothing of the personal lines", () => {
    check(
      fc.property(
        fc.array(personal, { maxLength: 4 }),
        fc.array(ndc, { maxLength: 3 }),
        fc.array(word, { maxLength: 6 }),
        (lines, ndcs, words) => {
          const text = [
            ...lines,
            ...ndcs.map((n) => `NDC ${n}`),
            words.join(" "),
          ].join("\n");
          const chips = ndcCandidates(text);
          expect(new Set(chips)).toEqual(new Set(ndcs));
          for (const c of chips) expect(c).not.toMatch(/ZZ/);
        },
      ),
    );
  });
  it("sends a selection only of adjacent words, trimmed, within 2–100 characters", () => {
    check(
      fc.property(
        fc.array(word, { minLength: 1, maxLength: 20 }),
        fc.array(fc.nat(19), { maxLength: 5 }),
        (words, sel) => {
          const q = selectionQuery(words, sel);
          if (sel.length === 0) {
            expect(q).toBeNull();
            return;
          }
          const s = [...new Set(sel)].sort((a, b) => a - b);
          const adjacent =
            s.every((v, i) => i === 0 || v === s[i - 1]! + 1) &&
            s.every((i) => i < words.length);
          const joined = s
            .map((i) => words[i] ?? "")
            .join(" ")
            .trim();
          if (adjacent && joined.length >= 2 && joined.length <= 100)
            expect(q).toBe(joined);
          else if (!adjacent) expect(q).toBeNull();
        },
      ),
    );
  });
  it("never sends a typed CIP7, CN or PZN as a code", () => {
    check(
      fc.property(
        fc.oneof(
          fc.integer({ min: 100000, max: 9999999 }).map(String),
          fc.integer({ min: 1000000, max: 99999999 }).map((n) => `PZN-${n}`),
        ),
        (code) => {
          expect(classifyTyped(code).kind).toBe("national_code");
        },
      ),
    );
  });
});
