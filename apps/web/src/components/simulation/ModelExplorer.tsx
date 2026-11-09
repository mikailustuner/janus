"use client";
/**
 * The in-browser model explorer (simulation-service Req 1; owner decision 2026-11-09). The
 * time machine's minimal compartmental model runs on the device; nothing is sent. Inputs: a
 * compound, a predefined virtual population, a dose within the model's fixed bounds (the cited
 * scenarios as quick picks) and a schedule from the compound's listed intervals. No
 * person-specific entry exists. The result is the distribution over the virtual population (chart
 * and table, peak and AUC bands), always with the model's validation status, an extrapolation
 * note outside the validated scenario, and "Virtual population, for research. Not about any
 * person and not a dose recommendation." This screen never reads the medicine list or findings
 * and links to no patient screen.
 */
import { useDeferredValue, useMemo, useState } from "react";

import {
  BackLink,
  LargeTitle,
  SegmentedControl,
  SummaryCard,
} from "@/components/cards";
import {
  compound as findCompound,
  defaults,
  EXPLORER,
  extrapolated,
  hoursFor,
  problems,
  run,
  type ExplorerInput,
} from "@/simulation/explorer";
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

export function ModelExplorer() {
  const t = useT();
  const n = useNumbers();
  const [input, setInput] = useState<ExplorerInput>(() => defaults());
  const c = findCompound(input.compound)!;
  const bad = problems(input);
  const deferred = useDeferredValue(input);
  const result = useMemo(() => run(deferred), [deferred]);
  const set = (p: Partial<ExplorerInput>) => setInput((x) => ({ ...x, ...p }));
  const repeated = input.doses > 1;
  const note = c.scenarios.find((s) => s.kind === "historical");
  return (
    <>
      <BackLink href="/research">{t("Research.title")}</BackLink>
      <LargeTitle
        title={t("Simulation.explorer.title")}
        summary={t("Simulation.explorer.summary")}
      />
      <p className="max-w-[72ch]">{t("Simulation.explorer.intro")}</p>
      <VirtualPopulationNote />
      <div className="grid gap-group lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)] lg:items-start">
        <form
          className="card flex min-w-0 flex-col gap-4 p-4 sm:p-5"
          aria-labelledby="sim-form-title"
          onSubmit={(e) => e.preventDefault()}
          data-testid="explorer-form"
        >
          <h2 id="sim-form-title" className="font-body text-lg font-bold">
            {t("Simulation.form.title")}
          </h2>
          <SegmentedControl
            legend={t("Simulation.form.compound")}
            legendVisible
            name="explorer-compound"
            variant="pills"
            value={input.compound}
            onChange={(id) => setInput(defaults(findCompound(id)))}
            options={EXPLORER.compounds.map((x) => ({
              value: x.id,
              label: t(`Simulation.compound.${x.id}`),
            }))}
          />
          <SegmentedControl
            legend={t("Simulation.form.population")}
            legendVisible
            name="explorer-population"
            variant="pills"
            value={input.population}
            onChange={(population) => set({ population })}
            options={c.populations.map((p) => ({
              value: p.id,
              label: t(`Simulation.population.${c.id}_${p.id}`),
            }))}
          />
          <p
            className="text-sm text-muted"
            data-testid="explorer-population-basis"
          >
            {t(`Simulation.populationBasis.${c.id}_${input.population}`)}
          </p>
          <label className="flex flex-col gap-1">
            <span className="font-bold">
              {t("Simulation.form.dose", {
                unit: t(`Simulation.doseUnit.${c.id}`),
                low: n.sig(c.dose_mg.low),
                high: n.sig(c.dose_mg.high),
              })}
            </span>
            <input
              type="number"
              inputMode="decimal"
              className={field}
              min={c.dose_mg.low}
              max={c.dose_mg.high}
              step="any"
              value={Number.isFinite(input.dose_mg) ? input.dose_mg : ""}
              onChange={(e) => set({ dose_mg: e.target.valueAsNumber })}
              aria-invalid={bad.includes("dose_mg") || undefined}
              aria-describedby="explorer-dose-help"
              data-testid="explorer-dose"
            />
            <span id="explorer-dose-help" className="text-sm text-muted">
              {bad.includes("dose_mg")
                ? t("Simulation.form.outOfBounds")
                : t("Simulation.form.doseHelp")}
            </span>
          </label>
          <div
            className="flex flex-wrap gap-2"
            aria-label={t("Simulation.form.scenarios")}
            role="group"
          >
            {c.scenarios.map((s) => (
              <button
                key={s.id}
                type="button"
                className="chip inline-flex min-h-11 items-center"
                onClick={() => set({ dose_mg: s.dose_mg })}
              >
                {t(`Simulation.scenario.${s.kind}`, {
                  dose: n.sig(s.dose_mg),
                  unit: t(`Simulation.doseUnit.${c.id}`),
                })}
              </button>
            ))}
          </div>
          {note ? (
            <p className="text-sm text-muted" data-testid="explorer-canon-note">
              {t(`Simulation.scenarioNote.${note.id}`)}
            </p>
          ) : null}
          <label className="flex flex-col gap-1">
            <span className="font-bold">
              {t("Simulation.form.doses", { max: EXPLORER.limits.doses_max })}
            </span>
            <input
              type="number"
              inputMode="numeric"
              className={field}
              min={1}
              max={EXPLORER.limits.doses_max}
              step={1}
              value={Number.isFinite(input.doses) ? input.doses : ""}
              onChange={(e) => {
                const doses = e.target.valueAsNumber;
                set({
                  doses,
                  interval_h:
                    doses > 1 ? (input.interval_h ?? c.intervals_h[0]!) : null,
                });
              }}
              aria-invalid={bad.includes("doses") || undefined}
              data-testid="explorer-doses"
            />
          </label>
          {repeated ? (
            <SegmentedControl
              legend={t("Simulation.form.interval")}
              legendVisible
              name="explorer-interval"
              variant="pills"
              value={String(input.interval_h)}
              onChange={(v) => set({ interval_h: Number(v) })}
              options={c.intervals_h.map((h) => ({
                value: String(h),
                label: t("Simulation.form.everyHours", { hours: h }),
              }))}
            />
          ) : null}
          <p className="text-sm text-muted">
            {t("Simulation.form.horizon", { hours: hoursFor(input) })}
          </p>
          <p className="text-sm text-muted">{t("Simulation.form.noPerson")}</p>
        </form>
        <div className="flex min-w-0 flex-col gap-group" aria-live="polite">
          <ValidationStatus compound={c.id} v={c.validation} />
          {bad.length || !result ? (
            <p
              className="card p-4"
              role="status"
              data-testid="explorer-invalid"
            >
              {t("Simulation.form.fix")}
            </p>
          ) : (
            <SummaryCard
              id="explorer-result"
              title={t("Simulation.result.title")}
              summary={t("Simulation.result.summary", {
                compound: t(`Simulation.compound.${deferred.compound}`),
                population: t(
                  `Simulation.population.${deferred.compound}_${deferred.population}`,
                ),
                samples: 500,
              })}
              data-testid="explorer-result"
            >
              {extrapolated(deferred) ? (
                <p className="font-bold" data-testid="explorer-extrapolation">
                  {t("Simulation.result.extrapolation")}
                </p>
              ) : null}
              <BandChart s={result} />
              <Bands
                peak={result.peak_band_ng_ml}
                auc={result.auc_single_dose_band_ng_h_ml}
              />
              <VirtualPopulationNote testId="explorer-result-disclaimer" />
            </SummaryCard>
          )}
        </div>
      </div>
    </>
  );
}
