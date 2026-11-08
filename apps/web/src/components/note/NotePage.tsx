"use client";
/**
 * The doctor note (design §9, §10, Req 17): note language (and the patient's language for the
 * side-by-side view), `POST /notes/document` with the pins of the results the patient saw, a
 * preview on light-face paper, and a PDF made in the browser. Box names are filled in here only.
 */
import { useLocale } from "next-intl";
import { useState } from "react";

import { parseLocator } from "@/flow/locator";
import { QUIET, type Qr } from "@/note/qr";

import { QrOptIn } from "./QrOptIn";

import { noteBody, pinsIn } from "@/api/builders";
import type { Locale, NoteOut } from "@/api/contracts";
import type { ApiError } from "@/api/errors";
import { SelectField } from "@/components/Field";
import { DownloadIcon, PrintIcon } from "@/components/icons";
import { StateView } from "@/components/StateView";
import {
  Button,
  ButtonLink,
  Card,
  PageTitle,
  SectionTitle,
} from "@/components/ui";
import { PATIENT_FACTS } from "@/demo/patients";
import { useUserRegion } from "@/components/region";
import { resultCache, useSession } from "@/flow/janus";
import { useCall } from "@/flow/useCall";
import { useEvaluation } from "@/flow/useEvaluation";
import { localeNames, routing } from "@/i18n/routing";
import {
  layout as layoutNote,
  paperFor,
  pdfFileName,
  type LaidBlock,
  type LaidDocument,
  type NoteLayout,
} from "@/note/layout";
import { useSettings } from "@/store/hooks";
import { useT } from "@/theme/words";

function BlockView({ b, t }: { b: LaidBlock; t: ReturnType<typeof useT> }) {
  if (b.kind === "sentence") return <p>{b.text}</p>;
  if (b.kind === "stat")
    return (
      <div className="flex flex-col gap-1 border-t border-line pt-2">
        {b.sentences.map((x) => (
          <p key={x.id}>{x.text}</p>
        ))}
        {b.pts ? <p className="text-sm text-muted">{b.pts}</p> : null}
      </div>
    );
  return (
    <div
      className="flex flex-col gap-0.5 border-t border-line pt-2"
      data-testid="note-medicine"
    >
      <p>
        <span className="text-muted">{b.productLabel}: </span>
        <span className="font-bold">
          {b.productName ?? t("Note.productNotKnown")}
        </span>
      </p>
      {b.ingredients.map((i) => (
        <p key={i.key}>
          {i.name ?? i.key}
          {i.tag ? (
            <span className="text-sm text-muted"> ({i.tag})</span>
          ) : null}
          {i.atc.length ? (
            <span className="mono text-sm"> {i.atc.join(", ")}</span>
          ) : null}
          {i.combinationCode ? (
            <span className="text-sm text-muted"> ({i.combinationCode})</span>
          ) : null}
        </p>
      ))}
      {b.notChecked.map((n) => (
        <p key={n} className="text-sm">
          {n}
        </p>
      ))}
      <p className="text-sm text-muted">{b.started}</p>
      {b.abruptStop ? (
        <p className="font-bold text-warn">{b.abruptStop}</p>
      ) : null}
    </div>
  );
}

function QrImage({ qr, label }: { qr: Qr; label: string }) {
  const side = qr.size + 2 * QUIET;
  // 50 mm at the CSS reference of 96 px per inch (Req 18.2); the PDF draws it at 50 mm too.
  return (
    <svg
      viewBox={`0 0 ${side} ${side}`}
      width="189"
      height="189"
      role="img"
      aria-label={label}
      shapeRendering="crispEdges"
      data-testid="note-qr"
    >
      <rect width={side} height={side} fill="var(--on-accent)" />
      <path d={qr.path} fill="var(--fg)" />
    </svg>
  );
}

function Paper({
  doc,
  demoLabel,
  t,
  uiLang,
  qr,
}: {
  doc: LaidDocument;
  demoLabel: string | null;
  t: ReturnType<typeof useT>;
  uiLang: string;
  qr?: Qr | null;
}) {
  return (
    <article
      lang={doc.language}
      className="paper mx-auto flex w-full max-w-[720px] flex-col gap-3 rounded-[var(--radius-card)] border border-line bg-surface p-5 text-fg shadow-sm lg:aspect-[210/297] lg:p-10"
      data-testid="note-paper"
    >
      {demoLabel ? (
        <p
          lang={uiLang}
          className="text-sm font-bold tracking-wide text-accent uppercase"
        >
          {demoLabel}
        </p>
      ) : null}
      {doc.sections.map((sec) => (
        <section
          key={sec.id}
          className="flex flex-col gap-2 break-inside-avoid"
        >
          {sec.heading ? (
            sec.id === "header" ? (
              <h2 className="text-2xl font-semibold">{sec.heading}</h2>
            ) : (
              <h3 className="text-lg font-semibold">{sec.heading}</h3>
            )
          ) : null}
          {sec.blocks.map((b) => (
            <BlockView key={b.id} b={b} t={t} />
          ))}
        </section>
      ))}
      {qr ? <QrImage qr={qr} label={t("Note.qrAlt")} /> : null}
    </article>
  );
}

