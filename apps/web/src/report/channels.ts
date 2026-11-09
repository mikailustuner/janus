/**
 * The reporting channels (report-assistant design §3.1, DP2, DP4): the generated JSON of
 * `data/report_channels.csv`, and the lookups the screen needs. Pure.
 */
import data from "./channels.json";
import type { Channel, Country, Region } from "./types";

export type { Channel, Country, Region } from "./types";

export const CHANNELS = data as Channel[];

const byId = new Map(CHANNELS.map((c) => [c.id, c]));

export function channel(id: string): Channel | null {
  return byId.get(id) ?? null;
}

/** Channels with a form or guidance page (online first, then PDF/Word, then guidance). */
const FORM_KINDS = ["online", "pdf", "document", "guidance"] as const;
const CONTACT_KINDS = ["email", "phone"] as const;

export function formChannels(country: Country, list = CHANNELS): Channel[] {
  return FORM_KINDS.flatMap((k) =>
    list.filter(
      (c) => c.country === country && c.kind === k && c.patientMayReport,
    ),
  );
}

export function contactChannels(country: Country, list = CHANNELS): Channel[] {
  return list.filter(
    (c) =>
      c.country === country &&
      (CONTACT_KINDS as readonly string[]).includes(c.kind),
  );
}

/** The EU national-authority finder (Req 3.2). */
export const FINDER_ID = "eu-adr-national";

/**
 * The verified field list that applies to a channel (DP4): the list of its `field_source`, used
 * only when that row was read in the form (`verified`) or its official definition (`derived`).
 */
export function fieldList(
  c: Channel,
  list = CHANNELS,
): { source: Channel; borrowed: boolean } | null {
  if (!c.fieldSource) return null;
  const source =
    c.fieldSource === c.id
      ? c
      : (list.find((x) => x.id === c.fieldSource) ?? null);
  if (!source || !["verified", "derived"].includes(source.fieldsStatus))
    return null;
  return { source, borrowed: source.id !== c.id };
}

export const COUNTRIES_EU = ["DE", "FR", "ES", "EU"] as const;

export function regionOf(country: Country): Region {
  return country === "TR" ? "TR" : country === "US" ? "US" : "EU";
}

/** Every URL the assistant may show (P2). */
export function knownUrls(list = CHANNELS): Set<string> {
  return new Set(list.flatMap((c) => [c.url, c.sourceUrl]));
}
