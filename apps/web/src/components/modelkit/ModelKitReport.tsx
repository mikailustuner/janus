"use client";
/**
 * The system validation report of the model kit (milestone M3): counts, the gate with its metrics,
 * the formulation resolved for the confirmed values, prediction intervals (shown only from 20
 * independent held-out studies, otherwise the reason), the measured precision with its interval
 * and n, and what is still missing. Nothing here is more precise than the data: a share with a
 * small n is shown with its count. Research use only. Not for clinical decisions.
 */
import { useLocale } from "next-intl";

import {
  BackLink,
  GroupedList,
  LargeTitle,
  Row,
  StatGrid,
  StatTile,
} from "@/components/cards";
import { StateView } from "@/components/StateView";
import { useCall } from "@/flow/useCall";
import {
  FORMULATIONS,
  ROUTES,
  STATUSES,
  type IntervalOut,
  type SystemOut,
} from "@/modelkit/model";
import { useT } from "@/theme/words";

import {
  ExperimentalChip,
  Reason,
  ScrollTable,
  Statements,
  useModelKitClient,
} from "./common";

export function ModelKitReport() {
  const t = useT();
  const { client, recorded, failed } = useModelKitClient();
  const call = useCall(client ? () => client.system() : null, [client]);
  return (
    <>
      <BackLink href="/research/model-kit">
        {t("ModelKit.report.back")}
      </BackLink>
      <LargeTitle title={t("ModelKit.report.title")} />
      <div className="flex flex-wrap gap-2">
        <ExperimentalChip />
      </div>
      <Statements recorded={recorded} />
      <p className="max-w-[72ch]">{t("ModelKit.report.intro")}</p>
      {failed || call.status === "error" ? (
        <StateView
          state="error"
          messageKey={
            call.status === "error" ? call.error.messageKey : "Errors.generic"
          }
          retry={call.status === "error" ? call.retry : undefined}
        />
      ) : call.status !== "ok" ? (
        <StateView state="loading" label={t("ModelKit.loading")} />
      ) : (
        <Body s={call.data} />
      )}
    </>
  );
}

