/**
 * Synthetic séance answers (catalogue and the two featured pairs) for the behaviour tests. Typed
 * with the production types and decoded by the production decoders; nothing is read from the
 * recorded file.
 *
 * Substances: acacia (sorts before the featured ones, so "the first listed" differs from "the
 * featured pair"), salt (its present-day exposure differs: never cross-linked), St John's wort
 * (featured, no FAERS mapping) and vinegar (featured, its component acetic acid is the FAERS
 * link, Q47512). Pair answers exist for the two featured pairs only, as in the demo.
 */
import * as D from "@/api/decode";
import {
  catalogueOut,
  seanceOut,
  type CatalogueOut,
  type PastItem,
  type SeanceOut,
  type Substance,
} from "@/seance/model";
import type { SeanceFixture } from "@/seance/client";

function checked<T>(decoder: D.Decoder<T>, value: T, what: string): T {
  const r = D.decode(decoder, value);
  if (!r.ok) throw new Error(`synthetic fixture ${what} does not decode`);
  return value;
}

const DISCLAIMER =
  "Janus provides information, not medical advice. Research prototype — not a medical device.";
const GOLD_CITATION =
  "Synthetic Author A. Synthetic Journal 2013;8(4):1-5. PMC0000001, CC BY 3.0.";

export function substanceOf(
  id: string,
  name: string,
  over: Partial<Substance> = {},
): Substance {
  return {
    id,
    name_en: name,
    transliteration: `${id}-translit`,
    heading_ar: "خل",
    kind: "plant",
    identification: `${name} (synthetic identification)`,
    identification_status: "matches_gold",
    identification_label: "identified",
    gold: {
      gold_id: "pmc0000001.t1.r02",
      scientific_name: `${name} synthetic`,
      citation: GOLD_CITATION,
    },
    hamdard_ref: "Hamdard 1998, synthetic entry",
    hazard: null,
    note: "Synthetic note.",
    ...over,
  };
}

const SOURCES = [
  {
    id: "openiti_canon",
    citation: "Synthetic Canon edition, Book 2.",
    license: "CC BY-NC-SA 4.0",
  },
  {
    id: "pmc0000001",
    citation: GOLD_CITATION,
    license: "CC BY 3.0",
  },
];

export function catalogue(): CatalogueOut {
  return checked(
    catalogueOut,
    {
      schema_version: "seance-1",
      substances: [
        substanceOf("acacia", "acacia (gum arabic tree)"),
        substanceOf("salt", "salt", { kind: "mineral" }),
        substanceOf("st_johns_wort", "St John's wort"),
        substanceOf("vinegar", "vinegar", { kind: "preparation" }),
      ],
      pairs: [
        {
          substance: "acacia",
          condition: "burn",
          past_passages: 1,
          science_studies: 0,
          present_link: "none",
          present_ingredient_key: null,
        },
        {
          substance: "acacia",
          condition: "infection",
          past_passages: 1,
          science_studies: 0,
          present_link: "none",
          present_ingredient_key: null,
        },
        {
          substance: "salt",
          condition: "wound",
          past_passages: 2,
          science_studies: 0,
          present_link: "different",
          present_ingredient_key: "Q2314",
        },
        {
          substance: "st_johns_wort",
          condition: "wound",
          past_passages: 1,
          science_studies: 1,
          present_link: "none",
          present_ingredient_key: null,
        },
        {
          substance: "vinegar",
          condition: "infection",
          past_passages: 2,
          science_studies: 2,
          present_link: "component",
          present_ingredient_key: "Q47512",
        },
      ],
      sources: SOURCES,
      disclaimer: DISCLAIMER,
    } satisfies CatalogueOut,
    "catalogue",
  );
}

const pastItem = (
  entry: string,
  page: string,
  start: number,
  end: number,
  condition: string,
): PastItem => ({
  claim_id: `canon.b2.${entry}.l${start}.aaaaaa:${condition}`,
  locator: {
    entry_id: `canon.b2.${entry}`,
    span_id: `canon.b2.${entry}.l${start}.aaaaaa`,
    book: 2,
    page,
    line_start: start,
    line_end: end,
  },
  arabic_span: "ضماد ورقه ينفع من حرق النار ويدمل الجراحات.",
  translation: "A plaster of its leaves helps burns and closes wounds.",
  translation_kind: "machine_translation",
  use_en: "Leaves as a plaster.",
  ai_review: "passed_both",
  expert_review: "pending",
  headline_eligible: true,
});

