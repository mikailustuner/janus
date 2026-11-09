"use client";
/**
 * One finding (Req 14.3, 14.11, 7, 29): a ghost in Night Pharmacy, "possible prescribing cascade"
 * in Glass Janus; the cascade in the interface language, the two medicines with box names as the
 * card's summary line, status and timing, priority data, notes, integrity notices, the abrupt-stop
 * and safety lines, and the sentence that it may be worth discussing with the doctor. A pattern
 * match, never a verdict; never `--risk` except the safety line itself.
 */
import { useLocale } from "next-intl";
import { useRef } from "react";

import type { CascadeResult } from "@/api/contracts";
import { AbruptStopLine } from "@/components/AbruptStopLine";
import { Disclosure } from "@/components/cards";
import { Ghost } from "@/components/Ghost";
import { formatMonth } from "@/components/format";
import { ChevronIcon } from "@/components/icons";
import { keyName } from "@/components/names";
import { ReadAloud } from "@/components/ReadAloud";
import { SafetyLine } from "@/components/SafetyLine";
import { Card, Chip } from "@/components/ui";
import type { FindingView } from "@/flow/findings";
import { Link } from "@/i18n/navigation";
import { findingReportHref } from "@/report/fragment";
import { useT, useTheme, useThemeWord } from "@/theme/words";
import { cascadeName, type Loaded } from "@/vocabulary";

const ORDER_LABEL = {
  within_window: "fits",
  after_window: "fitsLate",
  same_month: "notConfirmed",
  date_unknown: "notConfirmed",
} as const;

export function useFindingWords(vocab: Loaded) {
  return (fv: FindingView) => {
    const f = fv.finding;
    const cascade = cascadeName(vocab, f.rule_id);
    const event = fv.eventKey
      ? vocab.vocab.events[fv.eventKey]?.label
      : undefined;
    return {
      title: event ?? cascade?.adverse_event ?? f.rule_text.adverse_event,
      cascade: cascade ?? {
        drug_a: f.rule_text.drug_a,
        adverse_event: f.rule_text.adverse_event,
        drug_b: f.rule_text.drug_b,
      },
      index: keyName(vocab, f.index.ingredient_key, f.index.label_en),
      marker: keyName(vocab, f.marker.ingredient_key, f.marker.label_en),
    };
  };
}

