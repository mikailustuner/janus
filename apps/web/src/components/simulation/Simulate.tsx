"use client";
/**
 * Queued server runs (simulation-service Req 2, 5): a form with a compound picker, a predefined
 * virtual population and bounded inputs; the queue state while the job waits or runs (polling);
 * the result as a chart and a table, or the httk comparison of the two HTTK-Pop age ranges, always
 * with the validation status the job carries and the virtual-population sentence. 429 (queue
 * full, rate limited), 503 (switched off) and timeouts are shown with their meaning. Demo mode
 * answers from jobs recorded from the real local API. Nothing here reads the medicine list or
 * findings.
 */
import { useEffect, useRef, useState } from "react";

import {
  BackLink,
  Disclosure,
  LargeTitle,
  SegmentedControl,
  SummaryCard,
} from "@/components/cards";
import { useDemoClient } from "@/components/research/useDemoClient";
import { StateView } from "@/components/StateView";
import { Button, ButtonLink } from "@/components/ui";
import type { ApiError } from "@/api/errors";
import { useCall } from "@/flow/useCall";
import {
  defaultRequest,
  demoSimulation,
  liveSimulation,
  loadSimulationFixture,
  type Job,
  type ServerCompounds,
  type SimulationClient,
  type SimulationRequest,
} from "@/simulation/client";
import { useT } from "@/theme/words";

import {
  BandChart,
  Bands,
  ValidationStatus,
  VirtualPopulationNote,
  useNumbers,
} from "./common";

const field =
  "min-h-11 w-full rounded-[var(--radius-button)] border border-line bg-surface px-3 py-2 text-fg";
const MAX_POLLS = 90;
const SAMPLES = ["100", "500", "1000"] as const;

type Kind = SimulationRequest["kind"];
type Compartmental = Extract<SimulationRequest, { kind: "compartmental" }>;

export function Simulate() {
  const t = useT();
  const { client, recorded, failed } = useDemoClient(
    liveSimulation,
    loadSimulationFixture,
    demoSimulation,
  );
  const call = useCall(client ? () => client.compounds() : null, [client]);
  return (
    <>
      <BackLink href="/research">{t("Research.title")}</BackLink>
      <LargeTitle
        title={t("Simulation.server.title")}
        summary={t("Simulation.server.summary")}
      />
      <p className="max-w-[72ch]">{t("Simulation.server.intro")}</p>
      <VirtualPopulationNote />
      {recorded ? (
        <p className="chip self-start" data-testid="sim-demo">
          {t("Simulation.demo", { date: recorded })}
        </p>
      ) : null}
      {failed ? (
        <StateView state="error" messageKey="Errors.generic" />
      ) : call.status === "error" ? (
        <StateView
          state="error"
          messageKey={call.error.messageKey}
          retry={call.retry}
        />
      ) : call.status !== "ok" || !client ? (
        <StateView state="loading" label={t("Simulation.server.loading")} />
      ) : !call.data.server_runs ? (
        <StateView
          state="empty"
          message={t("Simulation.server.off")}
          action={
            <ButtonLink href="/research/model-explorer" variant="secondary">
              {t("Simulation.server.toExplorer")}
            </ButtonLink>
          }
        />
      ) : (
        <Runner c={call.data} client={client} />
      )}
    </>
  );
}

type Run =
  | { s: "idle" }
  | { s: "sending" }
  | { s: "job"; job: Job; request: SimulationRequest; polls: number }
  | { s: "error"; error: ApiError };

function fits(c: ServerCompounds, req: Compartmental): boolean {
  const comp = c.compartmental.find((x) => x.id === req.compound);
  if (!comp) return false;
  const schedule =
    req.doses === 1
      ? req.interval_h === null
      : req.interval_h !== null &&
        comp.intervals_h.includes(req.interval_h) &&
        (req.doses - 1) * req.interval_h + c.limits.horizon_after_last_dose_h <=
          c.limits.horizon_max_h;
  return (
    Number.isFinite(req.dose_mg) &&
    req.dose_mg >= comp.dose_mg.low &&
    req.dose_mg <= comp.dose_mg.high &&
    Number.isInteger(req.doses) &&
    req.doses >= 1 &&
    req.doses <= c.limits.doses_max &&
    schedule
  );
}

