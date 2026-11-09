"use client";
/**
 * The Summary (janus-report Req 1–4, design §4): the result of a check at a glance, as a bento
 * grid of tiles; every tile's heading is a link to the screen with the detail. Counts only (the
 * client decides nothing, experience DP3); the emergency notice first when a safety line applies;
 * no large zero (DP9); `--warn` only for the abrupt-stop line, `--risk` only for safety lines.
 */
import { useLocale } from "next-intl";
import {
  useEffect,
  useState,
  type ComponentProps,
  type ReactNode,
} from "react";

import { evidenceBody } from "@/api/builders";
import type { CascadeResult, EvidenceResolution } from "@/api/contracts";
import { AbruptStopLine } from "@/components/AbruptStopLine";
import { BackLink, LargeTitle, RowLink } from "@/components/cards";
import { EmergencyNotice } from "@/components/EmergencyNotice";
import { formatCount, formatDate, formatMonth } from "@/components/format";
import { AlertIcon, ChevronIcon } from "@/components/icons";
import { SafetyLine } from "@/components/SafetyLine";
import { StateView } from "@/components/StateView";
import { ButtonLink } from "@/components/ui";
import { useFindingWords } from "@/components/results/FindingCard";
import { ORDER_GROUPS, type OrderGroup } from "@/flow/findings";
import { useSession } from "@/flow/janus";
import {
  integritySummary,
  summaryView,
  type BoxRegion,
  type IntegritySummary,
} from "@/flow/summary";
import { useEvaluation } from "@/flow/useEvaluation";
import { Link } from "@/i18n/navigation";
import type { Item } from "@/store/list";
import { useT, useThemeWord, type Translate } from "@/theme/words";
import type { Loaded } from "@/vocabulary";
import { useVocabulary } from "@/vocabulary/use";

import {
  BarSwatch,
  MarkSwatch,
  Ring,
  SegmentBar,
  type Mark,
  type Tone,
} from "./rings";
import { ShareImage } from "./ShareImage";

export type IntegrityState =
  | { status: "none" }
  | { status: "loading" }
  | { status: "error" }
  | { status: "ok"; summary: IntegritySummary };

const GROUP_MARK: Record<OrderGroup, { mark: Mark; tone: Tone }> = {
  fits: { mark: "solid", tone: "accent" },
  fitsLate: { mark: "dashed", tone: "accent" },
  notConfirmed: { mark: "dotted", tone: "muted" },
};
const REGION_MARK: Record<BoxRegion, { mark: Mark; tone: Tone }> = {
  TR: { mark: "solid", tone: "accent" },
  EU: { mark: "dashed", tone: "chip" },
  US: { mark: "dotted", tone: "fg" },
  name: { mark: "hatched", tone: "muted" },
};
const KNOWN_SOURCES = [
  "titck",
  "openfda_ndc",
  "eu_fr_bdpm",
  "eu_es_cima",
  "wikidata",
];

export function sourceName(t: Translate, id: string): string {
  return KNOWN_SOURCES.includes(id)
    ? t(`Common.source.${id}`)
    : t("Common.source.other", { id });
}

/** One tile: a card whose heading is a link with a chevron into the detail screen. */
function Tile({
  id,
  title,
  href,
  className = "",
  children,
  testId,
}: {
  id: string;
  title: ReactNode;
  href: ComponentProps<typeof Link>["href"];
  className?: string;
  children: ReactNode;
  testId?: string;
}) {
  return (
    <section
      aria-labelledby={id}
      className={`card summary-tile ${className}`}
      data-testid={testId}
    >
      <h2 id={id} className="m-0">
        <Link href={href} className="tile-head" data-testid={`${testId}-link`}>
          <span className="min-w-0 flex-1">{title}</span>
          <ChevronIcon size={18} className="shrink-0 text-muted" />
        </Link>
      </h2>
      {children}
    </section>
  );
}

function LegendRow({
  swatch,
  label,
  value,
}: {
  swatch: ReactNode;
  label: ReactNode;
  value: string;
}) {
  return (
    <li className="flex min-h-7 items-center gap-2">
      {swatch}
      <span className="min-w-0 flex-1 text-sm">{label}</span>
      <span className="big-number text-base">{value}</span>
    </li>
  );
}

