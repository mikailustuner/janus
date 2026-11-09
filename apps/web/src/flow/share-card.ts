/**
 * The share image's text model (janus-report design §5, DP11, P6, P7). Pure: the caller passes the
 * translator and the names it may use; the model holds exactly the strings that are drawn. Counts
 * only by default; event names and ingredient names only when the person opted in; box names
 * never. The disclaimer is always there, the demo label only in demo mode.
 */
import type { Translate } from "@/theme/words";

import { orderGroup } from "./findings";
import type { SummaryView } from "./summary";

type OkSummary = Extract<SummaryView, { kind: "ok" }>;

export interface ShareOptions {
  events: boolean;
  ingredients: boolean;
}

export interface ShareInput {
  view: OkSummary;
  options: ShareOptions;
  demo: boolean;
  /** The title of each finding by position (the event label), in the interface language. */
  eventNames: readonly string[];
  /** The ingredient names of the list, in the interface language. */
  ingredientNames: readonly string[];
  /** Safety-line texts of the findings' events, already filled with the region's numbers. */
  safetyTexts: readonly string[];
  /** The emergency notice text for the region (shown with the safety lines). */
  emergencyText: string;
  /** "Do not stop this medicine suddenly." from the vocabulary. */
  abruptStop: string;
  month: string;
  t: Translate;
  formatNumber: (n: number) => string;
}

export interface ShareCard {
  title: string;
  month: string;
  headline: string;
  stats: { value: string; label: string }[];
  /** The ring of the patterns checked: checked of total. */
  rules: { checked: number; total: number };
  /** The ring's label under the number: "of 65". */
  ringLabel: string;
  noPattern: string | null;
  discuss: string | null;
  abruptStop: { count: string; line: string } | null;
  events: { heading: string; names: string[] } | null;
  ingredients: { heading: string; names: string[] } | null;
  emergency: string | null;
  safety: string[];
  demo: string | null;
  disclaimer: string;
  footer: string;
}

const unique = (xs: readonly string[]) => [...new Set(xs.filter(Boolean))];

export function shareCard(i: ShareInput): ShareCard {
  const { view: v, t } = i;
  const n = v.patterns.total;
  const events =
    i.options.events && n > 0
      ? {
          heading: t("Report.image.eventsHeading"),
          names: unique(
            v.findings.map((f) =>
              t("Report.image.eventLine", {
                event: i.eventNames[f.position] ?? "",
                order: t(`Findings.order.${orderGroup(f.finding.timing)}`),
              }),
            ),
          ),
        }
      : null;
  const ingredients =
    i.options.ingredients && i.ingredientNames.length
      ? {
          heading: t("Report.image.ingredientsHeading"),
          names: unique(i.ingredientNames),
        }
      : null;
  const safety = events ? unique(i.safetyTexts) : [];
  return {
    title: t("Report.image.title"),
    month: t("Report.checkedIn", { month: i.month }),
    headline: t("Report.image.headline", {
      medicines: v.medicines.total,
      patterns: n,
      checked: v.rules.checked,
      total: v.rules.total,
      month: i.month,
    }),
    stats: [
      {
        value: i.formatNumber(v.medicines.total),
        label: t("Report.image.medicines", { count: v.medicines.total }),
      },
      // No large zero (DP9): with no finding the no-pattern sentence stands instead.
      ...(n > 0
        ? [
            {
              value: i.formatNumber(n),
              label: t("Report.image.patterns", { count: n }),
            },
          ]
        : []),
    ],
    rules: v.rules,
    ringLabel: t("Report.rules.of", { total: i.formatNumber(v.rules.total) }),
    noPattern: n === 0 ? t("Findings.noPattern") : null,
    discuss: n > 0 ? t("Findings.discuss") : null,
    abruptStop: v.warnedItems.length
      ? {
          count: t("Report.image.abrupt", { count: v.warnedItems.length }),
          line: i.abruptStop,
        }
      : null,
    events,
    ingredients,
    emergency: safety.length ? i.emergencyText : null,
    safety,
    demo: i.demo ? t("Demo.label") : null,
    disclaimer: t("Disclaimer.text"),
    footer: t("Report.image.footer"),
  };
}

/** Every string of the card in reading order (the preview's alternative text; the tests). */
export function shareCardText(c: ShareCard): string {
  return [
    c.demo,
    c.title,
    c.month,
    c.emergency,
    ...c.safety,
    ...c.stats.map((s) => `${s.value} ${s.label}`),
    `${c.rules.checked} ${c.ringLabel}`,
    c.headline,
    c.noPattern,
    c.discuss,
    c.abruptStop ? `${c.abruptStop.count} ${c.abruptStop.line}` : null,
    c.events?.heading,
    ...(c.events?.names ?? []),
    c.ingredients?.heading,
    ...(c.ingredients?.names ?? []),
    c.disclaimer,
    c.footer,
  ]
    .filter((s): s is string => !!s)
    .join("\n");
}