function Runner({
  c,
  client,
}: {
  c: ServerCompounds;
  client: SimulationClient;
}) {
  const t = useT();
  const n = useNumbers();
  const [kind, setKind] = useState<Kind>("compartmental");
  const [req, setReq] = useState<SimulationRequest>(() =>
    defaultRequest(c, "compartmental"),
  );
  const [run, setRun] = useState<Run>({ s: "idle" });
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
    },
    [],
  );

  // Poll while the job waits or runs, at least a second apart; stop after MAX_POLLS.
  useEffect(() => {
    if (
      run.s !== "job" ||
      run.job.state === "done" ||
      run.job.state === "failed"
    )
      return;
    if (run.polls >= MAX_POLLS) return;
    timer.current = setTimeout(
      async () => {
        const r = await client.job(run.job.job_id);
        setRun((cur) =>
          cur.s !== "job" || cur.job.job_id !== run.job.job_id
            ? cur
            : r.ok
              ? { ...cur, job: r.data, polls: cur.polls + 1 }
              : { s: "error", error: r.error },
        );
      },
      Math.max(1, run.job.poll_after_s) * 1000,
    );
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, [run, client]);

  const submit = async () => {
    setRun({ s: "sending" });
    const r = await client.submit(req);
    setRun(
      r.ok
        ? { s: "job", job: r.data, request: req, polls: 0 }
        : { s: "error", error: r.error },
    );
  };
  const comp =
    req.kind === "compartmental"
      ? c.compartmental.find((x) => x.id === req.compound)
      : undefined;
  const validation =
    req.kind === "compartmental"
      ? comp?.validation
      : c.httk.find((x) => x.id === req.compound)?.validation;
  const busy =
    run.s === "sending" ||
    (run.s === "job" &&
      (run.job.state === "queued" || run.job.state === "running"));
  const ok = req.kind !== "compartmental" || fits(c, req);
  const note = comp?.scenarios.find((s) => s.kind === "historical");

  return (
    <div className="grid gap-group lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)] lg:items-start">
      <form
        className="card flex min-w-0 flex-col gap-4 p-4 sm:p-5"
        aria-labelledby="sim-run-title"
        onSubmit={(e) => {
          e.preventDefault();
          if (ok && !busy) void submit();
        }}
        data-testid="sim-form"
      >
        <h2 id="sim-run-title" className="font-body text-lg font-bold">
          {t("Simulation.form.title")}
        </h2>
        <SegmentedControl
          legend={t("Simulation.form.model")}
          legendVisible
          name="sim-kind"
          value={kind}
          onChange={(k) => {
            setKind(k);
            setReq(defaultRequest(c, k));
            setRun({ s: "idle" });
          }}
          options={[
            {
              value: "compartmental",
              label: t("Simulation.kind.compartmental"),
            },
            {
              value: "httk_population",
              label: t("Simulation.kind.httk_population"),
            },
          ]}
        />
        <SegmentedControl
          legend={t("Simulation.form.compound")}
          legendVisible
          name="sim-compound"
          variant="pills"
          value={req.compound}
          onChange={(compound) => {
            if (req.kind === "compartmental") {
              const x = c.compartmental.find((y) => y.id === compound)!;
              setReq({
                ...req,
                compound,
                population: x.populations[0]!.id,
                dose_mg: x.dose_mg.default,
                interval_h: null,
                doses: 1,
              });
            } else setReq({ ...req, compound });
          }}
          options={(req.kind === "compartmental"
            ? c.compartmental
            : c.httk
          ).map((x) => ({
            value: x.id,
            label: t(`Simulation.compound.${x.id}`),
          }))}
        />
        {req.kind === "compartmental" && comp ? (
          <>
            <SegmentedControl
              legend={t("Simulation.form.population")}
              legendVisible
              name="sim-population"
              variant="pills"
              value={req.population}
              onChange={(population) => setReq({ ...req, population })}
              options={comp.populations.map((p) => ({
                value: p.id,
                label: t(`Simulation.population.${comp.id}_${p.id}`),
              }))}
            />
            <label className="flex flex-col gap-1">
              <span className="font-bold">
                {t("Simulation.form.dose", {
                  unit: t(`Simulation.doseUnit.${comp.id}`),
                  low: n.sig(comp.dose_mg.low),
                  high: n.sig(comp.dose_mg.high),
                })}
              </span>
              <input
                type="number"
                inputMode="decimal"
                className={field}
                min={comp.dose_mg.low}
                max={comp.dose_mg.high}
                step="any"
                value={Number.isFinite(req.dose_mg) ? req.dose_mg : ""}
                onChange={(e) =>
                  setReq({ ...req, dose_mg: e.target.valueAsNumber })
                }
                data-testid="sim-dose"
              />
            </label>
            {note ? (
              <p className="text-sm text-muted">
                {t(`Simulation.scenarioNote.${note.id}`)}
              </p>
            ) : null}
            <label className="flex flex-col gap-1">
              <span className="font-bold">
                {t("Simulation.form.doses", { max: c.limits.doses_max })}
              </span>
              <input
                type="number"
                inputMode="numeric"
                className={field}
                min={1}
                max={c.limits.doses_max}
                step={1}
                value={Number.isFinite(req.doses) ? req.doses : ""}
                onChange={(e) => {
                  const doses = e.target.valueAsNumber;
                  setReq({
                    ...req,
                    doses,
                    interval_h:
                      doses > 1
                        ? (req.interval_h ?? comp.intervals_h[0]!)
                        : null,
                  });
                }}
                data-testid="sim-doses"
              />
            </label>
            {req.doses > 1 ? (
              <SegmentedControl
                legend={t("Simulation.form.interval")}
                legendVisible
                name="sim-interval"
                variant="pills"
                value={String(req.interval_h)}
                onChange={(v) => setReq({ ...req, interval_h: Number(v) })}
                options={comp.intervals_h.map((h) => ({
                  value: String(h),
                  label: t("Simulation.form.everyHours", { hours: h }),
                }))}
              />
            ) : null}
          </>
        ) : (
          <>
            <p className="text-sm">{t("Simulation.form.httkComparison")}</p>
            <p className="text-sm">{t("Simulation.form.httkDose")}</p>
          </>
        )}
        <SegmentedControl
          legend={t("Simulation.form.samples")}
          legendVisible
          name="sim-samples"
          variant="pills"
          value={String(req.samples) as (typeof SAMPLES)[number]}
          onChange={(v) => setReq({ ...req, samples: Number(v) })}
          options={SAMPLES.map((s) => ({ value: s, label: n.int(Number(s)) }))}
        />
        {!ok ? (
          <p className="text-sm font-bold">
            {t("Simulation.form.outOfBounds")}
          </p>
        ) : null}
        <p className="text-sm text-muted">
          {t("Simulation.server.limits", {
            queue: c.limits.queue_max,
            slots: c.limits.slots,
            timeout: c.limits.job_timeout_s,
            ttl: c.limits.result_ttl_h,
          })}
        </p>
        <Button type="submit" disabled={!ok || busy} data-testid="sim-submit">
          {t("Simulation.form.run")}
        </Button>
        <p className="text-sm text-muted">{t("Simulation.form.noPerson")}</p>
      </form>
      <div className="flex min-w-0 flex-col gap-group">
        {validation ? (
          <ValidationStatus compound={req.compound} v={validation} />
        ) : null}
        <div aria-live="polite" className="flex min-w-0 flex-col gap-group">
          <RunView run={run} />
        </div>
      </div>
    </div>
  );
}

