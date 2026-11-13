"use client";
/**
 * Validation studies (researcher area): one card per pre-registered study, from the generated
 * numbers (src/research/validation.generated.json). Static, no request. Every card states what was
 * tested, the results with their 95 % intervals, whether each hypothesis was met, the protocol and
 * results documents, and that expert review has not yet been done.
 */
import { useLocale } from "next-intl";
import type { ReactNode } from "react";

import { BackLink, LargeTitle, SummaryCard } from "@/components/cards";
import { formatCount } from "@/components/format";
import {
  calibrationValues,
  CARDS,
  hypothesisKey,
  percent,
  proportionValues,
  shareValues,
  VALIDATION,
  type CardKey,
} from "@/research/validation";
import { useT, type Translate } from "@/theme/words";

import { Footer } from "./ValidationFooter";
import { ModelKitGateCard, ModelKitPrecisionCard } from "./ModelKitCards";

function Outcome({
  label,
  sentence,
  met,
  bound,
  t,
}: {
  label: string;
  sentence: string;
  met: boolean;
  bound: string;
  t: Translate;
}) {
  return (
    <li className="flex min-w-0 flex-col gap-0.5">
      <span className="font-bold">{label}</span>
      <span className="mono">{sentence}</span>
      <span className="text-sm text-muted">
        {t(hypothesisKey(met))} {bound}
      </span>
    </li>
  );
}

function CascadeCard() {
  const t = useT();
  const locale = useLocale();
  const c = VALIDATION.cascade;
  const n = (x: number) => formatCount(x, locale);
  return (
    <SummaryCard
      id="cascade"
      title={t("ValidationStudies.cascade.title")}
      summary={t("ValidationStudies.cascade.summary")}
      data-testid="vs-cascade"
    >
      <p>
        {t("ValidationStudies.cascade.tested", {
          listed: n(c.listedCascades),
          published: n(c.publishedCascades),
          negatives: n(c.nonCascadePairs),
          cases: n(c.caseReports),
        })}
      </p>
      <ul className="grouped-plain">
        <Outcome
          t={t}
          label={t("ValidationStudies.cascade.specificity")}
          sentence={t(
            "ValidationStudies.proportion",
            proportionValues(c.specificity, locale),
          )}
          met={c.specificity.met}
          bound={t("ValidationStudies.cascade.bound", {
            bound: decimalBound(c.specificity.bound, locale),
          })}
        />
        <Outcome
          t={t}
          label={t("ValidationStudies.cascade.sensitivity")}
          sentence={t(
            "ValidationStudies.proportion",
            proportionValues(c.sensitivity, locale),
          )}
          met={c.sensitivity.met}
          bound={t("ValidationStudies.cascade.bound", {
            bound: decimalBound(c.sensitivity.bound, locale),
          })}
        />
      </ul>
      <p className="font-bold">
        {t("ValidationStudies.cascade.scope", { listed: n(c.listedCascades) })}
      </p>
      <p>
        {t("ValidationStudies.cascade.inScope", {
          k: n(c.inScope.k),
          n: n(c.inScope.n),
        })}
      </p>
      <p>
        {t("ValidationStudies.cascade.burden", {
          k: n(c.comparisonAlert.k),
          n: n(c.comparisonAlert.n),
        })}
      </p>
      <Footer card="cascade" t={t} />
    </SummaryCard>
  );
}

function decimalBound(x: number, locale: string): string {
  return new Intl.NumberFormat(locale, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(x);
}

function FaersCard() {
  const t = useT();
  const locale = useLocale();
  const f = VALIDATION.faers;
  return (
    <SummaryCard
      id="faers"
      title={t("ValidationStudies.faers.title")}
      summary={t("ValidationStudies.faers.summary")}
      data-testid="vs-faers"
    >
      <p>
        {t("ValidationStudies.faers.tested", {
          positive: formatCount(f.auc.nPositive, locale),
          negative: formatCount(f.auc.nNegative, locale),
        })}
      </p>
      <ul className="grouped-plain">
        <Outcome
          t={t}
          label={t("ValidationStudies.faers.aucLabel")}
          sentence={t("ValidationStudies.faers.auc", calibrationValues(locale))}
          met={f.auc.met}
          bound={t("ValidationStudies.faers.aucBound", {
            bound: decimalBound(f.auc.bound, locale),
          })}
        />
      </ul>
      <p className="font-bold">
        {t("ValidationStudies.faers.intervals", {
          ...shareValues(f.negativesNominal, locale),
          calibrated: percent(f.negativesCalibrated.estimate, locale, 1),
        })}
      </p>
      <p>{t("ValidationStudies.faers.intervalsPlain")}</p>
      <p>
        {t("ValidationStudies.faers.evans", {
          sensitivity: percent(f.evansSensitivity.estimate, locale),
          specificity: percent(f.evansSpecificity.estimate, locale),
        })}
      </p>
      <p className="font-bold">{t("ValidationStudies.faers.lookCloser")}</p>
      <Footer card="faers" t={t} />
    </SummaryCard>
  );
}

const VIEWS: Record<CardKey, () => ReactNode> = {
  cascade: CascadeCard,
  faers: FaersCard,
  modelkitPrecision: ModelKitPrecisionCard,
  modelkitGate: ModelKitGateCard,
};

export function ValidationStudies() {
  const t = useT();
  return (
    <>
      <BackLink href="/research">{t("Research.title")}</BackLink>
      <LargeTitle
        title={t("ValidationStudies.title")}
        summary={t("ValidationStudies.summary")}
      />
      <p className="max-w-[72ch]">{t("ValidationStudies.intro")}</p>
      <p className="card p-4 font-bold" data-testid="vs-review">
        {t("ValidationStudies.review")}
      </p>
      <div className="grid gap-group lg:grid-cols-2 lg:items-start">
        {CARDS.map((key) => {
          const View = VIEWS[key];
          return <View key={key} />;
        })}
      </div>
    </>
  );
}
