"use client";
/**
 * Hypothesis cards (light-face design §10, Req 4): a condition picker (radio group, keyboard),
 * the ranked cards of that condition (20 at a time), the inverse-signal context, the warnings and
 * the patient-reported entries without a card. Loading, empty, error and long-content states.
 */
import { useLocale } from "next-intl";
import { useState } from "react";

import { SegmentedControl, StatTile } from "@/components/cards";
import { StateView } from "@/components/StateView";
import { Button, Card, SectionTitle } from "@/components/ui";
import { formatCount, formatRatio } from "@/components/format";
import { useCall } from "@/flow/useCall";
import { lightClient } from "@/light/client";
import type { Card as CardData, CardsOut, GoalSummary } from "@/light/model";
import { nameIn } from "@/light/view";
import { liveSeance } from "@/seance/client";
import type { CatalogueOut } from "@/seance/model";
import { useT } from "@/theme/words";

import { CardView } from "./CardView";
import { LightFrame } from "./LightFrame";

const PAGE = 20;

function GoalPicker({
  goals,
  value,
  onChange,
}: {
  goals: GoalSummary[];
  value: string;
  onChange: (k: string) => void;
}) {
  const t = useT();
  const locale = useLocale();
  // Many conditions with long names: the pills variant of the segmented control (DP52).
  return (
    <SegmentedControl
      legend={t("Light.hypotheses.goal")}
      legendVisible
      name="goal"
      variant="pills"
      value={value}
      onChange={onChange}
      options={goals.map((g) => ({
        value: g.key,
        label: (
          <>
            {nameIn(g.labels, locale, g.key)}{" "}
            <span className="text-sm font-normal">
              ({t("Light.hypotheses.goalCount", { count: g.candidates })})
            </span>
          </>
        ),
      }))}
    />
  );
}

function CardsPanel({
  goal,
  summary,
  seance,
}: {
  goal: string;
  summary: GoalSummary;
  seance: CatalogueOut | null;
}) {
  const t = useT();
  const locale = useLocale();
  const [extra, setExtra] = useState<CardData[]>([]);
  const [more, setMore] = useState<{ loading: boolean; error: string | null }>({
    loading: false,
    error: null,
  });
  const call = useCall<CardsOut>(
    () => lightClient.cards(goal, 0, PAGE),
    [goal],
  );
  if (call.status === "loading")
    return <StateView state="loading" label={t("Light.hypotheses.loading")} />;
  if (call.status === "error")
    return (
      <StateView
        state="error"
        messageKey={call.error.messageKey}
        retry={call.retry}
      />
    );
  if (call.status !== "ok") return null;
  const d = call.data;
  const cards = [...d.cards, ...extra];
  const goalName = nameIn(d.goal.labels, locale, d.goal.key);
  const loadMore = async () => {
    setMore({ loading: true, error: null });
    const r = await lightClient.cards(goal, cards.length, PAGE);
    if (r.ok) {
      setExtra((x) => [...x, ...r.data.cards]);
      setMore({ loading: false, error: null });
    } else setMore({ loading: false, error: r.error.messageKey });
  };
  return (
    <section className="flex flex-col gap-3" aria-live="polite">
      <div className="flex flex-wrap items-center gap-4">
        <StatTile
          value={formatCount(d.total, locale)}
          label={t("Cards.label.cards", { count: d.total })}
          className="min-w-[9rem]"
        />
        <SectionTitle>
          {/* The tile shows the total; the heading keeps the sentence for screen readers. */}
          <span className="sr-only">
            {t("Light.hypotheses.total", { total: d.total, goal: goalName })}
          </span>
          <span aria-hidden>{goalName}</span>
        </SectionTitle>
      </div>
      <p className="text-sm">{t("Light.ties")}</p>
      {summary.inverse_tested ? (
        <p className="text-sm">
          {t("Light.hypotheses.inverseCount", {
            found: formatCount(summary.inverse_found, locale),
            tested: formatCount(summary.inverse_tested, locale),
            chance: formatRatio(summary.inverse_expected_by_chance, locale),
          })}
        </p>
      ) : null}
      {d.removed_by_integrity ? (
        <p className="text-sm">
          {t("Light.hypotheses.removed", { count: d.removed_by_integrity })}
        </p>
      ) : null}
      <p className="text-sm">{t("Light.notChecked")}</p>
      {cards.length === 0 ? (
        <StateView state="empty" message={t("Light.hypotheses.empty")} />
      ) : (
        <ol className="flex flex-col gap-3">
          {cards.map((c) => (
            <li key={c.ingredient.key}>
              <CardView card={c} snapshot={d.snapshot} seance={seance} />
            </li>
          ))}
        </ol>
      )}
      {cards.length < d.total ? (
        <div className="flex flex-col items-start gap-2">
          <p className="text-sm">
            {t("Light.hypotheses.shown", {
              shown: cards.length,
              total: d.total,
            })}
          </p>
          <Button
            variant="secondary"
            onClick={loadMore}
            disabled={more.loading}
          >
            {more.loading
              ? t("Common.loading")
              : t("Light.hypotheses.showMore")}
          </Button>
          {more.error ? <p role="alert">{t(more.error)}</p> : null}
        </div>
      ) : null}
      {d.patient_layer === "layer_unavailable" ? (
        <p className="text-sm">{t("Light.codes.patient_layer_unavailable")}</p>
      ) : null}
      {d.patient_reported.length ? (
        <Card as="section">
          <h3 className="font-semibold">{t("Light.hypotheses.patientOnly")}</h3>
          <p className="text-sm">{t("Light.hypotheses.patientOnlyNote")}</p>
          <ul className="flex flex-col gap-1">
            {d.patient_reported.map((p) => (
              <li key={`${p.ingredient.key}-${p.signal.event}`}>
                {nameIn(p.ingredient.labels, locale, p.ingredient.key)}:{" "}
                {t("Light.card.patientReleased", {
                  value: formatCount(p.signal.total_of_released, locale),
                })}
              </li>
            ))}
          </ul>
          <p className="text-sm">{t("Light.codes.patient_reported_meaning")}</p>
        </Card>
      ) : null}
    </section>
  );
}

export function Hypotheses() {
  const t = useT();
  const ov = useCall(() => lightClient.overview(), []);
  // The séance catalogue, for the cross-reference on a card; without it the cards show none.
  const seance = useCall(() => liveSeance.catalogue(), []);
  const [goal, setGoal] = useState<string | null>(null);
  const data = ov.status === "ok" ? ov.data : null;
  const goals = data ? data.goals.filter((g) => g.candidates > 0) : [];
  const chosen = goal ?? goals[0]?.key ?? null;
  const summary = goals.find((g) => g.key === chosen);
  return (
    <LightFrame
      title={t("Light.hypotheses.title")}
      intro={t("Light.hypotheses.intro")}
      status={data?.status ?? null}
      snapshot={data?.snapshot ?? null}
      attribution={data?.attribution ?? []}
    >
      {ov.status === "loading" ? (
        <StateView state="loading" label={t("Light.hypotheses.loading")} />
      ) : ov.status === "error" ? (
        <StateView
          state="error"
          messageKey={ov.error.messageKey}
          retry={ov.retry}
        />
      ) : chosen && summary ? (
        <>
          <GoalPicker goals={goals} value={chosen} onChange={setGoal} />
          <CardsPanel
            key={chosen}
            goal={chosen}
            summary={summary}
            seance={seance.status === "ok" ? seance.data : null}
          />
        </>
      ) : (
        <StateView state="empty" message={t("Light.hypotheses.empty")} />
      )}
    </LightFrame>
  );
}
