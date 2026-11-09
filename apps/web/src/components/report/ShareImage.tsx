"use client";
/**
 * The share image (janus-report Req 5, DP10–DP12): two opt-in checkboxes (event names, ingredient
 * names; off), "Prepare the image" draws the PNG in the browser, a modal dialog shows that exact
 * image with the sentence that it leaves Janus only through the person's own sharing, then Web
 * Share with the file where the browser can share files, else a download. No request is made.
 */
import { useLocale } from "next-intl";
import { useEffect, useRef, useState } from "react";

import type { CascadeResult } from "@/api/contracts";
import { formatCount, formatMonth } from "@/components/format";
import { candidateIngredients, keyName } from "@/components/names";
import { useUserRegion } from "@/components/region";
import { useFindingWords } from "@/components/results/FindingCard";
import { Button } from "@/components/ui";
import { useDemo } from "@/demo/session";
import {
  shareCard,
  shareCardText,
  type ShareCard,
  type ShareOptions,
} from "@/flow/share-card";
import { summaryView } from "@/flow/summary";
import type { Item } from "@/store/list";
import { useT } from "@/theme/words";
import { sentence, type Loaded } from "@/vocabulary";

import { drawShareCard } from "./draw";

type Ready = { blob: Blob; url: string; card: ShareCard; file: File };

