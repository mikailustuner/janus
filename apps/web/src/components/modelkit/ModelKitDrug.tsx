"use client";
/**
 * One drug of the model kit (model-kit Req 6.2): badges and the research-use statements, the
 * parameter table (value, unit, confidence class, sources; activating a value opens its evidence:
 * the quote, the source and BOTH reader verdicts), warnings, the validation chart with its
 * table, the excluded evidence with reasons, and the downloads. The key is read from the URL
 * fragment (`#sunitinib`), validated against the key pattern. Research use only.
 */
import { useLocale } from "next-intl";
import { useEffect, useMemo, useState, type ReactNode } from "react";

import {
  BackLink,
  GroupedList,
  LargeTitle,
  Row,
  SummaryCard,
} from "@/components/cards";
import { ChevronIcon, DownloadIcon } from "@/components/icons";
import { StateView } from "@/components/StateView";
import { Button } from "@/components/ui";
import { useCall, type CallState } from "@/flow/useCall";
import {
  EVIDENCE_PARAMS,
  FORMULATIONS,
  keyFromHash,
  paramKey,
  ROUTES,
  rowsById,
  shortStudy,
  TARGETS,
  type DrugOut,
  type EvidenceOut,
  type EvidenceRow,
  type MetricOut,
  type ModelKitClient,
  type ParamOut,
  type SpecialAtlas,
  type SpecialStatement,
} from "@/modelkit/model";
import { useT, type Translate } from "@/theme/words";

import {
  ExperimentalChip,
  Reason,
  ReasonList,
  ScrollTable,
  Statements,
  StatusChip,
  useModelKitClient,
} from "./common";
import { ValidationChart } from "./ValidationChart";

/** Rows of an evidence table shown before "show all" (long-content state). */
const ROW_LIMIT = 20;
const EXTERNAL = { target: "_blank", rel: "noopener noreferrer" } as const;
const BUTTON =
  "inline-flex min-h-11 min-w-11 items-center justify-center gap-2 rounded-[var(--radius-button)] px-4 py-2.5 text-base font-bold no-underline transition-colors duration-200 bg-accent text-on-accent hover:opacity-90";

/** The drug key after `#`; null when invalid, undefined before the first read. */
function useKey(): string | null | undefined {
  const [k, setK] = useState<string | null | undefined>(undefined);
  useEffect(() => {
    const read = () => setK(keyFromHash(location.hash));
    read();
    window.addEventListener("hashchange", read);
    return () => window.removeEventListener("hashchange", read);
  }, []);
  return k;
}

export function ModelKitDrug() {
  const t = useT();
  const key = useKey();
  const { client, recorded, failed } = useModelKitClient();
  const run = client && key ? key : null;
  const call = useCall(run ? () => client!.drug(run) : null, [client, run]);
  const ev = useCall(run ? () => client!.evidence(run) : null, [client, run]);
  const head = <LargeTitle title={t("ModelKit.title")} />;
  return (
    <>
      <BackLink href="/research/model-kit">{t("ModelKit.title")}</BackLink>
      {key === null ? (
        <>
          {head}
          <StateView state="empty" message={t("ModelKit.errors.invalidKey")} />
        </>
      ) : failed || call.status === "error" ? (
        <>
          {head}
          <StateView
            state="error"
            messageKey={
              call.status === "error" ? call.error.messageKey : "Errors.generic"
            }
            retry={call.status === "error" ? call.retry : undefined}
          />
        </>
      ) : call.status !== "ok" || !client ? (
        <>
          {head}
          <StateView state="loading" label={t("ModelKit.loading")} />
        </>
      ) : (
        <Detail out={call.data} ev={ev} client={client} recorded={recorded} />
      )}
    </>
  );
}

