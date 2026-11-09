"use client";
/**
 * One prescribing cascade in the time machine (experience Req 30.4; time-machine design §10.3):
 * the method, reported time to onset as "reports" with the zero-day caveat and the subset caveat,
 * the shape class only when the sample is not small, the onset curve, our interval next to the
 * published one (never a bare verdict), the risk window with its coverage, the older/younger
 * populations as bands with the validation table, and whether the patient sentence is shown.
 */
import { BackLink, LargeTitle, StatGrid, StatTile } from "@/components/cards";
import { StateView } from "@/components/StateView";
import type { Result } from "@/api/client";
import { useCall } from "@/flow/useCall";
import type { TimeMachineClient } from "@/timemachine/client";
import type { CascadeOut, Catalogue } from "@/timemachine/model";
import {
  englishShownFor,
  linearAxis,
  logAxis,
  patientTiming,
  shapeShown,
  TM_INDEX,
} from "@/timemachine/view";
import { useT } from "@/theme/words";
import { useVocabulary } from "@/vocabulary/use";

import {
  English,
  IntervalChart,
  OnsetCurve,
  References,
  Section,
  TmLabels,
  useHashId,
  useNum,
  useTimeMachineClient,
  ValidationBlock,
  type IntervalRow,
} from "./common";
import { cascadeTitle } from "./names";
import { reasonText } from "./SubstanceView";

async function load(
  c: TimeMachineClient,
  id: string,
): Promise<Result<{ c: CascadeOut; catalogue: Catalogue }>> {
  const [x, cat] = await Promise.all([c.cascade(id), c.catalogue()]);
  if (!x.ok) return x;
  if (!cat.ok) return cat;
  return { ok: true, data: { c: x.data, catalogue: cat.data } };
}

export function CascadeView() {
  const t = useT();
  const vocab = useVocabulary();
  const id = useHashId();
  const { client, recorded } = useTimeMachineClient();
  const call = useCall(client && id ? () => load(client, id) : null, [
    client,
    id,
  ]);
  return (
    <>
      <BackLink href="/research/time-machine">{t("TimeMachine.back")}</BackLink>
      <LargeTitle
        eyebrow={
          call.status === "ok"
            ? t("TimeMachine.cascadeRow", {
                row: call.data.c.cascade.pipc_position,
                method: t(`TimeMachine.method.${call.data.c.cascade.method}`),
              })
            : t("TimeMachine.title")
        }
        title={
          call.status === "ok" && vocab
            ? cascadeTitle(t, vocab, call.data.c.cascade)
            : t("TimeMachine.title")
        }
      />
      <TmLabels recorded={recorded} />
      {id === null ? (
        <StateView state="error" messageKey="TimeMachine.errors.unknown" />
      ) : call.status === "error" ? (
        <StateView
          state="error"
          messageKey={call.error.messageKey}
          retry={call.retry}
        />
      ) : call.status !== "ok" || !vocab ? (
        <StateView state="loading" label={t("TimeMachine.loading")} />
      ) : (
        <Body out={call.data.c} catalogue={call.data.catalogue} />
      )}
    </>
  );
}

