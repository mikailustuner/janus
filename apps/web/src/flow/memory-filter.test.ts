// Feature: experience, Property P35: for any filter the shown panels are exactly the filter's;
// `all` shows the four panels; the chosen event's safety line travels with the donated and
// outcome panels (Req 29.7, 7).
import { describe, expect, it } from "vitest";

import { check, fc } from "@/test/fc";

import { MEMORY_FILTERS, memoryPanels } from "./memory-filter";

describe("Collective Memory filter (P35)", () => {
  it("all shows every panel; each other filter shows exactly its own", () => {
    expect(memoryPanels("all")).toEqual({
      combination: true,
      regions: true,
      janus: true,
    });
    check(
      fc.property(fc.constantFrom(...MEMORY_FILTERS), (f) => {
        const p = memoryPanels(f);
        const shown = Object.values(p).filter(Boolean).length;
        expect(shown).toBe(f === "all" ? 3 : 1);
        if (f === "together") expect(p.combination).toBe(true);
        if (f === "regions") expect(p.regions).toBe(true);
        // The donated and outcome panels (and the safety line) are one switch.
        if (f === "janus") expect(p.janus).toBe(true);
      }),
    );
  });
});
