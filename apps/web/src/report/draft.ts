/**
 * The draft (report-assistant design §3.3, Req 4, 5, 9.2, P1, P3–P7, P9, P10). Pure: no I/O, no
 * storage; the screen holds the input in memory. A value goes under a native label only when the
 * channel's verified field list has a mapped field for it; otherwise under the Janus label.
 */
import { CHANNELS, fieldList, type Channel } from "./channels";
import { DRAFT_KEYS, MAPPINGS, type DraftKey } from "./mapping";

export interface DraftInput {
  channel: Channel;
  demo: boolean;
  /** The doctor view (Req 8.3): native labels only on channels for health professionals. */
  hcp: boolean;
  medicine: { box: string; ingredient: string };
  event: string;
  /** "YYYY-MM" or null ("don't know"). */
  onset: string | null;
  /** An index into the channel's recorded outcome options, or free text. */
  outcome: { option: number | null; text: string };
  /**
   * `type` comes from the resolver's product type (openFDA "HUMAN OTC DRUG" → `otc`, "HUMAN
   * PRESCRIPTION DRUG" → `rx`); anything else is `unknown` (DP13).
   */
  others: { label: string; ticked: boolean; type?: OtherType }[];
}

export type OtherType = "otc" | "rx" | "unknown";

export interface DraftRow {
  key: DraftKey;
  /** The native label as published ("Section > Label"), or null: shown under the Janus label. */
  label: string | null;
  section: string | null;
  field: string | null;
  /** Translation id `ReportAssistant.labels.<id>`, null for a Janus label. */
  id: string | null;
  value: string;
}

export interface Draft {
  channelId: string;
  demo: boolean;
  /** The channel whose field list is used, and whether it is another edition (Req 5.3). */
  fieldList: string | null;
  borrowed: boolean;
  rows: DraftRow[];
  /** Recorded required fields of the field list that the draft does not fill (Req 5.5). */
  missingRequired: string[];
  /**
   * Ticked other medicines of unknown type that were put under the prescription field because
   * the form splits prescription from over-the-counter medicines (3500B E11, DP13); the screen
   * says so. Empty when the form does not split them.
   */
  typeUnknown: string[];
}

/** The resolver's product type as the 3500B E10/E11 split needs it (DP13). */
export function otherType(productType: string | null | undefined): OtherType {
  if (productType === "HUMAN OTC DRUG") return "otc";
  if (productType === "HUMAN PRESCRIPTION DRUG") return "rx";
  return "unknown";
}

/** The mapping that applies to a channel in this view, or null (DP4, DP11). */
export function mappingFor(c: Channel, hcp: boolean, list = CHANNELS) {
  const fl = fieldList(c, list);
  if (!fl) return null;
  if (hcp && !c.audience.includes("hcp")) return null;
  const map = MAPPINGS[fl.source.id];
  return map ? { ...fl, map } : null;
}

/** The channel's own outcome options, when the mapped outcome field is the recorded one (DP6). */
export function outcomeOptions(
  c: Channel,
  hcp: boolean,
  list = CHANNELS,
): string[] {
  const m = mappingFor(c, hcp, list);
  if (!m) return [];
  const f = m.map.find((x) => x.key === "outcome");
  return f && f.label === m.source.outcomeField ? m.source.outcomeOptions : [];
}

export function medicineValue(box: string, ingredient: string): string {
  const b = box.trim();
  const i = ingredient.trim();
  if (!b) return i;
  if (!i || b.toLocaleLowerCase() === i.toLocaleLowerCase()) return b;
  return `${b} (${i})`;
}

/** Month and year in the form's language, e.g. "Ekim 2026" (design §3.3). */
export function monthValue(month: string, lang: string): string {
  const [y, m] = month.split("-").map(Number);
  return new Intl.DateTimeFormat(lang, {
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  }).format(Date.UTC(y!, m! - 1, 1));
}

const tickedOthers = (input: DraftInput) =>
  input.others
    .filter((o) => o.ticked && o.label.trim())
    .map((o) => ({ label: o.label.trim(), type: o.type ?? "unknown" }));

function values(
  input: DraftInput,
  options: string[],
  splitOtc: boolean,
): Record<DraftKey, string> {
  const lang = input.channel.languages[0] ?? "en";
  const option =
    input.outcome.option !== null ? options[input.outcome.option] : undefined;
  const others = tickedOthers(input);
  const join = (xs: typeof others) => xs.map((o) => o.label).join("; ");
  return {
    medicine: medicineValue(input.medicine.box, input.medicine.ingredient),
    event: input.event.trim(),
    onset: input.onset ? monthValue(input.onset, lang) : "",
    outcome: options.length > 0 ? (option ?? "") : input.outcome.text.trim(),
    others: join(splitOtc ? others.filter((o) => o.type !== "otc") : others),
    othersOtc: splitOtc ? join(others.filter((o) => o.type === "otc")) : "",
  };
}

const split = (label: string) => {
  const i = label.lastIndexOf(" > ");
  return i < 0
    ? { section: null, field: label }
    : { section: label.slice(0, i), field: label.slice(i + 3) };
};

export function buildDraft(input: DraftInput, list = CHANNELS): Draft {
  const m = mappingFor(input.channel, input.hcp, list);
  const splitOtc = !!m?.map.some((f) => f.key === "othersOtc");
  const v = values(
    input,
    outcomeOptions(input.channel, input.hcp, list),
    splitOtc,
  );
  const rows: DraftRow[] = [];
  const mapped = new Set<DraftKey>();
  for (const f of m?.map ?? []) {
    mapped.add(f.key);
    if (!v[f.key]) continue;
    rows.push({
      key: f.key,
      label: f.label,
      ...split(f.label),
      id: f.id,
      value: v[f.key],
    });
  }
  for (const key of DRAFT_KEYS)
    if (!mapped.has(key) && v[key])
      rows.push({
        key,
        label: null,
        section: null,
        field: null,
        id: null,
        value: v[key],
      });
  const filled = new Set(rows.flatMap((r) => (r.label ? [r.label] : [])));
  return {
    channelId: input.channel.id,
    demo: input.demo,
    fieldList: m?.source.id ?? null,
    borrowed: m?.borrowed ?? false,
    rows,
    missingRequired: m ? m.source.required.filter((r) => !filled.has(r)) : [],
    typeUnknown: splitOtc
      ? tickedOthers(input)
          .filter((o) => o.type === "unknown")
          .map((o) => o.label)
      : [],
  };
}

/** Copy-all (Req 5.4, P4, P6): the demo line first in a demo, then one `label: value` per row. */
export function copyAll(
  d: Draft,
  demoLine: string,
  janusLabel: (key: DraftKey) => string,
): string {
  return [
    ...(d.demo ? [demoLine] : []),
    ...d.rows.map((r) => `${r.label ?? janusLabel(r.key)}: ${r.value}`),
  ].join("\n");
}

/** "one-of(a|b)" → its alternatives, for display (Req 5.5). */
export function requiredParts(r: string): string[] {
  const m = /^one-of\((.*)\)$/.exec(r);
  return m ? m[1]!.split("|") : [r];
}
