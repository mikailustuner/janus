"use client";
/**
 * The presence rows of one box (design §8, Req 2.1, 2.2, 6, 7, 10.4): one row per source in the
 * order TR, FR, ES, DE, US with the box's own source last. Status, counts, the three comparison
 * results with their reasons, the attribution line and the stale notice. One inset grouped list (a
 * description list) at every width, with a Countries / Comparison view (experience Req 29.7);
 * statuses carry text and a shape, never colour.
 * Comparisons that used values typed from the box say so (owner decision 1).
 */
import { useLocale } from "next-intl";
import type { ReactNode } from "react";

import { formatDate } from "@/components/format";
import { useT, type Translate } from "@/theme/words";

import { itemKeys } from "../identity";
import type { Answer, ItemOut, PassportItem, SourceOut } from "../model";
import { SOURCE_COUNTRY, strengthParts } from "../format";
import { ResultIcon, StatusIcon } from "./icons";

const FIELDS = ["strength", "dose_form", "strength_and_dose_form"] as const;

/** The row index of the box's own source, or null (a box typed by name outside Germany). */
export function ownSource(item: PassportItem): number | null {
  if ("entered_by_name" in item.source)
    return item.origin.country === "DE" ? 3 : null;
  const i = ["titck", "eu_fr_bdpm", "eu_es_cima", null, "openfda_ndc"].indexOf(
    item.source.source_id,
  );
  return i >= 0 ? i : null;
}

export function rowOrder(item: PassportItem): number[] {
  const own = ownSource(item);
  return [0, 1, 2, 3, 4]
    .filter((i) => i !== own)
    .concat(own === null ? [] : [own]);
}

export function strengthText(
  t: Translate,
  item: PassportItem,
  locale: string,
): string | null {
  const parts = item.ingredients.filter((g) => g.strength);
  if (parts.length === 0) return null;
  const nf = new Intl.NumberFormat(locale, { maximumFractionDigits: 6 });
  return parts
    .map((g) => {
      const p = strengthParts(g.strength!);
      return t("Passport.strengthValue", {
        amount: nf.format(p.amount),
        unit: t(`Passport.unit.${p.unit}`),
        basis: t(`Passport.basis.${g.strength!.basis}`),
      });
    })
    .join(", ");
}

export const enteredStrength = (item: PassportItem) =>
  item.ingredients.some((g) => g.strengthOrigin === "entered");
export const enteredForm = (item: PassportItem) =>
  item.doseForm?.origin === "entered";

export function sourceLabel(t: Translate, s: SourceOut): string {
  const country = t(`Passport.place.${SOURCE_COUNTRY[s.source]}`);
  const name = s.attribution ? t(`Passport.sourceName.${s.attribution}`) : null;
  return name ? `${country} · ${name}` : country;
}

