"use client";
/**
 * The model-kit list (model-kit Req 6.1): the drugs with an "Experimental" badge, a status badge,
 * a one-line reason from the codes and the number of studies, and a link to the system report page. Demo mode answers from the
 * recorded file with no request.
 */
import { useEffect, useId, useState } from "react";

import { BackLink, GroupedList, LargeTitle, RowLink } from "@/components/cards";
import { StateView } from "@/components/StateView";
import { Button } from "@/components/ui";
import { useCall } from "@/flow/useCall";
import { Link } from "@/i18n/navigation";
import {
  NO_QUERY,
  STATUSES,
  PAGE_SIZE,
  type DrugSummary,
  type DrugsQuery,
  type Status,
} from "@/modelkit/model";
import { useT } from "@/theme/words";

import {
  ExperimentalChip,
  Reason,
  Statements,
  StatusChip,
  useModelKitClient,
} from "./common";

const FIELD =
  "min-h-11 w-full rounded-[var(--radius-button)] border border-line bg-surface px-3 py-2 text-fg font-normal";

export function ModelKitList() {
  const t = useT();
  const { client, recorded, failed } = useModelKitClient();
  const [text, setText] = useState("");
  const [q, setQ] = useState("");
  const [status, setStatus] = useState<Status | "">("");
  const [hasSet, setHasSet] = useState(false);
  const [offset, setOffset] = useState(0);
  // the name search waits for a pause in typing; any filter change goes back to the first page
  useEffect(() => {
    const id = setTimeout(() => {
      setQ(text.trim());
      setOffset(0);
    }, 250);
    return () => clearTimeout(id);
  }, [text]);
  const query: DrugsQuery = { ...NO_QUERY, q, status, hasSet, offset };
  const call = useCall(client ? () => client.drugs(query) : null, [
    client,
    q,
    status,
    hasSet,
    offset,
  ]);
  const searchId = useId();
  const statusId = useId();
  const ready = call.status === "ok";
  return (
    <>
      <BackLink href="/research">{t("Research.title")}</BackLink>
      <LargeTitle
        title={t("ModelKit.title")}
        summary={
          ready
            ? t("ModelKit.list.summary", { count: call.data.counts.all ?? 0 })
            : undefined
        }
        summaryTestId="mk-summary"
      />
      <div className="flex flex-wrap gap-2">
        <ExperimentalChip />
      </div>
      <Statements
        recorded={recorded}
        audit={ready ? call.data.statements.expert_audit : null}
      />
      <p className="max-w-[72ch]">{t("ModelKit.intro")}</p>
      <p className="max-w-[72ch] text-sm text-muted">
        {t("ModelKit.introValidation")}
      </p>
      <Link
        href="/research/validation-studies#modelkit-precision"
        className="inline-flex min-h-11 items-center self-start font-bold"
        data-testid="mk-validation-link"
      >
        {t("ModelKit.validationLink")}
      </Link>
      {failed ? (
        <StateView state="error" messageKey="Errors.generic" />
      ) : !client ? (
        <StateView state="loading" label={t("ModelKit.loading")} />
      ) : (
        <>
          <form
            role="search"
            aria-label={t("ModelKit.list.filter")}
            className="grid grid-cols-1 gap-3 sm:grid-cols-3"
            onSubmit={(e) => e.preventDefault()}
            data-testid="mk-filter"
          >
            <label
              htmlFor={searchId}
              className="flex min-w-0 flex-col gap-1 text-sm font-bold"
            >
              {t("ModelKit.list.search")}
              <input
                id={searchId}
                type="search"
                className={FIELD}
                value={text}
                maxLength={32}
                onChange={(e) => setText(e.target.value)}
                autoComplete="off"
                enterKeyHint="search"
                data-testid="mk-search"
              />
            </label>
            <label
              htmlFor={statusId}
              className="flex min-w-0 flex-col gap-1 text-sm font-bold"
            >
              {t("ModelKit.list.status")}
              <select
                id={statusId}
                className={FIELD}
                value={status}
                onChange={(e) => {
                  setStatus(e.target.value as Status | "");
                  setOffset(0);
                }}
                data-testid="mk-status-filter"
              >
                <option value="">{t("ModelKit.list.anyStatus")}</option>
                {STATUSES.map((st) => (
                  <option key={st} value={st}>
                    {t(`ModelKit.status.${st}`)}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex min-h-11 min-w-0 cursor-pointer items-end gap-3 pb-2 text-sm font-bold">
              <input
                type="checkbox"
                className="size-6 shrink-0 cursor-pointer accent-[var(--accent)]"
                checked={hasSet}
                onChange={(e) => {
                  setHasSet(e.target.checked);
                  setOffset(0);
                }}
                data-testid="mk-has-set"
              />
              <span className="pb-0.5">{t("ModelKit.list.hasSet")}</span>
            </label>
          </form>
          {call.status === "error" ? (
            <StateView
              state="error"
              messageKey={call.error.messageKey}
              retry={call.retry}
            />
          ) : call.status !== "ok" ? (
            <StateView state="loading" label={t("ModelKit.loading")} />
          ) : call.data.counts.all === 0 ? (
            <StateView state="empty" message={t("ModelKit.list.empty")} />
          ) : (
            <>
              <p role="status" aria-live="polite" data-testid="mk-matches">
                {t("ModelKit.list.matches", { count: call.data.total })}
              </p>
              {call.data.drugs.length === 0 ? (
                <StateView state="empty" message={t("ModelKit.list.noMatch")} />
              ) : (
                <GroupedList
                  header={t("ModelKit.list.title")}
                  headingId="mk-drugs"
                  data-testid="mk-drugs"
                >
                  {call.data.drugs.map((d) => (
                    <DrugRow key={d.key} d={d} />
                  ))}
                </GroupedList>
              )}
              <Pager
                offset={call.data.offset}
                shown={call.data.drugs.length}
                total={call.data.total}
                onPage={setOffset}
              />
              <GroupedList
                header={t("ModelKit.system.title")}
                headingId="mk-report-link"
                data-testid="mk-report-link"
              >
                <RowLink href="/research/model-kit/report">
                  <span className="flex flex-col gap-1">
                    <span className="text-lg">
                      {t("ModelKit.list.reportLink")}
                    </span>
                    <span className="font-normal text-muted">
                      {t("ModelKit.list.reportIntro")}
                    </span>
                  </span>
                </RowLink>
              </GroupedList>
            </>
          )}
        </>
      )}
    </>
  );
}

function Pager({
  offset,
  shown,
  total,
  onPage,
}: {
  offset: number;
  shown: number;
  total: number;
  onPage: (offset: number) => void;
}) {
  const t = useT();
  if (total <= PAGE_SIZE) return null;
  return (
    <nav
      aria-label={t("ModelKit.list.pages")}
      className="flex flex-wrap items-center gap-3"
      data-testid="mk-pager"
    >
      <Button
        type="button"
        variant="secondary"
        disabled={offset === 0}
        onClick={() => onPage(Math.max(0, offset - PAGE_SIZE))}
        data-testid="mk-prev"
      >
        {t("ModelKit.list.prev")}
      </Button>
      <span className="mono" data-testid="mk-range">
        {t("ModelKit.list.range", {
          from: shown ? offset + 1 : 0,
          to: offset + shown,
          total,
        })}
      </span>
      <Button
        type="button"
        variant="secondary"
        disabled={offset + shown >= total}
        onClick={() => onPage(offset + PAGE_SIZE)}
        data-testid="mk-next"
      >
        {t("ModelKit.list.next")}
      </Button>
    </nav>
  );
}

function DrugRow({ d }: { d: DrugSummary }) {
  const t = useT();
  return (
    <RowLink href={{ pathname: "/research/model-kit/drug", hash: d.key }}>
      <span className="flex flex-col gap-1.5" data-testid="mk-drug">
        <span className="text-lg break-words">{d.name}</span>
        <span className="flex flex-wrap gap-2">
          <ExperimentalChip />
          <StatusChip status={d.status} />
        </span>
        <span className="font-normal text-muted break-words">
          {d.status_reasons.map((c, i) => (
            <span key={c}>
              {i ? "; " : ""}
              <Reason code={c} />
            </span>
          ))}
        </span>
        <span className="text-sm font-normal text-muted">
          {t("ModelKit.list.studies", { count: d.studies })}
        </span>
      </span>
    </RowLink>
  );
}
