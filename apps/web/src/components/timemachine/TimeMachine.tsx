"use client";
/**
 * The time-machine index (experience Req 30.1, DP58; time-machine design §10.1): large title and
 * summary, the labels, remedies and cascades as grouped row links, the validation block with
 * every verdict and "how it was made". Loading, error (503 not installed, retry), empty states.
 */
import { GroupedList, LargeTitle, RowLink, BackLink } from "@/components/cards";
import { StateView } from "@/components/StateView";
import type { Result } from "@/api/client";
import { useCall } from "@/flow/useCall";
import type { TimeMachineClient } from "@/timemachine/client";
import type { CascadeOut, Catalogue, SubstanceOut } from "@/timemachine/model";
import { useT } from "@/theme/words";
import { useVocabulary } from "@/vocabulary/use";

import {
  SourcesBlock,
  TmLabels,
  useTimeMachineClient,
  ValidationBlock,
} from "./common";
import { cascadeTitle } from "./names";

interface Overview {
  catalogue: Catalogue;
  substances: SubstanceOut[];
  cascades: CascadeOut[];
}

async function overview(c: TimeMachineClient): Promise<Result<Overview>> {
  const cat = await c.catalogue();
  if (!cat.ok) return cat;
  const subs = await Promise.all(
    cat.data.substance_ids.map((id) => c.substance(id)),
  );
  const cas = await Promise.all(
    cat.data.cascade_ids.map((id) => c.cascade(id)),
  );
  const substances: SubstanceOut[] = [];
  for (const s of subs) {
    if (!s.ok) return s;
    substances.push(s.data);
  }
  const cascades: CascadeOut[] = [];
  for (const x of cas) {
    if (!x.ok) return x;
    cascades.push(x.data);
  }
  return { ok: true, data: { catalogue: cat.data, substances, cascades } };
}

export function TimeMachine() {
  const t = useT();
  const vocab = useVocabulary();
  const { client, recorded } = useTimeMachineClient();
  const call = useCall(client ? () => overview(client) : null, [client]);

  return (
    <>
      <BackLink href="/research">{t("Research.title")}</BackLink>
      <LargeTitle
        title={t("TimeMachine.title")}
        summary={
          call.status === "ok"
            ? t("TimeMachine.summary", {
                substances: call.data.catalogue.substance_ids.length,
                cascades: call.data.catalogue.cascade_ids.length,
              })
            : undefined
        }
        summaryTestId="tm-summary"
      />
      <p className="max-w-[72ch]">{t("TimeMachine.intro")}</p>
      <TmLabels recorded={recorded} />
      {call.status === "error" ? (
        <StateView
          state="error"
          messageKey={call.error.messageKey}
          retry={call.retry}
        />
      ) : call.status !== "ok" || !vocab ? (
        <StateView state="loading" label={t("TimeMachine.loading")} />
      ) : call.data.catalogue.substance_ids.length +
          call.data.catalogue.cascade_ids.length ===
        0 ? (
        <StateView state="empty" message={t("TimeMachine.empty")} />
      ) : (
        <div className="grid gap-group lg:grid-cols-2 lg:items-start">
          <div className="flex min-w-0 flex-col gap-group">
            <GroupedList
              header={t("TimeMachine.sections.substances")}
              headingId="tm-substances"
              data-testid="tm-substances"
              footer={<p>{t("TimeMachine.sections.substancesFooter")}</p>}
            >
              {call.data.substances.map((s) => (
                <RowLink
                  key={s.substance.substance_id}
                  href={{
                    pathname: "/research/time-machine/substance",
                    hash: s.substance.substance_id,
                  }}
                >
                  <span className="flex flex-col gap-0.5">
                    <span className="text-lg">
                      {t(`TimeMachine.substances.${s.substance.substance_id}`)}
                    </span>
                    <span className="font-normal text-muted">
                      {t("TimeMachine.rowSubstance", {
                        constituents: s.substance.constituents.length,
                        drugs: new Set(
                          s.substance.todays_drugs.map((d) => d.drug),
                        ).size,
                      })}
                    </span>
                  </span>
                </RowLink>
              ))}
            </GroupedList>
            <GroupedList
              header={t("TimeMachine.sections.cascades")}
              headingId="tm-cascades"
              data-testid="tm-cascades"
              footer={<p>{t("TimeMachine.sections.cascadesFooter")}</p>}
            >
              {call.data.cascades.map((c) => (
                <RowLink
                  key={c.cascade.cascade_id}
                  href={{
                    pathname: "/research/time-machine/cascade",
                    hash: c.cascade.cascade_id,
                  }}
                >
                  <span className="flex flex-col gap-0.5">
                    <span className="text-lg break-words">
                      {cascadeTitle(t, vocab, c.cascade)}
                    </span>
                    <span className="font-normal text-muted">
                      {t("TimeMachine.cascadeRow", {
                        row: c.cascade.pipc_position,
                        method: t(`TimeMachine.method.${c.cascade.method}`),
                      })}
                    </span>
                  </span>
                </RowLink>
              ))}
            </GroupedList>
          </div>
          <div className="flex min-w-0 flex-col gap-group">
            <ValidationBlock validation={call.data.catalogue.validation} />
            <SourcesBlock catalogue={call.data.catalogue} />
          </div>
        </div>
      )}
    </>
  );
}
