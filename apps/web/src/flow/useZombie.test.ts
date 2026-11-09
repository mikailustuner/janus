// Feature: zombie-alert, Req 2.3–2.6, 4.3, 5.2, 6.2: the check with a fake client (only a date is
// sent; failures change nothing; a truncated answer reads on from its oldest date),
// recording a note after an alert, the demo simulation, and the notification text.
import { describe, expect, it } from "vitest";

import type { JanusChangesClient, Result } from "@/api/client";
import type { ChangesResult, NoteOut } from "@/api/contracts";
import * as D from "@/api/decode";
import istanbul from "@/demo/fixtures/istanbul.json";
import { DEMO_CHANGE } from "@/demo/zombie";
import de from "../../messages/de.json";
import en from "../../messages/en.json";
import es from "../../messages/es.json";
import fr from "../../messages/fr.json";
import tr from "../../messages/tr.json";
import { SafeStorage } from "@/store/storage";
import { demoZombie, zombieDoc } from "@/store/zombie";

import {
  canSimulate,
  demoAdjust,
  docFor,
  recordNote,
  runCheck,
  simulate,
} from "./useZombie";
import { EMPTY, LIMIT, watchNote } from "./zombie";

const NOTE = D.decode(D.noteOut, istanbul.notes.en);
if (!NOTE.ok) throw new Error("fixture");
const note: NoteOut = NOTE.value;
const memory = () => zombieDoc(new SafeStorage(() => null));

const changes = (cs: ChangesResult["changes"]): ChangesResult => ({
  integrity_version: "v",
  as_of: "2026-11-09",
  since: "2026-11-08",
  observed_dates: [],
  status_counts: {
    ok: 1,
    corrected: 0,
    expression_of_concern: 0,
    retracted: 1,
    unknown: 0,
  },
  changes: cs,
  disclaimer: "d",
});

function fake(answer: Result<ChangesResult>) {
  const bodies: unknown[] = [];
  const client: JanusChangesClient = {
    evidenceChanges: async (b) => {
      bodies.push(b);
      return answer;
    },
  };
  return { client, bodies };
}

describe("runCheck", () => {
  it("sends only a date, alerts once, advances since", async () => {
    const d = memory();
    d.set({ ...EMPTY, note: watchNote(note, "2026-11-08") });
    const { client, bodies } = fake({
      ok: true,
      data: changes([DEMO_CHANGE, { ...DEMO_CHANGE, evidence_id: "x:other" }]),
    });
    const a = await runCheck(client, d, 1000);
    expect(bodies).toEqual([{ since: "2026-11-01", limit: LIMIT }]);
    expect(a.map((x) => x.evidenceId)).toEqual([DEMO_CHANGE.evidence_id]);
    expect(d.get().since).toBe("2026-11-09");
    expect(d.get().checkedAt).toBe(1000);
    expect(await runCheck(client, d, 2000)).toEqual([]);
    expect(d.get().alerts).toHaveLength(1);
  });

  it("a failure changes nothing but the attempt time; no note → no request", async () => {
    const d = memory();
    const { client, bodies } = fake({
      ok: false,
      error: {
        kind: "http",
        route: "evidence/changes",
        status: 503,
        code: "integrity_unavailable",
        fields: [],
        messageKey: "Errors.generic",
      },
    });
    await runCheck(client, d, 5);
    expect(bodies).toEqual([]);
    d.set({ ...EMPTY, note: watchNote(note, "2026-11-08") });
    const before = d.get();
    await runCheck(client, d, 7);
    expect(d.get()).toEqual({ ...before, checkedAt: 7 });
  });

  it("a truncated answer still sends no id and reads on from its oldest date", async () => {
    const d = memory();
    d.set({ ...EMPTY, note: watchNote(note, "2026-11-08") });
    const many = Array.from({ length: LIMIT }, (_, i) => ({
      ...DEMO_CHANGE,
      evidence_id: `x:${i}`,
      observed_on: i ? "2026-11-09" : "2026-11-02",
    }));
    const { client, bodies } = fake({ ok: true, data: changes(many) });
    await runCheck(client, d, 1);
    expect(bodies).toEqual([{ since: "2026-11-01", limit: LIMIT }]);
    expect(d.get().since).toBe("2026-11-02");
    expect(d.get().alerts).toEqual([]);
  });
});

describe("note update and demo", () => {
  it("recording the updated demo note turns the alert into What changed", () => {
    demoZombie.set({ ...EMPTY });
    recordNote(note, true);
    expect(canSimulate(demoZombie.get())).toBe(true);
    expect(simulate()).toHaveLength(1);
    expect(simulate()).toHaveLength(0);
    expect(canSimulate(demoZombie.get())).toBe(false);
    const after = demoAdjust(note, true);
    expect(demoAdjust(note, false)).toBe(note);
    recordNote(after, true);
    const z = demoZombie.get();
    expect(z.alerts).toEqual([]);
    expect(z.update?.removed.map((s) => s.id)).toEqual([
      "pipc:5:Q411347:Q388801:supporting",
    ]);
    expect(z.update?.alerts[0]?.simulated).toBe(true);
    expect(docFor(true)).toBe(demoZombie);
  });
});

describe("notification text (Req 4.3)", () => {
  const names = [
    ...istanbul.items.map((i) => i.boxName),
    "atorvastatin",
    "amlodipine",
    "ThinkCascades",
  ];
  it.each([
    ["en", en],
    ["tr", tr],
    ["de", de],
    ["fr", fr],
    ["es", es],
  ])("%s takes no value and names nothing", (_, m) => {
    const text = m.ZombieAlert.notification;
    expect(text).not.toMatch(/[{}]/);
    for (const n of names)
      expect(text.toLowerCase()).not.toContain(n.toLowerCase());
  });
});
