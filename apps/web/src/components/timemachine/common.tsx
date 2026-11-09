"use client";
/**
 * Shared parts of the time-machine screens (experience Req 30, DP58–DP64): the client (live or the
 * recorded demo fixture), the labels every screen carries, accessible interval and curve charts
 * with a table alternative, the validation table, sources and references. Tokens only; neutral
 * colours (no `--risk`: nothing here is a risk to a person).
 */
import { useLocale } from "next-intl";
import {
  useEffect,
  useMemo,
  useState,
  useSyncExternalStore,
  type ReactNode,
} from "react";

import { Disclosure, GroupedList, Row } from "@/components/cards";
import { useDemo } from "@/demo/session";
import {
  demoTimeMachine,
  liveTimeMachine,
  loadTimeMachineFixture,
  type TimeMachineClient,
  type TimeMachineFixture,
} from "@/timemachine/client";
import type { Catalogue, Reference, ValidationRow } from "@/timemachine/model";
import { place, type Axis } from "@/timemachine/view";
import { useT } from "@/theme/words";

const noSubscribe = () => () => {};

/**
 * The live client, or the demo client once the fixture is loaded. Nothing is chosen before the
 * first client render, so a live request never leaves in demo mode.
 */
export function useTimeMachineClient(): {
  client: TimeMachineClient | null;
  recorded: string | null;
} {
  const demo = useDemo();
  const mounted = useSyncExternalStore(
    noSubscribe,
    () => true,
    () => false,
  );
  const [fx, setFx] = useState<TimeMachineFixture | null>(null);
  useEffect(() => {
    let live = true;
    if (demo) loadTimeMachineFixture().then((f) => live && setFx(f));
    return () => {
      live = false;
    };
  }, [demo]);
  const client = useMemo(
    () =>
      !mounted
        ? null
        : demo
          ? fx
            ? demoTimeMachine(fx)
            : null
          : liveTimeMachine,
    [mounted, demo, fx],
  );
  return { client, recorded: demo ? (fx?.recorded ?? null) : null };
}

/** The id after `#` (an id is a code, not personal data); undefined before the first read. */
export function useHashId(): string | null | undefined {
  const [id, setId] = useState<string | null | undefined>(undefined);
  useEffect(() => {
    const read = () => {
      const v = decodeURIComponent(location.hash.slice(1));
      setId(/^[a-z][a-z0-9_]{0,63}$/.test(v) ? v : null);
    };
    read();
    window.addEventListener("hashchange", read);
    return () => window.removeEventListener("hashchange", read);
  }, []);
  return id;
}

export function useNum() {
  const locale = useLocale();
  return useMemo(() => {
    const sig = new Intl.NumberFormat(locale, { maximumSignificantDigits: 3 });
    const int = new Intl.NumberFormat(locale, { maximumFractionDigits: 0 });
    const pct = new Intl.NumberFormat(locale, {
      style: "percent",
      maximumFractionDigits: 1,
    });
    return {
      sig: (x: number) => sig.format(x),
      int: (x: number) => int.format(x),
      pct: (x: number) => pct.format(x),
    };
  }, [locale]);
}

/** The labels every time-machine screen carries (Req 30.2; time-machine Req 9.5). */
export function TmLabels({ recorded }: { recorded: string | null }) {
  const t = useT();
  return (
    <div className="flex flex-col gap-2">
      <p className="card p-4 font-bold" data-testid="tm-in-silico">
        {t("TimeMachine.inSilico")}
      </p>
      <p className="text-sm font-bold" data-testid="rule7">
        {t("Research.rule7")}
      </p>
      <p className="text-sm text-muted" role="note" data-testid="tm-review">
        {t("TimeMachine.review")}
      </p>
      {recorded ? (
        <p className="chip self-start" data-testid="tm-demo">
          {t("TimeMachine.demo", { date: recorded })}
        </p>
      ) : null}
    </div>
  );
}

/** An English source string shown verbatim in the research area (design §10.3). */
export function English({ children }: { children: string }) {
  const t = useT();
  return (
    <p className="text-sm break-words">
      <span className="text-muted">{t("TimeMachine.english")}: </span>
      <span lang="en">{children}</span>
    </p>
  );
}

