"use client";
/**
 * List-level Collective Memory (design §9, §21, Req 16.2, 16.8–16.12, 29): four separate panels —
 * FAERS for the medicines together, FAERS by region, donated reports, doctor-confirmed outcomes —
 * with a filter that shows all of them by default. Numbers are never summed or compared across
 * layers. Assessments stay out of the lists.
 */
import { useLocale } from "next-intl";
import { useMemo, useState } from "react";

import { combinationBody, regionsBody, sharedBody } from "@/api/builders";
import type {
  CombinationOut,
  RegionsOut,
  SharedOut,
  SnapshotOut,
} from "@/api/contracts";
import {
  Disclosure,
  LargeTitle,
  SegmentedControl,
  StatGrid,
  StatTile,
  SummaryCard,
} from "@/components/cards";
import { formatCount, formatDate, formatShare } from "@/components/format";
import { keyName } from "@/components/names";
import { EmergencyNotice } from "@/components/EmergencyNotice";
import { SafetyLine } from "@/components/SafetyLine";
import { StateView } from "@/components/StateView";
import { Card } from "@/components/ui";
import { inputKey, toEvaluateIn } from "@/flow/evaluate";
import { resultCache, useSession } from "@/flow/janus";
import { eventKeyOf } from "@/flow/locator";
import { noticeKey, ratioOf, sharedPanel, splitCaveats } from "@/flow/memory";
import { memoryPanels, type MemoryFilter } from "@/flow/memory-filter";
import { useCall, type CallState } from "@/flow/useCall";
import { listIngredientKeys } from "@/store/list";
import { useT } from "@/theme/words";
import type { CascadeResult } from "@/api/contracts";
import type { Loaded, SafetyLineCode } from "@/vocabulary";
import { useVocabulary } from "@/vocabulary/use";

import { ratioText } from "./CiBar";
import { useMemorySentence } from "./PairPanel";

function Panel<T>({
  call,
  children,
}: {
  call: CallState<T> & { retry: () => void };
  children: (d: T) => React.ReactNode;
}) {
  const t = useT();
  if (call.status === "loading")
    return <StateView state="loading" label={t("MemoryView.loading")} />;
  if (call.status === "error")
    return (
      <StateView
        state="error"
        messageKey={call.error.messageKey}
        retry={call.retry}
      />
    );
  if (call.status === "skip") return null;
  return <>{children(call.data)}</>;
}

function Notices({
  codes,
  window,
  snapshot,
}: {
  codes: string[];
  window: string[];
  snapshot: SnapshotOut | null;
}) {
  const t = useT();
  const say = useMemorySentence(snapshot);
  const caveats = splitCaveats(codes.map(noticeKey));
  return (
    <>
      {/* Req 28.5: these caveats stay outside the fold wherever counts are shown. */}
      {caveats.visible.length ? (
        <ul className="flex flex-col gap-2 border-s-2 border-line ps-3 text-sm">
          {caveats.visible.map((k) => (
            <li key={k}>{say(k, window)}</li>
          ))}
        </ul>
      ) : null}
      {caveats.folded.length ? (
        <Disclosure
          summary={t("MemoryView.detailsHeading")}
          className="border-t border-line"
        >
          <ul className="flex flex-col gap-2 text-sm">
            {caveats.folded.map((k) => (
              <li key={k}>{say(k, window)}</li>
            ))}
          </ul>
        </Disclosure>
      ) : null}
    </>
  );
}

/** A region and its value as one row: the label leading, the value trailing (Settings style). */
function ValueRow({ label, value }: { label: string; value: string }) {
  return (
    <li className="flex flex-row flex-wrap items-baseline justify-between gap-x-4 gap-y-0.5">
      <span>{label}</span>
      <span className="font-bold">{value}</span>
    </li>
  );
}

