"use client";
/**
 * The model-kit list (model-kit Req 6.1): the drugs with an "Experimental" badge, a status badge,
 * a one-line reason from the codes and the number of studies, then the system report (counts by
 * status, pooled fold errors with n, the interval statement). Demo mode answers from the
 * recorded file with no request.
 */
import { useLocale } from "next-intl";
import { useEffect, useId, useState } from "react";

import {
  BackLink,
  GroupedList,
  LargeTitle,
  Row,
  RowLink,
  StatGrid,
  StatTile,
} from "@/components/cards";
import { StateView } from "@/components/StateView";
import { Button } from "@/components/ui";
import { useCall } from "@/flow/useCall";
import {
  NO_QUERY,
  PAGE_SIZE,
  STATUSES,
  type DrugSummary,
  type DrugsQuery,
  type ModelKitClient,
  type Status,
  type SystemOut,
} from "@/modelkit/model";
import { useT } from "@/theme/words";

import {
  ExperimentalChip,
  Reason,
  ScrollTable,
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
      <Statements recorded={recorded} />
      <p className="max-w-[72ch]">{t("ModelKit.intro")}</p>
      <p className="max-w-[72ch] text-sm text-muted">
        {t("ModelKit.introValidation")}
      </p>
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
            </>
          )}
          {call.status === "ok" && call.data.counts.all === 0 ? null : (
            <SystemReport client={client} />
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

function SystemReport({ client }: { client: ModelKitClient }) {
  const t = useT();
  const call = useCall(() => client.system(), [client]);
  if (call.status === "error")
    return (
      <StateView
        state="error"
        messageKey={call.error.messageKey}
        retry={call.retry}
      />
    );
  if (call.status !== "ok")
    return <StateView state="loading" label={t("ModelKit.loading")} />;
  return <SystemBody s={call.data} />;
}

function SystemBody({ s }: { s: SystemOut }) {
  const t = useT();
  const locale = useLocale();
  const pct = new Intl.NumberFormat(locale, {
    style: "percent",
    maximumFractionDigits: 0,
  });
  const nf = new Intl.NumberFormat(locale, { maximumFractionDigits: 2 });
  return (
    <section
      className="flex min-w-0 flex-col gap-group"
      aria-labelledby="mk-system"
      data-testid="mk-system"
    >
      <h2 id="mk-system" className="group-header">
        {t("ModelKit.system.title")}
      </h2>
      <StatGrid>
        {STATUSES.map((st) => (
          <StatTile
            key={st}
            value={String(s.by_status[st] ?? 0)}
            label={t(`ModelKit.status.${st}`)}
            sentence={t("ModelKit.system.countSentence", {
              count: s.by_status[st] ?? 0,
              status: t(`ModelKit.status.${st}`),
            })}
          />
        ))}
        <StatTile
          value={String(s.n_drugs_both_tested)}
          label={t("ModelKit.system.bothTested")}
          sentence={t("ModelKit.system.bothTestedSentence", {
            count: s.n_drugs_both_tested,
          })}
        />
        <StatTile
          value={String(s.n_studies)}
          label={t("ModelKit.system.studies")}
          sentence={t("ModelKit.system.studiesSentence", {
            count: s.n_studies,
          })}
        />
      </StatGrid>
      <p>
        {t("ModelKit.system.n", { drugs: s.n_drugs, studies: s.n_studies })}
      </p>
      <ScrollTable label={t("ModelKit.system.metrics")}>
        <table className="tm-table words" data-testid="mk-system-metrics">
          <caption className="sr-only">{t("ModelKit.system.metrics")}</caption>
          <thead>
            <tr>
              <th scope="col">{t("ModelKit.val.metric")}</th>
              <th scope="col">{t("ModelKit.system.drugs")}</th>
              <th scope="col">{t("ModelKit.val.gmfe")}</th>
              <th scope="col">{t("ModelKit.system.within")}</th>
              <th scope="col">{t("ModelKit.system.points")}</th>
            </tr>
          </thead>
          <tbody>
            {s.metrics.map((m) => (
              <tr key={m.name}>
                <th scope="row">{t(`ModelKit.val.${m.name}`)}</th>
                <td className="mono">{m.n_drugs}</td>
                <td className="mono">
                  {m.gmfe === null ? "—" : nf.format(m.gmfe)}
                </td>
                <td>
                  <span className="mono">
                    {t("ModelKit.system.ofN", {
                      k: m.within_2_fold,
                      n: m.n_drugs,
                    })}
                  </span>
                  {m.within_2_fold_share !== null &&
                  m.wilson_low !== null &&
                  m.wilson_high !== null ? (
                    <span className="block text-muted">
                      {t("ModelKit.system.wilson", {
                        share: pct.format(m.within_2_fold_share),
                        low: pct.format(m.wilson_low),
                        high: pct.format(m.wilson_high),
                      })}
                    </span>
                  ) : null}
                </td>
                <td>
                  <span className="mono">
                    {t("ModelKit.system.pointsOf", {
                      k: m.points_within_2_fold,
                      n: m.n_points,
                    })}
                  </span>
                  {m.points_gmfe !== null ? (
                    <span className="block text-muted">
                      {t("ModelKit.system.pointsGmfe", {
                        gmfe: nf.format(m.points_gmfe),
                      })}
                    </span>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </ScrollTable>
      <GroupedList
        header={t("ModelKit.system.limits")}
        headingId="mk-system-limits"
        data-testid="mk-system-limits"
      >
        <Row data-testid="mk-interval">
          <Reason code={s.conformal} />{" "}
          {t("ModelKit.system.minDrugs", { n: s.min_drugs_for_interpretation })}
        </Row>
        <Row data-testid="mk-gate">
          {t(
            s.interpretable
              ? "ModelKit.system.gateReached"
              : "ModelKit.system.gateNotReached",
            { both: s.n_drugs_both_tested, min: s.min_drugs_for_interpretation },
          )}
        </Row>
        {s.caveats.map((c) => (
          <Row key={c}>
            <Reason code={c} />
          </Row>
        ))}
      </GroupedList>
    </section>
  );
}
