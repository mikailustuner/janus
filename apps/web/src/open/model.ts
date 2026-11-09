/**
 * The open outcome dataset (open-data design §4): decoder and clients. Live: GET only, through
 * the experience HTTP client. Demo: the answer recorded from the real local API
 * (`fixture.recorded.json`, scripts/record-open-data.mjs), with no request at all.
 */
import { HttpClient, type Result } from "@/api/client";
import * as D from "@/api/decode";

export const openOutcomes = D.obj({
  dataset: D.lit("janus-open-outcomes"),
  version: D.str,
  snapshot_date: D.str,
  license: D.lit("CC BY 4.0"),
  license_url: D.str,
  attribution: D.str,
  dictionary_url: D.str,
  release_rule: D.obj({
    k: D.int,
    epsilon: D.str,
    noise: D.str,
    sibling_rule: D.lit(true),
    hidden_cells_listed: D.lit(false),
  }),
  layers: D.arr(D.lit("contributions", "outcomes")),
  withheld_layers: D.arr(D.lit("contributions", "outcomes")),
  cells: D.arr(
    D.obj({
      layer: D.lit("contributions", "outcomes"),
      ingredients: D.arr(D.str, 1, 2),
      event: D.str,
      direction: D.lit("adverse", "benefit"),
      region: D.lit("TR", "EU", "US"),
      value: D.int,
    }),
  ),
  notices: D.arr(D.str),
});

export type OpenOutcomes = D.Infer<typeof openOutcomes>;

export interface OpenFixture {
  recorded: string;
  outcomes: unknown;
  csv: string;
}

export interface OpenDataClient {
  outcomes(): Promise<Result<OpenOutcomes>>;
  /** A download address: the API file live, a `data:` URL of the recorded file in demo mode. */
  download(kind: "json" | "csv"): string;
}

const http = new HttpClient();

export const liveOpenData: OpenDataClient = {
  outcomes: () => http.call("open/outcomes", "GET", null, openOutcomes),
  download: (kind) =>
    kind === "json" ? "/api/open/outcomes" : "/api/open/outcomes.csv",
};

export function demoOpenData(fx: OpenFixture): OpenDataClient {
  return {
    outcomes: async () => {
      const r = D.decode(openOutcomes, fx.outcomes);
      return r.ok
        ? { ok: true, data: r.value }
        : {
            ok: false,
            error: {
              kind: "contract",
              route: "open/outcomes",
              messageKey: "Errors.generic",
            },
          };
    },
    download: (kind) =>
      kind === "json"
        ? `data:application/json;charset=utf-8,${encodeURIComponent(JSON.stringify(fx.outcomes, null, 1))}`
        : `data:text/csv;charset=utf-8,${encodeURIComponent(fx.csv)}`,
  };
}

export function loadOpenFixture(): Promise<OpenFixture> {
  return import("./fixture.recorded.json").then(
    (m) => m.default as unknown as OpenFixture,
  );
}

/** Released cells per layer, in the dataset's order (the dashboard tiles and tables). */
export function byLayer(o: OpenOutcomes) {
  return o.layers.map((layer) => ({
    layer,
    cells: o.cells.filter((c) => c.layer === layer),
  }));
}
