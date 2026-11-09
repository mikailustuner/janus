"use client";
/**
 * The one patient-facing sentence of the time machine (time-machine design §10.5, Req 9;
 * experience Req 30.6, DP62), in the finding detail. All cascades of the catalogue are fetched (the
 * requests do not depend on the person's medicines); the sentence appears only when the gate of
 * `patientTiming` passes. No concentration, dose, potency, molecule or curve; nothing on failure.
 */
import { useNum, useTimeMachineClient } from "@/components/timemachine/common";
import { useCall } from "@/flow/useCall";
import { allCascades } from "@/timemachine/client";
import { patientTiming } from "@/timemachine/view";
import { keyName } from "@/components/names";
import { useT } from "@/theme/words";
import { eventKeyForRule } from "@/vocabulary";
import { useVocabulary } from "@/vocabulary/use";

export function TimingSentence({
  ruleId,
  indexKey,
}: {
  ruleId: string;
  indexKey: string;
}) {
  const t = useT();
  const n = useNum();
  const row = Number(/^pipc:(\d+)$/.exec(ruleId)?.[1] ?? NaN);
  const { client } = useTimeMachineClient();
  const vocab = useVocabulary();
  const call = useCall(
    client && Number.isInteger(row) ? () => allCascades(client) : null,
    [client, row],
  );
  if (call.status !== "ok" || !vocab) return null;
  const timing = patientTiming(row, indexKey, call.data);
  const eventKey = eventKeyForRule(vocab, ruleId);
  const event = eventKey ? vocab.vocab.events[eventKey]?.label : null;
  if (!timing || !event) return null;
  return (
    <section
      className="card flex flex-col gap-2 p-4 sm:p-5"
      aria-labelledby="tm-patient"
      data-testid="tm-patient-sentence"
    >
      <h2 id="tm-patient" className="font-body text-lg font-bold">
        {t("TimeMachine.patient.heading")}
      </h2>
      <p>
        {t("TimeMachine.patient.sentence", {
          event,
          drug: keyName(vocab, indexKey, null),
          start: n.int(timing.start),
          end: n.int(timing.end),
        })}
      </p>
      <p className="text-sm text-muted">{t("TimeMachine.patient.review")}</p>
    </section>
  );
}
