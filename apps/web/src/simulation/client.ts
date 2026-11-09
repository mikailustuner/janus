/**
 * The queued server runs (simulation-service Req 2, design §2): decoders and clients. Live: the
 * experience HTTP client (same origin, timeout, no retry; a submit is repeated only when the user
 * asks). Demo: a job recorded from the real local API end to end (`simulate.recorded.json`,
 * scripts/record-simulation.mjs), with no request at all.
 *
 * A request is built here from ids and numbers only (owner decision 2026-11-09: no person-specific
 * field exists); every answer carries the disclaimer, and the decoder requires it.
 */
import { HttpClient, type Result } from "@/api/client";
import * as D from "@/api/decode";

const band = D.arr(D.num, 3, 3);
const validation = D.obj({
  model: D.lit("compartmental", "httk"),
  credibility: D.lit("credible", "borderline", "failed"),
  cmax_fold: D.num,
  auc_fold: D.num,
  auc_independent: D.bool,
  reference_key: D.str,
  cmax_direction: D.lit("model_lower", "model_higher"),
  auc_direction: D.lit("model_lower", "model_higher"),
  validated_scope: D.str,
});

export const compartmentalResult = D.obj({
  model: D.lit("compartmental"),
  population: D.str,
  dose_mg: D.num,
  interval_h: D.nullable(D.int),
  doses: D.int,
  samples: D.int,
  hours: D.arr(D.num, 2, 400),
  p5_ng_ml: D.arr(D.num, 2, 400),
  p50_ng_ml: D.arr(D.num, 2, 400),
  p95_ng_ml: D.arr(D.num, 2, 400),
  peak_band_ng_ml: band,
  auc_single_dose_band_ng_h_ml: band,
});

const httkGroup = D.obj({
  population: D.str,
  age_years: D.arr(D.int, 2, 2),
  css_band_mg_l: band,
});

/** Both HTTK-Pop age ranges; the older-to-younger ratio of medians is the result. */
export const httkResult = D.obj({
  model: D.lit("httk"),
  samples: D.int,
  daily_dose_mg_per_kg: D.num,
  older_to_younger_median_ratio: D.num,
  groups: D.arr(httkGroup, 2, 2),
  tool_versions: D.obj({ r: D.str, httk: D.str }),
});

export const job = D.obj({
  job_id: D.pattern(/^[0-9a-f-]{36}$/),
  state: D.lit("queued", "running", "done", "failed"),
  cached: D.bool,
  queue_position: D.nullable(D.int),
  error: D.nullable(D.lit("timeout", "model_failed", "expired", "worker_lost")),
  result: D.nullable(
    D.tagged("model", { compartmental: compartmentalResult, httk: httkResult }),
  ),
  validation,
  disclaimer: D.str,
  expires_at: D.str,
  poll_after_s: D.int,
});

const bounds = D.obj({ low: D.num, default: D.num, high: D.num });
export const serverCompounds = D.obj({
  version: D.str,
  server_runs: D.bool,
  compartmental: D.arr(
    D.obj({
      id: D.str,
      dose_mg: bounds,
      intervals_h: D.arr(D.int, 1),
      scenarios: D.arr(
        D.obj({
          id: D.str,
          dose_mg: D.num,
          kind: D.str,
          note: D.nullable(D.str),
        }),
      ),
      populations: D.arr(D.obj({ id: D.str, cl_factor: D.num })),
      validation,
    }),
  ),
  httk: D.arr(D.obj({ id: D.str, validation })),
  httk_populations: D.arr(D.obj({ id: D.str, age_years: D.arr(D.int, 2, 2) })),
  limits: D.obj({
    queue_max: D.int,
    slots: D.int,
    job_timeout_s: D.int,
    result_ttl_h: D.int,
    horizon_after_last_dose_h: D.int,
    horizon_max_h: D.int,
    doses_max: D.int,
    population_samples: D.arr(D.int, 2, 2),
    compartmental_samples: D.arr(D.int, 2, 2),
  }),
  disclaimer: D.str,
});