function Body({ out, catalogue }: { out: CascadeOut; catalogue: Catalogue }) {
  const t = useT();
  const n = useNum();
  const c = out.cascade;
  const o = c.onset;
  const method = c.method;
  const label = englishShownFor(method, c.method_label);
  const note = englishShownFor(method, c.note);
  const half = c.middle_half_days ?? null;
  const entry = TM_INDEX.cascades.find((e) => e.id === c.cascade_id);
  const gate = entry
    ? entry.index_keys.some((k) =>
        patientTiming(c.pipc_position, k, [out], [entry]),
      )
    : false;

  const compareRows: IntervalRow[] = [];
  if (o)
    compareRows.push({
      label: t("TimeMachine.compare.janus"),
      low: o.q25_days,
      mid: o.median_days,
      high: o.q75_days,
    });
  const p = c.published;
  if (p && p.low_days !== null && p.high_days !== null)
    compareRows.push({
      label: t("TimeMachine.compare.published"),
      low: p.low_days,
      mid: p.median_days,
      high: p.high_days,
      tone: "muted",
    });

  return (
    <div className="grid gap-group lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] lg:items-start">
      <div className="flex min-w-0 flex-col gap-group">
        <Section
          id="tm-method"
          title={t(`TimeMachine.method.${method}`)}
          testId="tm-method"
        >
          {method !== "pbpk" ? (
            <p className="text-sm">{t(`TimeMachine.methodWhy.${method}`)}</p>
          ) : null}
          {method !== "onset_only" && !c.population ? (
            <p className="text-sm">{t("TimeMachine.methodNoOutput")}</p>
          ) : null}
          {/interpretive extension/i.test(c.note) ? (
            <p className="chip self-start" data-testid="tm-extension">
              {t("TimeMachine.extension")}
            </p>
          ) : null}
          {label ? <English>{label}</English> : null}
          {note ? <English>{note}</English> : null}
        </Section>

        <Section
          id="tm-onset"
          title={t("TimeMachine.onset.heading")}
          testId="tm-onset"
        >
          {!o ? (
            <p>{t("TimeMachine.onset.none")}</p>
          ) : (
            <>
              <StatGrid>
                <StatTile
                  value={n.int(o.reports)}
                  label={t("TimeMachine.onset.tile", { count: o.reports })}
                />
              </StatGrid>
              <p data-testid="tm-onset-sentence">
                {t("TimeMachine.onset.sentence", { count: o.reports })}
              </p>
              <p data-testid="tm-zero-day">
                {t("TimeMachine.onset.zeroDay", { count: o.zero_day_reports })}
              </p>
              <p>
                {o.median_ci_low !== null && o.median_ci_high !== null
                  ? t("TimeMachine.onset.median", {
                      median: n.int(o.median_days),
                      low: n.int(o.median_ci_low),
                      high: n.int(o.median_ci_high),
                    })
                  : t("TimeMachine.onset.medianNoCi", {
                      median: n.int(o.median_days),
                    })}
              </p>
              <p>
                {t("TimeMachine.onset.iqr", {
                  q25: n.int(o.q25_days),
                  q75: n.int(o.q75_days),
                })}
              </p>
              {o.small_sample ? (
                <p className="font-bold" data-testid="tm-small-sample">
                  {t("TimeMachine.onset.smallSample")}
                </p>
              ) : shapeShown(c) && o.weibull ? (
                <p data-testid="tm-shape">
                  {t("TimeMachine.onset.shape", {
                    class: t(
                      `TimeMachine.onset.shapeClass.${o.weibull.shape_class}`,
                    ),
                    shape: n.sig(o.weibull.shape),
                    low:
                      o.weibull.shape_ci_low === null
                        ? "—"
                        : n.sig(o.weibull.shape_ci_low),
                    high:
                      o.weibull.shape_ci_high === null
                        ? "—"
                        : n.sig(o.weibull.shape_ci_high),
                  })}
                </p>
              ) : o.weibull_omitted_reason ? (
                <p>{reasonText(t, o.weibull_omitted_reason)}</p>
              ) : null}
              {c.onset_curve && !o.small_sample ? (
                <OnsetCurve
                  days={c.onset_curve.days}
                  share={c.onset_curve.share}
                  band={
                    half ? { start: half.start_days, end: half.end_days } : null
                  }
                  axis={linearAxis(c.onset_curve.days)}
                />
              ) : null}
              {c.risk_window &&
              !(o.small_sample && c.risk_window.basis === "weibull") ? (
                <div className="flex flex-col gap-1">
                  <p data-testid="tm-risk-window">
                    {t("TimeMachine.onset.riskWindow", {
                      basis: t(
                        `TimeMachine.onset.basis.${c.risk_window.basis}`,
                      ),
                      start: n.int(c.risk_window.start_days),
                      end: n.int(c.risk_window.end_days),
                    })}
                  </p>
                  <p className="text-sm text-muted">
                    {t("TimeMachine.onset.coverage")}
                  </p>
                </div>
              ) : null}
              {out.faers_quality ? (
                <p className="text-sm text-muted">
                  {t("TimeMachine.onset.quality", {
                    window: `${out.faers_quality.window[0] ?? ""}–${out.faers_quality.window.at(-1) ?? ""}`,
                    share: n.pct(out.faers_quality.usable_pair_share),
                    pairs: n.int(out.faers_quality.usable_pairs),
                  })}
                </p>
              ) : null}
              <p
                className="text-sm font-bold"
                role="note"
                data-testid="tm-subset-caveat"
              >
                {t("TimeMachine.onset.subsetCaveat")}
              </p>
            </>
          )}
        </Section>

        <Section
          id="tm-published"
          title={t("TimeMachine.published.heading")}
          testId="tm-published"
        >
          {!p ? (
            <p>{t("TimeMachine.published.none")}</p>
          ) : p.kind === "qualitative" ? (
            <p>{t("TimeMachine.published.qualitative")}</p>
          ) : p.kind === "median_iqr" ? (
            <p>
              {t("TimeMachine.published.median_iqr", {
                median: p.median_days === null ? "—" : n.int(p.median_days),
                low: n.int(p.low_days ?? 0),
                high: n.int(p.high_days ?? 0),
              })}
            </p>
          ) : (
            <p>
              {t("TimeMachine.published.window", {
                low: n.int(p.low_days ?? 0),
                high: n.int(p.high_days ?? 0),
              })}
            </p>
          )}
          {p && p.reference_keys.length > 1 && p.kind !== "qualitative" ? (
            <p className="text-sm text-muted">
              {t("TimeMachine.published.combined")}
            </p>
          ) : null}
          {compareRows.length === 2 ? (
            <IntervalChart
              testId="tm-compare"
              legend={t("TimeMachine.compare.legend")}
              columns={[
                t("TimeMachine.compare.cols.low"),
                t("TimeMachine.compare.cols.mid"),
                t("TimeMachine.compare.cols.high"),
              ]}
              title={t("TimeMachine.compare.title")}
              unit={t("TimeMachine.curve.day")}
              axis={linearAxis(compareRows.flatMap((r) => [r.low, r.high]))}
              rows={compareRows}
            />
          ) : null}
          <p className="font-bold" data-testid="tm-agreement">
            {t(`TimeMachine.agreement.${c.agreement ?? "none"}`)}
          </p>
        </Section>

        <Section
          id="tm-gate"
          title={t("TimeMachine.gate.heading")}
          testId="tm-gate"
        >
          <p>
            {gate && half
              ? t("TimeMachine.gate.shown", {
                  start: n.int(half.start_days),
                  end: n.int(half.end_days),
                })
              : !o
                ? t("TimeMachine.gate.none")
                : o.small_sample
                  ? t("TimeMachine.gate.small")
                  : c.agreement === "disagrees"
                    ? t("TimeMachine.gate.agreement")
                    : t("TimeMachine.gate.notComparable")}
          </p>
        </Section>
      </div>

      <div className="flex min-w-0 flex-col gap-group">
        {c.population ? (
          <Section
            id="tm-population"
            title={t("TimeMachine.population.heading")}
            testId="tm-population"
          >
            <p className="text-sm">
              {t("TimeMachine.population.intro", {
                older: c.population.age_range_older,
                younger: c.population.age_range_younger,
              })}
            </p>
            <IntervalChart
              testId="tm-css"
              title={t("TimeMachine.population.title")}
              unit="mg/L"
              axis={logAxis(
                c.population.drugs.flatMap((d) => [
                  d.css_older_mg_per_l.p5,
                  d.css_older_mg_per_l.p95,
                  d.css_younger_mg_per_l.p5,
                  d.css_younger_mg_per_l.p95,
                ]),
              )}
              rows={c.population.drugs.flatMap((d) => [
                {
                  label: t("TimeMachine.population.older", {
                    drug: d.drug,
                    ages: c.population!.age_range_older,
                  }),
                  low: d.css_older_mg_per_l.p5,
                  mid: d.css_older_mg_per_l.p50,
                  high: d.css_older_mg_per_l.p95,
                },
                {
                  label: t("TimeMachine.population.younger", {
                    drug: d.drug,
                    ages: c.population!.age_range_younger,
                  }),
                  low: d.css_younger_mg_per_l.p5,
                  mid: d.css_younger_mg_per_l.p50,
                  high: d.css_younger_mg_per_l.p95,
                  tone: "muted" as const,
                },
              ])}
            />
            {c.population.drugs.map((d) => {
              const verdict =
                catalogue.validation.pbpk.find(
                  (r) => r.drug.toLowerCase() === d.drug.toLowerCase(),
                )?.credibility ?? "failed";
              return (
                <p
                  key={d.drug}
                  className="text-sm"
                  data-testid="tm-population-drug"
                >
                  <span className="font-bold">
                    {t("TimeMachine.population.credibility", {
                      drug: d.drug,
                      verdict,
                    })}
                  </span>{" "}
                  {t("TimeMachine.population.ratio", {
                    drug: d.drug,
                    ratio: n.sig(d.older_to_younger_ratio),
                  })}{" "}
                  {/* An absolute time from a model that is not credible is not shown
                      (pharmacologist review B3). */}
                  {verdict === "credible" &&
                  d.days_to_90pct_steady_state !== null
                    ? t("TimeMachine.population.steady", {
                        drug: d.drug,
                        days: n.int(d.days_to_90pct_steady_state),
                      })
                    : null}
                </p>
              );
            })}
            <p className="text-sm">
              <span className="font-bold">
                {t("TimeMachine.population.doseBasis")}:{" "}
              </span>
              <span lang="en">{c.population.dose_basis}</span>
            </p>
            <English>{c.population.source}</English>
          </Section>
        ) : null}
        {c.population ? (
          <ValidationBlock
            validation={catalogue.validation}
            open
            only={method === "pbpk" ? "pbpk" : "compartmental"}
          />
        ) : null}
        <References
          refs={out.references}
          keys={[...c.reference_keys, ...(p?.reference_keys ?? [])]}
        />
      </div>
    </div>
  );
}
