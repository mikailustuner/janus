"use client";
/**
 * "Since when?" (Req 13.1): month names of the locale, a year, or "don't know"; a month later
 * than the current one is refused. Returns `YYYY-MM` or null through `monthInput` (P3).
 */
import { useLocale } from "next-intl";
import { useId, useMemo, useState } from "react";

import { monthInput } from "@/flow/evaluate";
import { useT } from "@/theme/words";

export function MonthPicker({
  value,
  onChange,
  legend,
}: {
  value: string | null;
  onChange: (started: string | null) => void;
  /** Another question than "Since when?" (report-assistant: "When did it start?"). */
  legend?: string;
}) {
  const t = useT();
  const locale = useLocale();
  const id = useId();
  const now = new Date();
  const [year, setYear] = useState(
    value ? Number(value.slice(0, 4)) : now.getFullYear(),
  );
  const [month, setMonth] = useState(
    value ? Number(value.slice(5, 7)) : now.getMonth() + 1,
  );
  const [dontKnow, setDontKnow] = useState(value === null);
  const [error, setError] = useState(false);
  const months = useMemo(
    () =>
      Array.from({ length: 12 }, (_, i) =>
        new Intl.DateTimeFormat(locale, {
          month: "long",
          timeZone: "UTC",
        }).format(Date.UTC(2020, i, 1)),
      ),
    [locale],
  );
  const years = Array.from(
    { length: now.getFullYear() - 1949 },
    (_, i) => now.getFullYear() - i,
  );

  const emit = (next: { dontKnow: boolean; year: number; month: number }) => {
    const r = next.dontKnow
      ? monthInput({ dontKnow: true })
      : monthInput({ dontKnow: false, year: next.year, month: next.month });
    setError(!r.ok);
    if (r.ok) onChange(r.started);
  };

  return (
    <fieldset className="flex flex-col gap-2">
      <legend className="mb-1 font-bold">{legend ?? t("Month.label")}</legend>
      <div className="flex flex-wrap gap-2">
        <label className="flex flex-col text-sm" htmlFor={`${id}-m`}>
          {t("Month.month")}
          <select
            id={`${id}-m`}
            disabled={dontKnow}
            value={month}
            onChange={(e) => {
              setMonth(Number(e.target.value));
              emit({ dontKnow, year, month: Number(e.target.value) });
            }}
            className="min-h-11 rounded-[var(--radius-button)] border-2 border-muted bg-surface px-2 text-base text-fg"
          >
            {months.map((m, i) => (
              <option key={m} value={i + 1} className="bg-bg text-fg">
                {m}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col text-sm" htmlFor={`${id}-y`}>
          {t("Month.year")}
          <select
            id={`${id}-y`}
            disabled={dontKnow}
            value={year}
            onChange={(e) => {
              setYear(Number(e.target.value));
              emit({ dontKnow, year: Number(e.target.value), month });
            }}
            className="min-h-11 rounded-[var(--radius-button)] border-2 border-muted bg-surface px-2 text-base text-fg"
          >
            {years.map((y) => (
              <option key={y} value={y} className="bg-bg text-fg">
                {y}
              </option>
            ))}
          </select>
        </label>
      </div>
      <label className="flex min-h-11 items-center gap-3">
        <input
          type="checkbox"
          checked={dontKnow}
          onChange={(e) => {
            setDontKnow(e.target.checked);
            emit({ dontKnow: e.target.checked, year, month });
          }}
          className="size-5 accent-[var(--accent)]"
        />
        {t("Month.dontKnow")}
      </label>
      {error ? (
        <p role="alert" className="font-bold text-warn">
          {t("Month.future")}
        </p>
      ) : null}
    </fieldset>
  );
}
