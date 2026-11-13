/**
 * Synthetic open outcome dataset answers for the behaviour tests: the empty release (no released
 * cell yet) and a release with cells. Typed with the production types and decoded by the
 * production decoder; nothing is read from the recorded file.
 */
import * as D from "@/api/decode";
import {
  openOutcomes,
  type OpenFixture,
  type OpenOutcomes,
} from "@/open/model";

export type Cell = OpenOutcomes["cells"][number];

export function cell(over: Partial<Cell> = {}): Cell {
  return {
    layer: "contributions",
    ingredients: ["Q411347"],
    event: "peripheral_oedema",
    direction: "adverse",
    region: "EU",
    value: 23,
    ...over,
  };
}

export const CSV_HEADER =
  "dataset_version,snapshot_date,layer,ingredients,event,direction,region,value";

/** A release with the given cells (none by default: the honest empty state). */
export function openSet(cells: Cell[] = []): OpenFixture & {
  outcomes: OpenOutcomes;
} {
  const outcomes: OpenOutcomes = {
    dataset: "janus-open-outcomes",
    version: "open-outcomes-test+synthetic",
    snapshot_date: "2026-01-01",
    license: "CC BY 4.0",
    license_url: "https://creativecommons.org/licenses/by/4.0/",
    attribution: "Synthetic test data, CC BY 4.0.",
    dictionary_url: "https://example.org/open-data.md",
    release_rule: {
      k: 20,
      epsilon: "1",
      noise: "discrete Laplace, scale 1/epsilon",
      sibling_rule: true,
      hidden_cells_listed: false,
    },
    layers: ["contributions", "outcomes"],
    withheld_layers: [],
    cells,
    notices: [
      "counts_are_reports_not_people",
      "not_verified",
      "not_incidence",
      "noise_added",
    ],
  };
  const r = D.decode(openOutcomes, outcomes);
  if (!r.ok) throw new Error("synthetic fixture open outcomes does not decode");
  return {
    recorded: "synthetic",
    outcomes,
    csv: `${CSV_HEADER}\n${cells
      .map((c) =>
        [
          "open-outcomes-test+synthetic",
          "2026-01-01",
          c.layer,
          c.ingredients.join(";"),
          c.event,
          c.direction,
          c.region,
          c.value,
        ].join(","),
      )
      .join("\n")}${cells.length ? "\n" : ""}`,
  };
}
