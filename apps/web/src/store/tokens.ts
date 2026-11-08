/**
 * Outcome-loop note tokens and kept donation deletion tokens `janus.v1.tokens` (experience design
 * §4.1, §10.4, Req 18.3–18.5, 20.4). Only in the browser; tokens never go into a URL other than
 * the QR fragment, a log or analytics.
 */
import { Doc, PREFIX, storage, type SafeStorage } from "./storage";

export interface NoteToken {
  token: string;
  expiresOn: string; // YYYY-MM-DD
  issuedOn: string; // local date YYYY-MM-DD
  findingsCovered: number;
  findingsTotal: number;
  language: string;
  reminderDue: string; // issuedOn + 28 days
  reminderDismissed: boolean;
  /** Janus event keys of the note's findings, to pre-select the event of a donation (Req 18.4). */
  events?: string[];
}

export interface DeletionToken {
  token: string;
  storedSummary: {
    reportWeek: string;
    event: string;
    direction: "adverse" | "benefit";
  };
}

export interface TokensDoc {
  v: 1;
  notes: NoteToken[];
  deletions: DeletionToken[];
}

const DATE = /^\d{4}-\d{2}-\d{2}$/;

export function validateTokens(v: unknown): TokensDoc | null {
  if (typeof v !== "object" || v === null) return null;
  const o = v as Record<string, unknown>;
  if (o.v !== 1 || !Array.isArray(o.notes) || !Array.isArray(o.deletions))
    return null;
  const notes: NoteToken[] = [];
  for (const n of o.notes as Record<string, unknown>[]) {
    if (
      !n ||
      typeof n.token !== "string" ||
      typeof n.expiresOn !== "string" ||
      !DATE.test(n.expiresOn) ||
      typeof n.issuedOn !== "string" ||
      !DATE.test(n.issuedOn) ||
      typeof n.reminderDue !== "string" ||
      !DATE.test(n.reminderDue) ||
      !Number.isInteger(n.findingsCovered) ||
      !Number.isInteger(n.findingsTotal) ||
      typeof n.language !== "string" ||
      typeof n.reminderDismissed !== "boolean" ||
      (n.events !== undefined &&
        (!Array.isArray(n.events) ||
          n.events.some((e) => typeof e !== "string")))
    )
      return null;
    notes.push(n as unknown as NoteToken);
  }
  const deletions: DeletionToken[] = [];
  for (const d of o.deletions as Record<string, unknown>[]) {
    const s = d?.storedSummary as Record<string, unknown> | undefined;
    if (
      !d ||
      typeof d.token !== "string" ||
      !s ||
      typeof s.reportWeek !== "string" ||
      typeof s.event !== "string" ||
      (s.direction !== "adverse" && s.direction !== "benefit")
    )
      return null;
    deletions.push(d as unknown as DeletionToken);
  }
  return { v: 1, notes, deletions };
}

export function tokensDoc(store: SafeStorage = storage) {
  return new Doc<TokensDoc>(store, `${PREFIX}tokens`, validateTokens, () => ({
    v: 1,
    notes: [],
    deletions: [],
  }));
}

export const tokens = tokensDoc();