// --- charts ------------------------------------------------------------------------------

export interface IntervalRow {
  label: string;
  low: number;
  mid: number | null;
  high: number;
  /** "accent" for Janus's figures, "muted" for a comparison (published, younger group). */
  tone?: "accent" | "muted";
}

/**
 * Horizontal interval bars on one axis (concentration bands, onset vs published): a band from low
 * to high and a dot at the median, decade or round ticks, an optional reference line (potency).
 * The plot is one image with a text summary; the same numbers are in a table under it (Req 30.5).
 */
export function IntervalChart({
  title,
  rows,
  axis,
  unit,
  reference,
  testId,
  legend,
  columns,
}: {
  legend?: string;
  /** Column heads of the table (default P5 / P50 / P95). */
  columns?: [string, string, string];
  title: string;
  rows: readonly IntervalRow[];
  axis: Axis;
  unit: string;
  reference?: { value: number; label: string } | null;
  testId?: string;
}) {
  const t = useT();
  const n = useNum();
  const summary = rows
    .map(
      (r) =>
        `${r.label}: ${n.sig(r.low)}–${n.sig(r.high)}${r.mid !== null ? ` (${n.sig(r.mid)})` : ""} ${unit}`,
    )
    .concat(
      reference
        ? [`${reference.label}: ${n.sig(reference.value)} ${unit}`]
        : [],
    )
    .join("; ");
  return (
    <figure className="tile m-0 gap-3" data-testid={testId}>
      <figcaption className="text-sm font-bold">{title}</figcaption>
      <div
        role="img"
        aria-label={`${title}. ${summary}.`}
        className="flex flex-col gap-3"
      >
        {rows.map((r) => {
          const lo = place(axis, r.low) * 100;
          const hi = place(axis, r.high) * 100;
          return (
            <div key={r.label} className="flex flex-col gap-1" aria-hidden>
              <span className="text-sm break-words">{r.label}</span>
              <div className="relative mx-2 h-6">
                <div className="absolute inset-x-0 top-1/2 h-px -translate-y-1/2 bg-line" />
                {reference ? (
                  <div
                    className="absolute top-0 bottom-0 w-0.5 -translate-x-1/2 bg-fg"
                    style={{ left: `${place(axis, reference.value) * 100}%` }}
                  />
                ) : null}
                <div
                  className={`absolute top-1/2 h-3 -translate-y-1/2 rounded-full ${r.tone === "muted" ? "bg-muted opacity-60" : "bg-chip-fg opacity-75"}`}
                  style={{ left: `${lo}%`, width: `${Math.max(1, hi - lo)}%` }}
                />
                {r.mid !== null ? (
                  <div
                    className={`absolute top-1/2 size-4 -translate-x-1/2 -translate-y-1/2 rounded-full border-[3px] bg-bg ${r.tone === "muted" ? "border-muted" : "border-accent"}`}
                    style={{ left: `${place(axis, r.mid) * 100}%` }}
                  />
                ) : null}
              </div>
            </div>
          );
        })}
        <div className="mono relative mx-2 h-4 text-xs text-muted" aria-hidden>
          {axis.ticks.map((x) => (
            <span
              key={x}
              className="absolute -translate-x-1/2 whitespace-nowrap"
              style={{ left: `${place(axis, x) * 100}%` }}
            >
              {n.sig(x)}
            </span>
          ))}
        </div>
        <p className="text-xs text-muted" aria-hidden>
          {unit}
          {axis.kind === "log" ? " · log" : ""}
          {reference ? ` · ${reference.label}` : ""}
        </p>
      </div>
      <p className="text-sm text-muted">{legend ?? t("TimeMachine.legend")}</p>
      <Disclosure summary={t("TimeMachine.table")}>
        <div
          className="overflow-x-auto"
          tabIndex={0}
          role="region"
          aria-label={t("TimeMachine.tableRegion")}
        >
          <table
            className="tm-table"
            data-testid={testId ? `${testId}-table` : undefined}
          >
            <caption className="sr-only">{title}</caption>
            <thead>
              <tr>
                <th scope="col">{title.split(":")[0]}</th>
                <th scope="col">{columns?.[0] ?? "P5"}</th>
                <th scope="col">{columns?.[1] ?? "P50"}</th>
                <th scope="col">{columns?.[2] ?? "P95"}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.label}>
                  <th scope="row">{r.label}</th>
                  <td>{n.sig(r.low)}</td>
                  <td>{r.mid === null ? "—" : n.sig(r.mid)}</td>
                  <td>{n.sig(r.high)}</td>
                </tr>
              ))}
              {reference ? (
                <tr>
                  <th scope="row">{reference.label}</th>
                  <td colSpan={3}>{n.sig(reference.value)}</td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </Disclosure>
    </figure>
  );
}

