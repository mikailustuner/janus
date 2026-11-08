/**
 * Outcome-loop token lifecycle on the device (experience design §10.4, Req 18.4, 18.5, P29).
 * The reminder is due 28 days after issue and shows until dismissed; a withdrawal removes the
 * token only after the API confirmed it; a failed withdrawal keeps it.
 */
import { tokenOnlyBody } from "@/api/builders";
import type { JanusLoopClient, Result } from "@/api/client";
import type { TokenOut, WithdrawnOut } from "@/api/contracts";
import { addDays, REMINDER_DAYS } from "@/store/reminders";
import type { NoteToken, TokensDoc } from "@/store/tokens";

export function issued(
  out: TokenOut,
  language: string,
  today: string,
  events: string[],
): NoteToken {
  return {
    token: out.token,
    expiresOn: out.expires_on,
    issuedOn: today,
    findingsCovered: out.findings_covered,
    findingsTotal: out.findings_total,
    language,
    reminderDue: addDays(today, REMINDER_DAYS),
    reminderDismissed: false,
    events,
  };
}

export function addToken(doc: TokensDoc, t: NoteToken): TokensDoc {
  return {
    ...doc,
    notes: [...doc.notes.filter((n) => n.token !== t.token), t],
  };
}

export function dismiss(doc: TokensDoc, token: string): TokensDoc {
  return {
    ...doc,
    notes: doc.notes.map((n) =>
      n.token === token ? { ...n, reminderDismissed: true } : n,
    ),
  };
}

/** Withdraws one token; the document changes only when the API confirmed. */
export async function withdrawToken(
  doc: TokensDoc,
  token: string,
  client: Pick<JanusLoopClient, "withdraw">,
): Promise<{ doc: TokensDoc; result: Result<WithdrawnOut> }> {
  let result: Result<WithdrawnOut>;
  try {
    result = await client.withdraw(tokenOnlyBody(token));
  } catch {
    result = {
      ok: false,
      error: {
        kind: "build",
        route: "notes/withdraw",
        messageKey: "Errors.client_defect",
      },
    };
  }
  if (!result.ok) return { doc, result };
  return {
    doc: { ...doc, notes: doc.notes.filter((n) => n.token !== token) },
    result,
  };
}
