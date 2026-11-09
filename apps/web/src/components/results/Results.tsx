"use client";
/**
 * Results (experience design §9, §21, Req 1.3, 14, 7, 29): the emergency notice first when a
 * safety line is shown, the large title with the one-line summary, then the groups (form
 * confirmed, then product form not confirmed), chains, the medicines with their abrupt-stop lines
 * and not-checked entries, and the scope. Words come from the catalogues and the generated
 * vocabulary; the English canonical sentences are not shown.
 */
import { useLocale } from "next-intl";
import type { ReactNode } from "react";

import type { CascadeResult } from "@/api/contracts";
import { AbruptStopLine } from "@/components/AbruptStopLine";
import {
  GroupedList,
  LargeTitle,
  Row,
  StatGrid,
  StatTile,
} from "@/components/cards";
import { EmergencyNotice } from "@/components/EmergencyNotice";
import { formatCount } from "@/components/format";
import { TimelineSummary } from "@/components/medicines/Timeline";
import { keyName } from "@/components/names";
import { SafetyLine } from "@/components/SafetyLine";
import { StateView } from "@/components/StateView";
import { ButtonLink, Card, SectionTitle } from "@/components/ui";
import { ZombieAlertCard } from "@/components/zombie/Zombie";
import { resultsView } from "@/flow/findings";
import { useSession } from "@/flow/janus";
import { useEvaluation } from "@/flow/useEvaluation";
import { useT, useThemeWord } from "@/theme/words";
import { cascadeName, sentence, type Loaded } from "@/vocabulary";
import { useVocabulary } from "@/vocabulary/use";

import { FindingCard } from "./FindingCard";

