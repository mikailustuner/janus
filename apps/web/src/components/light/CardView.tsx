"use client";
/**
 * One hypothesis card (light-face design §7, Req 4.1): candidate, tied rank, signal types as text,
 * label counts and regions, the inverse FAERS signal with its interval bar and warnings, the
 * patient-reported layer, integrity-checked sources and the mechanism line. Never a colour-only
 * signal, never `--risk` except for a retracted source.
 */
import { useLocale } from "next-intl";

import { CiBar } from "@/components/memory/CiBar";
import { formatCount, formatDate, formatRatio } from "@/components/format";
import { ButtonLink, Card, Chip } from "@/components/ui";
import { ratioOf } from "@/flow/memory";
import type {
  Card as CardData,
  CardSignal,
  LightSnapshot,
  Source,
} from "@/light/model";
import { nameIn, rankText } from "@/light/view";
import { requestPair } from "@/seance/client";
import type { CatalogueOut } from "@/seance/model";
import { crossLinks } from "@/seance/view";
import { useT, useThemeWord } from "@/theme/words";

function SourceList({
  sources,
  removed,
}: {
  sources: Source[];
  removed: CardData["removed_sources"];
}) {
  const t = useT();
  const w = useThemeWord();
  return (
    <div className="flex flex-col gap-1 text-sm">
      <h4 className="font-semibold">{t("Light.card.sources")}</h4>
      <ul className="flex flex-col gap-1">
        {sources.map((s) => (
          <li key={s.id} className="break-words">
            <a
              data-inline="true"
              href={s.url}
              rel="noreferrer noopener"
              target="_blank"
              className="underline"
            >
              {s.title ?? s.id}
            </a>{" "}
            <span className="text-muted">
              (
              {t(
                `Light.card.sourceStatus.${s.status in STATUS ? s.status : "unknown"}`,
              )}
              {s.doi ? (
                <>
                  , <span className="mono">{s.doi}</span>
                </>
              ) : null}
              )
            </span>
          </li>
        ))}
      </ul>
      {removed.length ? (
        <>
          <h4 className="font-semibold">{t("Light.card.removedSources")}</h4>
          <ul>
            {removed.map((r) => (
              <li key={r.id} className="mono break-words">
                {r.reason === "retracted" ? (
                  <span className="text-risk font-bold">
                    {w("Evidence.stamp")}
                  </span>
                ) : (
                  t(`Evidence.reason.${r.reason}`)
                )}{" "}
                {r.id}
              </li>
            ))}
          </ul>
        </>
      ) : null}
    </div>
  );
}

const STATUS = {
  ok: 1,
  corrected: 1,
  expression_of_concern: 1,
  unknown: 1,
  no_doi: 1,
};

function Signal({ s, snapshot }: { s: CardSignal; snapshot: LightSnapshot }) {
  const t = useT();
  const locale = useLocale();
  const codes = (
    <ul className="flex flex-col gap-1 text-sm">
      {s.codes.map((c) => (
        <li key={c}>
          {c === "screening_statistic"
            ? t("Memory.screening")
            : [
                  "spontaneous_reporting",
                  "not_incidence",
                  "denominator_sensitive",
                ].includes(c)
              ? t(`Memory.codes.${c}`)
              : t(`Light.codes.${c}`)}
        </li>
      ))}
    </ul>
  );
  if (s.label) {
    const l = s.label;
    return (
      <section
        className="flex flex-col gap-2"
        aria-label={t("Light.card.signal.label_effect")}
      >
        <h4 className="font-semibold">{t("Light.card.signal.label_effect")}</h4>
        <p>
          {t("Light.card.labelCounts", {
            with: formatCount(l.labels_with_effect, locale),
            total: formatCount(l.labels_total, locale),
            share: formatRatio(l.share_low, locale),
          })}
        </p>
        <p>
          {t("Light.card.regions", {
            regions: l.regions
              .map((r) => t(`Light.card.region.${r}`))
              .join(", "),
          })}
        </p>
        <p className="text-sm">
          {t("Light.card.labelTerms", { terms: l.terms.join(", ") })}
        </p>
        <p className="text-sm">
          {t("Light.card.sections", {
            sections: l.sections
              .map((x) => t(`Light.card.section.${x}`))
              .join(", "),
          })}
        </p>
        {codes}
      </section>
    );
  }
  if (s.inverse) {
    const inv = s.inverse;
    const ratio = ratioOf(inv.stats);
    return (
      <section
        className="flex flex-col gap-2"
        aria-label={t("Light.card.signal.inverse_faers")}
      >
        <h4 className="font-semibold">
          {t("Light.card.signal.inverse_faers")}
        </h4>
        <p>
          {t("Light.card.inverseReports", {
            reports: inv.reports,
            expected: formatRatio(inv.expected, locale),
            oe: formatRatio(inv.observed_over_expected, locale),
          })}
        </p>
        {ratio ? <CiBar ratio={ratio} /> : null}
        <p className="text-sm break-words">
          {t("Light.card.pts", { pts: inv.pts.join(", ") })}
        </p>
        <p className="text-sm">
          {t("Light.card.faersSnapshot", {
            date: formatDate(snapshot.faers_snapshot_date, locale),
            window: snapshot.faers_window.join(", "),
          })}
        </p>
        {codes}
      </section>
    );
  }
  if (s.patient) {
    const p = s.patient;
    return (
      <section
        className="flex flex-col gap-2"
        aria-label={t("Light.card.signal.patient_reported")}
      >
        <h4 className="font-semibold">
          {t("Light.card.signal.patient_reported")}
        </h4>
        <p>
          {t("Light.card.patientReleased", {
            value: formatCount(p.total_of_released, locale),
          })}
        </p>
        <ul className="text-sm">
          {p.cells.map((c) => (
            <li key={c.region}>
              {c.status === "released" && c.value !== null
                ? t("Light.card.patientCell", {
                    region: t(`Common.region.${c.region}`),
                    value: formatCount(c.value, locale),
                  })
                : t("Light.card.patientHidden", {
                    region: t(`Common.region.${c.region}`),
                  })}
            </li>
          ))}
        </ul>
        {codes}
      </section>
    );
  }
  return null;
}