function Combination({
  c,
  vocab,
  snapshot,
}: {
  c: CombinationOut;
  vocab: Loaded;
  snapshot: SnapshotOut | null;
}) {
  const t = useT();
  const locale = useLocale();
  const over = t("MemoryView.over1000");
  const name = (k: string) => keyName(vocab, k, null);
  const groups =
    c.level === "combination"
      ? [
          {
            keys: c.ingredients.map((i) => i.key),
            reports: c.combination.reports,
            events: c.events,
          },
        ]
      : c.level === "pairwise"
        ? c.pairs.slice(0, 10)
        : c.singles.slice(0, 10).map((s) => ({
            keys: [s.key],
            reports: s.reports,
            events: s.events,
          }));
  const total = c.combination.reports;
  return (
    <SummaryCard
      title={t("MemoryView.combinationTitle")}
      id="combination"
      eyebrow={t("MemoryView.pairTitle")}
      data-testid="memory-combination"
    >
      {/* A big number only when reports name all the medicines; a large zero next to the pairs'
          counts would read as "no reports at all" (Req 29.4). */}
      {total > 0 ? (
        <StatGrid>
          <StatTile
            value={formatCount(total, locale)}
            label={t("Cards.label.reportsAll", { count: total })}
            sentence={t("MemoryView.combinationReports", { count: total })}
          />
        </StatGrid>
      ) : (
        <p className="font-bold">
          {t("MemoryView.combinationReports", { count: total })}
        </p>
      )}
      <p className="text-sm text-muted">
        {t(
          `Memory.codes.${c.level === "combination" ? "reported_together_only" : c.level === "pairwise" ? "pairwise_shown" : "single_shown"}`,
        )}
      </p>
      <ul className="grouped-plain border-y border-line">
        {groups.map((g) => (
          <li key={g.keys.join()} className="flex flex-col gap-1">
            <span className="flex flex-wrap items-baseline justify-between gap-x-4">
              <span className="font-bold">{g.keys.map(name).join(" + ")}</span>
              <span>{t("MemoryView.reports", { count: g.reports })}</span>
            </span>
            {g.events.length ? (
              <Disclosure
                summary={t("MemoryView.eventsHeading")}
                summaryClassName="text-sm"
              >
                <ul className="flex flex-col gap-1 text-sm">
                  {g.events.slice(0, 10).map((e) => {
                    const r = ratioOf(e.stats);
                    return (
                      <li key={e.pt}>
                        {e.pt}: {formatCount(e.reports, locale)}
                        {r ? (
                          <span className="mono">
                            {" "}
                            ·{" "}
                            {t("MemoryView.ratio", {
                              ror: ratioText(r.ror, locale, over),
                              low: ratioText(r.low, locale, over),
                              high: ratioText(r.high, locale, over),
                            })}
                          </span>
                        ) : null}
                        {e.safety_line ? (
                          <SafetyLine code={e.safety_line as SafetyLineCode} />
                        ) : null}
                      </li>
                    );
                  })}
                </ul>
                <p className="text-sm text-muted">{t("Memory.meddra")}</p>
              </Disclosure>
            ) : null}
          </li>
        ))}
      </ul>
      <Notices
        codes={c.notices}
        window={c.snapshot.window}
        snapshot={snapshot}
      />
      <p className="text-sm text-muted">
        {t("Memory.attribution", {
          date: formatDate(c.snapshot.snapshot_date, locale),
        })}
      </p>
    </SummaryCard>
  );
}

function Regions({
  r,
  snapshot,
}: {
  r: RegionsOut;
  snapshot: SnapshotOut | null;
}) {
  const t = useT();
  const locale = useLocale();
  return (
    <SummaryCard
      title={t("MemoryView.regionsTitle")}
      id="regions"
      eyebrow={t("MemoryView.pairTitle")}
      data-testid="memory-regions"
    >
      <ul className="grouped-plain border-y border-line">
        {r.rows.map((row) => (
          <ValueRow
            key={row.region}
            label={t(`Common.region.${row.region}`)}
            value={t("MemoryView.reports", { count: row.reports })}
          />
        ))}
      </ul>
      <p>
        {t("MemoryView.unknownRegion", {
          count: formatCount(r.unknown.reports, locale),
          share: formatShare(r.unknown.share, locale),
        })}
      </p>
      <ul className="flex flex-col gap-1 text-sm text-muted">
        {r.basis.map((b) => (
          <li key={b.region}>
            {t("MemoryView.basis", {
              region: t(`Common.region.${b.region}`),
              occurrence: formatCount(b.occurrence, locale),
              fallback: formatCount(b.reporter_fallback, locale),
            })}
          </li>
        ))}
      </ul>
      <p className="text-sm">
        <a
          href={r.adrreports_url}
          data-inline="true"
          rel="noreferrer noopener"
          target="_blank"
          className="underline underline-offset-4"
        >
          {t("MemoryView.adrreports")}
        </a>
      </p>
      <Notices
        codes={r.notices}
        window={r.snapshot.window}
        snapshot={snapshot}
      />
    </SummaryCard>
  );
}

