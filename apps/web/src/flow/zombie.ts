/**
 * Zombie Alert, the pure part (zombie-alert design §3–§5): what the browser keeps of a note, the
 * check body (a date, never an id: DP1), the local match of the changes against the cited ids,
 * the diff after the update, and the evidence-integrity rule the demo applies (DP10).
 */
import type {
  ChangesIn,
  EvidenceChange,
  EvidenceResolution,
  NoteBlock,
  NoteOut,
  Sentence,
} from "@/api/contracts";

export const LIMIT = 500;
export const MAX_SENTENCES = 300;
export const MAX_SEEN = 500;
export const MAX_RESOLVE_IDS = 200;
export const HOUR = 3_600_000;
export const DAY = 24 * HOUR;

/** Statuses that make a record non-citable (evidence-integrity Req 5.2, 5.3; DP3). */
export const NON_CITABLE: ReadonlySet<string> = new Set(["retracted"]);

export interface KeptSentence {
  id: string;
  text: string;
  ids: string[];
}

export interface WatchedNote {
  language: string;
  madeOn: string; // local date YYYY-MM-DD
  ids: string[];
  sentences: KeptSentence[];
}

export interface Alert {
  key: string;
  evidenceId: string;
  title: string | null;
  doi: string | null;
  observedOn: string;
  notice: { doi: string | null; url: string | null } | null;
  simulated: boolean;
}

export interface Update {
  alerts: Alert[];
  removed: KeptSentence[];
  changed: { before: KeptSentence; after: KeptSentence }[];
  language: string;
}

export interface ZombieDoc {
  v: 1;
  notify: boolean;
  note: WatchedNote | null;
  since: string | null;
  checkedAt: number | null;
  seen: string[];
  alerts: Alert[];
  update: Update | null;
}

export const EMPTY: ZombieDoc = {
  v: 1,
  notify: false,
  note: null,
  since: null,
  checkedAt: null,
  seen: [],
  alerts: [],
  update: null,
};

function sentencesOf(b: NoteBlock): Sentence[] {
  if (b.type === "sentence") return [b];
  if (b.type === "stat") return b.sentences;
  return b.abrupt_stop ? [b.abrupt_stop] : [];
}

/** Every sentence of the note's first document, with its section. */
function allSentences(note: NoteOut): { section: string; s: Sentence }[] {
  const doc = note.documents[0];
  if (!doc) return [];
  return doc.sections.flatMap((sec) =>
    sec.blocks.flatMap((b) =>
      sentencesOf(b).map((s) => ({ section: sec.id, s })),
    ),
  );
}

/** What the browser keeps of a note (Req 1.1, 1.5). */
export function watchNote(note: NoteOut, madeOn: string): WatchedNote {
  const all = allSentences(note);
  const ids = [...new Set(all.flatMap(({ s }) => s.evidence_ids))].sort();
  const sentences = all
    .filter(
      ({ section, s }) => section !== "integrity" && s.evidence_ids.length,
    )
    .slice(0, MAX_SENTENCES)
    .map(({ s }) => ({ id: s.id, text: s.text, ids: [...s.evidence_ids] }));
  return {
    language: note.documents[0]?.language ?? "en",
    madeOn,
    ids,
    sentences,
  };
}

/** The check body: a date and the limit, nothing else (Req 2.3, P1). */
export function checkBody(doc: ZombieDoc): ChangesIn | null {
  if (!doc.note || doc.note.ids.length === 0) return null;
  return { since: doc.since ?? doc.note.madeOn, limit: LIMIT };
}

export const changeKey = (c: {
  evidence_id: string;
  to_status: string;
  observed_on: string;
}) => `${c.evidence_id}|${c.to_status}|${c.observed_on}`;

export type ChangeLike = Pick<
  EvidenceChange,
  "evidence_id" | "title" | "doi" | "to_status" | "observed_on"
>;

/**
 * The local comparison (Req 2.4, 3.1, 3.2; P2–P4): new alerts for cited ids changed to a
 * non-citable status whose key was not seen, and the seen list after this answer.
 */