/**
 * The séance pairs of the same FAERS ingredient (same exposure or a component; never a different
 * exposure), as links that open the séance screen on that pair without putting it in the URL.
 */
function SeanceLinks({
  cat,
  ingredient,
}: {
  cat: CatalogueOut;
  ingredient: string;
}) {
  const t = useT();
  const w = useThemeWord();
  const links = crossLinks(cat, ingredient);
  if (!links.length) return null;
  return (
    <section className="flex flex-col gap-2 text-sm" data-testid="seance-links">
      <h4 className="font-semibold">{w("Seance.crossLink.title")}</h4>
      <ul className="flex flex-col gap-1">
        {links.flatMap((l) =>
          l.pairs.map((p) => (
            <li key={`${p.substance}-${p.condition}`} className="flex flex-col">
              <span>
                {t(
                  p.present_link === "same"
                    ? "Seance.crossLink.same"
                    : "Seance.crossLink.component",
                )}
              </span>
              <ButtonLink
                href="/research/seance"
                variant="quiet"
                className="px-0 text-start"
                onClick={() =>
                  requestPair({
                    substance: p.substance,
                    condition: p.condition,
                  })
                }
              >
                {t("Seance.crossLink.open", {
                  substance: l.substance.name_en,
                  condition: t(`Seance.condition.${p.condition}`),
                })}
              </ButtonLink>
            </li>
          )),
        )}
      </ul>
    </section>
  );
}

export function CardView({
  card,
  snapshot,
  seance = null,
}: {
  card: CardData;
  snapshot: LightSnapshot;
  seance?: CatalogueOut | null;
}) {
  const t = useT();
  const locale = useLocale();
  const r = rankText(card.rank);
  const title = t("Light.card.title", {
    ingredient: nameIn(card.ingredient.labels, locale, card.ingredient.key),
    goal: nameIn(card.goal.labels, locale, card.goal.key),
  });
  return (
    <Card as="article" aria-label={title} data-testid="hypothesis-card">
      <header className="flex flex-col gap-1">
        <h3 className="text-lg font-semibold break-words">{title}</h3>
        <p className="mono text-sm">{t(r.key, r.values)}</p>
        <p className="font-bold">{t("Light.rule7")}</p>
      </header>
      <div
        className="flex flex-wrap gap-2"
        aria-label={t("Light.card.signals")}
      >
        {card.signals.map((s) => (
          <Chip key={s.type}>{t(`Light.card.signal.${s.type}`)}</Chip>
        ))}
      </div>
      <details>
        <summary className="min-h-11 cursor-pointer py-2 font-semibold">
          {t("Light.card.details")}
        </summary>
        <div className="flex flex-col gap-4 pt-2">
          {card.signals.map((s) => (
            <Signal key={s.type} s={s} snapshot={snapshot} />
          ))}
          <SourceList sources={card.sources} removed={card.removed_sources} />
          {seance ? (
            <SeanceLinks cat={seance} ingredient={card.ingredient.key} />
          ) : null}
          <p className="text-sm">
            <span className="font-semibold">{t("Light.card.mechanism")}: </span>
            {t("Light.codes.mechanism_source_not_connected")}
          </p>
        </div>
      </details>
    </Card>
  );
}
