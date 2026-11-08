"use client";
/**
 * Scan (design §3, §6, §9, Req 10, 11): three ways in — the camera or a photo of the code, a photo
 * of the label read on the device, or typing. A demo code is recognised before any request on
 * every path. Images and recognised text never leave the device; only the filtered code, an NDC
 * or the words the user chose are sent.
 */
import { useLocale } from "next-intl";
import { useEffect, useRef, useState, useSyncExternalStore } from "react";

import { ndcBody, scanBody, searchBody } from "@/api/builders";
import type { Result } from "@/api/client";
import type { Locale, ResolutionResult } from "@/api/contracts";
import type { ApiError } from "@/api/errors";
import { StateView } from "@/components/StateView";
import { Button, Card, PageTitle } from "@/components/ui";
import { detectDemo, type DemoRef } from "@/demo/codes";
import { startDemo } from "@/demo/session";
import { useSession } from "@/flow/janus";
import { setPending, type Pending } from "@/flow/pending";
import { useRouter } from "@/i18n/navigation";
import {
  startCamera,
  scanFrames,
  stopCamera,
  type CameraError,
} from "@/scan/camera";
import { classifyTyped, outbound } from "@/scan/gs1";
import type { Recognised } from "@/scan/ocr";
import { ndcCandidates, selectionQuery } from "@/scan/ocr-extract";
import { useSettings } from "@/store/hooks";
import { useT } from "@/theme/words";

type Tab = "code" | "label" | "type";
type Status =
  | { kind: "idle" }
  | { kind: "busy"; label: string }
  | { kind: "message"; key: string }
  | { kind: "error"; error: ApiError }
  | { kind: "demo"; ref: DemoRef };

export function ScanPage() {
  const t = useT();
  const locale = useLocale() as Locale;
  const router = useRouter();
  const session = useSession();
  const { value: settings } = useSettings();
  const hashTab = useSyncExternalStore(
    (l) => {
      window.addEventListener("hashchange", l);
      return () => window.removeEventListener("hashchange", l);
    },
    () => location.hash.slice(1),
    () => "",
  );
  const [chosenTab, setTab] = useState<Tab | null>(null);
  const tab: Tab =
    chosenTab ?? (hashTab === "label" || hashTab === "type" ? hashTab : "code");
  const [status, setStatus] = useState<Status>({ kind: "idle" });
  const region = session.demo ? null : settings.scanRegion;

  const go = async (
    call: () => Promise<Result<ResolutionResult>>,
    source: Pending["source"],
    typed: string | null,
  ) => {
    setStatus({ kind: "busy", label: t("Scan.looking") });
    let r: Result<ResolutionResult>;
    try {
      r = await call();
    } catch {
      setStatus({
        kind: "error",
        error: {
          kind: "build",
          route: "resolve/scan",
          messageKey: "Errors.client_defect",
        },
      });
      return;
    }
    if (!r.ok) return setStatus({ kind: "error", error: r.error });
    setPending({ resolution: r.data, source, typed, replaces: null });
    router.push("/confirm");
  };

  /** Every path: a demo code first (no request), then the outbound filter. */
  const handleCode = (text: string) => {
    const demo = detectDemo(text);
    if (demo) return setStatus({ kind: "demo", ref: demo });
    const out = outbound(text);
    if (out.kind === "unreadable")
      return setStatus({ kind: "message", key: "Scan.errors.unreadable" });
    const client = session.client;
    if (!client) return;
    void go(
      () => client.resolveScan(scanBody(out.content, region)),
      { kind: "scan", content: out.content },
      null,
    );
  };

  const handleNdc = (ndc: string) => {
    const demo = detectDemo(ndc);
    if (demo) return setStatus({ kind: "demo", ref: demo });
    const client = session.client;
    if (client)
      void go(
        () => client.resolveNdc(ndcBody(ndc)),
        { kind: "ndc", ndc },
        null,
      );
  };

  const handleSearch = (query: string) => {
    const client = session.client;
    if (client)
      void go(
        () => client.resolveSearch(searchBody(query, region)),
        { kind: "search", query: query.trim(), region },
        query.trim(),
      );
  };

  const regionName = region
    ? t(`Common.region.${region}`)
    : t("Scan.regionAuto");
  const tabs: Tab[] = ["code", "label", "type"];

  return (
    <>
      <PageTitle>{t("Scan.title")}</PageTitle>
      <p>{t("Scan.intro")}</p>
      <p className="text-sm text-muted">
        {t("Scan.regionNote", { region: regionName })}
      </p>
      <div
        role="tablist"
        aria-label={t("Scan.title")}
        className="grid grid-cols-3 gap-1 rounded-[var(--radius-button)] bg-chip p-1"
      >
        {tabs.map((k) => (
          <button
            key={k}
            role="tab"
            id={`tab-${k}`}
            aria-selected={tab === k}
            aria-controls={`panel-${k}`}
            onClick={() => {
              setTab(k);
              setStatus({ kind: "idle" });
            }}
            className={`min-h-11 rounded-[var(--radius-button)] px-2 text-sm font-bold ${tab === k ? "bg-surface text-fg" : "text-chip-fg"}`}
          >
            {t(`Scan.tabs.${k}`)}
          </button>
        ))}
      </div>
      <div
        role="tabpanel"
        id={`panel-${tab}`}
        aria-labelledby={`tab-${tab}`}
        className="flex flex-col gap-4"
      >
        {tab === "code" ? <CodePanel onCode={handleCode} /> : null}
        {tab === "label" ? (
          <LabelPanel
            locale={locale}
            onNdc={handleNdc}
            onQuery={handleSearch}
          />
        ) : null}
        {tab === "type" ? (
          <TypePanel
            onTyped={(text) => {
              const demo = detectDemo(text);
              if (demo) return setStatus({ kind: "demo", ref: demo });
              const c = classifyTyped(text);
              if (c.kind === "scan") return handleCode(c.content);
              if (c.kind === "ndc") return handleNdc(c.ndc);
              if (c.kind === "national_code")
                return setStatus({ kind: "message", key: "Scan.nationalCode" });
              if (c.kind === "invalid")
                return setStatus({ kind: "message", key: "Scan.tooShort" });
              handleSearch(c.query);
            }}
          />
        ) : null}
      </div>
      {status.kind === "busy" ? (
        <StateView state="loading" label={status.label} />
      ) : null}
      {status.kind === "message" ? (
        <p role="alert" className="card p-3 font-bold">
          {t(status.key)}
        </p>
      ) : null}
      {status.kind === "error" ? (
        <StateView state="error" messageKey={status.error.messageKey} />
      ) : null}
      {status.kind === "demo" ? (
        <Card role="alert">
          {session.demo ? (
            <p>{t("Scan.demoKnown")}</p>
          ) : (
            <>
              <p className="font-bold">{t("Scan.demoPrompt")}</p>
              <Button
                className="self-start"
                onClick={() => {
                  startDemo(status.ref.patient);
                  router.push("/medicines");
                }}
              >
                {t("Scan.demoOpen")}
              </Button>
            </>
          )}
        </Card>
      ) : null}
    </>
  );
}

