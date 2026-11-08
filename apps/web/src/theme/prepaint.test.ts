// Feature: experience, Property P17: for any stored settings value (valid, partial, wrong types,
// not JSON, throwing storage) and any pathname, the pre-paint script sets only valid attribute
// values, sets data-face="light" exactly on the light routes, and never throws (Req 6.7, 9.2).
import { describe, expect, it } from "vitest";

import { check, fc } from "@/test/fc";

import { LIGHT_ROUTE, PREPAINT_SOURCE, SETTINGS_KEY } from "./prepaint";

function run(stored: string | null | "THROW", pathname: string) {
  const attrs: Record<string, string> = {};
  const document = {
    documentElement: { setAttribute: (k: string, v: string) => (attrs[k] = v) },
  };
  const window = {
    get localStorage() {
      if (stored === "THROW") throw new Error("blocked");
      return { getItem: (k: string) => (k === SETTINGS_KEY ? stored : null) };
    },
  };
  const location = { pathname };
  new Function("document", "window", "location", PREPAINT_SOURCE)(
    document,
    window,
    location,
  );
  return attrs;
}

const settingsValue = fc.oneof(
  fc
    .record(
      {
        v: fc.oneof(fc.constant(1), fc.integer(), fc.string()),
        theme: fc.oneof(
          fc.constantFrom("two-faces", "glass"),
          fc.string(),
          fc.integer(),
        ),
        largeText: fc.oneof(fc.boolean(), fc.string()),
        reduceTransparency: fc.oneof(fc.boolean(), fc.constant("yes")),
      },
      { requiredKeys: [] },
    )
    .map((o) => JSON.stringify(o)),
  fc.string(),
  fc.constant("null"),
  fc.constant("[1,2]"),
  fc.constant(null),
  fc.constant("THROW" as const),
);

const pathname = fc.oneof(
  fc.constantFrom(
    "/",
    "/en",
    "/tr/results",
    "/de/research",
    "/fr/research/seance",
    "/es/demo/doctor",
    "/en/demo",
    "/o",
    "/o/",
    "/on",
    "/en/researchers",
  ),
  fc.webPath(),
);

describe("pre-paint script", () => {
  it("never throws and sets only valid values", () => {
    check(
      fc.property(settingsValue, pathname, (stored, path) => {
        const a = run(stored, path);
        expect(["two-faces", "glass"]).toContain(a["data-theme-style"]);
        expect(["on", "off"]).toContain(a["data-large-text"]);
        expect(["on", "off"]).toContain(a["data-reduce-transparency"]);
        expect(a["data-face"]).toBe(
          LIGHT_ROUTE.test(path) ? "light" : "shadow",
        );
      }),
    );
  });

  it("applies a valid document and keeps defaults for anything else", () => {
    const doc = JSON.stringify({
      v: 1,
      theme: "glass",
      largeText: true,
      reduceTransparency: true,
    });
    expect(run(doc, "/en")).toEqual({
      "data-theme-style": "glass",
      "data-face": "shadow",
      "data-large-text": "on",
      "data-reduce-transparency": "on",
    });
    expect(run("{oops", "/en/research")["data-face"]).toBe("light");
    expect(run("THROW", "/o")["data-theme-style"]).toBe("two-faces");
    expect(
      run(JSON.stringify({ v: 2, theme: "glass" }), "/")["data-theme-style"],
    ).toBe("two-faces");
  });

  it("puts the light face exactly on research, the doctor page and the demo doctor page", () => {
    for (const p of [
      "/en/research",
      "/tr/research/export",
      "/o",
      "/de/demo/doctor",
    ])
      expect(LIGHT_ROUTE.test(p), p).toBe(true);
    for (const p of [
      "/en",
      "/en/results",
      "/on",
      "/en/researchers",
      "/en/demo",
      "/en/note",
    ])
      expect(LIGHT_ROUTE.test(p), p).toBe(false);
  });
});
