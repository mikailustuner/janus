"use client";
/**
 * The doctor's form (design §11, Req 19.2–19.5, 19.8): one card per finding with the API's texts
 * exactly as returned, the assessment, an optional action and, when the action needs it, which
 * medicine it concerns. Send is enabled with at least one answer; after success the form is
 * disabled. No advice: it asks what was done. Plain props, no app providers (the page is small).
 */
import { useState } from "react";

import type { OutcomeFormOut } from "@/api/contracts";

import { buildAnswers, canSend, NEEDS_MEDICINE, type Answer } from "./doctor";
import type { DoctorMessages } from "./messages";

const plural = (template: string, count: number) =>
  template.replace(
    /\{count, plural, one \{([^}]*)\} other \{([^}]*)\}\}/,
    (_, one: string, other: string) =>
      (count === 1 ? one : other).replace("#", String(count)),
  );

export function DoctorForm({
  form,
  m,
  demo,
  onSend,
}: {
  form: OutcomeFormOut;
  m: DoctorMessages;
  demo: boolean;
  onSend:
    | ((
        answers: NonNullable<ReturnType<typeof buildAnswers>>,
      ) => Promise<{ stored: number } | { error: string }>)
    | null;
}) {
  const [state, setState] = useState<Record<number, Answer>>({});
  const [phase, setPhase] = useState<
    | { s: "edit" }
    | { s: "sending" }
    | { s: "sent"; n: number }
    | { s: "error"; text: string }
  >({ s: "edit" });
  const set = (ref: number, patch: Partial<Answer>) =>
    setState((s) => ({ ...s, [ref]: { ...s[ref], ...patch } }));
  const locked = phase.s === "sending" || phase.s === "sent";
  const ok = canSend(form, state);

  return (
    <form
      lang={form.language}
      className="flex flex-col gap-5"
      onSubmit={async (e) => {
        e.preventDefault();
        const answers = buildAnswers(form, state);
        if (!answers || answers.length === 0 || !onSend) return;
        setPhase({ s: "sending" });
        const r = await onSend(answers);
        setPhase(
          "stored" in r
            ? { s: "sent", n: r.stored }
            : { s: "error", text: r.error },
        );
      }}
    >
      <header className="flex flex-col gap-2">
        {demo ? <p className="chip">{m.demo}</p> : null}
        <h1 className="text-2xl font-semibold">{form.texts.heading}</h1>
        <p>{form.texts.intro}</p>
      </header>
      {form.findings.map((f) => {
        const a = state[f.ref] ?? {};
        return (
          <fieldset
            key={f.ref}
            disabled={locked}
            className="card flex flex-col gap-3 p-4"
          >
            <legend className="sr-only">
              {f.cascade.drug_a} → {f.cascade.adverse_event} →{" "}
              {f.cascade.drug_b}
            </legend>
            <p className="font-bold">
              {f.cascade.drug_a} → {f.cascade.adverse_event} →{" "}
              {f.cascade.drug_b}
            </p>
            {[f.index, f.marker].map((x, i) => (
              <p key={i} className="text-sm">
                <span className="text-muted">
                  {i === 0 ? m.first : m.second}:{" "}
                </span>
                {x.name}
                {x.tag ? <span className="text-muted"> ({x.tag})</span> : null}
                {x.atc.length ? (
                  <span className="mono"> {x.atc.join(", ")}</span>
                ) : null}
              </p>
            ))}
            {!f.form_confirmed ? (
              <p className="text-sm text-muted">{m.notConfirmed}</p>
            ) : null}
            <div
              role="radiogroup"
              aria-label={form.texts.question_assessment}
              className="flex flex-col gap-1"
            >
              <p className="font-bold">{form.texts.question_assessment}</p>
              {form.options.assessment.map((o) => (
                <label
                  key={o.code}
                  className="flex min-h-11 items-center gap-3"
                >
                  <input
                    type="radio"
                    name={`a-${f.ref}`}
                    checked={a.assessment === o.code}
                    onChange={() =>
                      set(f.ref, { assessment: o.code as Answer["assessment"] })
                    }
                    className="size-5 accent-[var(--accent)]"
                  />
                  {o.text}
                </label>
              ))}
            </div>
            <div
              role="radiogroup"
              aria-label={form.texts.question_action}
              className="flex flex-col gap-1"
            >
              <p className="font-bold">{form.texts.question_action}</p>
              {form.options.action.map((o) => (
                <label
                  key={o.code}
                  className="flex min-h-11 items-center gap-3"
                >
                  <input
                    type="radio"
                    name={`x-${f.ref}`}
                    checked={a.action === o.code}
                    onChange={() =>
                      set(f.ref, {
                        action: o.code as Answer["action"],
                        actionOn: undefined,
                      })
                    }
                    className="size-5 accent-[var(--accent)]"
                  />
                  {o.text}
                </label>
              ))}
            </div>
            {a.action && NEEDS_MEDICINE.has(a.action) ? (
              <div
                role="radiogroup"
                aria-label={m.medicineQuestion}
                className="flex flex-col gap-1"
              >
                <p className="font-bold">{m.medicineQuestion}</p>
                {f.action_on.map((o) => (
                  <label
                    key={o.code}
                    className="flex min-h-11 items-center gap-3"
                  >
                    <input
                      type="radio"
                      name={`o-${f.ref}`}
                      checked={a.actionOn === o.code}
                      onChange={() =>
                        set(f.ref, { actionOn: o.code as Answer["actionOn"] })
                      }
                      className="size-5 accent-[var(--accent)]"
                    />
                    {o.text}
                  </label>
                ))}
              </div>
            ) : null}
          </fieldset>
        );
      })}
      <section className="flex flex-col gap-2 text-sm">
        <p>{form.texts.stored_fields}</p>
        <p>{form.texts.limits}</p>
      </section>
      {phase.s === "sent" ? (
        <p
          role="status"
          className="card p-4 font-bold"
          data-testid="doctor-sent"
        >
          {plural(m.sent, phase.n)}
        </p>
      ) : (
        <>
          {!ok ? <p className="text-sm text-muted">{m.noAnswer}</p> : null}
          <button
            type="submit"
            disabled={!ok || locked || !onSend}
            className="min-h-11 self-start rounded-[var(--radius-button)] bg-accent px-5 font-bold text-on-accent disabled:opacity-60"
          >
            {phase.s === "sending"
              ? m.sending
              : phase.s === "error"
                ? m.retry
                : m.send}
          </button>
        </>
      )}
      {phase.s === "error" ? <p role="alert">{phase.text}</p> : null}
      <p className="border-t border-line pt-3 text-sm text-muted">
        {form.texts.disclaimer}
      </p>
    </form>
  );
}
