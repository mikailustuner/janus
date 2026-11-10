"use client";
/**
 * The recall check of one US product (recall-check design §9, Req 6): a notice per FDA
 * enforcement report record that names the product code, or the checked-and-nothing-found line.
 *
 * The notice quotes the record (in English, as published) and adds nothing about the medicine.
 * The lot is compared here, on the device. No `--risk`: red is for emergencies and retracted
 * evidence (design.md); a recall notice uses `--warn`, an icon and text.
 */
import { useLocale } from "next-intl";

import { Disclosure } from "@/components/cards";
import { formatDate } from "@/components/format";
import { AlertIcon } from "@/components/icons";
import { Button, Mono } from "@/components/ui";
import type { RecallCall } from "@/recall/client";
import { lotMatch } from "@/recall/lot";
import type { RecallCheckOut, RecallMatch } from "@/recall/model";
import type { RecallQuery } from "@/recall/query";
import { useRecall, type RecallState } from "@/recall/useRecall";
import { useT } from "@/theme/words";

const STATUSES = ["Ongoing", "Completed", "Terminated"];
const link =
  "inline-flex min-h-11 items-center self-start text-sm font-bold underline underline-offset-4";

function Quote({ label, children }: { label: string; children: string }) {
  return (
    <div className="flex flex-col gap-1">
      <p className="text-sm text-muted">{label}</p>
      <blockquote
        lang="en"
        className="border-l-2 border-line pl-3 text-sm break-words whitespace-pre-line"
      >
        {children}
      </blockquote>
    </div>
  );
}

/** The limits of the check (Req 6.5, 6.6). With records shown, the data date, "United States
 *  only", the status note and the review status stay visible; with nothing found, the share of
 *  records that cannot be compared does. The rest is folded under "About this check". */
function About({ data }: { data: RecallCheckOut }) {
  const t = useT();
  const locale = useLocale();
  const { records, records_with_ndc, snapshot_date } = data.source;
  const found = data.matches.length > 0;
  const method = (
    <>
      <p className="text-sm text-muted">
        {t("Recall.method", { date: formatDate(snapshot_date, locale) })}
      </p>
      <p className="text-sm text-muted">{t("Recall.statusNote")}</p>
    </>
  );
  const coverage = (
    <p className="text-sm text-muted">
      {t("Recall.coverage", { without: records - records_with_ndc, records })}
    </p>
  );
  return (
    <>
      {found ? method : coverage}
      <Disclosure summary={t("Recall.about")} summaryClassName="text-sm">
        {found ? coverage : method}
      </Disclosure>
    </>
  );
}