function Body({ s }: { s: SystemOut }) {
  const t = useT();
  const locale = useLocale();
  const pct = new Intl.NumberFormat(locale, {
    style: "percent",
    maximumFractionDigits: 0,
  });
  const nf = new Intl.NumberFormat(locale, { maximumFractionDigits: 2 });
  const resolved =
    s.confirmed_parent_rows - (s.formulation_counts.unspecified ?? 0);
  const p = s.precision;
  return (
    <div className="flex min-w-0 flex-col gap-group" data-testid="mk-report">
      <section
        className="flex min-w-0 flex-col gap-group"
        aria-labelledby="mk-rp-counts"
        data-testid="mk-system"
      >
        <h2 id="mk-rp-counts" className="group-header">
          {t("ModelKit.report.countsTitle")}
        </h2>
        <StatGrid>
          {STATUSES.map((st) => (
            <StatTile
              key={st}
              value={String(s.by_status[st] ?? 0)}
              label={t(`ModelKit.status.${st}`)}
              sentence={t("ModelKit.system.countSentence", {
                count: s.by_status[st] ?? 0,
                status: t(`ModelKit.status.${st}`),
              })}
            />
          ))}
          <StatTile
            value={String(s.n_drugs_both_tested)}
            label={t("ModelKit.system.bothTested")}
            sentence={t("ModelKit.system.bothTestedSentence", {
              count: s.n_drugs_both_tested,
            })}
          />
          <StatTile
            value={String(s.n_with_set)}
            label={t("ModelKit.report.withSet")}
            sentence={t("ModelKit.report.withSetSentence", {
              set: s.n_with_set,
              complete: s.n_complete_set,
            })}
          />
          <StatTile
            value={String(s.n_studies)}
            label={t("ModelKit.system.studies")}
            sentence={t("ModelKit.system.studiesSentence", {
              count: s.n_studies,
            })}
          />
        </StatGrid>
        <p>{t("ModelKit.report.inStore", { count: s.n_drugs })}</p>
        <p data-testid="mk-rows">
          {t("ModelKit.report.rowsSentence", {
            rows: s.rows_total,
            confirmed: s.rows_confirmed,
            parent: s.confirmed_parent_rows,
          })}
        </p>
        <ScrollTable label={t("ModelKit.system.metrics")}>
          <table className="tm-table words" data-testid="mk-system-metrics">
            <caption className="sr-only">
              {t("ModelKit.system.metrics")}
            </caption>
            <thead>
              <tr>
                <th scope="col">{t("ModelKit.val.metric")}</th>
                <th scope="col">{t("ModelKit.system.drugs")}</th>
                <th scope="col">{t("ModelKit.val.gmfe")}</th>
                <th scope="col">{t("ModelKit.system.within")}</th>
                <th scope="col">{t("ModelKit.system.points")}</th>
              </tr>
            </thead>
            <tbody>
              {s.metrics.map((m) => (
                <tr key={m.name}>
                  <th scope="row">{t(`ModelKit.val.${m.name}`)}</th>
                  <td className="mono">{m.n_drugs}</td>
                  <td className="mono">
                    {m.gmfe === null ? "—" : nf.format(m.gmfe)}
                  </td>
                  <td>
                    <span className="mono">
                      {t("ModelKit.system.ofN", {
                        k: m.within_2_fold,
                        n: m.n_drugs,
                      })}
                    </span>
                    {m.within_2_fold_share !== null &&
                    m.wilson_low !== null &&
                    m.wilson_high !== null ? (
                      <span className="block text-muted">
                        {t("ModelKit.system.wilson", {
                          share: pct.format(m.within_2_fold_share),
                          low: pct.format(m.wilson_low),
                          high: pct.format(m.wilson_high),
                        })}
                      </span>
                    ) : null}
                  </td>
                  <td>
                    <span className="mono">
                      {t("ModelKit.system.pointsOf", {
                        k: m.points_within_2_fold,
                        n: m.n_points,
                      })}
                    </span>
                    {m.points_gmfe !== null ? (
                      <span className="block text-muted">
                        {t("ModelKit.system.pointsGmfe", {
                          gmfe: nf.format(m.points_gmfe),
                        })}
                      </span>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollTable>
        <p className="font-bold" data-testid="mk-gate">
          {t(
            s.interpretable
              ? "ModelKit.system.gateReached"
              : "ModelKit.system.gateNotReached",
            {
              both: s.n_drugs_both_tested,
              min: s.min_drugs_for_interpretation,
            },
          )}
        </p>
      </section>

      <section
        className="flex min-w-0 flex-col gap-group"
        aria-labelledby="mk-rp-form"
        data-testid="mk-formulation"
      >
        <h2 id="mk-rp-form" className="group-header">
          {t("ModelKit.report.formulationTitle")}
        </h2>
        <p className="max-w-[72ch]">
          {t("ModelKit.report.formulationIntro", {
            share: pct.format(
              s.confirmed_parent_rows ? resolved / s.confirmed_parent_rows : 0,
            ),
            k: resolved,
            n: s.confirmed_parent_rows,
          })}
        </p>
        <ScrollTable label={t("ModelKit.report.formulationTable")}>
          <table className="tm-table words" data-testid="mk-formulation-table">
            <caption className="sr-only">
              {t("ModelKit.report.formulationTable")}
            </caption>
            <thead>
              <tr>
                <th scope="col">{t("ModelKit.report.kind")}</th>
                <th scope="col">{t("ModelKit.report.values")}</th>
              </tr>
            </thead>
            <tbody>
              {FORMULATIONS.map((f) => (
                <tr key={f}>
                  <th scope="row">{t(`ModelKit.ev.formulations.${f}`)}</th>
                  <td className="mono">{s.formulation_counts[f] ?? 0}</td>
                </tr>
              ))}
              {ROUTES.map((r) => (
                <tr key={r}>
                  <th scope="row">
                    {t("ModelKit.ev.route")}: {t(`ModelKit.ev.routes.${r}`)}
                  </th>
                  <td className="mono">{s.route_counts[r] ?? 0}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollTable>
      </section>

      <section
        className="flex min-w-0 flex-col gap-group"
        aria-labelledby="mk-rp-int"
        data-testid="mk-intervals"
      >
        <h2 id="mk-rp-int" className="group-header">
          {t("ModelKit.report.intervalsTitle")}
        </h2>
        <ul className="m-0 flex list-none flex-col gap-2 p-0">
          {s.intervals.map((i) => (
            <li key={i.metric} data-testid={`mk-interval-${i.metric}`}>
              <IntervalSentence i={i} />
            </li>
          ))}
        </ul>
        <p className="text-sm text-muted" data-testid="mk-interval">
          <Reason code={s.conformal} />
        </p>
      </section>

      <section
        className="flex min-w-0 flex-col gap-group"
        aria-labelledby="mk-rp-prec"
        data-testid="mk-precision"
      >
        <h2 id="mk-rp-prec" className="group-header">
          {t("ModelKit.report.precisionTitle")}
        </h2>
        {p ? (
          <>
            <p className="max-w-[72ch] font-bold">
              {t("ModelKit.report.precisionLine", {
                share: pct.format(p.share),
                low: pct.format(p.wilson_low),
                high: pct.format(p.wilson_high),
                n: p.n,
                date: p.measured_on,
              })}
            </p>
            <p className="max-w-[72ch]">
              {t("ModelKit.report.precisionConservative", {
                share: pct.format(p.share_conservative),
                low: pct.format(p.wilson_low_conservative),
                high: pct.format(p.wilson_high_conservative),
                n: p.n_conservative,
              })}
            </p>
            {p.formulation_n !== null &&
            p.formulation_share !== null &&
            p.formulation_wilson_low !== null &&
            p.formulation_wilson_high !== null ? (
              <p className="max-w-[72ch]">
                {t("ModelKit.report.precisionFormulation", {
                  share: pct.format(p.formulation_share),
                  low: pct.format(p.formulation_wilson_low),
                  high: pct.format(p.formulation_wilson_high),
                  n: p.formulation_n,
                })}
              </p>
            ) : null}
            <p className="max-w-[72ch] text-sm">
              {t("ModelKit.report.precisionTarget", {
                target: pct.format(p.target),
              })}
            </p>
          </>
        ) : (
          <p>{t("ModelKit.report.precisionNone")}</p>
        )}
      </section>

      <section
        className="flex min-w-0 flex-col gap-group"
        aria-labelledby="mk-rp-miss"
        data-testid="mk-missing"
      >
        <h2 id="mk-rp-miss" className="group-header">
          {t("ModelKit.report.missingTitle")}
        </h2>
        <GroupedList
          header={t("ModelKit.report.missingTitle")}
          headingId="mk-rp-miss-list"
        >
          {s.missing.map((c) => (
            <Row key={c}>
              <Reason code={c} />
            </Row>
          ))}
          {s.caveats.map((c) => (
            <Row key={c}>
              <Reason code={c} />
            </Row>
          ))}
        </GroupedList>
        <Counts
          title={t("ModelKit.report.noSetTitle")}
          counts={s.no_set_reasons}
        />
        <Counts
          title={t("ModelKit.report.notValidatedTitle")}
          counts={s.not_validated_reasons}
        />
      </section>
    </div>
  );
}

function IntervalSentence({ i }: { i: IntervalOut }) {
  const t = useT();
  const metric = t(`ModelKit.val.${i.metric}`);
  const pct = new Intl.NumberFormat(useLocale(), {
    style: "percent",
    maximumFractionDigits: 0,
  });
  const nf = new Intl.NumberFormat(useLocale(), { maximumFractionDigits: 2 });
  return i.shown && i.fold_half !== null ? (
    <>
      {t("ModelKit.report.intervalsShownSentence", {
        metric,
        fold: nf.format(i.fold_half),
        coverage: pct.format(i.coverage),
        n: i.n_studies,
      })}
    </>
  ) : (
    <>
      {t("ModelKit.report.intervalsSentence", {
        metric,
        n: i.n_studies,
        min: i.min_studies,
      })}
    </>
  );
}

function Counts({
  title,
  counts,
}: {
  title: string;
  counts: Record<string, number>;
}) {
  const t = useT();
  const entries = Object.entries(counts).sort((a, b) => b[1] - a[1]);
  if (!entries.length) return null;
  return (
    <ScrollTable label={title}>
      <table className="tm-table words">
        <caption className="font-bold">{title}</caption>
        <tbody>
          {entries.map(([code, n]) => (
            <tr key={code}>
              <th scope="row">
                <Reason code={code} />
              </th>
              <td className="mono whitespace-nowrap">
                {t("ModelKit.report.drugsCount", { count: n })}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </ScrollTable>
  );
}