const present = (over: Partial<SeanceOut["witnesses"]["present"]>) => ({
  supports: false,
  confidence: "none" as const,
  missing_reason: "no_faers_mapping" as const,
  items: [],
  observed: null,
  pts: ["Wound", "Skin wound"],
  codes: [
    "spontaneous_reports" as const,
    "reports_not_people" as const,
    "not_deduplicated_across_cases" as const,
  ],
  ...over,
});

const science = (
  items: SeanceOut["witnesses"]["science"]["items"],
): SeanceOut["witnesses"]["science"] => ({
  supports: true,
  confidence: "low",
  missing_reason: null,
  items,
  excluded: [],
});

/** The answer of the featured pair St John's wort / wound: past and science speak, present is missing. */
export function wortWound(): SeanceOut {
  return checked(
    seanceOut,
    {
      schema_version: "seance-1",
      substance: substanceOf("st_johns_wort", "St John's wort"),
      condition: "wound",
      witnesses: {
        past: {
          supports: true,
          confidence: "low",
          missing_reason: null,
          items: [pastItem("h0219", "V01P447", 12231, 12232, "wound")],
        },
        present: present({}),
        science: science([
          {
            evidence_id: "paper:seance_science:synthetic_a",
            doi: "10.0000/synthetic.a",
            title: "A synthetic randomised trial of a topical ointment",
            study_type: "rct",
            finding_en:
              "Synthetic finding: better healing scores than a placebo ointment.",
            integrity_status: "unknown",
          },
        ]),
      },
      supporting_witnesses: 2,
      missing_witnesses: ["present"],
      framing: "hypothesis_not_treatment",
      headline: { eligible: true, reasons: [] },
      sources: SOURCES,
      disclaimer: DISCLAIMER,
    },
    "pair wort/wound",
  );
}

/** The answer of the featured pair vinegar / infection: too few reports for the present witness. */
export function vinegarInfection(): SeanceOut {
  return checked(
    seanceOut,
    {
      schema_version: "seance-1",
      substance: substanceOf("vinegar", "vinegar", { kind: "preparation" }),
      condition: "infection",
      witnesses: {
        past: {
          supports: true,
          confidence: "low",
          missing_reason: null,
          items: [
            pastItem("h0802", "V01P714", 19263, 19265, "infection"),
            pastItem("h0802", "V01P714", 19266, 19267, "infection"),
          ],
        },
        present: present({
          missing_reason: "too_few_reports",
          observed: {
            ingredient_key: "Q47512",
            exposure_match: "component",
            reports_with_both: 0,
            reports_with_ingredient: 59,
            ror: null,
            ror_ci: null,
            snapshot_date: "2026-01-01",
          },
          pts: ["Wound infection", "Wound infection bacterial"],
        }),
        science: science([
          {
            evidence_id: "paper:seance_science:synthetic_b",
            doi: "10.0000/synthetic.b",
            title: "A synthetic laboratory study of dilute acetic acid",
            study_type: "in_vitro",
            finding_en: "Synthetic finding: dilute acid inhibited growth.",
            integrity_status: "unknown",
          },
          {
            evidence_id: "paper:seance_science:synthetic_c",
            doi: "10.0000/synthetic.c",
            title: "A synthetic narrative review of topical acid",
            study_type: "narrative_review",
            finding_en: "Synthetic finding: narrative review of topical use.",
            integrity_status: "unknown",
          },
        ]),
      },
      supporting_witnesses: 2,
      missing_witnesses: ["present"],
      framing: "hypothesis_not_treatment",
      headline: { eligible: true, reasons: [] },
      sources: SOURCES,
      disclaimer: DISCLAIMER,
    },
    "pair vinegar/infection",
  );
}

export function seanceSet(): SeanceFixture & {
  catalogue: CatalogueOut;
  pairs: {
    request: { substance: string; condition: "wound" | "infection" };
    answer: SeanceOut;
  }[];
} {
  return {
    recorded: "synthetic",
    catalogue: catalogue(),
    pairs: [
      {
        request: { substance: "st_johns_wort", condition: "wound" },
        answer: wortWound(),
      },
      {
        request: { substance: "vinegar", condition: "infection" },
        answer: vinegarInfection(),
      },
    ],
  };
}