/**
 * The onset distribution (design §10.3 `onset_curve`): the cumulative share of reports by day as a
 * line, the middle half of the reports as a shaded band. SVG with a text alternative and a table.
 */
export function OnsetCurve({
  days,
  share,
  band,
  axis,
}: {
  days: readonly number[];
  share: readonly number[];
  band: { start: number; end: number } | null;
  axis: Axis;
}) {
  const t = useT();
  const n = useNum();
  const W = 320;
  const H = 140;
  const x = (d: number) => place(axis, d) * W;
  const y = (s: number) => H - Math.min(1, Math.max(0, s)) * H;
  const path = days
    .map(
      (d, i) =>
        `${i ? "L" : "M"}${x(d).toFixed(1)},${y(share[i] ?? 0).toFixed(1)}`,
    )
    .join(" ");
  const alt = t("TimeMachine.curve.alt", {
    first: n.pct(share[0] ?? 0),
    firstDay: n.int(days[0] ?? 0),
    last: n.pct(share.at(-1) ?? 0),
    lastDay: n.int(days.at(-1) ?? 0),
    q25: band ? n.int(band.start) : "—",
    q75: band ? n.int(band.end) : "—",
  });
  return (
    <figure className="tile m-0 gap-3" data-testid="tm-curve">
      <figcaption className="text-sm font-bold">
        {t("TimeMachine.curve.title")}
      </figcaption>
      <svg
        viewBox={`-30 -8 ${W + 40} ${H + 30}`}
        className="w-full max-w-[560px]"
        role="img"
        aria-label={alt}
      >
        {band ? (
          <rect
            x={x(band.start)}
            y={0}
            width={Math.max(1, x(band.end) - x(band.start))}
            height={H}
            className="fill-chip"
          />
        ) : null}
        {[0, 0.25, 0.5, 0.75, 1].map((s) => (
          <g key={s}>
            <line
              x1={0}
              x2={W}
              y1={y(s)}
              y2={y(s)}
              className="stroke-line"
              strokeWidth={1}
            />
            <text
              x={-6}
              y={y(s) + 4}
              textAnchor="end"
              className="fill-muted text-[10px]"
            >
              {n.pct(s)}
            </text>
          </g>
        ))}
        {axis.ticks.map((d) => (
          <text
            key={d}
            x={x(d)}
            y={H + 16}
            textAnchor="middle"
            className="fill-muted text-[10px]"
          >
            {n.int(d)}
          </text>
        ))}
        <path
          d={path}
          fill="none"
          className="stroke-accent"
          strokeWidth={2.5}
        />
        {days.map((d, i) => (
          <circle
            key={d}
            cx={x(d)}
            cy={y(share[i] ?? 0)}
            r={3}
            className="fill-bg stroke-accent"
            strokeWidth={2}
          />
        ))}
      </svg>
      <p className="text-xs text-muted" aria-hidden>
        {t("TimeMachine.curve.day")} · {t("TimeMachine.curve.band")}
      </p>
      <p className="text-sm text-muted">{t("TimeMachine.curve.note")}</p>
      <Disclosure summary={t("TimeMachine.table")}>
        <div
          className="overflow-x-auto"
          tabIndex={0}
          role="region"
          aria-label={t("TimeMachine.tableRegion")}
        >
          <table className="tm-table" data-testid="tm-curve-table">
            <caption className="sr-only">
              {t("TimeMachine.curve.title")}
            </caption>
            <thead>
              <tr>
                <th scope="col">{t("TimeMachine.curve.day")}</th>
                <th scope="col">{t("TimeMachine.curve.share")}</th>
              </tr>
            </thead>
            <tbody>
              {days.map((d, i) => (
                <tr key={d}>
                  <th scope="row">{n.int(d)}</th>
                  <td>{n.pct(share[i] ?? 0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Disclosure>
    </figure>
  );
}

// --- validation, sources, references -----------------------------------------------------

function ValidationRows({
  rows,
  compartmental,
}: {
  rows: readonly ValidationRow[];
  compartmental: boolean;
}) {
  const t = useT();
  const n = useNum();
  const pair = (a: number | null, b: number | null) =>
    `${a === null ? "—" : n.sig(a)} / ${b === null ? "—" : n.sig(b)}`;
  return (
    <div
      className="overflow-x-auto"
      tabIndex={0}
      role="region"
      aria-label={t("TimeMachine.tableRegion")}
    >
      <table
        className="tm-table nowrap"
        data-testid={
          compartmental ? "tm-validation-compartmental" : "tm-validation-pbpk"
        }
      >
        <thead>
          <tr>
            <th scope="col">{t("TimeMachine.validation.drug")}</th>
            <th scope="col">{t("TimeMachine.validation.cmax")}</th>
            <th scope="col">{t("TimeMachine.validation.fold")}</th>
            <th scope="col">{t("TimeMachine.validation.auc")}</th>
            <th scope="col">{t("TimeMachine.validation.fold")}</th>
            <th scope="col">{t("TimeMachine.validation.verdict")}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.drug} data-credibility={r.credibility}>
              <th scope="row">{r.drug}</th>
              <td>{pair(r.observed_cmax_ng_ml, r.predicted_cmax_ng_ml)}</td>
              <td>
                {r.cmax_fold_error === null ? "—" : n.sig(r.cmax_fold_error)}
              </td>
              <td>{pair(r.observed_auc_ng_h_ml, r.predicted_auc_ng_h_ml)}</td>
              <td>
                {r.auc_fold_error === null ? "—" : n.sig(r.auc_fold_error)}
              </td>
              <td className="font-bold">
                {t(`TimeMachine.validation.credibility.${r.credibility}`)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/**
 * The validation block (design §10.4), shown wherever a simulated concentration is shown, with
 * every verdict including the failures. English notes are not shown for the compartmental rows
 * (they name PBPK, DP59); their one fact is the translated AUC note.
 */
export function ValidationBlock({
  validation,
  open = false,
  only,
}: {
  validation: Catalogue["validation"];
  open?: boolean;
  /** On a page about one kind of model, only that kind's table (DP59: no PBPK next to a
   * compartmental model). */
  only?: "pbpk" | "compartmental";
}) {
  const t = useT();
  const count = (s: Record<string, number>) =>
    t("TimeMachine.validation.summary", {
      credible: s.credible ?? 0,
      borderline: s.borderline ?? 0,
      failed: s.failed ?? 0,
    });
  return (
    <section
      className="card flex min-w-0 flex-col gap-3 p-4 sm:p-5"
      aria-labelledby="tm-validation"
      data-testid="tm-validation"
    >
      <h2 id="tm-validation" className="font-body text-lg font-bold">
        {t("TimeMachine.sections.validation")}
      </h2>
      <p className="text-sm">{t("TimeMachine.validation.rule")}</p>
      {only === "compartmental" ? null : (
        <Disclosure
          defaultOpen={open}
          summary={`${t("TimeMachine.validation.pbpk")}: ${count(validation.pbpk_summary)}`}
        >
          <ValidationRows rows={validation.pbpk} compartmental={false} />
        </Disclosure>
      )}
      {only === "pbpk" ? null : (
        <Disclosure
          defaultOpen={open}
          summary={`${t("TimeMachine.validation.compartmental")}: ${count(validation.compartmental_summary)}`}
        >
          <ValidationRows rows={validation.compartmental} compartmental />
          <p className="text-sm text-muted">
            {t("TimeMachine.validation.aucNote")}
          </p>
        </Disclosure>
      )}
    </section>
  );
}

export function SourcesBlock({ catalogue }: { catalogue: Catalogue }) {
  const t = useT();
  const locale = useLocale();
  const date = (d: string) => {
    const x = new Date(d.length === 10 ? `${d}T00:00:00Z` : d);
    return Number.isNaN(x.getTime())
      ? d
      : new Intl.DateTimeFormat(locale, {
          dateStyle: "medium",
          timeZone: "UTC",
        }).format(x);
  };
  return (
    <GroupedList
      header={t("TimeMachine.sections.how")}
      headingId="tm-how"
      data-testid="tm-sources"
      footer={
        <p>
          {t("TimeMachine.sources.built", {
            date: date(catalogue.meta.built_at),
            seed: catalogue.meta.seed,
            simulations: catalogue.meta.simulations,
          })}
        </p>
      }
    >
      {Object.entries(catalogue.sources).map(([id, s]) => (
        <Row key={id}>
          <span className="mono font-bold">{id}</span>
          {s.snapshot_date ? (
            <span className="text-sm">
              {t("TimeMachine.sources.snapshot", {
                date: date(s.snapshot_date),
              })}
            </span>
          ) : null}
          {s.license ? (
            <span className="text-sm break-words">
              {t("TimeMachine.sources.licence", { licence: s.license })}
            </span>
          ) : null}
          {s.tool_versions ? (
            <span className="mono text-xs break-words text-muted">
              {t("TimeMachine.sources.tools", {
                tools: Object.entries(s.tool_versions)
                  .map(([k, v]) => `${k} ${v}`)
                  .join(", "),
              })}
            </span>
          ) : null}
          {s.run_id ? (
            <span className="mono text-xs break-all text-muted">
              {t("TimeMachine.sources.run", { run: s.run_id })}
            </span>
          ) : null}
        </Row>
      ))}
    </GroupedList>
  );
}

export function referenceHref(r: Reference): string | null {
  if (/^https:\/\//.test(r.doi_or_url)) return r.doi_or_url;
  if (/^10\.\d{4,9}\/\S+$/.test(r.doi_or_url))
    return `https://doi.org/${r.doi_or_url}`;
  return null;
}

export function References({
  refs,
  keys,
  folded = false,
}: {
  refs: readonly Reference[];
  keys?: readonly string[];
  /** Long lists start folded (a substance cites many sources). */
  folded?: boolean;
}) {
  const t = useT();
  const shown = keys ? refs.filter((r) => keys.includes(r.key)) : refs;
  if (!shown.length) return null;
  const list = (
    <GroupedList
      header={folded ? undefined : t("TimeMachine.references")}
      headingId="tm-refs"
      data-testid="tm-references"
    >
      {shown.map((r) => {
        const href = referenceHref(r);
        return (
          <Row key={r.key}>
            <span lang="en" className="break-words">
              {r.citation}
            </span>
            {href ? (
              <a
                href={href}
                target="_blank"
                rel="noopener noreferrer"
                className="mono inline-flex min-h-11 items-center text-sm break-all"
              >
                {r.doi_or_url}
              </a>
            ) : (
              <span className="mono text-sm break-all">{r.doi_or_url}</span>
            )}
            <span className="text-xs text-muted">
              {t("TimeMachine.verified", { how: r.verified })}
            </span>
          </Row>
        );
      })}
    </GroupedList>
  );
  return folded ? (
    <section className="card p-4" data-testid="tm-references-folded">
      <Disclosure summary={`${t("TimeMachine.references")} (${shown.length})`}>
        {list}
      </Disclosure>
    </section>
  ) : (
    list
  );
}

export function Section({
  id,
  title,
  children,
  testId,
}: {
  id: string;
  title: ReactNode;
  children: ReactNode;
  testId?: string;
}) {
  return (
    <section
      className="card flex min-w-0 flex-col gap-3 p-4 sm:p-5"
      aria-labelledby={id}
      data-testid={testId}
    >
      <h2 id={id} className="font-body text-lg font-bold">
        {title}
      </h2>
      {children}
    </section>
  );
}
