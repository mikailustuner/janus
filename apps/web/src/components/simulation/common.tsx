"use client";
/**
 * Shared parts of the model screens (simulation-service Req 1, 5): the labels every screen and
 * every result carries, the validation status of the model for the compound, and the band chart
 * (5th-95th percentile area, median line) with its table. Tokens only, no `--risk`: nothing here
 * is a risk to a person. These components never read the medicine list, findings or any patient
 * data (Req 5.2).
 */
import { useLocale } from "next-intl";
import { useMemo } from "react";

import { Disclosure } from "@/components/cards";
import type { HttkResult } from "@/simulation/client";
import { EXPLORER, tableRows } from "@/simulation/explorer";
import { useT } from "@/theme/words";

/** The fixed sentence of the owner decision 2026-11-09, then the in-silico label. */
export function VirtualPopulationNote({
  testId = "sim-disclaimer",
}: {
  testId?: string;
}) {
  const t = useT();
  return (
    <div className="card flex flex-col gap-1 p-4" data-testid={testId}>
      <p className="font-bold">{t("Simulation.virtualPopulation")}</p>
      <p className="text-sm">{t("Simulation.inSilico")}</p>
    </div>
  );
}

export function useNumbers() {
  const locale = useLocale();
  return useMemo(() => {
    const sig = new Intl.NumberFormat(locale, { maximumSignificantDigits: 3 });
    const int = new Intl.NumberFormat(locale, { maximumFractionDigits: 0 });
    return {
      sig: (x: number) => sig.format(x),
      int: (x: number) => int.format(x),
    };
  }, [locale]);
}

/**
 * How well the model matched published data for the compound: the verdict, the fold errors with
 * their direction, what was checked (scope) and what the verdict means (pharmacologist review).
 * `id` keeps headings unique when a page shows it twice (form and result).
 */
export function ValidationStatus({
  compound,
  v,
  id = "sim-validation",
}: {
  compound: string;
  v: {
    credibility: "credible" | "borderline" | "failed";
    cmax_fold: number;
    auc_fold: number;
    auc_independent: boolean;
    cmax_direction: "model_lower" | "model_higher";
    auc_direction: "model_lower" | "model_higher";
  };
  id?: string;
}) {
  const t = useT();
  const n = useNumbers();
  const scope =
    compound === "amlodipine" || compound === "rhein" ? compound : "httk";
  return (
    <section
      className="card flex flex-col gap-2 p-4"
      aria-labelledby={id}
      data-testid={id}
      data-credibility={v.credibility}
    >
      <h2 id={id} className="font-body text-lg font-bold">
        {t("Simulation.validation.title", {
          compound: t(`Simulation.compound.${compound}`),
        })}
      </h2>
      <p className="font-bold">
        {t(`TimeMachine.validation.credibility.${v.credibility}`)}
      </p>
      <p className="text-sm">
        {t("Simulation.validation.folds", {
          cmax: n.sig(v.cmax_fold),
          cdir: t(`Simulation.validation.direction.${v.cmax_direction}`),
          auc: n.sig(v.auc_fold),
          adir: t(`Simulation.validation.direction.${v.auc_direction}`),
        })}
      </p>
      <p className="text-sm">{t(`Simulation.validation.scope.${scope}`)}</p>
      <p className="text-sm">
        {t(`Simulation.validation.meaning.${v.credibility}`)}
      </p>
      {v.auc_independent ? null : (
        <p className="text-sm text-muted">
          {t("Simulation.validation.aucNotIndependent")}
        </p>
      )}
    </section>
  );
}

export interface BandSeries {
  hours: readonly number[];
  p5_ng_ml: readonly number[];
  p50_ng_ml: readonly number[];
  p95_ng_ml: readonly number[];
}

/**
 * The concentration-time distribution over the virtual population: an area from the 5th to the
 * 95th percentile and the median as a line. One image with a text summary; the numbers are in the
 * table under it. There is no single-person curve.
 */
