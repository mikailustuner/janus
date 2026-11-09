"use client";
/**
 * One box in other countries' data (design §8 "Item detail", Req 2, 7, 8.3, 10.2–10.5). The box
 * is named by the URL fragment (`/passport/item#<id>`), so nothing about it reaches a path. States:
 * loading (`aria-busy`, a polite announcement when done), error with retry (never "not found"),
 * partial (unavailable sources say why), not checkable (the reason, no rows).
 */
import { useLocale } from "next-intl";
import { useEffect, useState } from "react";

import { StateView } from "@/components/StateView";
import {
  BackLink,
  GroupedList,
  LargeTitle,
  Row,
  SegmentedControl,
} from "@/components/cards";
import { Button, ButtonLink } from "@/components/ui";
import { useT, type Translate } from "@/theme/words";

import type { PresenceView } from "./usePassport";
import { usePassport, usePresence } from "./usePassport";
import type { PassportItem } from "../model";
import { notSentReason } from "../request";
import { presenceSummary } from "../summary";
import { EntryForm, canEnter } from "./EntryForm";
import {
  enteredForm,
  enteredStrength,
  PresenceRows,
  type RowsView,
  strengthText,
} from "./PresenceRows";

function useHashId(): string | null | undefined {
  const [id, setId] = useState<string | null | undefined>(undefined);
  useEffect(() => {
    const read = () =>
      setId(decodeURIComponent(location.hash.slice(1)) || null);
    read();
    window.addEventListener("hashchange", read);
    return () => window.removeEventListener("hashchange", read);
  }, []);
  return id;
}

export function boxValues(
  t: Translate,
  item: PassportItem,
  locale: string,
): string {
  const parts = [
    strengthText(t, item, locale),
    item.doseForm ? t(`Passport.form.${item.doseForm.group}`) : null,
  ]
    .filter(Boolean)
    .join(" · ");
  if (!parts) return t("Passport.detail.boxValuesNone");
  const entered = enteredStrength(item) || enteredForm(item);
  return (
    t("Passport.detail.boxValues", { values: parts }) +
    (entered ? ` (${t("Passport.entered")})` : "")
  );
}

/** The body of the detail screen for one box and one presence state (also used by tests). */
export function PassportItemBody({
  item,
  presence,
  editable,
  retry,
}: {
  item: PassportItem;
  presence: PresenceView;
  /** False for the read-only demo lists. */
  editable: boolean;
  retry: () => void;
}) {
  const t = useT();
  const locale = useLocale();
  const [editing, setEditing] = useState(false);
  const [view, setView] = useState<RowsView>("countries");
  const reason = notSentReason(item);
  const answer =
    presence.status === "ok" ? presence.answers.get(item.id) : undefined;
  const announce =
    presence.status === "ok" && answer
      ? t("Passport.states.loaded", {
          count: answer.sources.filter((s) => s.status === "loaded").length,
        })
      : "";
  const summary = answer && !reason ? presenceSummary(answer.item) : null;
  const comparable = !!answer?.item.answers.some((a) => a.comparison);
  return (
    <>
      <BackLink href="/passport">{t("Passport.title")}</BackLink>
      <LargeTitle
        eyebrow={t(
          `Passport.origin.${item.origin.country ?? item.origin.region}`,
        )}
        title={<span className="[overflow-wrap:anywhere]">{item.boxName}</span>}
        summary={
          summary ? t("Cards.passport.listed", { ...summary }) : undefined
        }
      />
      <p role="status" aria-live="polite" className="sr-only">
        {announce}
      </p>
      {/* Desktop (Req 27): the rows beside an aside with the box and the notes. */}
      <div className="grid gap-group lg:grid-cols-[minmax(0,1fr)_minmax(280px,340px)] lg:items-start">
        <div className="flex min-w-0 flex-col gap-group">
          {/* This box's own values come first: what the comparisons are made with. */}
          <GroupedList>
            <Row>
              <p>{boxValues(t, item, locale)}</p>
              {editable && canEnter(item) ? (
                editing ? (
                  <EntryForm item={item} />
                ) : (
                  <Button
                    variant="secondary"
                    className="mt-2 w-fit"
                    onClick={() => setEditing(true)}
                  >
                    {t("Passport.entry.open")}
                  </Button>
                )
              ) : null}
            </Row>
          </GroupedList>
          <h2 className="sr-only">{t("Passport.detail.title")}</h2>
          {reason === "homeopathic" ? (
            <p className="card p-5 font-bold">{t("Passport.homeopathic")}</p>
          ) : reason ? (
            <p className="card p-5 font-bold">
              {t(`Passport.notCheckable.${reason}`)}
            </p>
          ) : presence.status === "loading" ? (
            <div aria-busy="true" className="card flex flex-col gap-3 p-5">
              <p>{t("Passport.states.loading")}</p>
              {[0, 1, 2].map((i) => (
                <div
                  key={i}
                  className="h-3 w-2/3 animate-pulse rounded-full bg-chip"
                />
              ))}
            </div>
          ) : presence.status === "error" || !answer ? (
            <StateView
              state="error"
              messageKey="Passport.states.error"
              retry={retry}
            />
          ) : (
            <>
              {comparable ? (
                <SegmentedControl
                  legend={t("Cards.show")}
                  name="presence-view"
                  value={view}
                  onChange={setView}
                  options={[
                    {
                      value: "countries",
                      label: t("Cards.passport.countries"),
                    },
                    {
                      value: "comparison",
                      label: t("Cards.passport.comparison"),
                    },
                  ]}
                />
              ) : null}
              {answer.sources.some((s) => s.reason === "not_loaded") ? (
                <p className="card p-4">{t("Passport.states.partial")}</p>
              ) : null}
              <PresenceRows
                item={item}
                out={answer.item}
                sources={answer.sources}
                view={view}
              />
              {presence.recordedOn ? (
                <p className="group-footer">
                  {t("Passport.states.recorded", { date: presence.recordedOn })}
                </p>
              ) : null}
            </>
          )}
        </div>
        <aside className="flex min-w-0 flex-col gap-group lg:sticky lg:top-4">
          {presence.status === "ok" && answer && !reason ? (
            <ul className="grouped text-sm">
              {answer.notices
                .filter(
                  (n) =>
                    n !== "unknown_ingredient_keys" ||
                    answer.item.unknown_keys.length > 0,
                )
                .map((n) => (
                  <li key={n}>{t(`Passport.notice.${n}`)}</li>
                ))}
              {answer.item.answers.some((a) => a.status === "present") ? (
                <li>{t("Passport.presentNote")}</li>
              ) : null}
            </ul>
          ) : null}
          <p className="card p-5 font-bold">{t("Passport.listingsOnly")}</p>
        </aside>
      </div>
    </>
  );
}

export function PassportItemView() {
  const t = useT();
  const view = usePassport();
  const id = useHashId();
  const presence = usePresence(view.items, view.ready, view.demo);
  if (!view.ready || id === undefined) return <StateView state="loading" />;
  const merged = id ? (view.resolveId(id) ?? id) : null;
  const item = view.items.find((i) => i.id === merged);
  if (!item)
    return (
      <StateView
        state="empty"
        message={t("Passport.detail.title")}
        action={<ButtonLink href="/passport">{t("Passport.back")}</ButtonLink>}
      />
    );
  return (
    <PassportItemBody
      item={item}
      presence={presence}
      editable={!view.readOnly}
      retry={presence.retry}
    />
  );
}