function SideBySide({
  note,
  t,
}: {
  note: NoteLayout;
  t: ReturnType<typeof useT>;
}) {
  const [a, b] = note.documents as [LaidDocument, LaidDocument];
  return (
    <section aria-labelledby="sbs" className="flex flex-col gap-3">
      <SectionTitle id="sbs">{t("Note.sideBySide")}</SectionTitle>
      <div className="paper flex flex-col gap-4 rounded-[var(--radius-card)] border border-line bg-surface p-4 text-fg">
        {note.sideBySide!.map((sec) => (
          <div key={sec.section} className="flex flex-col gap-2">
            {sec.heading[0] ? (
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                <h3 lang={a.language} className="font-semibold">
                  {sec.heading[0]}
                </h3>
                <h3 lang={b.language} className="font-semibold text-muted">
                  {sec.heading[1]}
                </h3>
              </div>
            ) : null}
            {sec.rows.map(([x, y]) => (
              <div
                key={x.id}
                className="grid grid-cols-1 gap-2 border-t border-line pt-2 sm:grid-cols-2"
              >
                <div lang={a.language}>
                  <BlockView b={x} t={t} />
                </div>
                <div lang={b.language} className="text-muted">
                  <BlockView b={y} t={t} />
                </div>
              </div>
            ))}
          </div>
        ))}
      </div>
      <p className="text-sm text-muted">
        {t("Note.doctorColumn", { language: localeNames[a.language] })} ·{" "}
        {t("Note.patientColumn", { language: localeNames[b.language] })}
      </p>
    </section>
  );
}

