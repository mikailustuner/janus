"use client";
/**
 * Observed against predicted (model-kit Req 6.2): a log-log scatter with one mark per held-out
 * observation (circle = AUC, square = Cmax, hollow = outside 2-fold), the shaded 2-fold band
 * between y = x / 2 and y = 2x, and the data table beneath it. The table carries every number;
 * the plot is a picture of it.
 */
import { useLocale } from "next-intl";
import { useMemo } from "react";

import { bandPolygon, logAxis, logPos, type PointOut } from "@/modelkit/model";
import { useT } from "@/theme/words";

const SIZE = 300;
const ML = 56;
const MT = 12;
const MB = 44;
const MR = 12;

export function ValidationChart({ points }: { points: readonly PointOut[] }) {
  const t = useT();
  const locale = useLocale();
  const nf = useMemo(
    () => new Intl.NumberFormat(locale, { maximumSignificantDigits: 4 }),
    [locale],
  );
  const axis = useMemo(
    () => logAxis(points.flatMap((p) => [p.observed, p.predicted])),
    [points],
  );
  const X = (v: number) => ML + logPos(axis, v) * SIZE;
  const Y = (v: number) => MT + SIZE - logPos(axis, v) * SIZE;
  const band = bandPolygon(axis)
    .map(([x, y]) => `${X(x)},${Y(y)}`)
    .join(" ");
  const count = (m: "auc" | "cmax") => points.filter((p) => p.metric === m);
  const inside = points.filter((p) => p.within_2_fold).length;
  const alt = t("ModelKit.chart.alt", {
    n: points.length,
    auc: count("auc").length,
    cmax: count("cmax").length,
    inside,
  });
  return (
    <figure className="tile m-0 gap-3" data-testid="mk-chart">
      <figcaption className="text-sm font-bold">
        {t("ModelKit.chart.title")}
      </figcaption>
      <svg
        viewBox={`0 0 ${ML + SIZE + MR} ${MT + SIZE + MB}`}
        className="w-full max-w-[420px]"
        role="img"
        aria-label={alt}
      >
        <polygon points={band} className="fill-chip" />
        {axis.ticks.map((v) => (
          <g key={v}>
            <line
              x1={ML}
              x2={ML + SIZE}
              y1={Y(v)}
              y2={Y(v)}
              className="stroke-line"
              strokeWidth={1}
            />
            <line
              x1={X(v)}
              x2={X(v)}
              y1={MT}
              y2={MT + SIZE}
              className="stroke-line"
              strokeWidth={1}
            />
            <text
              x={ML - 6}
              y={Y(v) + 4}
              textAnchor="end"
              className="fill-muted text-[11px]"
            >
              {nf.format(v)}
            </text>
            <text
              x={X(v)}
              y={MT + SIZE + 16}
              textAnchor="middle"
              className="fill-muted text-[11px]"
            >
              {nf.format(v)}
            </text>
          </g>
        ))}
        <line
          x1={X(axis.min)}
          y1={Y(axis.min)}
          x2={X(axis.max)}
          y2={Y(axis.max)}
          className="stroke-muted"
          strokeWidth={1.5}
          strokeDasharray="5 4"
        />
        {points.map((p) => {
          const cx = X(p.observed);
          const cy = Y(p.predicted);
          const hollow = !p.within_2_fold;
          const common = {
            className: hollow
              ? `${p.metric === "auc" ? "stroke-accent" : "stroke-fg"} fill-surface`
              : p.metric === "auc"
                ? "fill-accent stroke-surface"
                : "fill-fg stroke-surface",
            strokeWidth: hollow ? 2.5 : 1,
          };
          return p.metric === "auc" ? (
            <circle key={p.evidence_id} cx={cx} cy={cy} r={6} {...common} />
          ) : (
            <rect
              key={p.evidence_id}
              x={cx - 5.5}
              y={cy - 5.5}
              width={11}
              height={11}
              {...common}
            />
          );
        })}
        <text
          x={ML + SIZE / 2}
          y={MT + SIZE + 36}
          textAnchor="middle"
          className="fill-fg text-[12px] font-bold"
        >
          {t("ModelKit.chart.observed")}
        </text>
        <text
          transform={`translate(12 ${MT + SIZE / 2}) rotate(-90)`}
          textAnchor="middle"
          className="fill-fg text-[12px] font-bold"
        >
          {t("ModelKit.chart.predicted")}
        </text>
      </svg>
      <ul className="m-0 flex list-none flex-wrap gap-x-4 gap-y-1 p-0 text-sm">
        <li className="flex items-center gap-1.5">
          <svg width="14" height="14" aria-hidden>
            <circle cx="7" cy="7" r="6" className="fill-accent" />
          </svg>
          {t("ModelKit.val.auc")}
        </li>
        <li className="flex items-center gap-1.5">
          <svg width="14" height="14" aria-hidden>
            <rect x="1" y="1" width="12" height="12" className="fill-fg" />
          </svg>
          {t("ModelKit.val.cmax")}
        </li>
        <li className="flex items-center gap-1.5">
          <svg width="14" height="14" aria-hidden>
            <rect
              x="2"
              y="2"
              width="10"
              height="10"
              className="fill-surface stroke-fg"
              strokeWidth="2.5"
            />
          </svg>
          {t("ModelKit.chart.hollow")}
        </li>
        <li className="flex items-center gap-1.5">
          <svg width="14" height="14" aria-hidden>
            <rect x="0" y="0" width="14" height="14" className="fill-chip" />
          </svg>
          {t("ModelKit.chart.band")}
        </li>
        <li className="flex items-center gap-1.5">
          <svg width="18" height="14" aria-hidden>
            <line
              x1="0"
              y1="7"
              x2="18"
              y2="7"
              className="stroke-muted"
              strokeWidth="1.5"
              strokeDasharray="4 3"
            />
          </svg>
          {t("ModelKit.chart.diagonal")}
        </li>
      </ul>
      <p className="text-sm text-muted">{t("ModelKit.chart.unitNote")}</p>
      <div
        className="card relative overflow-x-auto p-0"
        tabIndex={0}
        role="region"
        aria-label={t("ModelKit.chart.tableTitle")}
      >
        <table className="tm-table nowrap" data-testid="mk-chart-table">
          <caption className="sr-only">
            {t("ModelKit.chart.tableTitle")}
          </caption>
          <thead>
            <tr>
              <th scope="col">{t("ModelKit.val.metric")}</th>
              <th scope="col">{t("ModelKit.chart.study")}</th>
              <th scope="col">{t("ModelKit.chart.dose")}</th>
              <th scope="col">{t("ModelKit.chart.observed")}</th>
              <th scope="col">{t("ModelKit.chart.predicted")}</th>
              <th scope="col">{t("ModelKit.val.ratio")}</th>
              <th scope="col">{t("ModelKit.val.within")}</th>
            </tr>
          </thead>
          <tbody>
            {points.map((p) => (
              <tr key={p.evidence_id}>
                <th scope="row">{t(`ModelKit.val.${p.metric}`)}</th>
                <td lang="en">{p.study_id}</td>
                <td className="mono">{nf.format(p.dose_mg)}</td>
                <td className="mono">{nf.format(p.observed)}</td>
                <td className="mono">{nf.format(p.predicted)}</td>
                <td className="mono">{nf.format(p.ratio)}</td>
                <td>
                  {p.within_2_fold ? t("ModelKit.yes") : t("ModelKit.no")}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </figure>
  );
}