function Detail({
  out,
  ev,
  client,
  recorded,
}: {
  out: DrugOut;
  ev: CallState<EvidenceOut> & { retry: () => void };
  client: ModelKitClient;
  recorded: string | null;
}) {
  const t = useT();
  const s = out.summary;
  const ps = out.parameter_set;
  const rows = ev.status === "ok" ? ev.data.rows : null;
  return (
    <>
      <LargeTitle
        eyebrow={t("ModelKit.title")}
        title={s.name}
        summary={
          <span className="flex flex-wrap gap-2">
            <ExperimentalChip />
            <StatusChip status={s.status} />
          </span>
        }
      />
      <Statements recorded={recorded} audit={out.statements.expert_audit} />
      <SummaryCard
        id="mk-status-card"
        title={t("ModelKit.drug.statusTitle")}
        summary={t("ModelKit.list.studies", { count: s.studies })}
        data-testid="mk-status-card"
      >
        <p className="font-bold" data-testid="mk-status-explain">
          {t(`ModelKit.drug.statusExplain.${s.status}`)}
        </p>
        <ReasonList codes={s.status_reasons} testId="mk-status-reasons" />
        <p className="text-sm text-muted">{t("ModelKit.introValidation")}</p>
      </SummaryCard>
      {ps ? (
        <Warnings ps={ps} />
      ) : (
        <SummaryCard
          id="mk-noset"
          title={t("ModelKit.drug.noSet")}
          summary={t("ModelKit.drug.noSetBody")}
          data-testid="mk-noset"
        >
          <ReasonList codes={out.no_set_reasons} testId="mk-noset-reasons" />
        </SummaryCard>
      )}
      {ps ? <Params out={out} ev={ev} rows={rows} /> : null}
      <Validation out={out} />
      <SpecialPopulations out={out} />
      <EvidenceSections out={out} ev={ev} />
      {ps ? <Downloads out={out} client={client} /> : null}
      {ev.status === "ok" ? (
        <div className="flex flex-col gap-1 text-sm text-muted" lang="en">
          {ev.data.attribution.map((a) => (
            <p key={a} className="break-words">
              {a}
            </p>
          ))}
        </div>
      ) : null}
    </>
  );
}

function Warnings({ ps }: { ps: NonNullable<DrugOut["parameter_set"]> }) {
  const t = useT();
  const nf = new Intl.NumberFormat(useLocale(), { maximumFractionDigits: 1 });
  if (!ps.warnings.length && ps.complete) return null;
  return (
    <section
      className="card flex flex-col gap-2 border-2 border-warn p-4"
      aria-labelledby="mk-warn"
      data-testid="mk-warnings"
    >
      <h2 id="mk-warn" className="font-body text-lg font-bold text-warn">
        {t("ModelKit.drug.warnings")}
      </h2>
      {ps.warnings.map((w) => (
        <p key={w} className="font-bold break-words">
          {w === "half_life_inconsistent" &&
          ps.implied_half_life_h !== null &&
          ps.stated_half_life_h !== null ? (
            <>
              <Reason code={w} />{" "}
              {t("ModelKit.drug.halfLives", {
                implied: nf.format(ps.implied_half_life_h),
                stated: nf.format(ps.stated_half_life_h),
              })}
            </>
          ) : (
            <Reason code={w} />
          )}
        </p>
      ))}
      {!ps.complete ? (
        <>
          <p className="font-bold">{t("ModelKit.drug.incomplete")}</p>
          <ReasonList codes={ps.missing} />
        </>
      ) : null}
    </section>
  );
}

/** A value you can activate: a real button that opens the evidence behind it. */
function ValueButton({
  label,
  expanded,
  controls,
  onClick,
  testId,
}: {
  label: ReactNode;
  expanded: boolean;
  controls: string;
  onClick: () => void;
  testId: string;
}) {
  return (
    <button
      type="button"
      className="mono inline-flex min-h-11 min-w-11 items-center gap-1.5 rounded-[var(--radius-segment)] px-1 text-start font-bold underline underline-offset-4 hover:bg-chip"
      aria-expanded={expanded}
      aria-controls={controls}
      onClick={onClick}
      data-testid={testId}
    >
      <ChevronIcon
        size={14}
        className={`shrink-0 transition-transform duration-150 ${expanded ? "rotate-90" : ""}`}
      />
      {label}
    </button>
  );
}

function Reader({ who, v }: { who: "A" | "B"; v: "agree" | "disagree" }) {
  const t = useT();
  return (
    <li data-testid={`mk-reader-${who.toLowerCase()}`}>
      <span className="font-bold">{t(`ModelKit.ev.reader${who}`)}: </span>
      {t(`ModelKit.ev.verdict.${v}`)}
    </li>
  );
}

