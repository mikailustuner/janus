"use client";
/**
 * The accessible alternative (cascade-map Req 6.1): a table of the shown patterns in row order,
 * with the same filters as the map. Two columns so that it fits 375 px without horizontal scroll;
 * each pattern is a button that opens the same panel as the map.
 */
import type { CannotCheck, GraphEdge } from "@/cascade-map/model";
import { useT } from "@/theme/words";
import type { Loaded } from "@/vocabulary";

import type { Selection } from "./MapView";

export function ListView({
  edges,
  total,
  vocab,
  matched,
  cannot,
  onOpen,
}: {
  edges: GraphEdge[];
  total: number;
  vocab: Loaded;
  matched: Map<number, number[]>;
  cannot: Map<number, CannotCheck>;
  onOpen: (s: Selection, opener: Element | null) => void;
}) {
  const t = useT();
  const rows = [...edges].sort((a, b) => a.row - b.row);
  return (
    <div className="card overflow-hidden p-0" data-testid="cascade-list">
      <table className="w-full border-collapse text-left">
        <caption className="sr-only">
          {t("CascadeMap.list.caption", { shown: rows.length, total })}
        </caption>
        <thead>
          <tr className="border-b border-line text-sm text-muted">
            <th scope="col" className="w-14 px-3 py-2 font-bold">
              {t("CascadeMap.list.row")}
            </th>
            <th scope="col" className="px-3 py-2 font-bold">
              {t("CascadeMap.list.pattern")}
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((e) => {
            const c = vocab.vocab.cascades[String(e.row)];
            const cc = cannot.get(e.row);
            const mine = matched.has(e.row);
            return (
              <tr
                key={e.row}
                className="border-b border-line last:border-0"
                data-testid={`row-${e.row}`}
              >
                <th
                  scope="row"
                  className="mono px-3 py-2 align-top text-sm font-medium"
                >
                  {e.row}
                </th>
                <td className="px-1 py-1">
                  <button
                    type="button"
                    className="flex min-h-11 w-full flex-col items-start gap-0.5 rounded-[var(--radius-button)] px-2 py-1.5 text-left hover:bg-chip"
                    onClick={(ev) =>
                      onOpen({ kind: "edge", row: e.row }, ev.currentTarget)
                    }
                  >
                    <span>
                      {c
                        ? t("Findings.cascade", {
                            drug_a: c.drug_a,
                            event: c.adverse_event,
                            drug_b: c.drug_b,
                          })
                        : `pipc:${e.row}`}
                    </span>
                    {mine ? (
                      <span className="flex items-center gap-1.5 text-sm font-bold">
                        <svg
                          width="22"
                          height="8"
                          aria-hidden
                          focusable="false"
                          className="shrink-0"
                        >
                          <line
                            x1="1"
                            y1="4"
                            x2="21"
                            y2="4"
                            className="cm-legend-matched"
                          />
                        </svg>
                        {t("CascadeMap.list.matched")}
                      </span>
                    ) : null}
                    {cc ? (
                      <span className="text-sm text-muted">
                        {t("CascadeMap.panel.cannot", {
                          reason: t(
                            `Findings.${cc.kind === "disabled" ? "disabled" : "notMatchable"}.${cc.reason}`,
                          ),
                        })}
                      </span>
                    ) : null}
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
