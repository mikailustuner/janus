"use client";
/**
 * The two model kit cards of the validation studies page: measured precision per source (with the
 * risk-coverage table for ClinicalTrials.gov) and the gate with what is and is not shown. Every
 * number comes from validation.generated.json; this file only places it in a sentence or a cell.
 */
import { useLocale } from "next-intl";

import { SummaryCard } from "@/components/cards";
import { formatCount } from "@/components/format";
import { ScrollTable } from "@/components/modelkit/common";
import { decimal, VALIDATION } from "@/research/validation";
import { useT, type Translate } from "@/theme/words";

import { Footer } from "./ValidationFooter";

const GATE_ROWS = VALIDATION.modelkitGate.rows;

function useNumbers() {
  const locale = useLocale();
  return {
    n: (x: number) => formatCount(x, locale),
    d: (x: number) => decimal(x, locale, 3),
    pct: (x: number) =>
      new Intl.NumberFormat(locale, {
        style: "percent",
        maximumFractionDigits: 1,
      }).format(x),
  };
}

function range(t: Translate, low: string, high: string) {
  return t("ValidationStudies.modelkitPrecision.interval", { low, high });
}

export function ModelKitPrecisionCard() {
  const t = useT();
  const { n, d, pct } = useNumbers();
  const locale = useLocale();
  const p = VALIDATION.modelkitPrecision;
  const verdict = (met: boolean) =>
    t(
      met
        ? "ValidationStudies.modelkitPrecision.pass"
        : "ValidationStudies.modelkitPrecision.held",
    );
  return (
    <SummaryCard
      id="modelkit-precision"
      title={t("ValidationStudies.modelkitPrecision.title")}
      summary={t("ValidationStudies.modelkitPrecision.summary")}
      className="min-w-0 lg:col-span-2"
      data-testid="vs-modelkit-precision"
    >
      <p>{t("ValidationStudies.modelkitPrecision.tested")}</p>
      <p className="font-bold">
        {t("ValidationStudies.modelkitPrecision.rule", {
          bound: decimal(p.bound, locale, 2),
        })}
      </p>
      <ScrollTable label={t("ValidationStudies.modelkitPrecision.caption")}>
        <table className="tm-table words" data-testid="vs-precision-sources">
          <caption className="sr-only">
            {t("ValidationStudies.modelkitPrecision.caption")}
          </caption>
          <thead>
            <tr>
              {(
                [
                  "source",
                  "values",
                  "precision",
                  "wilson",
                  "lower",
                  "rule",
                ] as const
              ).map((c) => (
                <th key={c} scope="col">
                  {t(`ValidationStudies.modelkitPrecision.cols.${c}`)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {p.sources.map((s) => (
              <tr key={s.key} data-testid={`vs-precision-${s.key}`}>
                <th scope="row">
                  {t(`ValidationStudies.modelkitPrecision.sources.${s.key}`)}
                </th>
                <td className="mono">
                  {n(s.values)} ({n(s.studies)})
                </td>
                <td className="mono">{d(s.precision)}</td>
                <td className="mono">
                  {range(t, d(s.wilsonLow), d(s.wilsonHigh))}
                </td>
                <td className="mono">{d(s.clusterLower)}</td>
                <td className="font-bold">{verdict(s.met)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </ScrollTable>
      <h3 className="font-bold">
        {t("ValidationStudies.modelkitPrecision.curve.title")}
      </h3>
      <p>{t("ValidationStudies.modelkitPrecision.curve.intro")}</p>
      <ScrollTable
        label={t("ValidationStudies.modelkitPrecision.curve.caption")}
      >
        <table className="tm-table words" data-testid="vs-precision-curve">
          <caption className="sr-only">
            {t("ValidationStudies.modelkitPrecision.curve.caption")}
          </caption>
          <thead>
            <tr>
              <th scope="col">
                {t("ValidationStudies.modelkitPrecision.curve.level")}
              </th>
              <th scope="col">
                {t("ValidationStudies.modelkitPrecision.curve.coverage")}
              </th>
              <th scope="col">
                {t("ValidationStudies.modelkitPrecision.cols.precision")}
              </th>
              <th scope="col">
                {t("ValidationStudies.modelkitPrecision.cols.lower")}
              </th>
              <th scope="col">
                {t("ValidationStudies.modelkitPrecision.cols.rule")}
              </th>
            </tr>
          </thead>
          <tbody>
            {p.curve.map((c) => (
              <tr key={c.level} data-testid="vs-curve-row">
                <th scope="row" className="mono">
                  {n(c.level)}
                </th>
                <td className="mono">{pct(c.coverage)}</td>
                <td className="mono">{d(c.precision)}</td>
                <td className="mono">{d(c.clusterLower)}</td>
                <td className="font-bold">{verdict(c.met)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </ScrollTable>
      <p className="text-sm">
        {t("ValidationStudies.modelkitPrecision.recall")}
      </p>
      <p className="text-sm font-bold">
        {t("ValidationStudies.modelkitPrecision.truth")}
      </p>
      <Footer card="modelkitPrecision" t={t} />
    </SummaryCard>
  );
}

/** The sentence values of one row of the "what is shown" table, from the generated numbers. */
function detailValues(
  id: string,
  g: typeof VALIDATION.modelkitGate,
  n: (x: number) => string,
  d: (x: number) => string,
): Record<string, string> {
  switch (id) {
    case "values_read_correctly":
      return {
        k: n(g.read.k),
        n: n(g.read.n),
        low: d(g.read.low),
        high: d(g.read.high),
        lower: d(g.read.clusterLower),
      };
    case "auc_within_2_fold":
      return {
        k: n(g.auc.k),
        n: n(g.auc.n),
        low: d(g.auc.low),
        high: d(g.auc.high),
        drugs: n(g.auc.drugs),
      };
    case "gate":
      return { needed: n(g.needed), both: n(g.both), upper: n(g.upperBound) };
    case "drug_validated":
      return {
        validated: n(g.validated.validated),
        total: n(g.validated.total),
        withSet: n(g.validated.withSet),
      };
    case "document_sources":
      return {
        pmc: d(g.documents.pmc),
        pmcLower: d(g.documents.pmcLower),
        fda: d(g.documents.fda),
        fdaLower: d(g.documents.fdaLower),
      };
    case "unit_errors_across_studies":
      return {
        would: n(g.crossStudy.wouldWithhold),
        checkable: n(g.crossStudy.checkable),
      };
    default:
      return {};
  }
}

export function ModelKitGateCard() {
  const t = useT();
  const { n, d } = useNumbers();
  const g = VALIDATION.modelkitGate;
  const x = g.crossStudy;
  const m = "ValidationStudies.modelkitGate";
  return (
    <SummaryCard
      id="modelkit-gate"
      title={t(`${m}.title`)}
      summary={t(`${m}.summary`)}
      className="min-w-0 lg:col-span-2"
      data-testid="vs-modelkit-gate"
    >
      <h3 className="font-bold">{t(`${m}.resultTitle`)}</h3>
      <p data-testid="vs-gate-result">
        {t(`${m}.result`, {
          needed: n(g.needed),
          both: n(g.both),
          upper: n(g.upperBound),
        })}{" "}
        {t(g.interpretable ? `${m}.met` : `${m}.open`)}
      </p>
      {g.limitedByData ? (
        <p className="font-bold">{t(`${m}.limited`)}</p>
      ) : null}
      <h3 className="font-bold">{t(`${m}.claimTitle`)}</h3>
      <p data-testid="vs-gate-claim">
        {t(`${m}.claim`, {
          drugs: n(g.claim.aucDrugs),
          k: n(g.claim.aucK),
          n: n(g.claim.aucN),
          low: d(g.claim.aucLow),
          high: d(g.claim.aucHigh),
          cmax: t(g.claim.cmaxDrugs === 0 ? `${m}.cmax0` : `${m}.cmaxN`, {
            drugs: n(g.claim.cmaxDrugs),
          }),
          needed: n(g.needed),
          both: n(g.both),
        })}
      </p>
      <h3 className="font-bold">{t(`${m}.shownTitle`)}</h3>
      <ScrollTable label={t(`${m}.shownCaption`)}>
        <table className="tm-table" data-testid="vs-gate-rows">
          <caption className="sr-only">{t(`${m}.shownCaption`)}</caption>
          <thead>
            <tr>
              {(["claim", "status", "detail"] as const).map((c) => (
                <th key={c} scope="col">
                  {t(`${m}.cols.${c}`)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {GATE_ROWS.map((r) => (
              <tr key={r.id} data-testid="vs-gate-row" data-status={r.status}>
                <th scope="row" className="min-w-[12rem] font-bold">
                  {t(`${m}.claims.${r.id}`)}
                </th>
                <td className="whitespace-nowrap font-bold">
                  {t(`${m}.status.${r.status}`)}
                </td>
                <td className="min-w-[16rem]">
                  {t(`${m}.details.${r.id}`, detailValues(r.id, g, n, d))}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </ScrollTable>
      <h3 className="font-bold">{t(`${m}.crossTitle`)}</h3>
      <p data-testid="vs-gate-cross">
        {t(x.switchedOn ? `${m}.crossOn` : `${m}.crossOff`, {
          would: n(x.wouldWithhold),
          checkable: n(x.checkable),
        })}
      </p>
      <p className="text-sm font-bold">
        {t("ValidationStudies.modelkitPrecision.truth")}
      </p>
      <Footer card="modelkitGate" t={t} />
    </SummaryCard>
  );
}
