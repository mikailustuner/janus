"use client";
/**
 * "More checks on this list" on the results screen (safety-check design §8, Req 7): automated
 * comparisons of the list beside the cascade findings. Each block states what a source says and
 * refers to a pharmacist or doctor; none grades a risk or tells the person what to do, and
 * nothing found is never a clearance. No `--risk` and no `--warn`: these are not alerts.
 */
import type { ReactNode } from "react";

import type { EvaluateIn, SourceRef } from "@/api/contracts";
import { Disclosure } from "@/components/cards";
import { keyName } from "@/components/names";
import { Button, Card, Mono, SectionTitle } from "@/components/ui";
import type { SafetyCall } from "@/safety/client";
import type {
  Duplication,
  DuplicationFinding,
  SafetyCheckOut,
} from "@/safety/model";
import { useSafety, type SafetyState } from "@/safety/useSafety";
import { useT } from "@/theme/words";
import type { Loaded } from "@/vocabulary";

const KNOWN = ["titck", "openfda_ndc", "eu_fr_bdpm", "eu_es_cima", "wikidata"];

type Names = { boxNames: readonly string[]; vocab: Loaded };

/** The box name of list item `i` (it never left the browser), else its number. */
function box(names: Names, i: number): string {
  return names.boxNames[i] || `#${i + 1}`;
}

function Sources({ sources }: { sources: readonly SourceRef[] }) {
  const t = useT();
  if (sources.length === 0) return null;
  const lines = sources.map((s) =>
    t("Common.sourceLine", {
      source: KNOWN.includes(s.source_id)
        ? t(`Common.source.${s.source_id}`)
        : t("Common.source.other", { id: s.source_id }),
      date: s.snapshot_date.slice(0, 10),
    }),
  );
  return (
    <p className="text-sm text-muted" data-testid="safety-sources">
      {t("SafetyCheck.dup.sources", { sources: lines.join("; ") })}
    </p>
  );
}

function DuplicationFindingItem({
  finding,
  names,
}: {
  finding: DuplicationFinding;
  names: Names;
}) {
  const t = useT();
  const name = (m: DuplicationFinding["members"][number]) =>
    keyName(names.vocab, m.ingredient_key, m.label_en);
  const first = finding.members[0]!;
  return (
    <li
      className="flex flex-col gap-2 rounded-[var(--radius-tile)] border border-line bg-surface p-3"
      data-testid="dup-finding"
      data-kind={finding.kind}
    >
      <p className="font-bold break-words">
        {finding.kind === "same_ingredient"
          ? t("SafetyCheck.dup.sameIngredient", {
              ingredient: name(first),
              count: finding.items.length,
            })
          : t("SafetyCheck.dup.sameGroup", {
              count: finding.items.length,
              group: finding.atc_group ?? "",
            })}
      </p>
      <ul className="flex flex-col gap-1">
        {finding.members.flatMap((m) =>
          m.items.map((i) => (
            <li
              key={`${m.ingredient_key}-${i}`}
              className="flex flex-wrap items-baseline gap-x-2 break-words"
            >
              <span className="min-w-0 font-bold break-words">
                {box(names, i)}
              </span>
              <span className="min-w-0 text-sm break-words text-muted">
                {name(m)}
              </span>
              {finding.kind === "same_group" ? (
                <span className="text-sm text-muted">
                  <Mono>{m.codes.join(", ")}</Mono>
                </span>
              ) : null}
            </li>
          )),
        )}
      </ul>
      {finding.kind === "same_group" && !finding.form_confirmed ? (
        <p className="text-sm">{t("SafetyCheck.dup.unconfirmed")}</p>
      ) : null}
    </li>
  );
}

function DuplicationBlock({
  data,
  dup,
  names,
}: {
  data: SafetyCheckOut;
  dup: Duplication;
  names: Names;
}) {
  const t = useT();
  const about = (
    <>
      <p className="text-sm text-muted">{t("SafetyCheck.dup.method")}</p>
      <Sources sources={dup.sources} />
    </>
  );
  if (dup.findings.length === 0)
    return (
      <div className="flex flex-col gap-2" data-testid="dup-none">
        <p>{t("SafetyCheck.dup.none", { count: data.ingredients_checked })}</p>
        <Disclosure summary={t("SafetyCheck.about")} summaryClassName="text-sm">
          {about}
        </Disclosure>
      </div>
    );
  return (
    <div className="flex flex-col gap-3" data-testid="dup-findings">
      <ul
        className="flex flex-col gap-3"
        aria-label={t("SafetyCheck.dup.listLabel")}
      >
        {dup.findings.map((f) => (
          <DuplicationFindingItem
            key={f.finding_id}
            finding={f}
            names={names}
          />
        ))}
      </ul>
      <p className="font-bold">{t("SafetyCheck.dup.advice")}</p>
      {about}
    </div>
  );
}

function Block({
  id,
  title,
  children,
}: {
  id: string;
  title: string;
  children: ReactNode;
}) {
  return (
    <Card aria-labelledby={id}>
      <SectionTitle id={id}>{title}</SectionTitle>
      {children}
    </Card>
  );
}

/** The view of one answer state. Pure: the tests render it without a network. */
export function SafetyView({
  state,
  boxNames,
  vocab,
  retry,
}: {
  state: SafetyState;
  boxNames: readonly string[];
  vocab: Loaded;
  retry?: () => void;
}) {
  const t = useT();
  const names = { boxNames, vocab };
  return (
    <section
      aria-labelledby="safety-checks"
      className="flex flex-col gap-3"
      data-testid="safety-checks"
    >
      <h2 id="safety-checks" className="group-header">
        {t("SafetyCheck.title")}
      </h2>
      <p className="px-row-x text-muted">
        {t("SafetyCheck.intro")} {t("SafetyCheck.review")}
      </p>
      {state.status === "loading" ? (
        <p
          role="status"
          aria-busy="true"
          className="card p-4 text-muted"
          data-testid="safety-loading"
        >
          {t("SafetyCheck.checking")}
        </p>
      ) : state.status === "error" ? (
        <div
          role="alert"
          className="card flex flex-col items-start gap-3 p-4"
          data-testid="safety-error"
        >
          <p>
            {t("SafetyCheck.failed")} {t(state.error.messageKey)}
          </p>
          {retry ? (
            <Button variant="secondary" onClick={retry}>
              {t("Common.retry")}
            </Button>
          ) : null}
        </div>
      ) : (
        <>
          {state.data.not_checked.length ? (
            <p className="px-row-x text-sm" data-testid="safety-not-checked">
              {t("SafetyCheck.notChecked", {
                count: state.data.not_checked.length,
              })}
            </p>
          ) : null}
          <Block id="safety-dup" title={t("SafetyCheck.dup.title")}>
            <DuplicationBlock
              data={state.data}
              dup={state.data.duplication}
              names={names}
            />
          </Block>
        </>
      )}
    </section>
  );
}

/** The checks of the list that was just evaluated; the body is the evaluation's own input. */
export function SafetyChecks({
  body,
  boxNames,
  vocab,
  call,
}: {
  body: EvaluateIn;
  boxNames: readonly string[];
  vocab: Loaded;
  call?: SafetyCall;
}) {
  const { retry, ...state } = useSafety(body, call);
  return (
    <SafetyView state={state} boxNames={boxNames} vocab={vocab} retry={retry} />
  );
}