export function FindingCard({
  view,
  result,
  boxNames,
  vocab,
  detail = true,
}: {
  view: FindingView;
  result: CascadeResult;
  boxNames: readonly string[];
  vocab: Loaded;
  /** True on the results screen (a summary card with a link to the detail). */
  detail?: boolean;
}) {
  const t = useT();
  const w = useThemeWord();
  const theme = useTheme();
  const locale = useLocale();
  const ref = useRef<HTMLElement>(null);
  const words = useFindingWords(vocab)(view);
  const f = view.finding;
  const boxes = (items: number[]) =>
    items
      .map((i) => boxNames[i] ?? "")
      .filter(Boolean)
      .join(", ");
  // The chip describes the order from the timing, never "probable"/"possible" (DP43): the engine
  // status `possible` also covers a known order after the window.
  const status = t(`Findings.order.${ORDER_LABEL[f.timing]}`);
  const orderKnown =
    f.timing === "within_window" || f.timing === "after_window";
  const row = f.rule_id.split(":")[1] ?? "";
  const startLine = (name: string, start: string | null) =>
    start
      ? t("Findings.started", { name, month: formatMonth(start, locale) })
      : t("Findings.startUnknown", { name });
  // On the finding detail the card's title is the page's large title (Req 29.2, DP56).
  const Title = detail ? "h3" : "h1";

  // The class chain, start months, priority data, notes and integrity notices: folded on the
  // results screen, open on the finding detail (DP39).
  const secondary = (
    <>
      <p className="text-sm text-muted">
        {t("Findings.cascade", {
          drug_a: words.cascade.drug_a,
          event: words.cascade.adverse_event,
          drug_b: words.cascade.drug_b,
        })}
      </p>
      <ul className="text-sm">
        <li>{startLine(words.index, f.index.start)}</li>
        <li>{startLine(words.marker, f.marker.start)}</li>
      </ul>
      {f.priority ? (
        <p className="text-sm">
          {t(`Findings.priority.${f.priority.measure}`, {
            value: f.priority.value,
            low: f.priority.ci_low,
            high: f.priority.ci_high,
          })}
        </p>
      ) : null}
      {f.rule_id === "pipc:49" ? (
        <p className="text-sm">{t("Findings.row49")}</p>
      ) : null}
      {view.supporting ? (
        <p className="text-sm">{t("Findings.supporting")}</p>
      ) : null}
      {f.via_form_extension ? (
        <p className="text-sm">{t("Findings.formExtension")}</p>
      ) : null}
      {f.integrity_codes.map((c) => (
        <p key={c} className="text-sm text-muted">
          {t(`Findings.integrity.${c}`)}
        </p>
      ))}
    </>
  );

  return (
    <Card
      as="article"
      aria-labelledby={`finding-${view.position}`}
      data-testid="finding"
      data-rule={f.rule_id}
      className="gap-4 sm:p-5"
    >
      <div ref={ref as never} className="flex flex-col gap-4">
        <header className="flex items-start gap-3">
          {theme === "two-faces" ? (
            <Ghost size={detail ? 36 : 48} animated className="mt-1 shrink-0" />
          ) : null}
          <div className="flex min-w-0 flex-1 flex-col items-start gap-1.5">
            <p className="text-sm text-muted">{w("Findings.kind")}</p>
            <Title
              id={`finding-${view.position}`}
              className={
                detail
                  ? "font-body text-xl leading-snug font-bold"
                  : "large-title"
              }
            >
              {words.title}
            </Title>
            <Chip>
              {f.months_between !== null
                ? t("Findings.statusMonths", {
                    status,
                    months: f.months_between,
                  })
                : status}
            </Chip>
          </div>
        </header>
        {/* The summary line: which two medicines; "then" only when the order is known (owner
            decision 2026-11-08, pharmacologist B2). */}
        <p className="text-lg leading-snug">
          {t(orderKnown ? "Findings.medicines" : "Findings.medicinesRoles", {
            index: words.index,
            indexBox: boxes(f.index.items),
            marker: words.marker,
            markerBox: boxes(f.marker.items),
          })}
        </p>
        <ul className="grouped-plain border-y border-line">
          <li className="flex flex-col gap-1">
            <p>{t("Findings.pattern")}</p>
            <p className="text-sm text-muted">
              {t("Findings.source", { row })}
            </p>
          </li>
          <li>
            <p>
              {t(`Findings.timing.${f.timing}`, {
                index: words.index,
                marker: words.marker,
                months: f.months_between ?? 0,
                window: result.window_months,
              })}
            </p>
          </li>
          {f.low_priority ? (
            <li>
              <p className="text-sm">{t("Findings.lowPriority")}</p>
            </li>
          ) : null}
        </ul>
        {detail ? (
          <Disclosure
            summary={t("Common.details")}
            summaryClassName="text-muted"
          >
            {secondary}
          </Disclosure>
        ) : (
          <div className="flex flex-col gap-2">{secondary}</div>
        )}
        {/* On the results screen the medicines section carries the line once per item (Req 14.5). */}
        {(detail ? [] : view.warnedItems).map((i) => (
          <div key={i} className="flex flex-col">
            <span className="text-sm text-muted">{boxNames[i]}</span>
            <AbruptStopLine vocab={vocab} />
          </div>
        ))}
        {view.safetyLine ? <SafetyLine code={view.safetyLine} /> : null}
        <p className="font-bold">{t("Findings.discuss")}</p>
        {detail ? (
          <Link
            href={findingReportHref({
              index: f.index,
              eventKey: view.eventKey,
            })}
            className="inline-flex min-h-11 w-fit items-center font-bold text-accent underline underline-offset-4"
          >
            {t("ReportAssistant.link")}
          </Link>
        ) : null}
      </div>
      <ReadAloud text={() => ref.current?.innerText ?? ""} />
      {detail ? (
        <Link
          href={{ pathname: "/results/finding", hash: String(view.position) }}
          className="-mx-4 -mb-4 flex min-h-13 items-center justify-between gap-3 rounded-b-[var(--radius-card)] border-t border-line px-4 font-bold text-accent no-underline transition-colors duration-150 hover:bg-chip sm:-mx-5 sm:-mb-5 sm:px-5"
        >
          {t("Findings.openDetail")}
          <ChevronIcon size={20} className="shrink-0" />
        </Link>
      ) : null}
    </Card>
  );
}
