// Feature: experience, Property P29: for any issue date and clock, the reminder is due exactly
// 28 days after issue and shows until dismissed; a withdrawal removes the token only after the
// API confirmed it; a failed withdrawal keeps it (Req 18.4, 18.5).
import { describe, expect, it } from "vitest";

import { check, fc } from "@/test/fc";
import { addDays, dueReminders } from "@/store/reminders";
import type { TokensDoc } from "@/store/tokens";

import { addToken, dismiss, issued, withdrawToken } from "./loop";

const date = fc
  .date({
    min: new Date(2026, 0, 1),
    max: new Date(2030, 11, 31),
    noInvalidDate: true,
  })
  .map((d) => d.toISOString().slice(0, 10));
const token = fc.stringMatching(/^[A-Za-z0-9_-]{40,60}$/);
const out = (t: string) => ({
  token: t,
  qr_url: null,
  expires_on: "2030-01-01",
  findings_covered: 2,
  findings_total: 3,
  note: {} as never,
});

describe("P29 tokens and reminder", () => {
  it("is due exactly 28 days after issue and until dismissed", () => {
    check(
      fc.property(
        date,
        fc.integer({ min: -40, max: 80 }),
        token,
        (issuedOn, offset, t) => {
          const rec = issued(out(t), "tr", issuedOn, ["cough"]);
          expect(rec.reminderDue).toBe(addDays(issuedOn, 28));
          const today = addDays(issuedOn, offset);
          let doc: TokensDoc = addToken(
            { v: 1, notes: [], deletions: [] },
            rec,
          );
          expect(dueReminders(doc.notes, today).length).toBe(
            offset >= 28 ? 1 : 0,
          );
          doc = dismiss(doc, t);
          expect(dueReminders(doc.notes, today)).toEqual([]);
        },
      ),
    );
  });
  it("removes a token only after the API confirmed the withdrawal", async () => {
    await check(
      fc.asyncProperty(
        token,
        fc.constantFrom("ok", "http", "network"),
        async (t, answer) => {
          const doc = addToken(
            { v: 1, notes: [], deletions: [] },
            issued(out(t), "en", "2026-11-08", []),
          );
          const client = {
            withdraw: async () =>
              answer === "ok"
                ? ({ ok: true, data: { status: "withdrawn" } } as const)
                : ({
                    ok: false,
                    error:
                      answer === "http"
                        ? {
                            kind: "http",
                            route: "notes/withdraw",
                            status: 503,
                            code: "notes_unavailable",
                            fields: [],
                            messageKey: "Withdraw.errors.unavailable",
                          }
                        : {
                            kind: "network",
                            route: "notes/withdraw",
                            messageKey: "Errors.network",
                          },
                  } as never),
          };
          const r = await withdrawToken(doc, t, client);
          expect(r.doc.notes.some((n) => n.token === t)).toBe(answer !== "ok");
        },
      ),
    );
  });
});