export function SummaryBody({
  result,
  items,
  vocab,
  integrity,
  share,
}: {
  result: CascadeResult;
  items: readonly Pick<Item, "candidate" | "boxName">[];
  vocab: Loaded;
  integrity: IntegrityState;
  /** The share card (browser only; render tests leave it out). */
  share?: ReactNode;
}) {
  const t = useT();
  const w = useThemeWord();
  const locale = useLocale();
  const words = useFindingWords(vocab);
  const v = summaryView(result, items, vocab);
  if (v.kind === "unavailable")
    return <StateView state="error" messageKey="Findings.unavailable" />;
  const n = (x: number) => formatCount(x, locale);
  const total = v.patterns.total;
  const full = v.medicines.total - v.medicines.notFully.length;
  const month = formatMonth(v.month, locale);

  return (
    <>
      {v.emergencyFirst ? <EmergencyNotice /> : null}
      <BackLink href="/results">{w("Findings.title")}</BackLink>
      <LargeTitle
        title={t("Report.title")}
        eyebrow={t("Report.checkedIn", { month })}
        summary={t("Report.summaryLine", {
          medicines: v.medicines.total,
          full,
          partly: v.medicines.notFully.length,
          patterns: total,
        })}
        summaryTestId="summary-line"
      />
      <div className="summary-grid">
        {/* Patterns: the lead tile. */}
        <Tile
          id="tile-patterns"
          title={w("Report.patterns.title")}
          href="/results"
          className="lead"
          testId="tile-patterns"
        >
          {total === 0 ? (
            <p className="text-lg font-bold" data-testid="no-pattern">
              {t("Findings.noPattern")}
            </p>
          ) : (
            <>
              <p className="sr-only">
                {t("Report.patterns.sentence", {
                  count: total,
                  fits: v.patterns.groups.fits.length,
                  late: v.patterns.groups.fitsLate.length,
                  unconfirmed: v.patterns.groups.notConfirmed.length,
                })}
              </p>
              <div className="flex flex-col items-center gap-5 sm:flex-row sm:items-start">
                <Ring
                  size={168}
                  thickness={16}
                  total={total}
                  segments={ORDER_GROUPS.map((g) => ({
                    value: v.patterns.groups[g].length,
                    ...GROUP_MARK[g],
                  }))}
                >
                  <span aria-hidden className="big-number text-5xl">
                    {n(total)}
                  </span>
                  <span
                    aria-hidden
                    className="mt-1 max-w-24 text-xs text-muted"
                  >
                    {t("Report.image.patterns", { count: total })}
                  </span>
                </Ring>
                <div className="flex w-full min-w-0 flex-1 flex-col gap-3">
                  {ORDER_GROUPS.map((g) => (
                    <section
                      key={g}
                      aria-labelledby={`group-${g}`}
                      className="flex flex-col gap-1"
                      data-testid={`group-${g}`}
                    >
                      <h3
                        id={`group-${g}`}
                        className="flex items-center gap-2 font-body text-sm font-bold"
                      >
                        <MarkSwatch {...GROUP_MARK[g]} />
                        <span className="min-w-0 flex-1">
                          {t(`Findings.order.${g}`)}
                        </span>
                        <span
                          className="big-number text-lg"
                          data-testid="group-count"
                        >
                          {n(v.patterns.groups[g].length)}
                        </span>
                      </h3>
                      {v.patterns.groups[g].length ? (
                        <ul className="grouped-plain">
                          {v.patterns.groups[g].map((f) => (
                            <RowLink
                              key={f.position}
                              href={{
                                pathname: "/results/finding",
                                hash: String(f.position),
                              }}
                            >
                              <span data-testid="summary-finding">
                                {words(f).title}
                              </span>
                            </RowLink>
                          ))}
                        </ul>
                      ) : null}
                    </section>
                  ))}
                </div>
              </div>
              {v.patterns.unconfirmedForm ? (
                <p className="text-sm text-muted">
                  {t("Report.patterns.unconfirmedForm", {
                    count: v.patterns.unconfirmedForm,
                  })}
                </p>
              ) : null}
              {v.safetyLines.map((code) => (
                <SafetyLine key={code} code={code} />
              ))}
              <p className="font-bold">{t("Findings.discuss")}</p>
            </>
          )}
        </Tile>

        {/* Medicines: fully checked / not fully checked. */}
        <Tile
          id="tile-medicines"
          title={t("Report.medicines.title")}
          href="/medicines"
          className="half"
          testId="tile-medicines"
        >
          <div className="flex items-center gap-4">
            <Ring
              total={v.medicines.total}
              segments={[
                { value: full, mark: "solid", tone: "accent" },
                {
                  value: v.medicines.notFully.length,
                  mark: "dotted",
                  tone: "muted",
                },
              ]}
            >
              <span aria-hidden className="big-number text-3xl">
                {n(v.medicines.total)}
              </span>
            </Ring>
            <ul aria-hidden className="flex min-w-0 flex-1 flex-col gap-1">
              <LegendRow
                swatch={<MarkSwatch mark="solid" tone="accent" />}
                label={t("Report.medicines.full")}
                value={n(full)}
              />
              <LegendRow
                swatch={<MarkSwatch mark="dotted" tone="muted" />}
                label={t("Report.medicines.partly")}
                value={n(v.medicines.notFully.length)}
              />
            </ul>
          </div>
          <p className="text-sm text-muted">
            {t("Report.medicines.sentence", {
              total: v.medicines.total,
              full,
              partly: v.medicines.notFully.length,
            })}
          </p>
        </Tile>

        {/* Patterns checked: n of m of the PIPC list. */}
        <Tile
          id="tile-rules"
          title={t("Report.rules.title")}
          href={{ pathname: "/results", hash: "scope" }}
          className="half"
          testId="tile-rules"
        >
          <div className="flex items-center gap-4">
            <Ring
              total={v.rules.total}
              segments={[
                { value: v.rules.checked, mark: "solid", tone: "chip" },
              ]}
            >
              <span aria-hidden className="big-number text-3xl">
                {n(v.rules.checked)}
              </span>
              <span aria-hidden className="mt-1 text-xs text-muted">
                {t("Report.rules.of", { total: n(v.rules.total) })}
              </span>
            </Ring>
            <p className="min-w-0 flex-1 text-sm text-muted">
              {t("Findings.scopeChecked", v.rules)}
            </p>
          </div>
        </Tile>

        {/* Abrupt-stop line: once per warned item (Req 2.4). */}
        {v.warnedItems.length ? (
          <Tile
            id="tile-abrupt"
            title={t("Report.abrupt.title")}
            href="/medicines"
            testId="tile-abrupt"
          >
            <div className="flex items-center gap-3">
              <AlertIcon size={28} className="shrink-0 text-warn" />
              <span aria-hidden className="big-number text-4xl">
                {n(v.warnedItems.length)}
              </span>
            </div>
            <p>
              {t("Report.abrupt.sentence", { count: v.warnedItems.length })}
            </p>
            <ul className="grouped-plain">
              {v.warnedItems.map((i) => (
                <li key={i} className="flex flex-col gap-0.5">
                  <span className="font-bold break-words">
                    {items[i]?.boxName}
                  </span>
                  <AbruptStopLine vocab={vocab} />
                </li>
              ))}
            </ul>
          </Tile>
        ) : null}

        {/* Regions of the boxes. */}
        <Tile
          id="tile-regions"
          title={t("Report.regions.title")}
          href="/passport"
          testId="tile-regions"
        >
          <p className="text-sm text-muted">{t("Report.regions.summary")}</p>
          <SegmentBar
            segments={(Object.keys(REGION_MARK) as BoxRegion[]).map((k) => ({
              value: v.regions[k],
              ...REGION_MARK[k],
            }))}
          />
          <ul className="flex flex-col gap-1">
            {(Object.keys(REGION_MARK) as BoxRegion[])
              .filter((k) => v.regions[k] > 0)
              .map((k) => (
                <LegendRow
                  key={k}
                  swatch={<BarSwatch {...REGION_MARK[k]} />}
                  label={
                    <>
                      {k === "name"
                        ? t("Report.regions.name")
                        : t(`Common.region.${k}`)}
                      <span className="sr-only">
                        {": "}
                        {t("Report.regions.count", { count: v.regions[k] })}
                      </span>
                    </>
                  }
                  value={n(v.regions[k])}
                />
              ))}
          </ul>
        </Tile>

        {/* Sources and their freshness. */}
        <Tile
          id="tile-sources"
          title={t("Report.sources.title")}
          href="/passport"
          className={v.warnedItems.length ? "full" : ""}
          testId="tile-sources"
        >
          <section
            aria-labelledby="sources-data"
            className="flex flex-col gap-1"
          >
            <h3
              id="sources-data"
              className="font-body text-sm font-bold text-muted"
            >
              {t("Report.sources.medicineData")}
            </h3>
            <ul className="grouped-plain">
              {v.sources.map((s) => (
                <li
                  key={`${s.sourceId}|${s.date}`}
                  className="flex flex-col gap-0.5"
                  data-testid="source-row"
                >
                  <span>
                    {t("Common.sourceLine", {
                      source: sourceName(t, s.sourceId),
                      date: formatDate(s.date, locale),
                    })}
                  </span>
                  <span className="text-sm text-muted">
                    {t("Report.sources.rowItems", { count: s.items })}
                  </span>
                </li>
              ))}
            </ul>
          </section>
          {total > 0 ? (
            <section
              aria-labelledby="sources-evidence"
              className="flex flex-col gap-1"
              data-testid="summary-integrity"
            >
              <h3
                id="sources-evidence"
                className="font-body text-sm font-bold text-muted"
              >
                {t("Report.sources.evidence")}
              </h3>
              {integrity.status === "loading" ? (
                <p role="status" aria-busy="true" className="text-sm">
                  {t("Report.sources.evidenceLoading")}
                </p>
              ) : integrity.status === "ok" ? (
                <div className="flex flex-col gap-1 rounded-[var(--radius-tile)] bg-chip p-3 text-sm text-chip-fg">
                  {/* The scope first, then the retracted sentence (cards safety review F2). */}
                  <p>
                    {t("Report.sources.evidenceCount", {
                      count: integrity.summary.sources,
                    })}
                  </p>
                  {integrity.summary.stale.map((s) => (
                    <p key={s.sourceId}>
                      {t("Evidence.line.stale", {
                        source: s.sourceId,
                        date: formatDate(s.date, locale),
                      })}
                    </p>
                  ))}
                  {integrity.summary.noRetracted ? (
                    <p className="font-bold">
                      {t("Evidence.line.noRetracted")}
                    </p>
                  ) : integrity.summary.withExclusions ? (
                    <p>
                      {t("Report.sources.withExclusions", {
                        count: integrity.summary.withExclusions,
                      })}
                    </p>
                  ) : (
                    // Never silent (safety review A6): point to each pattern's evidence.
                    <p>{t("Report.sources.seeFindings")}</p>
                  )}
                  {integrity.summary.newestCheck ? (
                    <p>
                      {t("Report.sources.lastCheck", {
                        date: formatDate(integrity.summary.newestCheck, locale),
                      })}
                    </p>
                  ) : null}
                  <p>{t("Evidence.line.about")}</p>
                </div>
              ) : (
                <p role="alert" className="text-sm">
                  {t("Report.sources.evidenceError")}
                </p>
              )}
              <ul className="grouped-plain">
                <RowLink
                  href={{
                    pathname: "/results/finding",
                    hash: String(v.findings[0]!.position),
                  }}
                >
                  {t("Report.sources.openEvidence")}
                </RowLink>
              </ul>
            </section>
          ) : null}
        </Tile>

        {share ? <div className="full">{share}</div> : null}
      </div>
    </>
  );
}

