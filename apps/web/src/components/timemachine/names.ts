/**
 * Names of a time-machine cascade in the interface language (DP58): the PIPC row's names from the
 * vocabulary; when the cascade was built from one index drug only (amlodipine, metoclopramide),
 * that drug's ingredient name replaces the class, because the reports and models are for that drug.
 */
import type { Cascade } from "@/timemachine/model";
import { TM_INDEX } from "@/timemachine/view";
import type { Translate } from "@/theme/words";
import type { Loaded } from "@/vocabulary";

export function cascadeTitle(
  t: Translate,
  v: Loaded,
  c: Pick<
    Cascade,
    "cascade_id" | "pipc_position" | "index_class" | "event" | "treating_class"
  >,
): string {
  const row = v.vocab.cascades[String(c.pipc_position)];
  const entry = TM_INDEX.cascades.find((e) => e.id === c.cascade_id);
  const single =
    entry && entry.index_keys.length === 1
      ? ((v.vocab.ingredients as Record<string, string>)[
          entry.index_keys[0]!
        ] ?? null)
      : null;
  return t("TimeMachine.cascadeTitle", {
    drugA: single ?? row?.drug_a ?? c.index_class,
    event: row?.adverse_event ?? c.event,
    drugB: row?.drug_b ?? c.treating_class,
  });
}