export function ShareImage({
  result,
  items,
  vocab,
}: {
  result: CascadeResult;
  items: readonly Item[];
  vocab: Loaded;
}) {
  const t = useT();
  const locale = useLocale();
  const demo = useDemo();
  const region = useUserRegion();
  const words = useFindingWords(vocab);
  const [options, setOptions] = useState<ShareOptions>({
    events: false,
    ingredients: false,
  });
  const [phase, setPhase] = useState<"idle" | "preparing" | "error" | "saved">(
    "idle",
  );
  const [ready, setReady] = useState<Ready | null>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  const opener = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (ready) dialog.current?.showModal();
  }, [ready]);
  // The Blob URL is revoked once the dialog has closed and a download has had time to start.
  useEffect(
    () => () => {
      if (ready) setTimeout(() => URL.revokeObjectURL(ready.url), 30_000);
    },
    [ready],
  );

  const build = (): ShareCard | null => {
    const v = summaryView(result, items, vocab);
    if (v.kind !== "ok") return null;
    const emergency = t(`Memory.emergency.${region}`);
    return shareCard({
      view: v,
      options,
      demo: demo !== null,
      eventNames: result.findings.map((_, position) => {
        const f = v.findings.find((x) => x.position === position);
        return f ? words(f).title : "";
      }),
      ingredientNames: items.flatMap((it) =>
        candidateIngredients(vocab, it.candidate, it.choices)
          .map((g) => g.name.text)
          .filter((x): x is string => !!x),
      ),
      safetyTexts: v.safetyLines.map((code) =>
        t(`Memory.codes.${code}`, {
          emergency,
          crisis: t(`Memory.crisis.${region}`),
        }),
      ),
      emergencyText: t("Emergency.text", { emergency }),
      abruptStop: sentence(vocab, "abrupt_stop"),
      warnedIngredientNames: result.item_warnings.map((w) =>
        keyName(vocab, w.ingredient_key, null),
      ),
      month: formatMonth(v.month, locale),
      t,
      formatNumber: (n) => formatCount(n, locale),
    });
  };

  const prepare = async () => {
    const card = build();
    if (!card || phase === "preparing") return;
    setPhase("preparing");
    try {
      const blob = await drawShareCard(card);
      const file = new File([blob], `janus-summary-${result.as_of_month}.png`, {
        type: "image/png",
      });
      setReady({ blob, url: URL.createObjectURL(blob), card, file });
      setPhase("idle");
    } catch {
      setPhase("error");
    }
  };

  const close = () => {
    dialog.current?.close();
  };
  // Focus returns to the button that opened the dialog (Req 5.7).
  const onClosed = () => {
    setReady(null);
    opener.current?.focus();
  };

  const canShareFile =
    !!ready &&
    typeof navigator !== "undefined" &&
    typeof navigator.canShare === "function" &&
    navigator.canShare({ files: [ready.file] });

  const save = () => {
    if (!ready) return;
    const a = document.createElement("a");
    a.href = ready.url;
    a.download = ready.file.name;
    document.body.append(a);
    a.click();
    a.remove();
    setPhase("saved");
    // Revoke after the download has started (the effect cleanup on close does it too).
    close();
  };
  const share = async () => {
    if (!ready) return;
    try {
      await navigator.share({ files: [ready.file] });
      close();
    } catch (e) {
      // Cancelled by the person: keep the dialog open, no error (Req 5.6).
      if (e instanceof DOMException && e.name === "AbortError") return;
      save();
    }
  };

  const check = (key: keyof ShareOptions, label: string, hint: string) => (
    <label className="flex min-h-11 cursor-pointer items-start gap-3 rounded-[var(--radius-tile)] p-2 hover:bg-chip">
      <input
        type="checkbox"
        className="mt-1 size-5 shrink-0 accent-[var(--accent)]"
        checked={options[key]}
        onChange={(e) => setOptions((o) => ({ ...o, [key]: e.target.checked }))}
        data-testid={`share-${key}`}
        aria-describedby={`share-${key}-hint`}
      />
      <span className="flex min-w-0 flex-col gap-0.5">
        <span className="font-bold">{label}</span>
        <span id={`share-${key}-hint`} className="text-sm text-muted">
          {hint}
        </span>
      </span>
    </label>
  );

  return (
    <section
      aria-labelledby="share-title"
      className="card summary-tile"
      data-testid="share-card"
    >
      <h2 id="share-title" className="font-body text-lg leading-snug font-bold">
        {t("Report.share.title")}
      </h2>
      <p className="text-muted">{t("Report.share.intro")}</p>
      <fieldset className="m-0 flex min-w-0 flex-col gap-1 border-0 p-0">
        <legend className="mb-1 text-sm font-bold">
          {t("Report.share.default")}
        </legend>
        {check(
          "events",
          t("Report.share.events"),
          t("Report.share.eventsHint"),
        )}
        {check(
          "ingredients",
          t("Report.share.ingredients"),
          t("Report.share.ingredientsHint"),
        )}
      </fieldset>
      <div className="flex flex-wrap items-center gap-3">
        <Button
          onClick={prepare}
          ref={opener}
          aria-disabled={phase === "preparing" || undefined}
          data-testid="share-prepare"
        >
          {phase === "preparing"
            ? t("Report.share.preparing")
            : t("Report.share.prepare")}
        </Button>
        <p aria-live="polite" className="text-sm">
          {phase === "error"
            ? t("Report.share.error")
            : phase === "saved"
              ? t("Report.share.saved")
              : ""}
        </p>
      </div>
      <dialog
        ref={dialog}
        aria-labelledby="share-confirm-title"
        aria-describedby="share-confirm-text"
        className="share-dialog card"
        onClose={onClosed}
        data-testid="share-dialog"
      >
        {ready ? (
          <div className="flex flex-col gap-4">
            <h2
              id="share-confirm-title"
              className="font-body text-xl leading-snug font-bold"
            >
              {t("Report.share.confirmTitle")}
            </h2>
            {/* The exact image that will be shared or saved (DP12). */}
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={ready.url}
              alt={t("Report.share.alt", { text: shareCardText(ready.card) })}
              width={1080}
              height={1350}
              className="mx-auto h-auto max-h-[52dvh] w-auto max-w-full rounded-[var(--radius-tile)] border border-line"
              data-testid="share-preview"
            />
            <p id="share-confirm-text" className="font-bold">
              {t("Report.share.confirmText")}
            </p>
            <div className="flex flex-wrap gap-3">
              {canShareFile ? (
                <Button onClick={share} data-testid="share-share">
                  {t("Report.share.share")}
                </Button>
              ) : null}
              <Button
                variant={canShareFile ? "secondary" : "primary"}
                onClick={save}
                data-testid="share-save"
              >
                {t("Report.share.save")}
              </Button>
              <Button
                variant="quiet"
                onClick={close}
                data-testid="share-cancel"
              >
                {t("Common.cancel")}
              </Button>
            </div>
          </div>
        ) : null}
      </dialog>
    </section>
  );
}
