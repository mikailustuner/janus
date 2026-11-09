"use client";
/**
 * Retrospective validation report (light-face design §8, §10, Req 5.2, 5.3): informative hits first
 * with the chance level, then one card per case with both runs, the two primary variants, the
 * labels removed, the FAERS numbers and their warning, and the evidence.
 */
import { useLocale } from "next-intl";

import { formatCount, formatRatio } from "@/components/format";
import { StateView } from "@/components/StateView";
import { Card, SectionTitle } from "@/components/ui";
import { useCall } from "@/flow/useCall";
import { lightClient } from "@/light/client";
import type { CaseResult, CaseRun, ValidationOut } from "@/light/model";
import { caseRank, nameIn, summaryValues } from "@/light/view";
import { useT, type Translate } from "@/theme/words";

import { LightFrame } from "./LightFrame";

function rankLabel(t: Translate, run: CaseRun): string {
  const r = caseRank(run);
  return r ? t(r.key, r.values) : t("Light.validation.noRank");
}

function Run({ title, run, k }: { title: string; run: CaseRun; k: number }) {
  const t = useT();
  const locale = useLocale();
  return (
    <div className="flex flex-col gap-1">
      <h4 className="font-semibold">{title}</h4>
      <p>
        <span className="mono">{rankLabel(t, run)}</span> ·{" "}
        {t(`Light.validation.reason.${run.reason}`, { k })}
      </p>
      {run.hit && !run.informative ? (
        <p className="text-sm">
          {t("Light.validation.uninformative", { population: run.population })}
        </p>
      ) : null}
      {run.rank && run.chance_hit !== null ? (
        <p className="text-sm">
          {t("Light.validation.chance", {
            k,
            p: new Intl.NumberFormat(locale, {
              maximumFractionDigits: 3,
            }).format(run.chance_hit),
          })}
        </p>
      ) : null}
    </div>
  );
}

function CaseCard({ c, data }: { c: CaseResult; data: ValidationOut }) {
  const t = useT();
  const locale = useLocale();
  const goal = data.goals.find((g) => g.key === c.case.goal);
  const ingredient = data.ingredients[c.case.ingredient_key] ?? {
    en: c.case.ingredient_name,
  };
  const title = t("Light.validation.case", {
    ingredient: nameIn(ingredient, locale, c.case.ingredient_name),
    goal: goal ? nameIn(goal.labels, locale, goal.key) : c.case.goal,
  });
  const e = c.faers?.estimates ?? null;
  return (
    <Card as="article" aria-label={title} data-testid="validation-case">
      <h3 className="text-lg font-semibold break-words">{title}</h3>
      <p className="text-sm">
        {t("Light.validation.original", { use: c.case.original_use })}
      </p>
      <p className="text-sm">
        {t("Light.validation.year", { year: c.case.later_year })}
      </p>
      <Run
        title={t("Light.validation.primary")}
        run={c.primary}
        k={data.top_k}
      />
      <p className="text-sm">
        {t("Light.validation.variants", {
          a: rankLabel(t, c.primary_indication),
          b: rankLabel(t, c.primary_strict),
        })}
      </p>
      <p className="text-sm">
        {t("Light.validation.labels", {
          used: formatCount(c.primary_strict.labels_used, locale),
          indication: formatCount(
            c.primary_strict.labels_removed_indication,
            locale,
          ),
          missing: formatCount(
            c.primary_strict.labels_removed_not_in_openfda,
            locale,
          ),
        })}
      </p>
      <Run
        title={t("Light.validation.sensitivityRun")}
        run={c.sensitivity}
        k={data.top_k}
      />
      <p className="text-sm">
        {c.faers && e
          ? t("Light.validation.faers", {
              reports: c.faers.cells.a,
              ror: formatRatio(e.ror, locale),
              low: formatRatio(e.ror_ci.low, locale),
              high: formatRatio(e.ror_ci.high, locale),
            })
          : t("Light.validation.faersNone")}{" "}
        {t("Light.codes.faers_includes_later_use")}
      </p>
      <p className="text-sm">{c.case.note}</p>
      <p className="text-sm">
        <span className="font-semibold">
          {t("Light.validation.evidence")}:{" "}
        </span>
        {c.case.evidence_ids.map((id) => {
          const s = data.sources.find((x) => x.id === id);
          return s ? (
            <a
              data-inline="true"
              key={id}
              href={s.url}
              target="_blank"
              rel="noreferrer noopener"
              className="underline break-words"
            >
              {s.title ?? id}
            </a>
          ) : (
            <span key={id} className="mono break-words">
              {id}
            </span>
          );
        })}
      </p>
    </Card>
  );
}

export function Validation() {
  const t = useT();
  const locale = useLocale();
  const call = useCall(() => lightClient.validation(), []);
  const data = call.status === "ok" ? call.data : null;
  return (
    <LightFrame
      title={t("Light.validation.title")}
      intro={t("Light.validation.intro")}
      status={data?.status ?? null}
      snapshot={data?.snapshot ?? null}
      attribution={data?.attribution ?? []}
    >
      {call.status === "loading" ? (
        <StateView state="loading" label={t("Light.validation.loading")} />
      ) : call.status === "error" ? (
        <StateView
          state="error"
          messageKey={call.error.messageKey}
          retry={call.retry}
        />
      ) : data ? (
        <>
          <Card as="section" data-testid="validation-summary">
            <SectionTitle>{t("Light.validation.title")}</SectionTitle>
            {/* No big number here: the hit count is only honest next to its chance baseline,
                so the sentence carries both (safety audit F4). */}
            <p className="font-bold">
              {t(
                "Light.validation.summary",
                summaryValues(
                  data.primary,
                  data.cases.length,
                  data.top_k,
                  locale,
                ),
              )}
            </p>
            <p>
              {t(
                "Light.validation.sensitivity",
                summaryValues(
                  data.sensitivity,
                  data.cases.length,
                  data.top_k,
                  locale,
                ),
              )}
            </p>
            <p className="text-sm">{t("Light.codes.validation_not_blind")}</p>
            <p className="text-sm">{t("Light.ties")}</p>
            <p className="text-sm">{t("Light.validation.document")}</p>
          </Card>
          {data.cases.length === 0 ? (
            <StateView state="empty" message={t("Research.empty")} />
          ) : (
            <ol className="flex flex-col gap-3">
              {data.cases.map((c) => (
                <li key={c.case.id}>
                  <CaseCard c={c} data={data} />
                </li>
              ))}
            </ol>
          )}
        </>
      ) : null}
    </LightFrame>
  );
}
