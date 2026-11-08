"use client";
/**
 * The doctor QR page `/o` (design §11, DP19, Req 19, 25.1): no account, the token read from the
 * fragment and held in memory only, the form texts from the API in the note's language, errors
 * in the note's language when known, else the browser's. A `demo-` fragment shows the recorded
 * demo form and sends nothing.
 */
import { useEffect, useRef, useState } from "react";

import type { OutcomeFormOut } from "@/api/contracts";
import * as D from "@/api/decode";

import { doctorSession } from "./doctor";
import { DoctorForm } from "./DoctorForm";
import { browserLang, DOCTOR_MESSAGES, type Lang } from "./messages";

type View =
  | { s: "loading" }
  | { s: "error"; key: string }
  | { s: "form"; form: OutcomeFormOut; demo: boolean };

const ERROR_KEYS = [
  "invalid_token",
  "token_expired",
  "token_not_usable",
  "token_used",
  "unavailable",
] as const;

export function DoctorPage() {
  const [lang, setLang] = useState<Lang>("en");
  const [view, setView] = useState<View>({ s: "loading" });
  const session = useRef<ReturnType<typeof doctorSession> | null>(null);

  useEffect(() => {
    const s = doctorSession(location.hash, (u, i) => fetch(u, i));
    session.current = s;
    let live = true;
    const fallback = browserLang(navigator.languages ?? [navigator.language]);
    queueMicrotask(() => live && setLang(fallback));
    if (s.fragment.kind === "demo") {
      const patient = s.fragment.patient as "istanbul" | "cologne" | "ohio";
      const load = {
        istanbul: () => import("@/demo/fixtures/istanbul.json"),
        cologne: () => import("@/demo/fixtures/cologne.json"),
        ohio: () => import("@/demo/fixtures/ohio.json"),
      }[patient];
      load().then((m) => {
        const r = D.decode(
          D.outcomeFormOut,
          (m.default as { doctorForm: unknown }).doctorForm,
        );
        if (!live) return;
        if (r.ok) {
          setLang(r.value.language);
          setView({ s: "form", form: r.value, demo: true });
        } else setView({ s: "error", key: "unavailable" });
      });
    } else if (s.fragment.kind === "invalid") {
      queueMicrotask(
        () => live && setView({ s: "error", key: "invalid_token" }),
      );
    } else {
      s.form()!.then((r) => {
        if (!live) return;
        if (r.ok) {
          setLang(r.data.language);
          setView({ s: "form", form: r.data, demo: false });
          return;
        }
        const code = r.error.kind === "http" ? r.error.code : null;
        setView({
          s: "error",
          key: (ERROR_KEYS as readonly string[]).includes(code ?? "")
            ? code!
            : r.error.kind === "http" && r.error.status === 503
              ? "unavailable"
              : r.error.kind === "network" || r.error.kind === "timeout"
                ? "network"
                : "unavailable",
        });
      });
    }
    return () => {
      live = false;
    };
  }, []);

  useEffect(() => {
    document.documentElement.lang = lang;
    if (view.s === "form") performance.mark("janus:form-ready");
  }, [lang, view.s]);

  const m = DOCTOR_MESSAGES[lang];
  return (
    <main className="mx-auto flex w-full max-w-[720px] flex-col gap-4 px-4 py-6">
      <p className="font-display text-lg font-semibold">{m.title}</p>
      {view.s === "loading" ? (
        <p role="status" aria-busy="true">
          {m.loading}
        </p>
      ) : view.s === "error" ? (
        <p role="alert" className="card p-4">
          {view.key === "network"
            ? m.network
            : m.errors[view.key as (typeof ERROR_KEYS)[number]]}
        </p>
      ) : (
        <DoctorForm
          form={view.form}
          m={m}
          demo={view.demo}
          onSend={
            view.demo
              ? null
              : async (answers) => {
                  const r = await session.current!.send(answers)!;
                  if (r.ok) return { stored: r.data.stored };
                  if (r.error.kind === "network" || r.error.kind === "timeout")
                    return { error: m.network };
                  const code = r.error.kind === "http" ? r.error.code : null;
                  return {
                    error:
                      m.errors[
                        (ERROR_KEYS as readonly string[]).includes(code ?? "")
                          ? (code as (typeof ERROR_KEYS)[number])
                          : "unavailable"
                      ],
                  };
                }
          }
        />
      )}
      {view.s !== "form" ? (
        <p className="border-t border-line pt-3 text-sm text-muted">
          {m.disclaimer}
        </p>
      ) : null}
    </main>
  );
}