/** The evidence behind one value: quote, source, both reader verdicts and the confirm reason. */
function EvidencePanel({ row }: { row: EvidenceRow }) {
  const t = useT();
  const nf = new Intl.NumberFormat(useLocale(), {
    maximumSignificantDigits: 6,
  });
  return (
    <div
      className="flex min-w-0 flex-col gap-2 border-t border-line pt-3 first:border-t-0 first:pt-0"
      data-testid="mk-evidence"
    >
      <p className="text-sm font-bold">
        {paramLabel(t, row.parameter)}:{" "}
        <span className="mono">
          {nf.format(row.value)} <span lang="en">{row.unit}</span>
        </span>
      </p>
      {row.origin === "derived" ? (
        <p className="text-sm font-bold" data-testid="mk-derived">
          {t("ModelKit.ev.derived")}
          {row.derivation ? <>: {row.derivation}</> : null}
        </p>
      ) : null}
      <blockquote
        lang="en"
        className="m-0 border-s-4 border-line ps-3 break-words"
        data-testid="mk-quote"
      >
        {row.quote}
      </blockquote>
      <p className="text-sm break-words">
        <span className="font-bold">{t("ModelKit.ev.locator")}: </span>
        <span lang="en" className="mono break-all" data-testid="mk-locator">
          {row.source_locator}
        </span>
      </p>
      <p className="text-sm break-words">
        <span className="font-bold">{t("ModelKit.ev.studyId")}: </span>
        <span lang="en" className="mono break-all" data-testid="mk-study-id">
          {row.study_id}
        </span>
      </p>
      <p className="text-sm break-words" data-testid="mk-formulation">
        <span className="font-bold">{t("ModelKit.ev.formulation")}: </span>
        {formulationLabel(t, row.formulation)}
        {" · "}
        <span className="font-bold">{t("ModelKit.ev.route")}: </span>
        {routeLabel(t, row.route)}
      </p>
      {row.note ? (
        <p className="text-sm break-words">
          <span className="font-bold">{t("ModelKit.ev.note")}: </span>
          <span lang="en" data-testid="mk-note">
            {row.note}
          </span>
        </p>
      ) : null}
      <p className="text-sm break-words" lang="en">
        {row.source_version}
      </p>
      {row.source_url ? (
        <a
          className="inline-flex min-h-11 items-center self-start font-bold break-all"
          href={row.source_url}
          {...EXTERNAL}
          data-testid="mk-source-link"
        >
          {t("ModelKit.ev.openSource")}
        </a>
      ) : (
        <p className="text-sm text-muted">{t("ModelKit.ev.noLink")}</p>
      )}
      <ul className="m-0 flex list-none flex-col gap-1 p-0 text-sm">
        <Reader who="A" v={row.reader_a} />
        <Reader who="B" v={row.reader_b} />
        <li data-testid="mk-confirm">
          <span className="font-bold">{t("ModelKit.ev.confirm")}: </span>
          <span lang="en" className="break-words">
            {row.confirm_reason}
          </span>
        </li>
      </ul>
    </div>
  );
}

function formulationLabel(t: Translate, f: string): string {
  return (FORMULATIONS as readonly string[]).includes(f)
    ? t(`ModelKit.ev.formulations.${f}`)
    : f;
}

function routeLabel(t: Translate, r: string): string {
  return (ROUTES as readonly string[]).includes(r)
    ? t(`ModelKit.ev.routes.${r}`)
    : r;
}

function paramLabel(t: Translate, name: string): string {
  return (EVIDENCE_PARAMS as readonly string[]).includes(name)
    ? t(`ModelKit.evParam.${name}`)
    : name;
}

function EvidenceState({
  ev,
}: {
  ev: CallState<EvidenceOut> & { retry: () => void };
}) {
  const t = useT();
  return ev.status === "error" ? (
    <StateView
      state="error"
      messageKey={ev.error.messageKey}
      retry={ev.retry}
    />
  ) : (
    <StateView state="loading" label={t("ModelKit.loading")} />
  );
}