function CodePanel({ onCode }: { onCode: (text: string) => void }) {
  const t = useT();
  const video = useRef<HTMLVideoElement>(null);
  const [cam, setCam] = useState<"off" | "starting" | "on" | CameraError>(
    "off",
  );
  const [slow, setSlow] = useState(false);
  const [photo, setPhoto] = useState<"idle" | "busy" | "none">("idle");
  const stream = useRef<MediaStream | null>(null);
  const abort = useRef<AbortController | null>(null);

  const stop = () => {
    abort.current?.abort();
    stopCamera(stream.current);
    stream.current = null;
    setCam("off");
  };
  useEffect(() => stop, []);

  const start = async () => {
    if (!video.current) return;
    setCam("starting");
    setSlow(false);
    try {
      stream.current = await startCamera(video.current);
      setCam("on");
      abort.current = new AbortController();
      const timer = setTimeout(() => setSlow(true), 15_000);
      const text = await scanFrames(video.current, abort.current.signal);
      clearTimeout(timer);
      stop();
      if (text) onCode(text);
    } catch (e) {
      setCam(e === "denied" ? "denied" : "unavailable");
    }
  };

  return (
    <Card>
      <video
        ref={video}
        playsInline
        muted
        className={`w-full rounded-[var(--radius-button)] bg-fg ${cam === "on" ? "" : "hidden"}`}
        aria-label={t("Scan.cameraHint")}
      />
      {cam === "on" ? <p className="text-sm">{t("Scan.cameraHint")}</p> : null}
      {cam === "starting" ? (
        <p role="status">{t("Scan.cameraStarting")}</p>
      ) : null}
      {slow ? <p role="status">{t("Scan.noCodeYet")}</p> : null}
      {cam === "denied" || cam === "unavailable" ? (
        <p role="alert">{t("Scan.cameraDenied")}</p>
      ) : null}
      <div className="flex flex-wrap gap-3">
        {cam === "on" ? (
          <Button variant="secondary" onClick={stop}>
            {t("Scan.stopCamera")}
          </Button>
        ) : (
          <Button onClick={start}>{t("Scan.startCamera")}</Button>
        )}
        <label className="inline-flex min-h-11 cursor-pointer items-center rounded-[var(--radius-button)] border-2 border-accent px-4 font-bold">
          {t("Scan.pickPhoto")}
          <input
            type="file"
            accept="image/*"
            className="sr-only"
            onChange={async (e) => {
              const file = e.target.files?.[0];
              e.target.value = "";
              if (!file) return;
              setPhoto("busy");
              const { decode } = await import("@/scan/zxing");
              const text = await decode(file).catch(() => null);
              setPhoto(text ? "idle" : "none");
              if (text) onCode(text);
            }}
          />
        </label>
      </div>
      {photo === "busy" ? <p role="status">{t("Scan.decoding")}</p> : null}
      {photo === "none" ? <p role="alert">{t("Scan.noCodeInPhoto")}</p> : null}
    </Card>
  );
}

