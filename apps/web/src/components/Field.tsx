"use client";
/** Form fields: a radio group and a switch, each with a visible label and 44 px targets. */
import { useId, type ReactNode } from "react";

export function RadioGroup<T extends string>({
  legend,
  hint,
  name,
  value,
  options,
  onChange,
}: {
  legend: ReactNode;
  hint?: ReactNode;
  name: string;
  value: T;
  options: { value: T; label: ReactNode; hint?: ReactNode }[];
  onChange: (v: T) => void;
}) {
  const hintId = useId();
  return (
    <fieldset
      className="flex flex-col gap-1"
      aria-describedby={hint ? hintId : undefined}
    >
      <legend className="mb-1 font-bold">{legend}</legend>
      {hint ? (
        <p id={hintId} className="mb-1 text-sm text-muted">
          {hint}
        </p>
      ) : null}
      {options.map((o) => (
        <label
          key={o.value}
          className="flex min-h-11 cursor-pointer items-center gap-3 rounded-[var(--radius-button)] px-2 hover:bg-chip"
        >
          <input
            type="radio"
            name={name}
            value={o.value}
            checked={value === o.value}
            onChange={() => onChange(o.value)}
            className="size-5 shrink-0 accent-[var(--accent)]"
          />
          <span className="flex flex-col">
            <span>{o.label}</span>
            {o.hint ? (
              <span className="text-sm text-muted">{o.hint}</span>
            ) : null}
          </span>
        </label>
      ))}
    </fieldset>
  );
}

export function Switch({
  label,
  hint,
  checked,
  onChange,
}: {
  label: ReactNode;
  hint?: ReactNode;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label className="flex min-h-11 cursor-pointer items-center justify-between gap-3 rounded-[var(--radius-button)] px-2 hover:bg-chip">
      <span className="flex flex-col">
        <span className="font-bold">{label}</span>
        {hint ? <span className="text-sm text-muted">{hint}</span> : null}
      </span>
      <input
        type="checkbox"
        role="switch"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="size-6 shrink-0 cursor-pointer accent-[var(--accent)]"
      />
    </label>
  );
}

export function SelectField<T extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label: ReactNode;
  value: T;
  options: { value: T; label: string; lang?: string }[];
  onChange: (v: T) => void;
}) {
  const id = useId();
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="font-bold">
        {label}
      </label>
      <select
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value as T)}
        className="min-h-11 rounded-[var(--radius-button)] border-2 border-muted bg-surface px-3 text-fg"
      >
        {options.map((o) => (
          <option
            key={o.value}
            value={o.value}
            lang={o.lang}
            className="bg-bg text-fg"
          >
            {o.label}
          </option>
        ))}
      </select>
    </div>
  );
}