export function BandChart({
  s,
  testId = "sim-chart",
}: {
  s: BandSeries;
  testId?: string;
}) {
  const t = useT();
  const n = useNumbers();
  const W = 320;
  const H = 150;
  const maxH = s.hours.at(-1) ?? 1;
  const maxC = Math.max(1e-12, ...s.p95_ng_ml);
  const x = (h: number) => (h / maxH) * W;
  const y = (c: number) => H - (c / maxC) * H;
  const area = [
    ...s.hours.map(
      (h, i) => `${x(h).toFixed(1)},${y(s.p95_ng_ml[i]!).toFixed(1)}`,
    ),
    ...[...s.hours].reverse().map((h, j) => {
      const i = s.hours.length - 1 - j;
      return `${x(h).toFixed(1)},${y(s.p5_ng_ml[i]!).toFixed(1)}`;
    }),
  ].join(" ");
  const median = s.hours
    .map(
      (h, i) =>
        `${i ? "L" : "M"}${x(h).toFixed(1)},${y(s.p50_ng_ml[i]!).toFixed(1)}`,
    )
    .join(" ");
  const iPeak = s.p50_ng_ml.indexOf(Math.max(...s.p50_ng_ml));
  const alt = t("Simulation.chart.alt", {
    hours: n.int(maxH),
    p50: n.sig(s.p50_ng_ml[iPeak] ?? 0),
    p5: n.sig(s.p5_ng_ml[iPeak] ?? 0),
    p95: n.sig(s.p95_ng_ml[iPeak] ?? 0),
    at: n.sig(s.hours[iPeak] ?? 0),
  });
  const ticksX = [0, 0.25, 0.5, 0.75, 1].map((f) => f * maxH);
  const ticksY = [0, 0.5, 1].map((f) => f * maxC);
  const rows = tableRows(s);
  return (
    <figure className="tile m-0 gap-3" data-testid={testId}>
      <figcaption className="text-sm font-bold">
        {t("Simulation.chart.title")}
      </figcaption>
      <svg
        viewBox={`-44 -8 ${W + 56} ${H + 34}`}
        className="w-full max-w-[640px]"
        role="img"
        aria-label={alt}
      >
        {ticksY.map((c) => (
          <g key={c}>
            <line
              x1={0}
              x2={W}
              y1={y(c)}
              y2={y(c)}
              className="stroke-line"
              strokeWidth={1}
            />
            <text
              x={-6}
              y={y(c) + 4}
              textAnchor="end"
              className="fill-muted text-[10px]"
            >
              {n.sig(c)}
            </text>
          </g>
        ))}
        {ticksX.map((h) => (
          <text
            key={h}
            x={x(h)}
            y={H + 16}
            textAnchor="middle"
            className="fill-muted text-[10px]"
          >
            {n.int(h)}
          </text>
        ))}
        <polygon points={area} className="fill-chip" />
        <path
          d={median}
          fill="none"
          className="stroke-accent"
          strokeWidth={2.5}
        />
      </svg>
      <p className="text-xs text-muted" aria-hidden>
        {t("Simulation.chart.axes")}
      </p>
      <p className="text-sm">{t("Simulation.chart.legend")}</p>
      <Disclosure summary={t("Simulation.chart.table")}>
        <div
          className="overflow-x-auto"
          tabIndex={0}
          role="region"
          aria-label={t("Simulation.chart.table")}
        >
          <table className="tm-table nowrap" data-testid={`${testId}-table`}>
            <caption className="sr-only">{t("Simulation.chart.title")}</caption>
            <thead>
              <tr>
                <th scope="col">{t("Simulation.chart.hour")}</th>
                <th scope="col">P5</th>
                <th scope="col">{t("Simulation.chart.median")}</th>
                <th scope="col">P95</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.h}>
                  <th scope="row">{n.sig(r.h)}</th>
                  <td>{n.sig(r.p5)}</td>
                  <td>{n.sig(r.p50)}</td>
                  <td>{n.sig(r.p95)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Disclosure>
    </figure>
  );
}

/** Peak and single-dose AUC as bands over the virtual population (never one value). */
export function Bands({
  peak,
  auc,
}: {
  peak: readonly [number, number, number] | readonly number[];
  auc: readonly [number, number, number] | readonly number[];
}) {
  const t = useT();
  const n = useNumbers();
  return (
    <ul className="grouped" data-testid="sim-bands">
      <li>
        {t("Simulation.bands.peak", {
          p5: n.sig(peak[0]!),
          p50: n.sig(peak[1]!),
          p95: n.sig(peak[2]!),
        })}
      </li>
      <li>
        {t("Simulation.bands.auc", {
          p5: n.sig(auc[0]!),
          p50: n.sig(auc[1]!),
          p95: n.sig(auc[2]!),
        })}
      </li>
    </ul>
  );
}

const REPO = "https://github.com/mikailustuner/janus/blob/main";

