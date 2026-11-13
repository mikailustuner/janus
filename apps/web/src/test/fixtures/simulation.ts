/**
 * Synthetic queued-run answers (compounds list, one done compartmental job, one done httk job) for
 * the behaviour tests. Typed with the production types and decoded by the production decoders;
 * nothing is read from the recorded file. The drugs are the ones the form offers: amlodipine for
 * the compartmental model, three httk compounds with haloperidol last (the form's default).
 */
import * as D from "@/api/decode";
import {
  compartmentalResult,
  httkResult,
  job,
  serverCompounds,
  type CompartmentalResult,
  type HttkResult,
  type Job,
  type ServerCompounds,
  type SimulationRequest,
} from "@/simulation/client";

export const SENTENCE =
  "Virtual population, for research. Not about any person and not a dose recommendation.";
const DISCLAIMER = `${SENTENCE} In silico and exploratory. Janus provides information, not medical advice. Research prototype — not a medical device.`;

function checked<T>(decoder: D.Decoder<T>, value: T, what: string): T {
  const r = D.decode(decoder, value);
  if (!r.ok) throw new Error(`synthetic fixture ${what} does not decode`);
  return value;
}

const validation = (
  model: "compartmental" | "httk",
  credibility: "credible" | "borderline" | "failed",
) => ({
  model,
  credibility,
  cmax_fold: 2.4,
  auc_fold: 1.4,
  auc_independent: true,
  reference_key: "synthetic_reference",
  cmax_direction: "model_lower" as const,
  auc_direction: "model_higher" as const,
  validated_scope: "one oral dose in healthy volunteers (synthetic)",
});

export function compounds(
  over: Partial<ServerCompounds> = {},
): ServerCompounds {
  return checked(
    serverCompounds,
    {
      version: "simulation-allowlist-test",
      server_runs: true,
      compartmental: [
        {
          id: "amlodipine",
          dose_mg: { low: 2.5, default: 10, high: 10 },
          intervals_h: [24],
          scenarios: [
            {
              id: "validation_10mg",
              dose_mg: 10,
              kind: "validation",
              note: null,
            },
          ],
          populations: [
            { id: "adult", cl_factor: 1 },
            { id: "adult_65plus", cl_factor: 0.76 },
          ],
          validation: validation("compartmental", "borderline"),
        },
      ],
      httk: [
        { id: "risperidone", validation: validation("httk", "failed") },
        { id: "metoclopramide", validation: validation("httk", "borderline") },
        { id: "haloperidol", validation: validation("httk", "failed") },
      ],
      httk_populations: [
        { id: "adult", age_years: [20, 50] },
        { id: "adult_65plus", age_years: [65, 79] },
      ],
      limits: {
        queue_max: 10,
        slots: 2,
        job_timeout_s: 30,
        result_ttl_h: 24,
        horizon_after_last_dose_h: 48,
        horizon_max_h: 360,
        doses_max: 14,
        population_samples: [100, 1000],
        compartmental_samples: [100, 2000],
      },
      disclaimer: DISCLAIMER,
      ...over,
    },
    "compounds",
  );
}

/** A one-dose concentration curve: ordered bands p5 <= p50 <= p95 over 40 hours. */
export function compartmentalOf(): CompartmentalResult {
  const hours = Array.from({ length: 41 }, (_, i) => i);
  const curve = (peak: number) =>
    hours.map((h) => (h === 0 ? 0 : peak * (h / 6) * Math.exp(1 - h / 6)));
  return checked(
    compartmentalResult,
    {
      model: "compartmental",
      population: "adult",
      dose_mg: 10,
      interval_h: null,
      doses: 1,
      samples: 1000,
      hours,
      p5_ng_ml: curve(2.5),
      p50_ng_ml: curve(3.8),
      p95_ng_ml: curve(6),
      peak_band_ng_ml: [2.5, 3.8, 6],
      auc_single_dose_band_ng_h_ml: [130, 216, 376],
    },
    "compartmental result",
  );
}

/** An httk result: both age ranges, the ratio of medians, half-life with its calibrated interval. */
export function httkOf(): HttkResult {
  const w = 87.4 ** 0.5; // the interval is x / w .. x * w around the half-life (87.4-fold wide)
  const t = 91.77;
  return checked(
    httkResult,
    {
      model: "httk",
      samples: 1000,
      daily_dose_mg_per_kg: 1,
      older_to_younger_median_ratio: 1.06 / 0.67, // ratio of the two medians
      groups: [
        {
          population: "adult",
          age_years: [20, 50],
          css_band_mg_l: [0.2, 0.67, 3.5],
        },
        {
          population: "adult_65plus",
          age_years: [65, 79],
          css_band_mg_l: [0.35, 1.06, 5],
        },
      ],
      half_life_h: t,
      half_life_interval_h: [t / w, t * w],
      model_error: {
        calibration_version: "simulation-calibration-test",
        half_life: {
          dataset: "Synthetic half-life reference set",
          retrieved: "2026-01-01",
          n_drugs: 205,
          geometric_bias_fold: 2.1,
          bias_direction: "model_higher",
          gmfe: 3.83,
          within_2_fold: 0.307,
          interval_nominal_coverage: 0.8,
          interval_held_out_coverage: 0.84,
        },
        concentrations_validated: false,
      },
      tool_versions: { r: "R synthetic", httk: "0.0.0" },
    },
    "httk result",
  );
}

const jobOf = (
  id: string,
  model: "compartmental" | "httk",
  result: CompartmentalResult | HttkResult,
): Job =>
  checked(
    job,
    {
      job_id: id,
      state: "done",
      cached: false,
      queue_position: null,
      error: null,
      result,
      validation: validation(model, model === "httk" ? "failed" : "borderline"),
      disclaimer: DISCLAIMER,
      expires_at: "2026-01-02T00:00:00+00:00",
      poll_after_s: 2,
    },
    `${model} job`,
  );

export interface SimulationSet {
  recorded: string;
  compounds: ServerCompounds;
  jobs: { request: SimulationRequest; job: Job }[];
}

export function simulationSet(): SimulationSet {
  return {
    recorded: "synthetic",
    compounds: compounds(),
    jobs: [
      {
        request: {
          kind: "compartmental",
          compound: "amlodipine",
          population: "adult",
          dose_mg: 10,
          interval_h: null,
          doses: 1,
          samples: 1000,
        },
        job: jobOf(
          "11111111-1111-4111-8111-111111111111",
          "compartmental",
          compartmentalOf(),
        ),
      },
      {
        request: {
          kind: "httk_population",
          compound: "haloperidol",
          samples: 1000,
        },
        job: jobOf("22222222-2222-4222-8222-222222222222", "httk", httkOf()),
      },
    ],
  };
}
