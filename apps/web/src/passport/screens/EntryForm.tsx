"use client";
/**
 * "Add strength and form from the box" (DP21, design §6.6): controlled inputs for each recognised
 * ingredient without a published strength, and the form group when the source has none. The
 * values stay in the browser (`entries.ts`) and are sent as codes only; an amount that cannot be
 * read exactly (including "1,000" / "1.000", DP25) is refused with a message.
 */
import { useId, useState } from "react";

import { Button } from "@/components/ui";
import { useT } from "@/theme/words";

import { setEntry, type Entry } from "../entries";
import { ENTRY_BASES, strengthFromEntry, type EntryUnit } from "../entry";
import {
  FORM_GROUPS,
  type FormGroup,
  type PassportItem,
  type StrengthCode,
} from "../model";

const UNITS: EntryUnit[] = ["mg", "g", "ug", "IU"];
const field =
  "min-h-11 rounded-[var(--radius-button)] border-2 border-muted bg-surface px-3 text-fg";

/** Whether the box has values its source does not give (TİTCK, typed by name). */
export function canEnter(item: PassportItem): boolean {
  return (
    !item.homeopathic &&
    item.ingredients.some((g) => g.key) &&
    (item.ingredients.some((g) => g.key && g.strengthOrigin !== "source") ||
      item.doseForm?.origin !== "source")
  );
}

export function EntryForm({ item }: { item: PassportItem }) {
  const t = useT();
  const id = useId();
  const lines = item.ingredients.filter(
    (g) => g.key && g.strengthOrigin !== "source",
  );
  const [values, setValues] = useState(() =>
    Object.fromEntries(
      lines.map((g) => [g.key!, { amount: "", unit: "mg", basis: "unit" }]),
    ),
  );
  const askForm = item.doseForm?.origin !== "source";
  const [form, setForm] = useState<FormGroup | "">(item.doseForm?.group ?? "");
  const [invalid, setInvalid] = useState(false);
  const save = () => {
    const strengths: Record<string, StrengthCode> = {};
    for (const [key, v] of Object.entries(values)) {
      if (!v.amount.trim()) continue;
      const code = strengthFromEntry(v.amount, v.unit, v.basis);
      if (!code) return setInvalid(true);
      strengths[key] = code;
    }
    setInvalid(false);
    const entry: Entry = { strengths, form: askForm && form ? form : null };
    setEntry(item.id, entry);
  };
  return (
    <fieldset className="card flex flex-col gap-4 p-4">
      <legend className="px-1 font-bold">{t("Passport.entry.title")}</legend>
      <p className="text-sm text-muted">{t("Passport.entry.hint")}</p>
      {lines.map((g) => {
        const v = values[g.key!]!;
        const set = (patch: Partial<typeof v>) =>
          setValues((x) => ({ ...x, [g.key!]: { ...v, ...patch } }));
        return (
          <div key={g.key} className="flex flex-col gap-2">
            <p className="font-bold">
              {t("Passport.entry.ingredient", { ingredient: g.label })}
            </p>
            <div className="flex flex-wrap gap-3">
              <label className="flex flex-col gap-1">
                <span>{t("Passport.entry.amount")}</span>
                <input
                  inputMode="decimal"
                  value={v.amount}
                  onChange={(e) => set({ amount: e.target.value })}
                  aria-describedby={`${id}-hint`}
                  className={`${field} w-32`}
                />
              </label>
              <label className="flex flex-col gap-1">
                <span>{t("Passport.entry.unit")}</span>
                <select
                  value={v.unit}
                  onChange={(e) => set({ unit: e.target.value })}
                  className={field}
                >
                  {UNITS.map((u) => (
                    <option key={u} value={u}>
                      {t(`Passport.unit.${u}`)}
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex flex-col gap-1">
                <span>{t("Passport.entry.basis")}</span>
                <select
                  value={v.basis}
                  onChange={(e) => set({ basis: e.target.value })}
                  className={field}
                >
                  {ENTRY_BASES.map((b) => (
                    <option key={b} value={b}>
                      {t(`Passport.basis.${b}`)}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          </div>
        );
      })}
      <p id={`${id}-hint`} className="text-sm text-muted">
        {t("Passport.entry.amountHint")}
      </p>
      {askForm ? (
        <label className="flex flex-col gap-1">
          <span className="font-bold">{t("Passport.entry.form")}</span>
          <select
            value={form}
            onChange={(e) => setForm(e.target.value as FormGroup | "")}
            className={field}
          >
            <option value="">{t("Passport.entry.formNone")}</option>
            {FORM_GROUPS.map((g) => (
              <option key={g} value={g}>
                {t(`Passport.form.${g}`)}
              </option>
            ))}
          </select>
        </label>
      ) : null}
      {invalid ? (
        <p role="alert" className="font-bold">
          {t("Passport.entry.invalid")}
        </p>
      ) : null}
      <div className="flex flex-wrap gap-3">
        <Button onClick={save}>{t("Passport.entry.save")}</Button>
        <Button variant="quiet" onClick={() => setEntry(item.id, null)}>
          {t("Passport.entry.clear")}
        </Button>
      </div>
    </fieldset>
  );
}