function LabelPanel({
  locale,
  onNdc,
  onQuery,
}: {
  locale: Locale;
  onNdc: (ndc: string) => void;
  onQuery: (q: string) => void;
}) {
  const t = useT();
  const [state, setState] = useState<
    | { kind: "idle" }
    | { kind: "busy"; p: number }
    | { kind: "none" | "failed" }
    | { kind: "done"; text: Recognised }
  >({ kind: "idle" });
  const [selected, setSelected] = useState<number[]>([]);
  const words =
    state.kind === "done" ? state.text.lines.flatMap((l) => l.words) : [];
  const ndcs =
    state.kind === "done"
      ? ndcCandidates(state.text.lines.map((l) => l.text).join("\n"))
      : [];
  const query = selectionQuery(words, selected);
  return (
    <Card>
      <label className="inline-flex min-h-11 cursor-pointer items-center self-start rounded-[var(--radius-button)] bg-accent px-4 font-bold text-on-accent">
        {t("Scan.ocr.pick")}
        <input
          type="file"
          accept="image/*"
          className="sr-only"
          onChange={async (e) => {
            const file = e.target.files?.[0];
            e.target.value = "";
            if (!file) return;
            setSelected([]);
            setState({ kind: "busy", p: 0 });
            try {
              const { recognise } = await import("@/scan/ocr");
              const text = await recognise(file, locale, (p) =>
                setState({ kind: "busy", p }),
              );
              setState(
                text.lines.length ? { kind: "done", text } : { kind: "none" },
              );
            } catch {
              setState({ kind: "failed" });
            }
          }}
        />
      </label>
      {state.kind === "busy" ? (
        <p role="status" aria-busy="true">
          {t("Scan.ocr.loading", { percent: `${Math.round(state.p * 100)} %` })}
        </p>
      ) : null}
      {state.kind === "none" ? <p role="alert">{t("Scan.ocr.none")}</p> : null}
      {state.kind === "failed" ? (
        <p role="alert">{t("Scan.ocr.failed")}</p>
      ) : null}
      {state.kind === "done" ? (
        <>
          <p className="text-sm">{t("Scan.ocr.instructions")}</p>
          {ndcs.length ? (
            <div className="flex flex-wrap gap-2">
              {ndcs.map((n) => (
                <Button key={n} variant="secondary" onClick={() => onNdc(n)}>
                  {t("Scan.ocr.ndcChip", { ndc: n })}
                </Button>
              ))}
            </div>
          ) : null}
          <div className="flex max-h-72 flex-wrap gap-1 overflow-y-auto">
            {words.map((w, i) => (
              <button
                key={i}
                aria-pressed={selected.includes(i)}
                onClick={() =>
                  setSelected((s) =>
                    s.includes(i) ? s.filter((x) => x !== i) : [...s, i],
                  )
                }
                className={`min-h-11 min-w-11 rounded-full border-2 px-3 text-sm ${selected.includes(i) ? "border-accent bg-accent text-on-accent" : "border-muted"}`}
              >
                {w}
              </button>
            ))}
          </div>
          <div className="flex flex-wrap gap-3">
            <Button disabled={!query} onClick={() => query && onQuery(query)}>
              {query ? t("Scan.ocr.lookupWords", { query }) : t("Scan.submit")}
            </Button>
            {selected.length ? (
              <Button variant="quiet" onClick={() => setSelected([])}>
                {t("Scan.ocr.clear")}
              </Button>
            ) : null}
          </div>
        </>
      ) : null}
    </Card>
  );
}

function TypePanel({ onTyped }: { onTyped: (text: string) => void }) {
  const t = useT();
  const [text, setText] = useState("");
  return (
    <Card>
      <form
        className="flex flex-col gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          onTyped(text);
        }}
      >
        <label className="flex flex-col gap-1">
          <span className="font-bold">{t("Scan.typeLabel")}</span>
          <span className="text-sm text-muted">{t("Scan.typeHint")}</span>
          <input
            value={text}
            onChange={(e) => setText(e.target.value)}
            maxLength={100}
            autoComplete="off"
            className="min-h-11 rounded-[var(--radius-button)] border-2 border-muted bg-surface px-3 text-fg"
          />
        </label>
        <Button type="submit" className="self-start">
          {t("Scan.submit")}
        </Button>
      </form>
    </Card>
  );
}
