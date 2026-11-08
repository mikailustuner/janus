// Feature: experience, Property P16: for any sequence of reads and writes with any failure
// schedule (throwing getItem / setItem, quota, corrupt JSON, wrong version), no call throws, the
// session continues in memory with one notice, and valid documents round-trip (Req 9.4, 9.5).
import { describe, expect, it } from "vitest";

import istanbul from "@/demo/fixtures/istanbul.json";
import { check, fc } from "@/test/fc";

import { validateList, type ListDoc } from "./list";
import { DEFAULT_SETTINGS, settingsDoc, validateSettings } from "./settings";
import { Doc, SafeStorage, type StorageLike } from "./storage";
import { validateTokens } from "./tokens";

type Fault = "none" | "throw" | "quota";

function fakeStorage(
  schedule: Fault[],
): StorageLike & { map: Map<string, string> } {
  const map = new Map<string, string>();
  let i = 0;
  const next = () => schedule[i++ % Math.max(1, schedule.length)] ?? "none";
  return {
    map,
    getItem(k) {
      if (next() === "throw") throw new Error("SecurityError");
      return map.get(k) ?? null;
    },
    setItem(k, v) {
      const f = next();
      if (f === "throw") throw new Error("SecurityError");
      if (f === "quota") throw new DOMException("full", "QuotaExceededError");
      map.set(k, v);
    },
    removeItem(k) {
      if (next() === "throw") throw new Error("SecurityError");
      map.delete(k);
    },
    get length() {
      return map.size;
    },
    key: (n) => [...map.keys()][n] ?? null,
  };
}

const settingsArb = fc.record({
  v: fc.constant(1 as const),
  theme: fc.constantFrom("two-faces" as const, "glass" as const),
  largeText: fc.boolean(),
  reduceTransparency: fc.boolean(),
  readAloud: fc.boolean(),
  noteLanguage: fc.constantFrom("en" as const, "tr" as const, null),
  scanRegion: fc.constantFrom(
    "TR" as const,
    "US" as const,
    "EU" as const,
    null,
  ),
  userRegion: fc.constantFrom(
    "US" as const,
    "TR" as const,
    "EU" as const,
    "OTHER" as const,
    "UNKNOWN" as const,
  ),
  statisticsRegion: fc.constantFrom(
    "TR" as const,
    "EU" as const,
    "US" as const,
    null,
  ),
});

describe("safe storage", () => {
  it("never throws, falls back to memory with one notice, and keeps the session's data", () => {
    check(
      fc.property(
        fc.array(fc.constantFrom<Fault>("none", "none", "throw", "quota"), {
          maxLength: 8,
        }),
        fc.array(
          fc.tuple(fc.constantFrom("read", "write", "remove"), settingsArb),
          { maxLength: 20 },
        ),
        (schedule, ops) => {
          const backend = fakeStorage(schedule);
          const store = new SafeStorage(() => backend);
          let notices = 0;
          store.onNotice(() => notices++);
          const doc = settingsDoc(store);
          let last = doc.get();
          for (const [op, value] of ops) {
            if (op === "write") {
              doc.set(value);
              last = value;
            } else if (op === "remove") store.remove(doc.key);
            else
              expect(() => store.read(doc.key, validateSettings)).not.toThrow();
          }
          expect(doc.get()).toEqual(last);
          if (store.memoryOnly)
            expect(store.raised.has("unavailable")).toBe(true);
          expect(notices).toBeLessThanOrEqual(2);
        },
      ),
    );
  });

  it("round-trips valid documents and refuses corrupt or other-version ones", () => {
    check(
      fc.property(settingsArb, (s) => {
        const backend = fakeStorage([]);
        const store = new SafeStorage(() => backend);
        settingsDoc(store).set(s);
        expect(
          new Doc(
            store,
            "janus.v1.settings",
            validateSettings,
            () => DEFAULT_SETTINGS,
          ).get(),
        ).toEqual(s);
      }),
    );
    const backend = fakeStorage([]);
    const store = new SafeStorage(() => backend);
    for (const raw of [
      "{oops",
      JSON.stringify({ v: 2, theme: "glass" }),
      JSON.stringify({ v: 1, theme: 3 }),
    ]) {
      backend.map.set("janus.v1.settings", raw);
      expect(store.read("janus.v1.settings", validateSettings).status).toBe(
        "invalid",
      );
    }
    expect(store.raised.has("invalid")).toBe(true);
    expect(settingsDoc(store).get()).toEqual(DEFAULT_SETTINGS);
  });

  it("validates the list and token documents", () => {
    const res = istanbul.items[0]!.resolution;
    const list: ListDoc = {
      v: 1,
      items: [
        {
          id: "a",
          sourceKey: { kind: "scan", content: "(01)02952680000017" },
          datasetVersion: res.dataset_version,
          candidate: res.candidates[0] as ListDoc["items"][number]["candidate"],
          choices: [],
          started: "2024-01",
          boxName: "Box",
          needsConfirmation: false,
        },
      ],
    };
    expect(validateList(JSON.parse(JSON.stringify(list)))).toEqual(list);
    expect(
      validateList({
        ...list,
        items: [{ ...list.items[0], started: "2024-13" }],
      }),
    ).toBeNull();
    expect(validateTokens({ v: 1, notes: [], deletions: [] })).toEqual({
      v: 1,
      notes: [],
      deletions: [],
    });
    expect(
      validateTokens({ v: 1, notes: [{ token: 1 }], deletions: [] }),
    ).toBeNull();
  });

  it("works with no backend at all (server, blocked storage)", () => {
    const store = new SafeStorage(() => null);
    const doc = settingsDoc(store);
    doc.set({ ...DEFAULT_SETTINGS, theme: "glass" });
    expect(doc.get().theme).toBe("glass");
    expect(store.memoryOnly).toBe(true);
  });
});
