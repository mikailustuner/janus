"use client";
/**
 * The panel of a pattern or a class (cascade-map Req 4): the rule as published, its source and
 * evidence ids, "cannot be checked" with the scope card's reasons, and the person's matching
 * findings as returned by the API (never computed here, experience DP3). A bottom sheet on phones,
 * beside the map from 1024 px; Escape and the close button return focus to the opener.
 */
import { useEffect, useRef } from "react";

import type { CascadeResult } from "@/api/contracts";
import { AbruptStopLine } from "@/components/AbruptStopLine";
import { CloseIcon } from "@/components/icons";
import { keyName } from "@/components/names";
import { Button, ButtonLink } from "@/components/ui";
import type { CannotCheck, Graph } from "@/cascade-map/model";
import { useT } from "@/theme/words";
import type { Loaded } from "@/vocabulary";

import type { Selection } from "./MapView";

export function RulePanel({
  selection,
  graph,
  vocab,
  names,
  matched,
  cannot,
  result,
  boxNames,
  onClose,
  onOpen,
  onOnlyClass,
}: {
  selection: Selection;
  graph: Graph;
  vocab: Loaded;
  names: Map<string, string>;
  matched: Map<number, number[]>;
  cannot: Map<number, CannotCheck>;
  result: CascadeResult | null;
  boxNames: readonly string[];
  onClose: () => void;
  onOpen: (s: Selection) => void;
  onOnlyClass: (id: string) => void;
}) {
  const t = useT();
  const heading = useRef<HTMLHeadingElement>(null);
  const key =
    selection.kind === "edge" ? `e${selection.row}` : `n${selection.id}`;
  useEffect(() => {
    heading.current?.focus({ preventScroll: true });
    heading.current?.closest(".cm-panel")?.scrollTo({ top: 0 });
  }, [key]);

  const cascade = (row: number) => {
    const c = vocab.vocab.cascades[String(row)];
    return c
      ? t("Findings.cascade", {
          drug_a: c.drug_a,
          event: c.adverse_event,
          drug_b: c.drug_b,
        })
      : `pipc:${row}`;
  };
  const reason = (c: CannotCheck) =>
    t(
      `Findings.${c.kind === "disabled" ? "disabled" : "notMatchable"}.${c.reason}`,
    );

  const header = (eyebrow: string, title: string) => (
    <div className="flex items-start justify-between gap-3">
      <div className="flex min-w-0 flex-col gap-1">
        <p className="text-sm text-muted">{eyebrow}</p>
        <h2
          ref={heading}
          tabIndex={-1}
          id="cm-panel-title"
          className="text-xl leading-snug font-semibold outline-none"
        >
          {title}
        </h2>
      </div>
      <Button
        variant="quiet"
        className="shrink-0 !px-2 no-underline"
        onClick={onClose}
        aria-label={t("Common.close")}
      >
        <CloseIcon size={22} />
      </Button>
    </div>
  );

  let body;
  if (selection.kind === "node") {
    const node = graph.nodes.find((n) => n.id === selection.id);
    if (!node) return null;
    const list = (rows: number[]) => (
      <ul className="flex flex-col gap-2">
        {rows.map((row) => (
          <li key={row}>
            <button
              type="button"
              className="flex min-h-11 w-full flex-col items-start rounded-[var(--radius-button)] border border-line px-3 py-2 text-left hover:bg-chip"
              onClick={() => onOpen({ kind: "edge", row })}
            >
              <span className="text-sm text-muted">
                {t("CascadeMap.panel.row", { row })}
                {matched.has(row) ? ` · ${t("CascadeMap.list.matched")}` : ""}
                {cannot.has(row) ? ` · ${t("Findings.notChecked")}` : ""}
              </span>
              <span>{cascade(row)}</span>
            </button>
          </li>
        ))}
      </ul>
    );
    body = (
      <>
        {header(
          t("CascadeMap.panel.classEyebrow"),
          names.get(node.id) ?? node.id,
        )}
        {node.index.length ? (
          <section
            className="flex flex-col gap-2"
            aria-labelledby="cm-as-first"
          >
            <h3 id="cm-as-first" className="font-bold">
              {t("CascadeMap.panel.asFirst", { count: node.index.length })}
            </h3>
            {list(node.index)}
          </section>
        ) : null}
        {node.marker.length ? (
          <section
            className="flex flex-col gap-2"
            aria-labelledby="cm-as-second"
          >
            <h3 id="cm-as-second" className="font-bold">
              {t("CascadeMap.panel.asSecond", { count: node.marker.length })}
            </h3>
            {list(node.marker)}
          </section>
        ) : null}
        <Button
          variant="secondary"
          className="self-start"
          onClick={() => onOnlyClass(node.id)}
        >
          {t("CascadeMap.panel.onlyThis")}
        </Button>
      </>
    );
  } else {
    const edge = graph.edges.find((e) => e.row === selection.row);
    if (!edge) return null;
    const c = vocab.vocab.cascades[String(edge.row)];
    const cc = cannot.get(edge.row);
    const positions = matched.get(edge.row) ?? [];
    const warned = new Set(result?.item_warnings.map((w) => w.item) ?? []);
    const boxes = (items: number[]) =>
      items.map((i) => boxNames[i] ?? "").join(", ");
    const evidence = [
      `rule:pipc:${edge.row}`,
      "dataset:pipc",
      ...edge.supporting,
    ];
    body = (
      <>
        {header(
          t("CascadeMap.panel.row", { row: edge.row }),
          cascade(edge.row),
        )}
        {cc ? (
          <p className="font-bold" data-testid="cm-cannot">
            {t("CascadeMap.panel.cannot", { reason: reason(cc) })}
          </p>
        ) : null}
        <dl className="grid grid-cols-1 gap-x-4 gap-y-1 sm:grid-cols-[auto_1fr]">
          <dt className="text-sm text-muted">{t("CascadeMap.panel.first")}</dt>
          <dd className="mb-1">{c?.drug_a}</dd>
          <dt className="text-sm text-muted">{t("CascadeMap.panel.event")}</dt>
          <dd className="mb-1">{c?.adverse_event}</dd>
          <dt className="text-sm text-muted">{t("CascadeMap.panel.second")}</dt>
          <dd className="mb-1">{c?.drug_b}</dd>
        </dl>
        {edge.row === 49 ? (
          <p className="text-sm">{t("Findings.row49")}</p>
        ) : null}
        {edge.supporting.length ? (
          <p className="text-sm">{t("Findings.supporting")}</p>
        ) : null}
        <p className="text-sm text-muted">
          {t("Findings.source", { row: edge.row })}
        </p>
        <div className="flex flex-col gap-1">
          <h3 className="text-sm font-bold">
            {t("CascadeMap.panel.evidence")}
          </h3>
          <ul className="mono flex flex-col text-sm">
            {evidence.map((id) => (
              <li key={id}>{id}</li>
            ))}
          </ul>
        </div>
        {result ? (
          <section
            className="flex flex-col gap-2 border-t border-line pt-3"
            aria-labelledby="cm-yours"
            data-testid="cm-yours"
          >
            <h3 id="cm-yours" className="font-bold">
              {t("CascadeMap.panel.yours")}
            </h3>
            {positions.length ? (
              positions.map((p) => {
                const f = result.findings[p]!;
                const items = [
                  ...new Set([...f.index.items, ...f.marker.items]),
                ];
                return (
                  <div key={f.finding_id} className="flex flex-col gap-2">
                    <p>
                      {t("Findings.medicinesRoles", {
                        index: keyName(
                          vocab,
                          f.index.ingredient_key,
                          f.index.label_en,
                        ),
                        indexBox: boxes(f.index.items),
                        marker: keyName(
                          vocab,
                          f.marker.ingredient_key,
                          f.marker.label_en,
                        ),
                        markerBox: boxes(f.marker.items),
                      })}
                    </p>
                    {items.some((i) => warned.has(i)) ? (
                      <AbruptStopLine vocab={vocab} />
                    ) : null}
                    <p>{t("Findings.discuss")}</p>
                    <ButtonLink
                      href={{ pathname: "/results/finding", hash: String(p) }}
                      variant="secondary"
                      className="self-start"
                    >
                      {t("Findings.openDetail")}
                    </ButtonLink>
                  </div>
                );
              })
            ) : (
              <p>{t("CascadeMap.panel.noneYours")}</p>
            )}
          </section>
        ) : null}
      </>
    );
  }

  return (
    <div
      className="cm-panel card flex flex-col gap-3 p-4"
      role="dialog"
      aria-modal="false"
      aria-labelledby="cm-panel-title"
      data-testid="cm-panel"
      onKeyDown={(e) => {
        if (e.key === "Escape") {
          e.stopPropagation();
          onClose();
        }
      }}
    >
      {body}
    </div>
  );
}
