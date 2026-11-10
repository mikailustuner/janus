"use client";
/**
 * Photo of the label (ocr-first design §5, Req 2–4): the camera or a photo, read on the device.
 * The ingredient names Janus recognises are offered as candidates; none is chosen for the user
 * and nothing is sent before a choice. Every state has a way on: camera refused or missing,
 * reading failed, no text, no ingredient name. The words of the label stay available for a
 * product name or an ingredient Janus's list does not hold.
 */
import { useEffect, useRef, useState } from "react";

import type { Locale } from "@/api/contracts";
import { CameraIcon } from "@/components/icons";
import { Button, Card } from "@/components/ui";
import {
  captureFrame,
  startCamera,
  stopCamera,
  type CameraError,
} from "@/scan/camera";
import {
  dispatchLabel,
  labelResult,
  outboundOf,
  useLabelState,
  type Choice,
} from "@/scan/label-session";
import { useList } from "@/store/hooks";
import { listIngredientKeys } from "@/store/list";
import { useT } from "@/theme/words";
import { ingredientName } from "@/vocabulary";
import { useVocabulary } from "@/vocabulary/use";

/** Candidates shown before "show all". */
const FIRST = 5;

export function LabelPanel({
  locale,
  onNdc,
  onQuery,
  onType,
}: {
  locale: Locale;
  onNdc: (ndc: string) => void;
  /** `key`: the ingredient the user chose, when the query is its name. */
  onQuery: (q: string, key: string | null) => void;
  onType: () => void;
}) {
  const t = useT();
  const state = useLabelState();
  const vocab = useVocabulary();
  const { value: list } = useList();
  const video = useRef<HTMLVideoElement>(null);
  const stream = useRef<MediaStream | null>(null);
  const [cam, setCam] = useState<"off" | "starting" | "on" | CameraError>(
    "off",
  );
  const [selected, setSelected] = useState<number[]>([]);
  const [all, setAll] = useState(false);

  const stop = () => {
    stopCamera(stream.current);
    stream.current = null;
    setCam((c) => (c === "on" || c === "starting" ? "off" : c));
  };
  useEffect(() => stop, []);

  const start = async () => {
    if (!video.current) return;
    setCam("starting");
    try {
      stream.current = await startCamera(video.current);
      setCam("on");
    } catch (e) {
      setCam(e === "denied" ? "denied" : "unavailable");
    }
  };

  const read = async (photo: Blob) => {
    setSelected([]);
    setAll(false);
    dispatchLabel({ type: "start" });
    try {
      const [{ recognise }, { buildIndex, matchIngredients }, names] =
        await Promise.all([
          import("@/scan/ocr"),
          import("@/scan/ingredient-match"),
          import("@/vocabulary/ingredient-names.json"),
        ]);
      const index = buildIndex(names.default);
      const match = (lines: string[]) => matchIngredients(lines, index);
      const pass = await recognise(
        photo,
        locale,
        (p) => {
          const r = labelResult(p, match);
          return r.candidates.length > 0 || r.ndcs.length > 0;
        },
        (progress, turned) =>
          dispatchLabel({ type: "progress", progress, turned }),
      );
      dispatchLabel({ type: "read", result: labelResult(pass, match) });
    } catch {
      dispatchLabel({ type: "failed" });
    }
  };

  const send = (choice: Choice) => {
    if (!vocab) return;
    const out = outboundOf(state, choice, vocab.index.english_names);
    if (!out) return;
    if (out.kind === "ndc") onNdc(out.ndc);
    else onQuery(out.query, out.key);
  };

  const busy = state.kind === "busy";
  const result = state.kind === "done" ? state.result : null;
  const inList = new Set(listIngredientKeys(list.items));
  const chosenWords = outboundOf(state, { kind: "words", selected }, {});
  const query = chosenWords?.kind === "search" ? chosenWords.query : null;
  const typeInstead = (
    <Button variant="secondary" onClick={onType}>
      {t("Scan.wayType")}
    </Button>
  );

  return (
    <Card>
      <p>{t("Scan.labelLead")}</p>
      <video
        ref={video}
        playsInline
        muted
        className={`w-full rounded-[var(--radius-button)] bg-fg ${cam === "on" ? "" : "hidden"}`}
        aria-label={t("Scan.ocr.cameraHint")}
      />
      {cam === "on" ? (
        <p className="text-sm">{t("Scan.ocr.cameraHint")}</p>
      ) : null}
      {cam === "starting" ? (
        <p role="status">{t("Scan.cameraStarting")}</p>
      ) : null}
      {cam === "denied" || cam === "unavailable" ? (
        <p role="alert" data-testid="label-camera-unavailable">
          {t("Scan.ocr.cameraDenied")}
        </p>
      ) : null}
      <div className="flex flex-wrap gap-3">
        {cam === "on" ? (
          <>
            <Button
              disabled={busy}
              onClick={async () => {
                const frame = video.current
                  ? await captureFrame(video.current)
                  : null;
                stop();
                if (frame) void read(frame);
                else dispatchLabel({ type: "failed" });
              }}
            >
              <CameraIcon size={20} />
              {t("Scan.ocr.capture")}
            </Button>
            <Button variant="secondary" onClick={stop}>
              {t("Scan.stopCamera")}
            </Button>
          </>
        ) : (
          <Button disabled={busy || cam === "starting"} onClick={start}>
            <CameraIcon size={20} />
            {t("Scan.ocr.camera")}
          </Button>
        )}
        <label
          className={`inline-flex min-h-11 cursor-pointer items-center rounded-[var(--radius-button)] border-2 border-accent px-4 py-2.5 font-bold has-[:focus-visible]:outline-3 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-accent ${busy ? "pointer-events-none opacity-60" : ""}`}
        >
          {t("Scan.ocr.pick")}
          <input
            type="file"
            accept="image/*"
            className="sr-only"
            disabled={busy}
            onChange={(e) => {
              const file = e.target.files?.[0];
              e.target.value = "";
              if (!file) return;
              stop();
              void read(file);
            }}
          />
        </label>
      </div>
      <p className="text-sm text-muted">{t("Scan.ocr.privacy")}</p>

      {state.kind === "busy" ? (
        <div
          role="status"
          aria-busy="true"
          className="flex flex-col gap-2"
          data-testid="label-reading"
        >
          <p>
            {t(state.turned ? "Scan.ocr.turning" : "Scan.ocr.loading", {
              percent: `${Math.round(state.progress * 100)} %`,
            })}
          </p>
          <div
            aria-hidden="true"
            className="h-3 overflow-hidden rounded-full bg-chip"
          >
            <div
              className="h-full origin-left bg-accent transition-transform duration-200"
              style={{ transform: `scaleX(${state.progress})` }}
            />
          </div>
        </div>
      ) : null}
      {state.kind === "none" ? (
        <div role="alert" className="flex flex-col items-start gap-3">
          <p>{t("Scan.ocr.none")}</p>
          {typeInstead}
        </div>
      ) : null}
      {state.kind === "failed" ? (
        <div role="alert" className="flex flex-col items-start gap-3">
          <p>{t("Scan.ocr.failed")}</p>
          {typeInstead}
        </div>
      ) : null}

      {result ? (
        <>
          {result.candidates.length > 0 ? (
            <section
              aria-labelledby="label-candidates"
              className="flex flex-col gap-3"
            >
              <h2 id="label-candidates" className="text-lg font-bold">
                {t("Scan.ocr.candidatesTitle")}
              </h2>
              <p className="text-sm">{t("Scan.ocr.candidatesIntro")}</p>
              {result.candidates.length > 1 ? (
                <p className="text-sm">{t("Scan.ocr.several")}</p>
              ) : null}
              <ul className="flex flex-col gap-2">
                {result.candidates
                  .slice(0, all ? undefined : FIRST)
                  .map((c, i) => {
                    const name = vocab
                      ? ingredientName(vocab, c.key, null)
                      : null;
                    return (
                      <li key={c.key}>
                        <button
                          type="button"
                          disabled={!vocab}
                          data-testid="label-candidate"
                          data-strength={c.strength}
                          onClick={() => send({ kind: "ingredient", index: i })}
                          className="flex min-h-14 w-full flex-col items-start gap-0.5 rounded-[var(--radius-tile)] border-2 border-accent bg-surface px-4 py-2.5 text-left text-fg hover:bg-chip"
                        >
                          <span className="text-lg font-bold break-words">
                            {name?.text ?? c.key}
                          </span>
                          <span className="text-sm break-words text-muted">
                            {t("Scan.ocr.asWritten", { text: c.written })}
                          </span>
                          {c.strength === "close" ? (
                            <span className="text-sm font-bold">
                              {t("Scan.ocr.similar")}
                            </span>
                          ) : null}
                          {inList.has(c.key) ? (
                            <span className="text-sm">
                              {t("Scan.ocr.inList")}
                            </span>
                          ) : null}
                        </button>
                      </li>
                    );
                  })}
              </ul>
              {!all && result.candidates.length > FIRST ? (
                <Button
                  variant="quiet"
                  className="self-start"
                  onClick={() => setAll(true)}
                >
                  {t("Scan.ocr.showAll", {
                    count: result.candidates.length,
                  })}
                </Button>
              ) : null}
            </section>
          ) : (
            <p role="status" data-testid="label-no-ingredient">
              {t("Scan.ocr.noIngredient")}
            </p>
          )}
          {result.ndcs.length ? (
            <div className="flex flex-wrap gap-2">
              {result.ndcs.map((n, i) => (
                <Button
                  key={n}
                  variant="secondary"
                  onClick={() => send({ kind: "ndc", index: i })}
                >
                  {t("Scan.ocr.ndcChip", { ndc: n })}
                </Button>
              ))}
            </div>
          ) : null}
          <details
            className="flex flex-col gap-3"
            open={result.candidates.length === 0}
          >
            <summary className="min-h-11 cursor-pointer py-2.5 font-bold">
              {t("Scan.ocr.wordsTitle")}
            </summary>
            <div className="flex flex-col gap-3 pt-2">
              <p className="text-sm">{t("Scan.ocr.instructions")}</p>
              <div className="flex max-h-72 flex-wrap gap-1 overflow-y-auto p-1">
                {result.words.map((w, i) => (
                  <button
                    key={i}
                    type="button"
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
                <Button
                  disabled={!query}
                  onClick={() => send({ kind: "words", selected })}
                >
                  {query
                    ? t("Scan.ocr.lookupWords", { query })
                    : t("Scan.submit")}
                </Button>
                {selected.length ? (
                  <Button variant="quiet" onClick={() => setSelected([])}>
                    {t("Scan.ocr.clear")}
                  </Button>
                ) : null}
              </div>
            </div>
          </details>
          <div className="flex flex-wrap gap-3">
            {typeInstead}
            <Button
              variant="quiet"
              onClick={() => {
                setSelected([]);
                dispatchLabel({ type: "clear" });
              }}
            >
              {t("Scan.ocr.remove")}
            </Button>
          </div>
        </>
      ) : null}
    </Card>
  );
}