function Params({
  out,
  ev,
  rows,
}: {
  out: DrugOut;
  ev: CallState<EvidenceOut> & { retry: () => void };
  rows: readonly EvidenceRow[] | null;
}) {
  const t = useT();
  const nf = new Intl.NumberFormat(useLocale(), {
    maximumSignificantDigits: 4,
  });
  const ps = out.parameter_set!;
  const [open, setOpen] = useState<string | null>(null);
  const byId = useMemo(() => (rows ? rowsById(rows) : null), [rows]);
  const label = (p: ParamOut) => {
    const k = paramKey(p.name, ps.apparent);
    return k ? t(k) : p.label;
  };
  return (
    <section
      className="flex min-w-0 flex-col gap-2"
      aria-labelledby="mk-params"
      data-testid="mk-params"
    >
      <h2 id="mk-params" className="group-header">
        {t("ModelKit.params.title")}
      </h2>
      {ps.apparent ? (
        <p className="font-bold" data-testid="mk-apparent">
          {t("ModelKit.params.apparent")}
        </p>
      ) : null}
      <p className="text-sm text-muted">
        {t("ModelKit.params.model", {
          model: t(`ModelKit.models.${ps.model}`),
        })}{" "}
        <Reason code={ps.model_reason} />
      </p>
      <p className="text-sm text-muted">{t("ModelKit.params.hint")}</p>
      <ScrollTable label={t("ModelKit.params.title")}>
        <table className="tm-table words" data-testid="mk-param-table">
          <caption className="sr-only">{t("ModelKit.params.title")}</caption>
          <thead>
            <tr>
              <th scope="col">{t("ModelKit.params.name")}</th>
              <th scope="col">{t("ModelKit.params.value")}</th>
              <th scope="col">{t("ModelKit.params.class")}</th>
              <th scope="col">{t("ModelKit.params.sources")}</th>
            </tr>
          </thead>
          <tbody>
            {ps.params.map((p) => {
              const id = `mk-ev-${p.name}`;
              const shown = open === p.name;
              return [
                <tr key={p.name} data-testid="mk-param" data-param={p.name}>
                  <th scope="row">{label(p)}</th>
                  <td className="whitespace-nowrap">
                    <ValueButton
                      label={
                        <>
                          {nf.format(p.value)}{" "}
                          <span lang="en" className="font-normal">
                            {p.unit}
                          </span>
                        </>
                      }
                      expanded={shown}
                      controls={id}
                      onClick={() => setOpen(shown ? null : p.name)}
                      testId={`mk-value-${p.name}`}
                    />
                  </td>
                  <td className="mono">{p.confidence_class}</td>
                  <td className="mono">{p.n_studies}</td>
                </tr>,
                shown ? (
                  <tr key={`${p.name}-ev`}>
                    <td
                      colSpan={4}
                      id={id}
                      data-testid="mk-popover"
                      className="whitespace-normal"
                    >
                      <div className="sticky start-0 flex w-[calc(100vw-5.5rem)] max-w-[44rem] flex-col gap-3 py-2">
                        {p.derivation ? (
                          <p className="text-sm">
                            <span className="font-bold">
                              {t("ModelKit.params.derivation")}:{" "}
                            </span>
                            <Reason code={p.derivation} />
                          </p>
                        ) : null}
                        {p.notes.length ? <ReasonList codes={p.notes} /> : null}
                        {p.evidence_ids.length === 0 ? (
                          <p className="text-sm">
                            {t("ModelKit.params.noRows")}
                          </p>
                        ) : byId ? (
                          p.evidence_ids.map((e) => {
                            const row = byId.get(e);
                            return row ? (
                              <EvidencePanel key={e} row={row} />
                            ) : null;
                          })
                        ) : (
                          <EvidenceState ev={ev} />
                        )}
                      </div>
                    </td>
                  </tr>
                ) : null,
              ];
            })}
          </tbody>
        </table>
      </ScrollTable>
      <GroupedList
        header={t("ModelKit.params.legend")}
        headingId="mk-legend"
        level={3}
        data-testid="mk-legend"
      >
        {(["A", "B", "C"] as const).map((c) => (
          <Row key={c}>
            <span>
              <span className="mono font-bold">{c}</span>{" "}
              {t(`ModelKit.params.class${c}`)}
            </span>
          </Row>
        ))}
      </GroupedList>
    </section>
  );
}