function Comparison({
  t,
  item,
  answer,
  locale,
}: {
  t: Translate;
  item: PassportItem;
  answer: Answer;
  locale: string;
}) {
  const c = answer.comparison;
  if (!c) return null;
  const strength = strengthText(t, item, locale) ?? "";
  const form = item.doseForm ? t(`Passport.form.${item.doseForm.group}`) : "";
  return (
    <div className="flex flex-col gap-1.5">
      <p className="font-bold">{t("Passport.detail.comparisonTitle")}</p>
      <ul className="flex flex-col gap-1.5">
        {FIELDS.map((f) => {
          const r = c[f];
          const reason = r.reason
            ? t(`Passport.compareReason.${r.reason}`, {
                comparable: r.comparable,
                products: answer.products,
              })
            : "";
          // The box's typed value was compared (not when the source gave nothing to compare).
          const compared =
            r.result !== "could_not_compare" ||
            r.reason === "not_all_comparable";
          const entered =
            compared &&
            ((f !== "dose_form" && enteredStrength(item)) ||
              (f !== "strength" && enteredForm(item)));
          return (
            <li
              key={f}
              data-result={r.result}
              data-field={f}
              data-compared={compared ? "yes" : "no"}
              className="flex items-start gap-2"
            >
              <ResultIcon result={r.result} />
              <p>
                {/* "Strength not compared: …" already names the field. */}
                {r.result === "could_not_compare" ? null : (
                  <span className="font-bold">
                    {t(`Passport.compareLabel.${f}`)}:{" "}
                  </span>
                )}
                {t(`Passport.compare.${f}.${r.result}`, {
                  equal: r.equal,
                  strength,
                  form,
                  reason,
                })}
                {entered ? (
                  <span className="text-muted"> ({t("Passport.entered")})</span>
                ) : null}
              </p>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export type RowsView = "countries" | "comparison";

function RowBody({
  item,
  answer,
  source,
  view,
}: {
  item: PassportItem;
  answer: Answer;
  source: SourceOut;
  view: RowsView;
}) {
  const t = useT();
  const locale = useLocale();
  const date = source.snapshot_date
    ? formatDate(source.snapshot_date, locale)
    : "";
  const name = source.attribution
    ? t(`Passport.sourceName.${source.attribution}`)
    : "";
  const ingredients = itemKeys(item).length;
  const country = t(`Passport.country.${SOURCE_COUNTRY[source.source]}`);
  const names = (keys: readonly string[]) =>
    new Intl.ListFormat(locale, { type: "conjunction" }).format(
      keys.map((k) => item.ingredients.find((g) => g.key === k)?.label ?? k),
    );
  const lines: ReactNode[] = [];
  if (answer.status === "source_unavailable")
    lines.push(
      <p key="r">{t(`Passport.reason.${source.reason ?? "not_loaded"}`)}</p>,
    );
  else {
    lines.push(
      <p key="s">
        {t(`Passport.status.${answer.status}`, {
          source: name,
          count: answer.products,
          ingredients,
          date,
          country,
        })}
      </p>,
    );
    if (answer.with_other_ingredients > 0)
      lines.push(
        <p key="w" className="text-muted">
          {t("Passport.detail.withOther", {
            count: answer.with_other_ingredients,
            ingredients,
          })}
        </p>,
      );
    if (
      answer.status === "not_present" &&
      answer.keys_found.length > 0 &&
      ingredients > 1
    )
      lines.push(
        <p key="k" className="text-muted">
          {t("Passport.detail.keysFound", { names: names(answer.keys_found) })}
        </p>,
      );
    if (answer.homeopathic_left_out > 0)
      lines.push(
        <p key="h" className="text-muted">
          {t("Passport.homeopathicLeftOut", {
            count: answer.homeopathic_left_out,
          })}
        </p>,
      );
  }
  // Both views stay in the document; the control shows one (Req 29.7, DP56). A row without a
  // comparison keeps its listing line in the comparison view.
  const showStatus = view === "countries" || !answer.comparison;
  return (
    <div className="flex min-w-0 flex-col gap-2 [overflow-wrap:anywhere]">
      <div
        className="flex items-start gap-2"
        data-status={answer.status}
        hidden={!showStatus}
      >
        <StatusIcon status={answer.status} />
        <div className="flex flex-col gap-1">{lines}</div>
      </div>
      <div hidden={view !== "comparison"}>
        <Comparison t={t} item={item} answer={answer} locale={locale} />
      </div>
      {source.status === "loaded" &&
      source.attribution &&
      source.snapshot_date ? (
        <p className="text-sm text-muted">
          {t(`Passport.attribution.${source.attribution}`, { date })}
        </p>
      ) : null}
      {source.stale ? (
        <p className="text-sm font-bold">{t("Passport.stale")}</p>
      ) : null}
    </div>
  );
}

export function PresenceRows({
  item,
  out,
  sources,
  view = "countries",
}: {
  item: PassportItem;
  out: ItemOut;
  sources: readonly SourceOut[];
  view?: RowsView;
}) {
  const t = useT();
  const own = ownSource(item);
  const rows = rowOrder(item).map((i) => ({
    i,
    source: sources[i]!,
    answer: out.answers[i]!,
    head: sourceLabel(t, sources[i]!),
  }));
  // One inset grouped list at every width (Req 29.3, DP56): the country and source as the row
  // head, what the source data show under it.
  return (
    <section
      aria-labelledby="presence-caption"
      className="flex min-w-0 flex-col gap-2"
    >
      <h3 id="presence-caption" className="group-header">
        {t("Passport.detail.caption")}
      </h3>
      <dl className="grouped m-0">
        {rows.map((r) => (
          <div key={r.i} className="flex flex-col gap-2">
            <dt className="flex flex-wrap items-center gap-x-2 gap-y-1 font-bold [overflow-wrap:anywhere]">
              {r.head}
              {r.i === own ? (
                <span className="chip text-sm">
                  {t("Passport.detail.ownSource")}
                </span>
              ) : null}
            </dt>
            <dd className="m-0">
              <RowBody
                item={item}
                answer={r.answer}
                source={r.source}
                view={view}
              />
            </dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
