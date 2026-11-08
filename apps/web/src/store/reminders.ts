/**
 * In-app outcome reminders (experience design §10.4, DP23, Req 18.4): due 28 days after the token
 * was issued, shown until dismissed; never a push notification. Pure date arithmetic on local
 * calendar dates.
 */
import type { NoteToken } from "./tokens";

export const REMINDER_DAYS = 28;

/** `YYYY-MM-DD` + n days, in the proleptic Gregorian calendar (UTC arithmetic, no time zone). */
export function addDays(date: string, days: number): string {
  const [y, m, d] = date.split("-").map(Number) as [number, number, number];
  const t = Date.UTC(y, m - 1, d) + days * 86_400_000;
  return new Date(t).toISOString().slice(0, 10);
}

export function localDate(now: Date = new Date()): string {
  const p = (n: number) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${p(now.getMonth() + 1)}-${p(now.getDate())}`;
}

export function dueReminders(
  notes: readonly NoteToken[],
  today: string,
): NoteToken[] {
  return notes.filter((n) => !n.reminderDismissed && n.reminderDue <= today);
}