function RunView({ run }: { run: Run }) {
  const t = useT();
  const n = useNumbers();
  if (run.s === "idle")
    return (
      <p className="card p-4 text-muted" data-testid="sim-idle">
        {t("Simulation.server.idle")}
      </p>
    );
  if (run.s === "sending")
    return <StateView state="loading" label={t("Simulation.server.sending")} />;
  if (run.s === "error")
    return <StateView state="error" messageKey={run.error.messageKey} />;
  const { job, request } = run;
  if (job.state === "queued" || job.state === "running")
    return (
      <div
        role="status"
        className="card flex flex-col gap-2 p-4"
        data-testid="sim-status"
        data-state={job.state}
      >
        <p className="font-bold">
          {job.state === "queued"
            ? t("Simulation.server.queued", {
                position: job.queue_position ?? 1,
              })
            : t("Simulation.server.running")}
        </p>
        {run.polls >= MAX_POLLS ? (
          <p>{t("Simulation.server.stoppedPolling")}</p>
        ) : null}
      </div>
    );
  if (job.state === "failed")
    return (
      <div
        role="alert"
        className="card flex flex-col gap-2 p-4"
        data-testid="sim-failed"
      >
        <p>{t(`Simulation.failed.${job.error ?? "model_failed"}`)}</p>
      </div>
    );
  const r = job.result!;
  return (
    <SummaryCard
      id="sim-result"
      title={t("Simulation.result.title")}
      summary={
        job.cached
          ? t("Simulation.result.cached")
          : t("Simulation.result.fresh")
      }
      data-testid="sim-result"
    >
      {r.model === "compartmental" && request.kind === "compartmental" ? (
        <>
          <p className="text-sm">
            {t("Simulation.result.summary", {
              compound: t(`Simulation.compound.${request.compound}`),
              population: t(
                `Simulation.population.${request.compound}_${r.population}`,
              ),
              samples: r.samples,
            })}
          </p>
          {request.doses > 1 ? (
            <p className="font-bold">{t("Simulation.result.extrapolation")}</p>
          ) : null}
          <BandChart s={r} testId="sim-chart" />
          <Bands
            peak={r.peak_band_ng_ml}
            auc={r.auc_single_dose_band_ng_h_ml}
          />
        </>
      ) : r.model === "httk" ? (
        <>
          <p className="text-sm">
            {t("Simulation.result.httkSummary", {
              compound: t(`Simulation.compound.${request.compound}`),
              samples: r.samples,
            })}
          </p>
          <p className="text-lg font-bold" data-testid="sim-ratio">
            {t("Simulation.result.ratio", {
              ratio: n.sig(r.older_to_younger_median_ratio),
            })}
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
        </>
      ) : null}
      <ValidationStatus
        compound={request.compound}
        v={job.validation}
        id="sim-result-validation"
      />
      <VirtualPopulationNote testId="sim-result-disclaimer" />
    </SummaryCard>
  );
}