/** Loads the evidence of every finding (the detail's request; the fixture in demo mode). */
function useIntegrity(
  result: CascadeResult | null,
  client: ReturnType<typeof useSession>["client"],
): IntegrityState {
  const [state, setState] = useState<{
    key: string;
    value: IntegrityState;
  } | null>(null);
  const key = result
    ? result.findings.map((f) => f.finding_id).join("|")
    : null;
  useEffect(() => {
    if (!result || !client || !result.findings.length || key === null) return;
    let live = true;
    Promise.all(
      result.findings.map((f) =>
        client.resolveEvidence(
          evidenceBody([
            ...new Set([
              ...f.evidence_ids,
              ...f.excluded_evidence.map((e) => e.id),
            ]),
          ]),
        ),
      ),
    ).then((rs) => {
      if (!live) return;
      const ok = rs.every((r) => r.ok);
      setState({
        key,
        value: ok
          ? {
              status: "ok",
              summary: integritySummary(
                rs.map((r) => (r as { data: EvidenceResolution }).data),
              ),
            }
          : { status: "error" },
      });
    });
    return () => {
      live = false;
    };
  }, [result, client, key]);
  if (!result || !result.findings.length) return { status: "none" };
  return state && state.key === key ? state.value : { status: "loading" };
}

export function Summary() {
  const t = useT();
  const session = useSession();
  const vocab = useVocabulary();
  const evaluation = useEvaluation(session);
  const result = evaluation.status === "ok" ? evaluation.result : null;
  const integrity = useIntegrity(result, session.client);
  const items = session.items;
  if (
    !session.ready ||
    !vocab ||
    evaluation.status === "idle" ||
    evaluation.status === "loading"
  )
    return <StateView state="loading" label={t("Findings.evaluating")} />;
  if (evaluation.status === "blocked") {
    if (evaluation.reason === "empty")
      return (
        <StateView
          state="empty"
          message={t("Findings.empty")}
          action={<ButtonLink href="/scan">{t("Medicines.add")}</ButtonLink>}
        />
      );
    return (
      <StateView
        state="error"
        messageKey={
          evaluation.reason === "too_many"
            ? "Medicines.tooMany"
            : "Medicines.needsConfirmation"
        }
      />
    );
  }
  if (evaluation.status === "error") {
    const retry =
      evaluation.error.kind === "network" || evaluation.error.kind === "timeout"
        ? evaluation.retry
        : undefined;
    return (
      <StateView
        state="error"
        messageKey={evaluation.error.messageKey}
        retry={retry}
      />
    );
  }
  if (!result) return null;
  return (
    <SummaryBody
      result={result}
      items={items}
      vocab={vocab}
      integrity={integrity}
      share={<ShareImage result={result} items={items} vocab={vocab} />}
    />
  );
}
