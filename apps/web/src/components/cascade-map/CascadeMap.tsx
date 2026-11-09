"use client";
/**
 * The cascade map screen `/cascades` (cascade-map design §6, Req 1–8): the framing line, the
 * matches of the current list (the API's or the demo fixture's findings only, experience DP3),
 * the segmented control Map | List, the filters, and the panel. The map works whatever state the
 * evaluation is in; the matches line carries that state.
 */
import { useLocale } from "next-intl";
import {
  useCallback,
  useDeferredValue,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import type { CascadeResult } from "@/api/contracts";
import {
  byLabel,
  cannotCheck,
  eventLabel,
  filterEdges,
  graph,
  labels,
  matchedRows,
  NO_FILTER,
  touchedNodes,
  type Filter,
} from "@/cascade-map/model";
import { StateView } from "@/components/StateView";
import { Button, ButtonLink, PageTitle } from "@/components/ui";
import { useSession } from "@/flow/janus";
import { useEvaluation } from "@/flow/useEvaluation";
import { useT } from "@/theme/words";
import { useVocabulary } from "@/vocabulary/use";

import { ListView } from "./ListView";
import { MapView, type Selection } from "./MapView";
import { RulePanel } from "./RulePanel";

const field =
  "min-h-11 w-full rounded-[var(--radius-button)] border border-line bg-surface px-3 py-2 text-fg";

function Legend() {
  const t = useT();
  const line = (cls: string) => (
    <svg
      width="34"
      height="10"
      aria-hidden
      focusable="false"
      className="shrink-0"
    >
      <line x1="2" y1="5" x2="32" y2="5" className={cls} />
    </svg>
  );
  return (
    <div className="flex flex-col gap-1 text-sm" data-testid="cm-legend">
      <h2 className="font-bold">{t("CascadeMap.legend.title")}</h2>
      <ul className="flex flex-col gap-1">
        <li className="flex items-center gap-2">
          <svg
            width="34"
            height="14"
            aria-hidden
            focusable="false"
            className="shrink-0"
          >
            <circle cx="17" cy="7" r="5" className="cm-legend-star" />
          </svg>
          {t("CascadeMap.legend.star")}
        </li>
        <li className="flex items-center gap-2">
          {line("cm-legend-line")}
          {t("CascadeMap.legend.line")}
        </li>
        <li className="flex items-center gap-2">
          {line("cm-legend-matched")}
          {t("CascadeMap.legend.matched")}
        </li>
        <li className="flex items-center gap-2">
          {line("cm-legend-cannot")}
          {t("CascadeMap.legend.cannot")}
        </li>
      </ul>
    </div>
  );
}

export function CascadeMap() {
  const t = useT();
  const locale = useLocale();
  const vocab = useVocabulary();
  const session = useSession();
  const evaluation = useEvaluation(session);
  const [view, setView] = useState<"map" | "list">("map");
  const [filter, setFilter] = useState<Filter>(NO_FILTER);
  const [selection, setSelection] = useState<Selection | null>(null);
  const opener = useRef<Element | null>(null);

  const result: CascadeResult | null =
    evaluation.status === "ok" &&
    evaluation.result.statement?.code !== "rule_base_unavailable"
      ? evaluation.result
      : null;
  const names = useMemo(
    () => (vocab ? labels(graph, vocab) : new Map<string, string>()),
    [vocab],
  );
  // The map follows the filters as a transition: React renders it in slices, so typing in the
  // search field never blocks the main thread for long (design §7).
  const deferred = useDeferredValue(filter);
  const shown = useMemo(
    () => (vocab ? filterEdges(graph, deferred, vocab, names) : []),
    [vocab, deferred, names],
  );
  const visible = useMemo(() => touchedNodes(shown), [shown]);
  const matched = useMemo(() => matchedRows(result), [result]);
  const cannot = useMemo(() => cannotCheck(graph, result), [result]);
  const events = useMemo(() => {
    if (!vocab) return [];
    const coll = new Intl.Collator(locale);
    return [...new Set(graph.edges.map((e) => e.event))]
      .map((key) => ({ key, label: eventLabel(key, vocab) }))
      .sort((a, b) => coll.compare(a.label, b.label));
  }, [vocab, locale]);
  const classes = useMemo(
    () =>
      byLabel(
        graph.nodes.map((n) => n.id),
        names,
        locale,
      ),
    [names, locale],
  );

  // The opener gets focus back on close; it is reset on close, so it is set only while closed.
  const open = useCallback((s: Selection, from: Element | null) => {
    if (from) opener.current = from;
    else if (!opener.current) opener.current = document.activeElement;
    setSelection(s);
  }, []);
  const eventText = useCallback(
    (row: number) => vocab?.vocab.cascades[String(row)]?.adverse_event ?? "",
    [vocab],
  );

  if (!vocab) return <StateView state="loading" />;

  const total = graph.edges.length;
  const filtered =
    filter !== NO_FILTER &&
    (filter.classId || filter.event || filter.query.trim());

  const close = () => {
    setSelection(null);
    const el = opener.current;
    opener.current = null;
    requestAnimationFrame(() => {
      if (el instanceof HTMLElement || el instanceof SVGElement)
        if (el.isConnected) el.focus({ preventScroll: true });
    });
  };

  let matches: ReactNode;
  if (
    !session.ready ||
    evaluation.status === "idle" ||
    evaluation.status === "loading"
  )
    matches = <p aria-busy="true">{t("Findings.evaluating")}</p>;
  else if (evaluation.status === "blocked")
    matches =
      evaluation.reason === "empty" ? (
        <div className="flex flex-wrap items-center gap-3">
          <p>{t("CascadeMap.matches.none")}</p>
          <ButtonLink href="/scan" variant="secondary">
            {t("Medicines.add")}
          </ButtonLink>
        </div>
      ) : (
        <p>
          {t(
            evaluation.reason === "too_many"
              ? "Medicines.tooMany"
              : "Medicines.needsConfirmation",
          )}
        </p>
      );
  else if (evaluation.status === "error" || !result)
    matches = (
      <div className="flex flex-wrap items-center gap-3">
        <p>{t("CascadeMap.matches.error")}</p>
        {evaluation.status === "error" &&
        (evaluation.error.kind === "network" ||
          evaluation.error.kind === "timeout") ? (
          <Button variant="secondary" onClick={evaluation.retry}>
            {t("Common.retry")}
          </Button>
        ) : null}
      </div>
    );
  else
    matches = (
      <p>
        {result.findings.length
          ? t("CascadeMap.matches.count", { count: matched.size })
          : t("Findings.noPattern")}
      </p>
    );

  const set = (f: Partial<Filter>) => {
    setFilter((old) => ({ ...old, ...f }));
  };

  return (
    <div
      className="flex flex-col gap-5"
      onKeyDown={(e) => {
        if (e.key === "Escape" && selection) {
          e.preventDefault();
          close();
        }
      }}
    >
      <PageTitle eyebrow={t("CascadeMap.eyebrow")}>
        {t("CascadeMap.title", { total })}
      </PageTitle>
      <p className="max-w-[72ch]">{t("CascadeMap.intro")}</p>
      <p
        className="card max-w-[72ch] p-4 font-bold"
        role="note"
        data-testid="cm-framing"
      >
        {t("CascadeMap.framing")}
      </p>
      <div
        role="status"
        aria-live="polite"
        className="max-w-[72ch]"
        data-testid="cm-matches"
      >
        {matches}
      </div>

      <div className="flex flex-col gap-3">
        <div
          className="cm-seg self-start"
          role="group"
          aria-label={t("CascadeMap.views.label")}
          data-testid="cm-views"
        >
          {(["map", "list"] as const).map((v) => (
            <button
              key={v}
              type="button"
              aria-pressed={view === v}
              onClick={() => setView(v)}
            >
              {t(`CascadeMap.views.${v}`)}
            </button>
          ))}
        </div>
        <fieldset className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          <legend className="sr-only">{t("CascadeMap.filter.label")}</legend>
          <label className="col-span-2 flex min-w-0 flex-col gap-1 text-sm font-bold sm:col-span-1">
            {t("CascadeMap.filter.search")}
            <input
              type="search"
              className={`${field} font-normal`}
              value={filter.query}
              onChange={(e) => set({ query: e.target.value })}
              autoComplete="off"
              enterKeyHint="search"
            />
          </label>
          <label className="flex min-w-0 flex-col gap-1 text-sm font-bold">
            {t("CascadeMap.filter.class")}
            <select
              className={`${field} font-normal`}
              value={filter.classId ?? ""}
              onChange={(e) => set({ classId: e.target.value || null })}
            >
              <option value="">{t("CascadeMap.filter.anyClass")}</option>
              {classes.map((id) => (
                <option key={id} value={id}>
                  {names.get(id)}
                </option>
              ))}
            </select>
          </label>
          <label className="flex min-w-0 flex-col gap-1 text-sm font-bold">
            {t("CascadeMap.filter.event")}
            <select
              className={`${field} font-normal`}
              value={filter.event ?? ""}
              onChange={(e) => set({ event: e.target.value || null })}
            >
              <option value="">{t("CascadeMap.filter.anyEvent")}</option>
              {events.map((ev) => (
                <option key={ev.key} value={ev.key}>
                  {ev.label}
                </option>
              ))}
            </select>
          </label>
        </fieldset>
        <div className="flex min-h-11 flex-wrap items-center gap-3">
          <p
            className="text-sm text-muted"
            aria-live="polite"
            data-testid="cm-count"
          >
            {t("CascadeMap.shown", { shown: shown.length, total })}
          </p>
          {filtered ? (
            <Button variant="quiet" onClick={() => setFilter(NO_FILTER)}>
              {t("CascadeMap.filter.clear")}
            </Button>
          ) : null}
        </div>
      </div>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_360px] lg:items-start">
        <div className="flex min-w-0 flex-col gap-3">
          {shown.length === 0 ? (
            <StateView
              state="empty"
              message={t("CascadeMap.empty")}
              action={
                <Button
                  variant="secondary"
                  onClick={() => setFilter(NO_FILTER)}
                >
                  {t("CascadeMap.filter.clear")}
                </Button>
              }
            />
          ) : view === "map" ? (
            <>
              <MapView
                graph={graph}
                names={names}
                locale={locale}
                edges={shown}
                visible={visible}
                matched={matched}
                cannot={cannot}
                selected={selection}
                onOpen={open}
                eventText={eventText}
              />
              <p id="cm-keys" className="text-sm text-muted">
                {t("CascadeMap.keys")}
              </p>
              <div className="lg:hidden">
                <Legend />
              </div>
            </>
          ) : (
            <ListView
              edges={shown}
              total={total}
              vocab={vocab}
              matched={matched}
              cannot={cannot}
              onOpen={open}
            />
          )}
        </div>
        {selection ? (
          <RulePanel
            key={
              selection.kind === "edge"
                ? `e${selection.row}`
                : `n${selection.id}`
            }
            selection={selection}
            graph={graph}
            vocab={vocab}
            names={names}
            matched={matched}
            cannot={cannot}
            result={result}
            boxNames={session.items.map((i) => i.boxName)}
            onClose={close}
            onOpen={(s) => setSelection(s)}
            onOnlyClass={(id) => {
              setFilter({ ...NO_FILTER, classId: id });
              setSelection(null);
            }}
          />
        ) : (
          <aside className="card hidden flex-col gap-4 p-4 lg:sticky lg:top-4 lg:flex">
            <p>{t("CascadeMap.panel.hint")}</p>
            {view === "map" ? <Legend /> : null}
          </aside>
        )}
      </div>
    </div>
  );
}