export function NotePage() {
  const t = useT();
  const locale = useLocale() as Locale;
  const session = useSession();
  const { value: settings } = useSettings();
  const region = useUserRegion();
  const evaluation = useEvaluation(session);
  const defaultLang =
    settings.noteLanguage ??
    (session.demo ? PATIENT_FACTS[session.demo].noteLanguage : locale);
  const [noteLang, setNoteLang] = useState<Locale | null>(null);
  const lang = noteLang ?? defaultLang;
  const [size, setSize] = useState<"A4" | "LETTER">(paperFor(lang, region));
  const [state, setState] = useState<
    | { s: "idle" }
    | { s: "loading" }
    | { s: "error"; error: ApiError }
    | { s: "ok"; note: NoteOut; layout: NoteLayout; qr: Qr | null }
  >({ s: "idle" });
  const [pdfState, setPdf] = useState<"idle" | "busy" | "failed">("idle");
  const snapshot = useCall(
    session.client ? () => session.client!.memorySnapshot() : null,
    [session.client],
  );

  if (
    !session.ready ||
    evaluation.status === "loading" ||
    evaluation.status === "idle"
  )
    return <StateView state="loading" />;
  if (evaluation.status !== "ok")
    return (
      <StateView
        state="empty"
        message={t("Note.empty")}
        action={
          <ButtonLink href="/medicines">{t("Medicines.title")}</ButtonLink>
        }
      />
    );

  const boxNames = session.items.map((i) => i.boxName);
  const demoLabel = session.demo ? t("Demo.label") : null;
  const languages: Locale[] = lang === locale ? [lang] : [lang, locale];

  const make = async () => {
    setState({ s: "loading" });
    let body;
    try {
      body = noteBody(
        evaluation.input,
        pinsIn({
          rule_base_version: evaluation.result.rule_base_version,
          integrity_version: evaluation.result.integrity_version,
          counts_build_id:
            snapshot.status === "ok" ? snapshot.data.build_id : null,
        }),
        languages,
        region,
        session.demo ? null : settings.statisticsRegion,
      );
    } catch {
      setState({
        s: "error",
        error: {
          kind: "build",
          route: "notes/document",
          messageKey: "Errors.client_defect",
        },
      });
      return;
    }
    const r = await session.client!.noteDocument(body);
    if (!r.ok) {
      if (r.error.kind === "http" && r.error.status === 409) {
        // Req 17.2: re-evaluate, show the new results, print only after that.
        resultCache.clear();
        evaluation.retry();
      }
      setState({ s: "error", error: r.error });
      return;
    }
    try {
      setState({
        s: "ok",
        note: r.data,
        layout: layoutNote(r.data, boxNames, !!session.demo),
        qr: null,
      });
    } catch {
      setState({
        s: "error",
        error: {
          kind: "contract",
          route: "notes/document",
          messageKey: "Errors.generic",
        },
      });
    }
  };

  const download = async () => {
    if (state.s !== "ok") return;
    setPdf("busy");
    try {
      const { renderNotePdf } = await import("@/note/pdf");
      const v = state.layout.versions;
      const blob = await renderNotePdf(
        state.layout,
        {
          demo: demoLabel,
          pageOf: (page, pages) => t("Note.pageOf", { page, pages }),
          qr: state.qr
            ? { path: state.qr.path, side: state.qr.size + 2 * QUIET }
            : null,
          versions: t("Note.versions", {
            rules: v.rule_base_version.slice(0, 8),
            dataset: v.dataset_version.slice(0, 8),
            integrity: v.integrity_version.slice(0, 8),
          }),
        },
        size,
        location.origin,
      );
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = pdfFileName(state.layout.asOfMonth);
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 10_000);
      setPdf("idle");
    } catch {
      setPdf("failed");
    }
  };

  return (
    <>
      <PageTitle>{t("Note.title")}</PageTitle>
      <p className="max-w-[72ch]">{t("Note.intro")}</p>
      {/* Desktop (Req 27): the paper page centred on the left, the actions in a sticky aside. */}
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_320px] lg:items-start">
        <aside className="no-print flex min-w-0 flex-col gap-5 lg:sticky lg:top-4 lg:col-start-2 lg:row-start-1">
          <Card className="no-print">
            <SelectField
              label={t("Note.language")}
              value={lang}
              options={routing.locales.map((l) => ({
                value: l,
                label: localeNames[l],
                lang: l,
              }))}
              onChange={(l) => {
                setNoteLang(l);
                setSize(paperFor(l, region));
                setState({ s: "idle" });
              }}
            />
            <p className="text-sm text-muted">
              {t("Note.patientLanguage", { language: localeNames[locale] })}
            </p>
            <Button
              className="self-start"
              onClick={make}
              disabled={state.s === "loading"}
            >
              {t("Note.make")}
            </Button>
          </Card>
          {state.s === "ok" ? (
            <Card className="no-print">
              <SelectField
                label={t("Note.paper")}
                value={size}
                options={[
                  { value: "A4", label: t("Note.a4") },
                  { value: "LETTER", label: t("Note.letter") },
                ]}
                onChange={setSize}
              />
              <div className="flex flex-wrap gap-3">
                <Button
                  onClick={download}
                  disabled={pdfState === "busy"}
                  data-testid="download-pdf"
                >
                  <DownloadIcon size={20} />
                  {pdfState === "busy"
                    ? t("Note.preparingPdf")
                    : t("Note.download")}
                </Button>
                <Button variant="secondary" onClick={() => window.print()}>
                  <PrintIcon size={20} />
                  {t("Note.print")}
                </Button>
              </div>
              {pdfState === "failed" ? (
                <p role="alert">{t("Note.pdfFailed")}</p>
              ) : null}
            </Card>
          ) : null}
        </aside>
        <div className="flex min-w-0 flex-col gap-5 lg:col-start-1 lg:row-start-1">
          {state.s === "loading" ? (
            <StateView state="loading" label={t("Note.making")} />
          ) : null}
          {state.s === "error" ? (
            <StateView
              state="error"
              messageKey={state.error.messageKey}
              retry={
                state.error.kind === "network" || state.error.kind === "timeout"
                  ? make
                  : undefined
              }
            />
          ) : null}
          {state.s === "ok" ? (
            <>
              <SectionTitle>{t("Note.preview")}</SectionTitle>
              <Paper
                doc={state.layout.documents[0]!}
                demoLabel={demoLabel}
                t={t}
                uiLang={locale}
                qr={state.qr}
              />
              {state.note.documents[0]?.sections.some(
                (x) =>
                  x.id === "findings" || x.id === "findings_form_unconfirmed",
              ) && evaluation.result.findings.length ? (
                <QrOptIn
                  session={session}
                  noteIn={() =>
                    noteBody(
                      evaluation.input,
                      pinsIn({
                        rule_base_version: evaluation.result.rule_base_version,
                        integrity_version: evaluation.result.integrity_version,
                        counts_build_id:
                          snapshot.status === "ok"
                            ? snapshot.data.build_id
                            : null,
                      }),
                      [lang],
                      region,
                      session.demo ? null : settings.statisticsRegion,
                    )
                  }
                  language={lang}
                  events={evaluation.result.findings
                    .map((f) => parseLocator(f.faers_locator)?.event)
                    .filter((e): e is string => !!e)}
                  onIssued={(note, qr) =>
                    setState((st) =>
                      st.s === "ok"
                        ? {
                            s: "ok",
                            note: note ?? st.note,
                            layout: note
                              ? {
                                  ...layoutNote(note, boxNames, !!session.demo),
                                  sideBySide: st.layout.sideBySide,
                                }
                              : st.layout,
                            qr,
                          }
                        : st,
                    )
                  }
                />
              ) : null}
              {state.layout.sideBySide ? (
                <SideBySide note={state.layout} t={t} />
              ) : null}
            </>
          ) : null}
        </div>
      </div>
    </>
  );
}
