"use client";
/**
 * The model-kit list (model-kit Req 6.1): the drugs with an "Experimental" badge, a status badge,
 * a one-line reason from the codes and the number of studies, then the system report (counts by
 * status, pooled fold errors with n, the interval statement). Demo mode answers from the
 * recorded file with no request.
 */
import { useLocale } from "next-intl";

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
import { useCall } from "@/flow/useCall";
import {
  STATUSES,
  type DrugSummary,
  type ModelKitClient,
  type SystemOut,
} from "@/modelkit/model";
import { useT } from "@/theme/words";

import {
  ExperimentalChip,
  Reason,
  Statements,
  StatusChip,
  useModelKitClient,
} from "./common";

export function ModelKitList() {
  const t = useT();
  const { client, recorded, failed } = useModelKitClient();
  const call = useCall(client ? () => client.drugs() : null, [client]);
  return (
    <>
      <BackLink href="/research">{t("Research.title")}</BackLink>
      <LargeTitle
        title={t("ModelKit.title")}
        summary={
          call.status === "ok"
            ? t("ModelKit.list.summary", { count: call.data.drugs.length })
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
      ) : call.status === "error" ? (
        <StateView
          state="error"
          messageKey={call.error.messageKey}
          retry={call.retry}
        />
      ) : call.status !== "ok" || !client ? (
        <StateView state="loading" label={t("ModelKit.loading")} />
      ) : call.data.drugs.length === 0 ? (
        <StateView state="empty" message={t("ModelKit.list.empty")} />
      ) : (
        <>
          <GroupedList
            header={t("ModelKit.list.title")}
            headingId="mk-drugs"
            data-testid="mk-drugs"
          >
            {call.data.drugs.map((d) => (
              <DrugRow key={d.key} d={d} />
            ))}
          </GroupedList>
          <SystemReport client={client} />
        </>
      )}
    </>
  );
}

function DrugRow({ d }: { d: DrugSummary }) {
  const t = useT();
  return (
    <RowLink
      href={{ pathname: "/research/model-kit/drug", hash: d.key }}
    >
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
          value={String(s.n_studies)}
          label={t("ModelKit.system.studies")}
          sentence={t("ModelKit.system.studiesSentence", {
            count: s.n_studies,
          })}
        />
      </StatGrid>
      <p>{t("ModelKit.system.n", { drugs: s.n_drugs, studies: s.n_studies })}</p>
      <div
        className="card relative overflow-x-auto p-0"
        tabIndex={0}
        role="region"
        aria-label={t("ModelKit.system.metrics")}
      >
        <table className="tm-table" data-testid="mk-system-metrics">
          <caption className="sr-only">{t("ModelKit.system.metrics")}</caption>
          <thead>
            <tr>
              <th scope="col">{t("ModelKit.val.metric")}</th>
              <th scope="col">{t("ModelKit.system.drugs")}</th>
              <th scope="col">{t("ModelKit.val.gmfe")}</th>
              <th scope="col">{t("ModelKit.system.within")}</th>
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
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <GroupedList
        header={t("ModelKit.system.limits")}
        headingId="mk-system-limits"
        data-testid="mk-system-limits"
      >
        <Row data-testid="mk-interval">
          <Reason code={s.conformal} />{" "}
          {t("ModelKit.system.minDrugs", { n: s.min_drugs_for_interpretation })}
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
