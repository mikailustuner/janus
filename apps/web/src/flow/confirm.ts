/**
 * `ResolutionResult` → the confirm view model (experience design §9, Req 12, P21). Pure. No
 * candidate is preselected; `no_open_product_database` offers label text and name search and is
 * never "not found"; an empty result with loaded sources is "not found" with each source and its
 * date; digits-based matches carry the less-certain note; the published product code is shown
 * as published and never as an ingredient code.
 */
import type { Candidate, ResolutionResult } from "@/api/contracts";

export interface CardView {
  index: number;
  candidate: Candidate;
  digitsNote: boolean;
  publishedAtc: string | null;
  homeopathic: boolean;
  ambiguous: { position: number; keys: string[] }[];
  ingredientCodes: string[];
  attribution: { sourceId: string; date: string };
  status:
    | { kind: "fr"; text: string }[]
    | { kind: "es"; code: string; date?: string; value?: string }[];
  marketingEnd: string | null;
  notInWikidata: boolean;
}

export type ConfirmView =
  | { kind: "no_open_database"; country: string | null }
  | { kind: "not_supported" }
  | {
      kind: "not_found";
      regions: string[];
      sources: { sourceId: string; date: string }[];
    }
  | {
      kind: "candidates";
      cards: CardView[];
      notices: string[];
      expiry: string | null;
    };

const ES_STATUS =
  /^(commercialised|serialised):(true|false)$|^(registration_status|presentation_status):(\S+) (\S+)$/;

function statusLines(c: Candidate): CardView["status"] {
  if (c.kind !== "product") return [];
  if (c.country === "ES")
    return c.status_published.map((s) => {
      const m = ES_STATUS.exec(s);
      if (!m) return { kind: "es" as const, code: "raw", value: s };
      if (m[1]) return { kind: "es" as const, code: `${m[1]}_${m[2]}` };
      return {
        kind: "es" as const,
        code: m[3] === "registration_status" ? "registration" : "presentation",
        value: m[4],
        date: m[5],
      };
    });
  return c.status_published.map((text) => ({ kind: "fr" as const, text }));
}

/**
 * `prefer`: an ingredient key the user chose on the label; its ingredient candidate is listed
 * first (ocr-first Req 2.6). The order is the only effect: `index` stays the position in the
 * resolution and nothing is preselected.
 */
export function confirmView(
  r: ResolutionResult,
  prefer: string | null = null,
): ConfirmView {
  const noDb = r.notices.find((n) => n.code === "no_open_product_database");
  if (r.candidates.length === 0) {
    if (noDb)
      return { kind: "no_open_database", country: noDb.country ?? null };
    if (r.notices.some((n) => n.code === "region_adapter_not_available"))
      return { kind: "not_supported" };
    return {
      kind: "not_found",
      regions: [...r.regions_searched],
      sources: r.sources.map((s) => ({
        sourceId: s.source_id,
        date: s.snapshot_date.slice(0, 10),
      })),
    };
  }
  const cards: CardView[] = r.candidates.map((c, index) => ({
    index,
    candidate: c,
    digitsNote:
      c.kind === "product" &&
      (c.matched_by === "ntin_digits" || c.matched_by === "ai_712"),
    publishedAtc: c.kind === "product" ? c.published_atc : null,
    homeopathic: c.kind === "product" && c.homeopathic,
    ambiguous:
      c.kind === "product"
        ? c.ingredients
            .filter((g) => g.status === "ambiguous")
            .map((g) => ({ position: g.position, keys: [...g.key_candidates] }))
        : [],
    ingredientCodes:
      c.kind === "product"
        ? c.ingredients.flatMap((g) => g.atc_codes.map((a) => a.code))
        : c.atc_codes.map((a) => a.code),
    attribution: {
      sourceId: c.source.source_id,
      date: c.source.snapshot_date.slice(0, 10),
    },
    status: statusLines(c),
    marketingEnd: c.kind === "product" ? c.marketing_end_date : null,
    notInWikidata:
      (c.kind === "ingredient" && c.rxcui_status === "not_in_wikidata") ||
      (c.kind === "product" &&
        c.ingredients.some((g) => g.rxcui_status === "not_in_wikidata")),
  }));
  const preferred = (v: CardView) =>
    prefer !== null &&
    v.candidate.kind === "ingredient" &&
    v.candidate.ingredient_key.qid === prefer;
  return {
    kind: "candidates",
    cards: [...cards.filter(preferred), ...cards.filter((v) => !preferred(v))],
    notices: r.notices
      .map((n) => n.code)
      .filter((c) => c !== "no_open_product_database"),
    expiry: r.scan?.expiry ?? null,
  };
}

/** A candidate can be added once every ambiguous position has a key or an explicit "don't know". */
export function readyToAdd(
  card: CardView,
  answers: Record<number, string | "dont_know">,
): boolean {
  return card.ambiguous.every((a) => answers[a.position] !== undefined);
}