/**
 * Results for the older virtual population carry the measured context (owner decision
 * 2026-11-09): HTTK-Pop's age effect is nearly the same for every drug; FDA labels report a median
 * exposure increase of about 35 % in older adults (Janus research note).
 */
export function OlderAdultsNote() {
  const t = useT();
  const n = useNumbers();
  const o = EXPLORER.calibration.older_adults;
  return (
    <p className="text-sm" data-testid="sim-older-note">
      {t("Simulation.olderAdults.note", {
        low: n.sig(o.httk_pop_ratio_range[0]),
        high: n.sig(o.httk_pop_ratio_range[1]),
        percent: Math.round((o.label_median_exposure_ratio - 1) * 100),
        drugs: o.label_atlas_drugs_numeric,
      })}{" "}
      <a
        className="inline-flex min-h-11 items-center font-bold"
        href={`${REPO}/${o.source}`}
        target="_blank"
        rel="noopener noreferrer"
      >
        {t("Simulation.olderAdults.link")}
      </a>
    </p>
  );
}

/** Compartmental bands: population spread, no calibrated interval, model error as validated. */
export function CompartmentalModelNote() {
  const t = useT();
  return (
    <p className="text-sm" data-testid="sim-model-note">
      {t("Simulation.modelError.compartmental")}
    </p>
  );
}

/**
 * The httk result (owner decision 2026-11-09): the older-to-younger ratio, the model's half-life
 * of the drug with its measured error against Obach 2008 and its calibrated 80 % interval (the only
 * calibrated interval), and the concentrations marked not validated against measured data.
 */
export function HttkResultView({
  r,
  compound,
}: {
  r: HttkResult;
  compound: string;
}) {
  const t = useT();
  const n = useNumbers();
  const h = r.model_error.half_life;
  const pct = (x: number) => Math.round(x * 100);
  return (
    <div className="flex flex-col gap-3" data-testid="sim-httk">
      <p className="text-sm">
        {t("Simulation.result.httkSummary", {
          compound: t(`Simulation.compound.${compound}`),
          samples: r.samples,
        })}
      </p>
      <p className="text-lg font-bold" data-testid="sim-ratio">
        {t("Simulation.result.ratio", {
          ratio: n.sig(r.older_to_younger_median_ratio),
        })}
      </p>
      <OlderAdultsNote />
      <section
        className="tile m-0 flex flex-col gap-2"
        aria-label={t("Simulation.modelError.title")}
        data-testid="sim-model-error"
      >
        <p className="font-bold">
          {t("Simulation.modelError.halfLife", {
            hours: n.sig(r.half_life_h),
            low: n.sig(r.half_life_interval_h[0]!),
            high: n.sig(r.half_life_interval_h[1]!),
          })}
        </p>
        <p className="text-sm" data-testid="sim-interval-label">
          {t("Simulation.modelError.interval", {
            n: h.n_drugs,
            nominal: pct(h.interval_nominal_coverage),
          })}
        </p>
        <p className="text-sm" data-testid="sim-bias">
          {t("Simulation.modelError.bias", {
            n: h.n_drugs,
            date: h.retrieved,
            bias: n.sig(h.geometric_bias_fold),
            direction: t(`Simulation.validation.direction.${h.bias_direction}`),
            within: pct(h.within_2_fold),
            gmfe: n.sig(h.gmfe),
          })}
        </p>
        <p className="text-sm text-muted" lang="en">
          {h.dataset}
        </p>
      </section>
      <p className="text-sm font-bold" data-testid="sim-not-validated">
        {t("Simulation.modelError.notValidated")}
      </p>
      <p className="text-sm">{t("Simulation.result.httkRelative")}</p>
      <Disclosure summary={t("Simulation.result.httkAbsolute")}>
        <ul className="flex flex-col gap-1 text-sm" data-testid="sim-css">
          {r.groups.map((g) => (
            <li key={g.population}>
              {t("Simulation.result.css", {
                population: t(`Simulation.httkPopulation.${g.population}`),
                p5: n.sig(g.css_band_mg_l[0]!),
                p50: n.sig(g.css_band_mg_l[1]!),
                p95: n.sig(g.css_band_mg_l[2]!),
              })}
            </li>
          ))}
        </ul>
      </Disclosure>
      <p className="mono text-xs text-muted">
        R {r.tool_versions.r.replace(/^R version /, "")} · httk{" "}
        {r.tool_versions.httk}
      </p>
    </div>
  );
}
