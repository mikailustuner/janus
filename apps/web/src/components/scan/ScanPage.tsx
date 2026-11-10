"use client";
/**
 * Scan (design §3, §6, §9, Req 10, 11; ocr-first Req 1): three ways in, shown side by side — the
 * camera or a photo of the code, a photo of the label read on the device, or typing. The label
 * and the name work with a box from any country; the code works where Janus holds the product
 * list. Wherever a code cannot be used, the other two ways are offered. A demo code is
 * recognised before any request on every path. Images and recognised text never leave the
 * device; only the filtered code, an NDC or the name or words the user chose are sent.
 */
import { useLocale } from "next-intl";
import { useEffect, useRef, useState, useSyncExternalStore } from "react";

import { ndcBody, scanBody, searchBody } from "@/api/builders";
import type { Result } from "@/api/client";
import type { Locale, ResolutionResult } from "@/api/contracts";
import type { ApiError } from "@/api/errors";
import { CameraIcon, KeyboardIcon, ScanIcon } from "@/components/icons";
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
import { useLabelState } from "@/scan/label-session";
import { useSettings } from "@/store/hooks";
import { useT } from "@/theme/words";

import { LabelPanel } from "./LabelPanel";

type Tab = "code" | "label" | "type";
const TAB_ICON = { code: ScanIcon, label: CameraIcon, type: KeyboardIcon };
type Status =
  | { kind: "idle" }
  | { kind: "busy"; label: string }
  /** `ways`: the label photo and the name are offered under the message. */
  | { kind: "message"; key: string; ways?: boolean }
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
  // A label result still in memory (a label with several ingredients) opens the label tab.
  const labelKept = useLabelState().kind === "done";
  const tab: Tab =
    chosenTab ??
    (hashTab === "label" || hashTab === "type"
      ? hashTab
      : labelKept
        ? "label"
        : "code");
  const [status, setStatus] = useState<Status>({ kind: "idle" });
  const region = session.demo ? null : settings.scanRegion;

  const go = async (
    call: () => Promise<Result<ResolutionResult>>,
    source: Pending["source"],
    typed: string | null,
    lot: string | null = null,
    prefer: string | null = null,
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
    setPending({
      resolution: r.data,
      source,
      typed,
      lot,
      replaces: null,
      prefer,
    });
    router.push("/confirm");
  };

  /** Every path: a demo code first (no request), then the outbound filter. The lot is kept
   *  beside the request, never in it. */
  const handleCode = (text: string, typedLot: string | null = null) => {
    const demo = detectDemo(text);
    if (demo) return setStatus({ kind: "demo", ref: demo });
    const out = outbound(text);
    if (out.kind === "unreadable")
      return setStatus({
        kind: "message",
        key: "Scan.errors.unreadable",
        ways: true,
      });
    const client = session.client;
    if (!client) return;
    void go(
      () => client.resolveScan(scanBody(out.content, region)),
      { kind: "scan", content: out.content },
      null,
      out.lot ?? typedLot,
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

  /** `key`: the ingredient the user chose from the label candidates, shown first on confirm. */
  const handleSearch = (query: string, key: string | null = null) => {
    const client = session.client;
    if (client)
      void go(
        () =>
          client.resolveSearch(
            key ? searchBody(query, region, 20) : searchBody(query, region),
          ),
        { kind: "search", query: query.trim(), region },
        query.trim(),
        null,
        key,
      );
  };
  const open = (k: Tab) => {
    setTab(k);
    setStatus({ kind: "idle" });
  };

  const regionName = region
    ? t(`Common.region.${region}`)
    : t("Scan.regionAuto");
  const tabs: Tab[] = ["code", "label", "type"];

  return (
    <>
      <PageTitle>{t("Scan.title")}</PageTitle>
      <p>{t("Scan.intro")}</p>
      <p data-testid="any-country">{t("Scan.anyCountry")}</p>
      <p className="text-sm text-muted">
        {t("Scan.regionNote", { region: regionName })}
      </p>
      <div
        role="tablist"
        aria-label={t("Scan.title")}
        className="grid grid-cols-3 gap-1 rounded-[var(--radius-button)] bg-chip p-1"
      >
        {tabs.map((k) => {
          const Icon = TAB_ICON[k];
          return (
            <button
              key={k}
              role="tab"
              id={`tab-${k}`}
              aria-selected={tab === k}
              aria-controls={`panel-${k}`}
              onClick={() => open(k)}
              className={`flex min-h-16 flex-col items-center justify-center gap-1 rounded-[var(--radius-button)] px-1 py-2 text-center text-sm leading-tight font-bold ${tab === k ? "bg-surface text-fg" : "text-chip-fg"}`}
            >
              <Icon size={22} />
              <span className="break-words hyphens-auto">
                {t(`Scan.tabs.${k}`)}
              </span>
            </button>
          );
        })}
      </div>
      <div
        role="tabpanel"
        id={`panel-${tab}`}
        aria-labelledby={`tab-${tab}`}
        className="flex flex-col gap-4"
      >
        {tab === "code" ? <CodePanel onCode={handleCode} onWay={open} /> : null}
        {tab === "label" ? (
          <LabelPanel
            locale={locale}
            onNdc={handleNdc}
            onQuery={handleSearch}
            onType={() => open("type")}
          />
        ) : null}
        {tab === "type" ? (
          <TypePanel
            onTyped={(text) => {
              const demo = detectDemo(text);
              if (demo) return setStatus({ kind: "demo", ref: demo });
              const c = classifyTyped(text);
              if (c.kind === "scan") return handleCode(c.content, c.lot);
              if (c.kind === "ndc") return handleNdc(c.ndc);
              if (c.kind === "national_code")
                return setStatus({
                  kind: "message",
                  key: "Scan.nationalCode",
                  ways: true,
                });
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
        <div role="alert" className="card flex flex-col gap-3 p-3">
          <p className="font-bold">{t(status.key)}</p>
          {status.ways ? <Ways onWay={open} except={tab} /> : null}
        </div>
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

/** The ways that work with any box: the label photo and the name. */
function Ways({ onWay, except }: { onWay: (k: Tab) => void; except?: Tab }) {
  const t = useT();
  return (
    <div className="flex flex-wrap gap-3" data-testid="other-ways">
      {except !== "label" ? (
        <Button variant="secondary" onClick={() => onWay("label")}>
          <CameraIcon size={20} />
          {t("Scan.wayLabel")}
        </Button>
      ) : null}
      {except !== "type" ? (
        <Button variant="secondary" onClick={() => onWay("type")}>
          <KeyboardIcon size={20} />
          {t("Scan.wayType")}
        </Button>
      ) : null}
    </div>
  );
}

function CodePanel({
  onCode,
  onWay,
}: {
  onCode: (text: string) => void;
  onWay: (k: Tab) => void;
}) {
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
      <p>{t("Scan.codeLead")}</p>
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
      {slow || photo === "none" || cam === "denied" || cam === "unavailable" ? (
        <Ways onWay={onWay} />
      ) : null}
    </Card>
  );
}

function TypePanel({ onTyped }: { onTyped: (text: string) => void }) {
  const t = useT();
  const [text, setText] = useState("");
  return (
    <Card>
      <p>{t("Scan.typeLead")}</p>
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