function Notice({
  match,
  lot,
  searchUrl,
}: {
  match: RecallMatch;
  lot: string | null;
  searchUrl: string;
}) {
  const t = useT();
  const locale = useLocale();
  const lotState = lotMatch(lot, match.lot_codes);
  const status = match.status
    ? t(
        `Recall.statusValue.${STATUSES.includes(match.status) ? match.status : "other"}`,
        { status: match.status },
      )
    : t("Recall.notGiven");
  return (
    <li
      className="flex flex-col gap-3 rounded-[var(--radius-tile)] border-2 border-warn bg-surface p-3"
      data-testid="recall-notice"
      data-lot={lotState}
    >
      <p className="flex items-start gap-2 font-bold">
        <AlertIcon size={20} className="mt-0.5 shrink-0 text-warn" />
        <span>
          {t(`Recall.title.${lotState === "listed" ? "lot" : "product"}`)}
        </span>
      </p>
      <dl className="grid grid-cols-1 gap-x-4 gap-y-2 text-sm sm:grid-cols-2">
        <div>
          <dt className="text-muted">{t("Recall.number")}</dt>
          <dd>
            <Mono>{match.recall_number}</Mono>
          </dd>
        </div>
        <div>
          <dt className="text-muted">{t("Recall.reportDate")}</dt>
          <dd>
            {match.report_date
              ? formatDate(match.report_date, locale)
              : t("Recall.notGiven")}
          </dd>
        </div>
        <div>
          <dt className="text-muted">{t("Recall.classification")}</dt>
          <dd>{match.classification ?? t("Recall.notGiven")}</dd>
        </div>
        <div>
          <dt className="text-muted">{t("Recall.status")}</dt>
          <dd data-testid="recall-status">
            {match.terminated && match.termination_date
              ? t("Recall.terminatedOn", {
                  date: formatDate(match.termination_date, locale),
                })
              : status}
          </dd>
        </div>
      </dl>
      <Quote label={t("Recall.reason")}>
        {match.reason_for_recall ?? t("Recall.notGiven")}
      </Quote>
      <p className="text-sm">{t(`Recall.ndc.${match.ndc_match}`)}</p>
      <p className="text-sm" data-testid="recall-lot">
        {t(`Recall.lot.${lotState}`, { lot: lot ?? "" })}
      </p>
      <p className="font-bold">{t("Recall.advice")}</p>
      <Disclosure summary={t("Recall.details")} summaryClassName="text-sm">
        <Quote label={t("Recall.lotText")}>
          {match.code_info ?? t("Recall.notGiven")}
        </Quote>
        {match.code_info_truncated ? (
          <p className="text-sm text-muted">{t("Recall.lotTextCut")}</p>
        ) : null}
        <Quote label={t("Recall.productText")}>
          {match.product_description ?? t("Recall.notGiven")}
        </Quote>
        {match.recalling_firm ? (
          <p className="text-sm break-words">
            <span className="text-muted">{t("Recall.firm")}: </span>
            <span lang="en">{match.recalling_firm}</span>
          </p>
        ) : null}
      </Disclosure>
      <div className="flex flex-wrap gap-x-5">
        <a
          className={link}
          href={match.record_url}
          target="_blank"
          rel="noopener noreferrer"
        >
          {t("Recall.openRecord")}
        </a>
        <a
          className={link}
          href={searchUrl}
          target="_blank"
          rel="noopener noreferrer"
        >
          {t("Recall.search")}
        </a>
      </div>
    </li>
  );
}

/** The view of one answer state. Pure: the tests render it without a network. */
export function RecallView({
  state,
  lot,
  retry,
}: {
  state: RecallState;
  lot: string | null;
  retry?: () => void;
}) {
  const t = useT();
  const locale = useLocale();
  if (state.status === "loading")
    return (
      <p
        role="status"
        aria-busy="true"
        className="text-sm text-muted"
        data-testid="recall-loading"
      >
        {t("Recall.checking")}
      </p>
    );
  if (state.status === "error")
    return (
      <div
        role="alert"
        className="flex flex-col items-start gap-2 text-sm"
        data-testid="recall-error"
      >
        <p>
          {t("Recall.failed")} {t(state.error.messageKey)}
        </p>
        {retry ? (
          <Button variant="secondary" onClick={retry}>
            {t("Common.retry")}
          </Button>
        ) : null}
      </div>
    );
  const { data } = state;
  const outdated = data.notices.includes("snapshot_outdated") ? (
    <p className="text-sm font-bold">{t("Recall.outdated")}</p>
  ) : null;
  if (data.matches.length === 0)
    return (
      <div className="flex flex-col gap-1" data-testid="recall-none">
        <p className="text-sm text-muted">
          {t("Recall.none", {
            date: formatDate(data.source.snapshot_date, locale),
          })}
        </p>
        {outdated}
        <About data={data} />
      </div>
    );
  const hidden = data.total_matches - data.matches.length;
  return (
    <div className="flex flex-col gap-2" data-testid="recall-matches">
      <ul className="flex flex-col gap-3" aria-label={t("Recall.listLabel")}>
        {data.matches.map((m) => (
          <Notice
            key={m.recall_number}
            match={m}
            lot={lot}
            searchUrl={data.source.search_url}
          />
        ))}
      </ul>
      {hidden > 0 ? (
        <p className="text-sm">{t("Recall.more", { count: hidden })}</p>
      ) : null}
      {outdated}
      <About data={data} />
    </div>
  );
}

/** The recall check of one confirmed US product. `lot` never leaves this component. */
export function RecallCheck({
  query,
  lot,
  call,
}: {
  query: RecallQuery;
  lot: string | null;
  call?: RecallCall;
}) {
  const { retry, ...state } = useRecall(query.ndc, call);
  return <RecallView state={state} lot={lot} retry={retry} />;
}