export type Job = D.Infer<typeof job>;
export type CompartmentalResult = D.Infer<typeof compartmentalResult>;
export type HttkResult = D.Infer<typeof httkResult>;
export type ServerCompounds = D.Infer<typeof serverCompounds>;

export type SimulationRequest =
  | {
      kind: "compartmental";
      compound: string;
      population: string;
      dose_mg: number;
      interval_h: number | null;
      doses: number;
      samples: number;
    }
  | { kind: "httk_population"; compound: string; samples: number };

/** The form's starting request for a model: the first compound and population, the default dose. */
export function defaultRequest(
  c: ServerCompounds,
  kind: SimulationRequest["kind"],
): SimulationRequest {
  if (kind === "compartmental") {
    const x = c.compartmental[0]!;
    return {
      kind,
      compound: x.id,
      population: x.populations[0]!.id,
      dose_mg: x.dose_mg.default,
      interval_h: null,
      doses: 1,
      samples: 1000,
    };
  }
  return { kind, compound: c.httk[c.httk.length - 1]!.id, samples: 1000 };
}

export interface SimulationClient {
  compounds(): Promise<Result<ServerCompounds>>;
  submit(body: SimulationRequest): Promise<Result<Job>>;
  job(id: string): Promise<Result<Job>>;
}

const http = new HttpClient();
const UUID =
  /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

export const liveSimulation: SimulationClient = {
  compounds: () =>
    http.call("simulate/compounds", "GET", null, serverCompounds),
  submit: (body) => http.call("simulate", "POST", body, job),
  job: async (id) =>
    UUID.test(id)
      ? http.call(
          "simulate/jobs",
          "GET",
          null,
          job,
          undefined,
          `simulate/jobs/${id}`,
        )
      : {
          ok: false,
          error: {
            kind: "build",
            route: "simulate/jobs",
            messageKey: "Errors.client_defect",
          },
        },
};

export interface SimulationFixture {
  recorded: string;
  compounds: unknown;
  /** Answers to the requests the demo offers (the form's defaults), done. */
  jobs: { request: SimulationRequest; job: unknown }[];
}

const same = (a: SimulationRequest, b: SimulationRequest) =>
  JSON.stringify(Object.entries(a).sort()) ===
  JSON.stringify(Object.entries(b).sort());

export function demoSimulation(fx: SimulationFixture): SimulationClient {
  const decoded = <T>(
    d: D.Decoder<T>,
    v: unknown,
    route: "simulate" | "simulate/compounds" | "simulate/jobs",
  ): Result<T> => {
    const r = D.decode(d, v);
    return r.ok
      ? { ok: true, data: r.value }
      : {
          ok: false,
          error: { kind: "contract", route, messageKey: "Errors.generic" },
        };
  };
  const notRecorded: Result<Job> = {
    ok: false,
    error: {
      kind: "http",
      route: "simulate",
      status: 503,
      code: "simulation_unavailable",
      fields: [],
      messageKey: "Simulation.errors.demoOnly",
    },
  };
  return {
    compounds: async () =>
      decoded(serverCompounds, fx.compounds, "simulate/compounds"),
    submit: async (body) => {
      const hit = fx.jobs.find((j) => same(j.request, body));
      return hit ? decoded(job, hit.job, "simulate") : notRecorded;
    },
    job: async (id) => {
      const hit = fx.jobs.find(
        (j) => (j.job as { job_id?: string }).job_id === id,
      );
      return hit ? decoded(job, hit.job, "simulate/jobs") : notRecorded;
    },
  };
}

export function loadSimulationFixture(): Promise<SimulationFixture> {
  return import("./simulate.recorded.json").then(
    (m) => m.default as unknown as SimulationFixture,
  );
}