export function matchChanges(
  doc: ZombieDoc,
  changes: readonly ChangeLike[],
  simulated = false,
  notices: Record<string, Alert["notice"]> = {},
): { alerts: Alert[]; seen: string[] } {
  const cited = new Set(doc.note?.ids ?? []);
  const seen = new Set(doc.seen);
  const alerts: Alert[] = [];
  for (const c of changes) {
    if (!cited.has(c.evidence_id) || !NON_CITABLE.has(c.to_status)) continue;
    const key = changeKey(c);
    if (seen.has(key)) continue;
    seen.add(key);
    alerts.push({
      key,
      evidenceId: c.evidence_id,
      title: c.title,
      doi: c.doi,
      observedOn: c.observed_on,
      notice: notices[c.evidence_id] ?? null,
      simulated,
    });
  }
  const all = [...seen];
  return { alerts, seen: all.slice(Math.max(0, all.length - MAX_SEEN)) };
}

/** Body of the fallback resolve: the cited ids only (Req 2.5, P5). */
export function resolveBody(doc: ZombieDoc): { evidence_ids: string[] } | null {
  const ids = [...new Set(doc.note?.ids ?? [])].slice(0, MAX_RESOLVE_IDS);
  return ids.length ? { evidence_ids: ids } : null;
}

/** Retracted cited items of a resolution, as changes observed on its date (Req 2.5). */
export function changesFromResolution(r: EvidenceResolution): ChangeLike[] {
  return r.items
    .filter((i) => i.integrity && NON_CITABLE.has(i.integrity.status))
    .map((i) => ({
      evidence_id: i.id,
      title: i.title,
      doi: i.doi,
      to_status: i.integrity!.status,
      observed_on: i.integrity!.checked_at ?? r.as_of,
    }));
}

/** The retraction notice of each retracted item (DP2). */
export function noticesFrom(
  r: EvidenceResolution,
): Record<string, Alert["notice"]> {
  const out: Record<string, Alert["notice"]> = {};
  for (const i of r.items) {
    const n = i.integrity?.notices.find((x) => x.type === "retraction");
    if (n) out[i.id] = { doi: n.notice_doi, url: n.notice_url };
  }
  return out;
}

/** "What changed" (Req 5.2, P7). */
export function diffNote(
  before: readonly KeptSentence[],
  after: NoteOut,
  changedIds: readonly string[],
): Pick<Update, "removed" | "changed"> {
  const changed = new Set(changedIds);
  const now = new Map(
    allSentences(after).map(({ s }) => [
      s.id,
      { id: s.id, text: s.text, ids: [...s.evidence_ids] },
    ]),
  );
  const out: Pick<Update, "removed" | "changed"> = { removed: [], changed: [] };
  for (const b of before) {
    if (!b.ids.some((id) => changed.has(id))) continue;
    const a = now.get(b.id);
    if (!a) out.removed.push(b);
    else if (a.text !== b.text || a.ids.join("\n") !== b.ids.join("\n"))
      out.changed.push({ before: b, after: a });
  }
  return out;
}

/**
 * The evidence-integrity rule (Req 5.4) for the demo simulation (DP10): keep only the ids that
 * stay citable; a sentence that had ids and has none left is removed and listed as a removal.
 */
export function withoutEvidence(
  note: NoteOut,
  removedIds: readonly string[],
): NoteOut {
  const gone = new Set(removedIds);
  const removals: NoteOut["removals"] = [];
  const keep = (s: Sentence): Sentence | null => {
    const ids = s.evidence_ids.filter((id) => !gone.has(id));
    if (s.evidence_ids.length && !ids.length) {
      removals.push({ sentence_id: s.id, reason: "evidence_not_citable" });
      return null;
    }
    return ids.length === s.evidence_ids.length
      ? s
      : { ...s, evidence_ids: ids };
  };
  const block = (b: NoteBlock): NoteBlock | null => {
    if (b.type === "sentence") return keep(b);
    if (b.type === "stat") {
      const sentences = b.sentences.map(keep).filter((s): s is Sentence => !!s);
      return sentences.length ? { ...b, sentences } : null;
    }
    return b.abrupt_stop ? { ...b, abrupt_stop: keep(b.abrupt_stop) } : b;
  };
  const documents = note.documents.map((d) => ({
    ...d,
    sections: d.sections.map((sec) => ({
      ...sec,
      blocks: sec.blocks.map(block).filter((b): b is NoteBlock => !!b),
    })),
  })) as NoteOut["documents"];
  const seen = new Set<string>();
  return {
    ...note,
    removals: [
      ...note.removals,
      ...removals.filter(
        (r) => !seen.has(r.sentence_id) && seen.add(r.sentence_id),
      ),
    ],
    documents,
  };
}

/** True when the last attempt is at least `gap` old (Req 2.1, 2.2). */
export const isDue = (checkedAt: number | null, now: number, gap: number) =>
  checkedAt === null || now - checkedAt >= gap || now < checkedAt;
