"use client";
/**
 * Results (experience design §9, Req 1.3, 14, 7): the emergency notice first when a safety line
 * is shown, then the groups (form confirmed, then product form not confirmed), chains, the
 * medicines with their abrupt-stop lines and not-checked entries, and the scope. Words come from
 * the catalogues and the generated vocabulary; the English canonical sentences are not shown.
 */
import type { ReactNode } from "react";

import type { CascadeResult } from "@/api/contracts";
import { AbruptStopLine } from "@/components/AbruptStopLine";
import { EmergencyNotice } from "@/components/EmergencyNotice";
import { TimelineSummary } from "@/components/medicines/Timeline";
import { keyName } from "@/components/names";
import { SafetyLine } from "@/components/SafetyLine";
import { StateView } from "@/components/StateView";
import { ButtonLink, Card, PageTitle, SectionTitle } from "@/components/ui";
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
      <PageTitle
        eyebrow={t("Findings.checkedOf", {
          items: boxNames.length,
          total: view.rules.checked, // patterns actually checked (pharmacologist review A2)
        })}
      >
        <span data-testid="finding-count">
          {w("Findings.count", { count })}
        </span>
      </PageTitle>
      <ZombieAlertCard />
      {/* Desktop (Req 27): findings on the left at reading width, a sticky aside on the right. */}
      <div className="grid gap-5 lg:grid-cols-[minmax(0,72ch)_minmax(300px,1fr)] lg:items-start">
        <div className="flex min-w-0 flex-col gap-5">
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
            <p className="card p-4 text-lg" data-testid="no-pattern">
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
              {/* A group heading only when both groups are shown (the page title names the findings). */}
              {view.unconfirmed.length ? (
                <SectionTitle id="group-confirmed">
                  {w("Findings.groupConfirmed")}
                </SectionTitle>
              ) : null}
              <ul className="flex flex-col gap-3">
                {view.confirmed.map(card)}
              </ul>
            </section>
          ) : null}
          {view.unconfirmed.length ? (
            <section
              aria-labelledby="group-unconfirmed"
              className="flex flex-col gap-3"
            >
              <SectionTitle id="group-unconfirmed">
                {t("Findings.groupUnconfirmed")}
              </SectionTitle>
              <p>
                {t("Findings.groupUnconfirmedIntro", {
                  codes: view.unconfirmedCodes.join(", "),
                })}
              </p>
              <ul className="flex flex-col gap-3">
                {view.unconfirmed.map(card)}
              </ul>
            </section>
          ) : null}
          {view.chains.length ? (
            <Card aria-labelledby="chains">
              <SectionTitle id="chains">{t("Findings.chains")}</SectionTitle>
              <p>{t("Findings.chainsIntro")}</p>
              <ul className="list-disc pl-5">
                {view.chains.map((c) => (
                  <li key={c.chainId}>
                    {c.keys.map((k) => keyName(vocab, k, null)).join(" → ")}
                  </li>
                ))}
              </ul>
              {view.chainsTruncated ? (
                <p className="text-sm">{t("Findings.chainsTruncated")}</p>
              ) : null}
            </Card>
          ) : null}
        </div>
        <aside className="flex min-w-0 flex-col gap-5 lg:sticky lg:top-4">
          <Card aria-labelledby="checked-medicines">
            <SectionTitle id="checked-medicines">
              {t("Findings.medicinesHeading")}
            </SectionTitle>
            <ul className="flex flex-col gap-2">
              {boxNames.map((name, i) => {
                const nc = view.notChecked.filter((n) => n.item === i);
                return (
                  <li
                    key={i}
                    className="flex flex-col gap-1 border-t border-line pt-2 first:border-0 first:pt-0"
                  >
                    <span className="font-bold">{name}</span>
                    {view.warnedItems.includes(i) ? (
                      <AbruptStopLine vocab={vocab} />
                    ) : null}
                    {nc.map((n) => (
                      <span key={n.position} className="text-sm">
                        {t("Findings.notChecked")}:{" "}
                        {sentence(vocab, `not_checked.${n.reason}`)}
                      </span>
                    ))}
                  </li>
                );
              })}
            </ul>
          </Card>
          <Card aria-labelledby="scope">
            <SectionTitle id="scope">{t("Findings.scope")}</SectionTitle>
            <p>{t("Findings.scopeChecked", view.rules)}</p>
            <ul className="flex flex-col gap-1 text-sm">
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
          </Card>
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
          <div className="flex flex-wrap gap-3">
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