function Validation({ out }: { out: DrugOut }) {
  const t = useT();
  const locale = useLocale();
  const nf = new Intl.NumberFormat(locale, { maximumFractionDigits: 3 });
  const v = out.validation;
  return (
    <section
      className="flex min-w-0 flex-col gap-group"
      aria-labelledby="mk-val"
      data-testid="mk-validation"
    >
      <h2 id="mk-val" className="group-header">
        {t("ModelKit.val.title")}
      </h2>
      <p className="text-sm text-muted">{t("ModelKit.val.intro")}</p>
      {v.points.some((p) => p.rebuilt_without_study) ? (
        <p className="text-sm" data-testid="mk-rebuilt">
          {t("ModelKit.val.rebuiltCount", {
            k: v.points.filter((p) => p.rebuilt_without_study).length,
            n: v.points.length,
          })}
        </p>
      ) : null}
      <ScrollTable label={t("ModelKit.val.metrics")}>
        <table className="tm-table words" data-testid="mk-metrics">
          <caption className="sr-only">{t("ModelKit.val.metrics")}</caption>
          <thead>
            <tr>
              <th scope="col">{t("ModelKit.val.metric")}</th>
              <th scope="col">{t("ModelKit.val.n")}</th>
              <th scope="col">{t("ModelKit.val.ratio")}</th>
              <th scope="col">{t("ModelKit.val.gmfe")}</th>
              <th scope="col">{t("ModelKit.val.within")}</th>
            </tr>
          </thead>
          <tbody>
            {v.metrics.map((m: MetricOut) => (
              <tr key={m.name} data-testid={`mk-metric-${m.name}`}>
                <th scope="row">{t(`ModelKit.val.${m.name}`)}</th>
                <td className="mono whitespace-nowrap">
                  {m.tested
                    ? t("ModelKit.val.nCell", {
                        points: m.n_points,
                        studies: m.n_studies,
                      })
                    : t("ModelKit.val.notTested")}
                </td>
                <td className="mono">
                  {m.gm_ratio === null ? "—" : nf.format(m.gm_ratio)}
                </td>
                <td className="mono">
                  {m.gmfe === null ? "—" : nf.format(m.gmfe)}
                </td>
                <td className="whitespace-nowrap">
                  {m.tested ? (
                    <>
                      <span className="mono">
                        {t("ModelKit.system.ofN", {
                          k: m.within_2_fold_points,
                          n: m.n_points,
                        })}
                      </span>
                      <span className="block">
                        {m.all_within_2_fold
                          ? t("ModelKit.val.ratioInside")
                          : t("ModelKit.val.ratioOutside")}
                      </span>
                    </>
                  ) : (
                    "—"
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </ScrollTable>
      {v.failed_point_ids.length ? (
        <div className="flex flex-col gap-1" data-testid="mk-failed-points">
          <p className="font-bold">{t("ModelKit.val.failedPoints")}</p>
          <ul className="m-0 flex list-disc flex-col gap-1 ps-5">
            {v.points
              .filter((p) => v.failed_point_ids.includes(p.evidence_id))
              .map((p) => (
                <li key={p.evidence_id} className="break-words">
                  {t("ModelKit.val.failedPoint", {
                    metric: t(`ModelKit.val.${p.metric}`),
                    study: shortStudy(p.study_id),
                    ratio: nf.format(p.ratio),
                  })}
                </li>
              ))}
          </ul>
        </div>
      ) : null}
      {v.suspect.length ? (
        <div className="flex flex-col gap-1" data-testid="mk-suspect">
          <p className="font-bold">{t("ModelKit.val.suspect")}</p>
          <ReasonList codes={v.suspect} />
        </div>
      ) : null}
      {v.points.length ? (
        <ValidationChart points={v.points} />
      ) : (
        <p className="card p-4" data-testid="mk-no-points">
          {t("ModelKit.val.noPoints")}
        </p>
      )}
      <section
        className="flex min-w-0 flex-col gap-2"
        aria-labelledby="mk-val-int"
        data-testid="mk-intervals"
      >
        <h3 id="mk-val-int" className="font-bold">
          {t("ModelKit.val.intervalHeading")}
        </h3>
        {out.intervals.map((i) => (
          <p key={i.metric} data-testid={`mk-interval-${i.metric}`}>
            {i.shown && i.fold_half !== null
              ? t("ModelKit.val.intervalShown", {
                  metric: t(`ModelKit.val.${i.metric}`),
                  fold: nf.format(i.fold_half),
                  coverage: new Intl.NumberFormat(locale, {
                    style: "percent",
                    maximumFractionDigits: 0,
                  }).format(i.coverage),
                  n: i.n_studies,
                })
              : t("ModelKit.val.intervalNone", {
                  metric: t(`ModelKit.val.${i.metric}`),
                })}
            {i.shown || !i.reason ? null : (
              <>
                {" "}
                <Reason code={i.reason} />{" "}
                {t("ModelKit.val.intervalN", {
                  n: i.n_studies,
                  min: i.min_studies,
                })}
              </>
            )}
          </p>
        ))}
      </section>
    </section>
  );
}

function EvidenceSections({
  out,
  ev,
}: {
  out: DrugOut;
  ev: CallState<EvidenceOut> & { retry: () => void };
}) {
  const t = useT();
  if (ev.status !== "ok")
    return (
      <section className="flex flex-col gap-2" aria-labelledby="mk-evid">
        <h2 id="mk-evid" className="group-header">
          {t("ModelKit.ev.title")}
        </h2>
        <EvidenceState ev={ev} />
      </section>
    );
  const rows = ev.data.rows;
  const used = rows.filter((r) => r.role !== "excluded");
  const excluded = rows.filter((r) => r.role === "excluded");
  return (
    <>
      {used.length ? (
        <EvidenceTable
          id="mk-used"
          title={t("ModelKit.ev.used")}
          rows={used}
          reasons={false}
        />
      ) : null}
      {excluded.length ? (
        <EvidenceTable
          id="mk-excluded"
          title={t(
            out.parameter_set ? "ModelKit.ev.excluded" : "ModelKit.ev.table",
          )}
          rows={excluded}
          reasons
        />
      ) : null}
      {!rows.length ? (
        <StateView state="empty" message={t("ModelKit.ev.empty")} />
      ) : null}
    </>
  );
}

function EvidenceTable({
  id,
  title,
  rows,
  reasons,
}: {
  id: string;
  title: string;
  rows: readonly EvidenceRow[];
  reasons: boolean;
}) {
  const t = useT();
  const nf = new Intl.NumberFormat(useLocale(), {
    maximumSignificantDigits: 5,
  });
  const [open, setOpen] = useState<string | null>(null);
  const [all, setAll] = useState(false);
  const visible = all ? rows : rows.slice(0, ROW_LIMIT);
  return (
    <section
      className="flex min-w-0 flex-col gap-2"
      aria-labelledby={id}
      data-testid={id}
    >
      <h2 id={id} className="group-header">
        {title}
      </h2>
      {reasons ? (
        <p className="text-sm text-muted">{t("ModelKit.ev.excludedHint")}</p>
      ) : null}
      <p className="text-sm text-muted">{t("ModelKit.ev.formulationHint")}</p>
      <ScrollTable label={title}>
        <table className="tm-table words">
          <caption className="sr-only">{title}</caption>
          <thead>
            <tr>
              <th scope="col">{t("ModelKit.ev.parameter")}</th>
              <th scope="col">{t("ModelKit.params.value")}</th>
              <th scope="col">{t("ModelKit.chart.study")}</th>
              <th scope="col">{t("ModelKit.ev.formulation")}</th>
              <th scope="col">
                {reasons ? t("ModelKit.ev.reason") : t("ModelKit.ev.role")}
              </th>
            </tr>
          </thead>
          <tbody>
            {visible.map((r) => {
              const pid = `${id}-${r.id}`;
              const expanded = open === r.id;
              return [
                <tr key={r.id} data-testid="mk-ev-row">
                  <th scope="row">{paramLabel(t, r.parameter)}</th>
                  <td className="whitespace-nowrap">
                    <ValueButton
                      label={
                        <>
                          {nf.format(r.value)}{" "}
                          <span lang="en" className="font-normal">
                            {r.unit}
                          </span>
                        </>
                      }
                      expanded={expanded}
                      controls={pid}
                      onClick={() => setOpen(expanded ? null : r.id)}
                      testId="mk-ev-value"
                    />
                  </td>
                  <td
                    lang="en"
                    className="mono whitespace-nowrap"
                    title={r.study_id}
                  >
                    {shortStudy(r.study_id)}
                  </td>
                  <td data-testid="mk-ev-formulation">
                    {formulationLabel(t, r.formulation)}
                  </td>
                  <td>
                    {reasons ? (
                      <Reason code={r.reason ?? "not_used"} />
                    ) : (
                      t(`ModelKit.ev.roles.${r.role}`)
                    )}
                  </td>
                </tr>,
                expanded ? (
                  <tr key={`${r.id}-p`}>
                    <td colSpan={5} id={pid} className="whitespace-normal">
                      <div className="sticky start-0 w-[calc(100vw-5.5rem)] max-w-[44rem] py-2">
                        <EvidencePanel row={r} />
                      </div>
                    </td>
                  </tr>
                ) : null,
              ];
            })}
          </tbody>
        </table>
      </ScrollTable>
      {rows.length > ROW_LIMIT ? (
        <Button
          type="button"
          onClick={() => setAll(!all)}
          aria-expanded={all}
          data-testid={`${id}-more`}
        >
          {all
            ? t("ModelKit.ev.showFewer")
            : t("ModelKit.ev.showAll", { count: rows.length })}
        </Button>
      ) : null}
    </section>
  );
}

/** Statements shown before "show all" (long-content state). */
const SP_LIMIT = 6;

/** "Renal impairment, moderate" / "Older adults, age 65 and over": the class and grade of a statement. */
function spTitle(t: Translate, cls: string, grade: string): string {
  const c = t(`ModelKit.sp.class.${cls}`);
  return grade ? `${c}, ${t(`ModelKit.sp.grade.${grade}`)}` : c;
}

function SpQuote({
  quote,
  setId,
  version,
  url,
  effective,
}: {
  quote: string;
  setId: string;
  version: string;
  url: string;
  effective?: string;
}) {
  const t = useT();
  return (
    <>
      <blockquote
        lang="en"
        className="m-0 max-w-[72ch] break-words border-s-4 border-line ps-3 text-sm"
      >
        {quote}
      </blockquote>
      <p className="text-xs text-muted break-words">
        {effective
          ? t("ModelKit.sp.sourceDated", { version, date: effective })
          : t("ModelKit.sp.source", { version })}
      </p>
      <a
        href={url}
        {...EXTERNAL}
        className="inline-flex min-h-11 max-w-full items-center gap-2 self-start text-sm underline"
      >
        <span>{t("ModelKit.sp.openLabel")}</span>
        <span lang="en" className="mono break-all text-xs">
          {setId}
        </span>
      </a>
    </>
  );
}

function SpStatement({ s }: { s: SpecialStatement }) {
  const t = useT();
  const nf = new Intl.NumberFormat(useLocale(), { maximumFractionDigits: 2 });
  return (
    <li
      className="card flex min-w-0 flex-col gap-1 p-4"
      data-testid="mk-sp-statement"
      data-class={s.pop_class}
    >
      <p className="font-bold break-words">
        {spTitle(t, s.pop_class, s.grade)}
      </p>
      <p className="break-words">
        {t(`ModelKit.sp.measure.${s.measure}`)}:{" "}
        <span className="font-bold">
          {t("ModelKit.sp.ratio", { ratio: nf.format(s.ratio) })}
        </span>{" "}
        <span lang="en" className="text-muted">
          ({s.ratio_text})
        </span>
      </p>
      {s.definition ? (
        <p className="text-sm break-words">
          {t("ModelKit.sp.definition")}: <span lang="en">{s.definition}</span>
        </p>
      ) : null}
      {s.reference ? (
        <p className="text-sm break-words">
          {t("ModelKit.sp.reference")}: <span lang="en">{s.reference}</span>
        </p>
      ) : null}
      <SpQuote
        quote={s.quote}
        setId={s.set_id}
        version={s.version}
        url={s.source_url}
        effective={s.effective_date}
      />
      {s.n_labels > 1 ? (
        <p className="text-xs text-muted">
          {t("ModelKit.sp.nLabels", { count: s.n_labels })}
        </p>
      ) : null}
    </li>
  );
}

function SpAtlasRow({ a }: { a: SpecialAtlas }) {
  const t = useT();
  const nf = new Intl.NumberFormat(useLocale(), { maximumFractionDigits: 2 });
  const known = ["auc", "cmax", "cl", "conc"].includes(a.measure.toLowerCase());
  return (
    <li
      className="card flex min-w-0 flex-col gap-1 p-4"
      data-testid="mk-sp-atlas-row"
    >
      <p className="font-bold break-words">
        {known
          ? t(`ModelKit.sp.atlasMeasure.${a.measure.toLowerCase()}`)
          : a.measure}
        :{" "}
        {a.qualitative
          ? t("ModelKit.sp.qualitative")
          : t("ModelKit.sp.ratio", { ratio: nf.format(a.ratio) })}
      </p>
      <p className="text-sm font-bold">
        <Reason code="automated_extraction_unconfirmed" />
      </p>
      <SpQuote
        quote={a.quote}
        setId={a.set_id}
        version={a.version}
        url={a.source_url}
      />
      {a.quote_checked ? null : (
        <p className="text-xs text-muted">{t("ModelKit.sp.notChecked")}</p>
      )}
    </li>
  );
}

function SpecialPopulations({ out }: { out: DrugOut }) {
  const t = useT();
  const sp = out.special_populations;
  const [all, setAll] = useState(false);
  const visible = all ? sp.statements : sp.statements.slice(0, SP_LIMIT);
  return (
    <section
      className="flex min-w-0 flex-col gap-group"
      aria-labelledby="mk-sp"
      data-testid="mk-sp"
    >
      <h2 id="mk-sp" className="group-header">
        {t("ModelKit.sp.title")}
      </h2>
      <p className="max-w-[72ch] text-sm text-muted">
        {t("ModelKit.sp.intro")}
      </p>
      <ReasonList codes={sp.notes} testId="mk-sp-notes" />
      {sp.statements.length ? (
        <>
          <ul className="m-0 flex list-none flex-col gap-2 p-0">
            {visible.map((s) => (
              <SpStatement
                key={`${s.pop_class}-${s.grade}-${s.measure}-${s.ratio}-${s.set_id}`}
                s={s}
              />
            ))}
          </ul>
          {sp.statements.length > SP_LIMIT ? (
            <Button
              type="button"
              onClick={() => setAll(!all)}
              aria-expanded={all}
              data-testid="mk-sp-more"
            >
              {all
                ? t("ModelKit.ev.showFewer")
                : t("ModelKit.ev.showAll", { count: sp.statements.length })}
            </Button>
          ) : null}
        </>
      ) : (
        <StateView state="empty" message={t("ModelKit.sp.empty")} />
      )}
      {sp.atlas.length ? (
        <details className="flex flex-col gap-2" data-testid="mk-sp-atlas">
          <summary className="flex min-h-11 cursor-pointer items-center font-bold">
            {t("ModelKit.sp.atlasTitle", { count: sp.atlas.length })}
          </summary>
          <p className="max-w-[72ch] text-sm text-muted">
            {t("ModelKit.sp.atlasIntro")}
          </p>
          <ul className="m-0 flex list-none flex-col gap-2 p-0">
            {sp.atlas.map((a) => (
              <SpAtlasRow key={`${a.measure}-${a.ratio}-${a.set_id}`} a={a} />
            ))}
          </ul>
        </details>
      ) : null}
    </section>
  );
}

function Downloads({ out, client }: { out: DrugOut; client: ModelKitClient }) {
  const t = useT();
  const key = out.summary.key;
  const targets = TARGETS.filter((x) => out.targets.includes(x));
  if (!targets.length) return null;
  return (
    <SummaryCard
      id="mk-downloads"
      title={t("ModelKit.dl.title")}
      summary={t("ModelKit.dl.body")}
      data-testid="mk-downloads"
    >
      <div className="flex flex-wrap gap-2">
        {targets.map((x) =>
          client.downloads ? (
            <a
              key={x}
              className={BUTTON}
              href={client.exportUrl(key, x)}
              download
              data-testid={`mk-download-${x}`}
            >
              <DownloadIcon size={18} className="shrink-0" />
              {t(`ModelKit.dl.${x}`)}
            </a>
          ) : (
            <Button
              key={x}
              disabled
              aria-describedby="mk-dl-demo"
              data-testid={`mk-download-${x}`}
            >
              <DownloadIcon size={18} className="shrink-0" />
              {t(`ModelKit.dl.${x}`)}
            </Button>
          ),
        )}
      </div>
      {!client.downloads ? (
        <p id="mk-dl-demo" className="text-sm" data-testid="mk-dl-demo">
          {t("ModelKit.dl.demo")}
        </p>
      ) : null}
      <p className="text-sm text-muted">{t("ModelKit.dl.contents")}</p>
      {targets.includes("pksim") ? (
        <p className="text-sm text-muted" data-testid="mk-dl-pksim-note">
          {t("ModelKit.dl.pksimNote")}
        </p>
      ) : null}
    </SummaryCard>
  );
}