function Shared({ s, title }: { s: SharedOut; title: string }) {
  const t = useT();
  const locale = useLocale();
  const p = sharedPanel(s);
  return (
    <Card
      aria-label={title}
      data-testid={`memory-${s.layer}`}
      className="sm:p-5"
    >
      <h2 className="font-body text-lg leading-snug font-bold">{title}</h2>
      {p.status !== "ok" ? (
        <p>{t(`Memory.codes.${p.status}`)}</p>
      ) : (
        <ul className="grouped-plain border-t border-line">
          {p.cells.map((c) => (
            <ValueRow
              key={c.region}
              label={t(`Common.region.${c.region}`)}
              value={
                c.hidden || c.value === null
                  ? t("Memory.codes.hidden_under_20_noise_added")
                  : formatCount(c.value, locale)
              }
            />
          ))}
        </ul>
      )}
    </Card>
  );
}

export function MemoryPage() {
  const t = useT();
  const session = useSession();
  const vocab = useVocabulary();
  const client = session.client;
  const allKeys = useMemo(
    () => listIngredientKeys(session.items),
    [session.items],
  );
  const [chosen, setChosen] = useState<string[]>([]);
  const [filter, setFilter] = useState<MemoryFilter>("all");
  const keys = allKeys.length <= 20 ? allKeys : chosen;
  const built = session.ready ? toEvaluateIn(session.items) : null;
  const result = built?.ok
    ? resultCache.get<CascadeResult>(inputKey(built.body))
    : undefined;
  const events = useMemo(
    () =>
      vocab && result
        ? [
            ...new Set(
              result.findings
                .map((f) => eventKeyOf(f, vocab))
                .filter((e): e is string => !!e),
            ),
          ]
        : [],
    [vocab, result],
  );
  const [eventPick, setEventPick] = useState<string | null>(null);
  const event = eventPick ?? events[0] ?? null;
  const ok = !!client && keys.length >= 1;

  const snapshot = useCall(client ? () => client.memorySnapshot() : null, [
    client,
  ]);
  const combination = useCall(
    ok && keys.length >= 2
      ? () => client!.memoryCombination(combinationBody(keys))
      : null,
    [client, keys.join()],
  );
  const regions = useCall(
    ok ? () => client!.memoryRegions(regionsBody(keys)) : null,
    [client, keys.join()],
  );
  const contributions = useCall(
    ok && event
      ? () =>
          client!.memoryShared(
            sharedBody("contributions", keys, event, "adverse"),
          )
      : null,
    [client, keys.join(), event],
  );
  const outcomes = useCall(
    ok && event
      ? () =>
          client!.memoryShared(sharedBody("outcomes", keys, event, "adverse"))
      : null,
    [client, keys.join(), event],
  );

  if (!session.ready || !vocab) return <StateView state="loading" />;
  const snap = snapshot.status === "ok" ? snapshot.data : null;
  // Rule 10, Req 7.8: when an event with a safety line can be shown here (the findings' events, or
  // the events of the combination panel), the emergency notice comes first on the screen,
  // whatever the filter.
  const combinationLines =
    combination.status === "ok"
      ? [
          combination.data.events,
          ...combination.data.pairs.map((p) => p.events),
          ...combination.data.singles.map((x) => x.events),
        ]
          .flat()
          .some((e) => e.safety_line)
      : false;
  const chosenLine = event
    ? (vocab.vocab.events[event]?.safety_line ?? null)
    : null;
  const emergencyFirst =
    combinationLines || events.some((e) => vocab.vocab.events[e]?.safety_line);
  const show = memoryPanels(filter);
  return (
    <>
      {emergencyFirst ? <EmergencyNotice /> : null}
      <LargeTitle
        title={t("MemoryView.title")}
        summary={
          keys.length
            ? t("Cards.memory.summary", { count: keys.length })
            : undefined
        }
      />
      <p className="max-w-[72ch]">{t("MemoryView.intro")}</p>
      {snap ? (
        <p className="text-sm text-muted">
          {t("MemoryView.snapshot", {
            date: snap.snapshot_date,
            first: snap.window[0] ?? "",
            last: snap.window[snap.window.length - 1] ?? "",
          })}
        </p>
      ) : null}
      {/* Req 16.12: the staleness notices of the snapshot; the limits are in each panel. */}
      {snap?.notices
        .filter(
          (n) =>
            n === "source_may_be_outdated" ||
            n === "counts_built_against_other_dataset",
        )
        .map((n) => (
          <p key={n} role="status" className="card p-4 text-sm">
            {t(`Memory.codes.${n}`)}
          </p>
        ))}
      {allKeys.length > 20 ? (
        <Card>
          <p>{t("MemoryView.tooMany")}</p>
          <ul className="flex flex-col">
            {allKeys.map((k) => (
              <li key={k}>
                <label className="flex min-h-11 items-center gap-3">
                  <input
                    type="checkbox"
                    className="size-5 accent-[var(--accent)]"
                    checked={chosen.includes(k)}
                    disabled={!chosen.includes(k) && chosen.length >= 20}
                    onChange={(e) =>
                      setChosen((c) =>
                        e.target.checked ? [...c, k] : c.filter((x) => x !== k),
                      )
                    }
                  />
                  {keyName(vocab, k, null)}
                </label>
              </li>
            ))}
          </ul>
        </Card>
      ) : null}
      {keys.length ? (
        <SegmentedControl
          legend={t("Cards.show")}
          name="memory-filter"
          value={filter}
          onChange={setFilter}
          className="max-w-[720px]"
          options={[
            { value: "all", label: t("Cards.memory.all") },
            { value: "together", label: t("Cards.memory.together") },
            { value: "regions", label: t("MemoryView.regionsTitle") },
            { value: "janus", label: t("Cards.memory.janus") },
          ]}
        />
      ) : null}
      {/* Desktop (Req 27): the combination panel beside the regional and shared panels. */}
      <div
        className={`grid gap-group lg:items-start ${filter === "all" ? "lg:grid-cols-2" : ""}`}
      >
        {show.combination ? (
          <div className="flex min-w-0 flex-col gap-group">
            {keys.length < 2 ? (
              <StateView state="empty" message={t("MemoryView.fewKeys")} />
            ) : (
              <Panel call={combination}>
                {(c) => <Combination c={c} vocab={vocab} snapshot={snap} />}
              </Panel>
            )}
          </div>
        ) : null}
        {show.regions || show.janus ? (
          <div className="flex min-w-0 flex-col gap-group">
            {show.regions ? (
              <Panel call={regions}>
                {(r) => <Regions r={r} snapshot={snap} />}
              </Panel>
            ) : null}
            {show.janus ? (
              <>
                {events.length ? (
                  <label className="flex flex-col gap-1">
                    <span className="group-header">
                      {t("MemoryView.eventPicker")}
                    </span>
                    <select
                      value={event ?? ""}
                      onChange={(e) => setEventPick(e.target.value)}
                      className="min-h-11 rounded-[var(--radius-button)] border-2 border-muted bg-surface px-3 text-fg"
                    >
                      {events.map((e) => (
                        <option key={e} value={e} className="bg-bg text-fg">
                          {vocab.vocab.events[e]?.label ?? e}
                        </option>
                      ))}
                    </select>
                  </label>
                ) : null}
                {chosenLine ? <SafetyLine code={chosenLine} /> : null}
                <Panel call={contributions}>
                  {(s) => <Shared s={s} title={t("MemoryView.donatedTitle")} />}
                </Panel>
                <Panel call={outcomes}>
                  {(s) => (
                    <Shared s={s} title={t("MemoryView.outcomesTitle")} />
                  )}
                </Panel>
              </>
            ) : null}
          </div>
        ) : null}
      </div>
    </>
  );
}