/** The results body for a result: presentational, used by the page and the P8 test. */
export function ResultsBody({
  result,
  boxNames,
  vocab,
  aside,
}: {
  result: CascadeResult;
  boxNames: readonly string[];
  vocab: Loaded;
  /** Extra aside content (the timeline summary and the actions on the page). */
  aside?: ReactNode;
}) {
  const t = useT();
  const w = useThemeWord();
  const locale = useLocale();
  const view = resultsView(result, vocab);
  if (view.kind === "unavailable")
    return <StateView state="error" messageKey="Findings.unavailable" />;
  const count = view.confirmed.length + view.unconfirmed.length;
  const cascadeText = (ruleId: string) => {
    const c = cascadeName(vocab, ruleId);
    return c
      ? t("Findings.cascade", {
          drug_a: c.drug_a,
          event: c.adverse_event,
          drug_b: c.drug_b,
        })
      : ruleId;
  };
  const card = (fv: (typeof view.confirmed)[number]) => (
    <li key={fv.finding.finding_id}>
      <FindingCard
        view={fv}
        result={result}
        boxNames={boxNames}
        vocab={vocab}
      />
    </li>
  );
  return (
    <>
      {view.emergencyFirst ? <EmergencyNotice /> : null}
      <LargeTitle
        title={w("Findings.title")}
        summary={
          <>
            <span data-testid="finding-count">
              {w("Findings.count", { count })}
            </span>
            {" · "}
            {t("Cards.results.medicinesChecked", { count: boxNames.length })}
          </>
        }
      />
      <ZombieAlertCard />
      {/* Desktop (Req 27): findings on the left at reading width, a sticky aside on the right. */}
      <div className="grid gap-group lg:grid-cols-[minmax(0,72ch)_minmax(300px,1fr)] lg:items-start">
        <div className="flex min-w-0 flex-col gap-group">
          {view.safetyLines.length ? (
            <Card aria-labelledby="safety">
              <SectionTitle id="safety">
                {t("Findings.safetyHeading")}
              </SectionTitle>
              {view.safetyLines.map((code) => (
                <SafetyLine key={code} code={code} />
              ))}
            </Card>
          ) : null}
          {view.noPattern ? (
            <p className="card p-5 text-lg" data-testid="no-pattern">
              {t("Findings.noPattern")}
            </p>
          ) : null}
          {view.confirmed.length ? (
            <section
              aria-labelledby={
                view.unconfirmed.length ? "group-confirmed" : undefined
              }
              className="flex flex-col gap-3"
            >
              {/* A group heading only when both groups are shown (the summary names the findings). */}
              {view.unconfirmed.length ? (
                <h2 id="group-confirmed" className="group-header">
                  {w("Findings.groupConfirmed")}
                </h2>
              ) : null}
              <ul className="flex flex-col gap-4">
                {view.confirmed.map(card)}
              </ul>
            </section>
          ) : null}
          {view.unconfirmed.length ? (
            <section
              aria-labelledby="group-unconfirmed"
              className="flex flex-col gap-3"
            >
              <h2 id="group-unconfirmed" className="group-header">
                {t("Findings.groupUnconfirmed")}
              </h2>
              <p className="px-row-x text-muted">
                {t("Findings.groupUnconfirmedIntro", {
                  codes: view.unconfirmedCodes.join(", "),
                })}
              </p>
              <ul className="flex flex-col gap-4">
                {view.unconfirmed.map(card)}
              </ul>
            </section>
          ) : null}
          {view.chains.length ? (
            <GroupedList
              header={t("Findings.chains")}
              headingId="chains"
              footer={
                view.chainsTruncated ? (
                  <p>{t("Findings.chainsTruncated")}</p>
                ) : undefined
              }
            >
              <Row>
                <p>{t("Findings.chainsIntro")}</p>
              </Row>
              {view.chains.map((c) => (
                <Row key={c.chainId}>
                  <p className="font-bold">
                    {c.keys.map((k) => keyName(vocab, k, null)).join(" → ")}
                  </p>
                </Row>
              ))}
            </GroupedList>
          ) : null}
        </div>
        <aside className="flex min-w-0 flex-col gap-group lg:sticky lg:top-4">
          <GroupedList
            header={t("Findings.medicinesHeading")}
            headingId="checked-medicines"
          >
            {boxNames.map((name, i) => {
              const nc = view.notChecked.filter((n) => n.item === i);
              return (
                <Row key={i}>
                  <span className="font-bold">{name}</span>
                  {view.warnedItems.includes(i) ? (
                    <AbruptStopLine vocab={vocab} />
                  ) : null}
                  {nc.map((n) => (
                    <span key={n.position} className="text-sm text-muted">
                      {t("Findings.notChecked")}:{" "}
                      {sentence(vocab, `not_checked.${n.reason}`)}
                    </span>
                  ))}
                </Row>
              );
            })}
          </GroupedList>
          <GroupedList
            header={t("Findings.scope")}
            headingId="scope"
            footer={
              view.cannotCheck.length ? (
                <ul className="flex flex-col gap-1">
                  {view.cannotCheck.map((r) => (
                    <li key={r.ruleId}>
                      {t("Findings.scopeRule", {
                        row: r.row,
                        cascade: cascadeText(r.ruleId),
                        reason: t(
                          `Findings.${r.kind === "disabled" ? "disabled" : "notMatchable"}.${r.reason}`,
                        ),
                      })}
                    </li>
                  ))}
                </ul>
              ) : undefined
            }
          >
            <Row className="gap-3">
              <StatGrid>
                <StatTile
                  value={formatCount(view.rules.checked, locale)}
                  label={t("Cards.label.patternsChecked", {
                    count: view.rules.checked,
                  })}
                />
              </StatGrid>
              <p>{t("Findings.scopeChecked", view.rules)}</p>
            </Row>
          </GroupedList>
          {aside}
        </aside>
      </div>
    </>
  );
}

export function Results() {
  const t = useT();
  const session = useSession();
  const vocab = useVocabulary();
  const evaluation = useEvaluation(session);
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
  if (evaluation.status !== "ok") return null;
  return (
    <ResultsBody
      result={evaluation.result}
      boxNames={session.items.map((i) => i.boxName)}
      vocab={vocab}
      aside={
        <>
          {/* Desktop only: the phone keeps the timeline on its own screen. */}
          <div className="hidden lg:block">
            <TimelineSummary items={session.items} result={evaluation.result} />
          </div>
          <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap lg:flex-col">
            {evaluation.result.findings.length ? (
              <ButtonLink href="/note">{t("Findings.makeNote")}</ButtonLink>
            ) : null}
            <ButtonLink href="/memory" variant="secondary">
              {t("Findings.memory")}
            </ButtonLink>
            <ButtonLink href="/timeline" variant="secondary">
              {t("Medicines.timeline")}
            </ButtonLink>
          </div>
        </>
      }
    />
  );
}
