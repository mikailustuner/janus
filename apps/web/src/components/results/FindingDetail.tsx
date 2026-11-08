"use client";
/**
 * One finding with its evidence and the FAERS pair (design §9, Req 15, 16.1). The finding's
 * position is in the URL fragment, so no ingredient key reaches the server in a path (DP35).
 * Evidence and the pair load independently; each panel has its own states.
 */
import { useEffect, useState } from "react";

import { pairBody, evidenceBody } from "@/api/builders";
import { EmergencyNotice } from "@/components/EmergencyNotice";
import { EvidenceBody } from "@/components/evidence/EvidenceView";
import { PairPanel } from "@/components/memory/PairPanel";
import { keyName } from "@/components/names";
import { StateView } from "@/components/StateView";
import { ButtonLink } from "@/components/ui";
import { resultsView } from "@/flow/findings";
import { useSession } from "@/flow/janus";
import { parseLocator } from "@/flow/locator";
import { useCall } from "@/flow/useCall";
import { useEvaluation } from "@/flow/useEvaluation";
import { useT } from "@/theme/words";
import { useVocabulary } from "@/vocabulary/use";

import { FindingCard } from "./FindingCard";

function useHashIndex(): number | null | undefined {
  const [i, setI] = useState<number | null | undefined>(undefined);
  useEffect(() => {
    const read = () => {
      const n = Number(location.hash.slice(1));
      setI(Number.isInteger(n) && n >= 0 ? n : null);
    };
    read();
    window.addEventListener("hashchange", read);
    return () => window.removeEventListener("hashchange", read);
  }, []);
  return i;
}

export function FindingDetail() {
  const t = useT();
  const session = useSession();
  const vocab = useVocabulary();
  const evaluation = useEvaluation(session);
  const position = useHashIndex();
  const result = evaluation.status === "ok" ? evaluation.result : null;
  const finding =
    result && typeof position === "number"
      ? (result.findings[position] ?? null)
      : null;
  const client = session.client;
  const locator = parseLocator(finding?.faers_locator);

  const evidence = useCall(
    finding && client
      ? () =>
          client.resolveEvidence(
            evidenceBody([
              ...new Set([
                ...finding.evidence_ids,
                ...finding.excluded_evidence.map((e) => e.id),
              ]),
            ]),
          )
      : null,
    [finding?.finding_id, client],
  );
  const pair = useCall(
    locator && client
      ? () =>
          client.memoryPair(pairBody(locator.ingredient, locator.event, "ALL"))
      : null,
    [finding?.faers_locator, client],
  );
  const snapshot = useCall(
    client && locator ? () => client.memorySnapshot() : null,
    [client, !!locator],
  );

  if (
    !session.ready ||
    !vocab ||
    evaluation.status === "loading" ||
    evaluation.status === "idle" ||
    position === undefined
  )
    return <StateView state="loading" />;
  if (evaluation.status === "error")
    return (
      <StateView
        state="error"
        messageKey={evaluation.error.messageKey}
        retry={evaluation.retry}
      />
    );
  if (!result || !finding)
    return (
      <StateView
        state="empty"
        message={t("Findings.empty")}
        action={
          <ButtonLink href="/results">{t("Shell.nav.results")}</ButtonLink>
        }
      />
    );
  const view = resultsView(result, vocab);
  if (view.kind !== "ok")
    return <StateView state="error" messageKey="Findings.unavailable" />;
  const fv = [...view.confirmed, ...view.unconfirmed].find(
    (f) => f.position === position,
  )!;
  const eventLabel = fv.eventKey
    ? (vocab.vocab.events[fv.eventKey]?.label ?? fv.eventKey)
    : "";

  return (
    <>
      {fv.safetyLine ? <EmergencyNotice /> : null}
      <ButtonLink href="/results" variant="quiet" className="self-start">
        {t("Common.back")}
      </ButtonLink>
      <FindingCard
        view={fv}
        result={result}
        boxNames={session.items.map((i) => i.boxName)}
        vocab={vocab}
        detail={false}
      />
      {evidence.status === "loading" ? (
        <StateView state="loading" label={t("Evidence.loading")} />
      ) : evidence.status === "error" ? (
        <div className="flex flex-col gap-2">
          <StateView
            state="error"
            messageKey={evidence.error.messageKey}
            retry={evidence.retry}
          />
          <ul className="mono text-sm">
            {finding.evidence_ids.map((id) => (
              <li key={id}>{id}</li>
            ))}
          </ul>
        </div>
      ) : evidence.status === "ok" ? (
        <EvidenceBody resolution={evidence.data} />
      ) : null}
      {locator ? (
        pair.status === "loading" ? (
          <StateView state="loading" label={t("MemoryView.loading")} />
        ) : pair.status === "error" ? (
          <StateView
            state="error"
            messageKey={pair.error.messageKey}
            retry={pair.retry}
          />
        ) : pair.status === "ok" ? (
          <PairPanel
            pair={pair.data}
            ingredient={keyName(
              vocab,
              finding.index.ingredient_key,
              finding.index.label_en,
            )}
            event={eventLabel}
            snapshot={snapshot.status === "ok" ? snapshot.data : null}
          />
        ) : null
      ) : null}
      <div className="flex flex-wrap gap-3">
        <ButtonLink href="/note">{t("Findings.makeNote")}</ButtonLink>
        <ButtonLink href="/memory" variant="secondary">
          {t("Findings.memory")}
        </ButtonLink>
      </div>
    </>
  );
}
