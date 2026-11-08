"use client";
/**
 * The outcome-loop opt-in (design §10.3–§10.4, Req 18.1–18.3, 18.6): the consent text first; only
 * after the user accepts, `POST /notes/token` with one language, the consent version and the
 * outcome region. The token goes into the QR address after `#` and into this browser's storage,
 * nowhere else. In demo no request is made: the QR opens the demo doctor page.
 */
import { useLocale } from "next-intl";
import { useState } from "react";

import { tokenBody } from "@/api/builders";
import type { LoopRegion, NoteIn, NoteOut } from "@/api/contracts";
import { formatDate } from "@/components/format";
import { useUserRegion } from "@/components/region";
import { Button, Card, SectionTitle } from "@/components/ui";
import { OUTCOME_CONSENT_VERSION } from "@/consent/versions";
import type { Session } from "@/flow/janus";
import { addToken, issued } from "@/flow/loop";
import { Link } from "@/i18n/navigation";
import { makeQr, qrAddress, type Qr } from "@/note/qr";
import { localDate } from "@/store/reminders";
import { tokens } from "@/store/tokens";
import { useT } from "@/theme/words";

const FROM_USER: Record<string, LoopRegion | null> = {
  US: "US",
  TR: "TR",
  EU: "EU",
  OTHER: null,
  UNKNOWN: null,
};

export function QrOptIn({
  session,
  noteIn,
  language,
  events,
  onIssued,
}: {
  session: Session;
  noteIn: () => NoteIn;
  language: string;
  events: string[];
  onIssued: (note: NoteOut | null, qr: Qr | null) => void;
}) {
  const t = useT();
  const locale = useLocale();
  const userRegion = useUserRegion();
  const [accepted, setAccepted] = useState(false);
  const [region, setRegion] = useState<LoopRegion | null>(
    FROM_USER[userRegion] ?? null,
  );
  const [state, setState] = useState<
    | { s: "idle" | "busy" }
    | { s: "error"; key: string }
    | { s: "done"; expires: string | null }
  >({ s: "idle" });
  const c = `OutcomeConsent.${OUTCOME_CONSENT_VERSION}`;

  const make = async () => {
    if (!accepted || !region) return;
    setState({ s: "busy" });
    if (session.demo) {
      onIssued(null, makeQr(`${location.origin}/o#demo-${session.demo}`));
      setState({ s: "done", expires: null });
      return;
    }
    if (!session.loop) return;
    let r;
    try {
      r = await session.loop.noteToken(
        tokenBody(noteIn(), OUTCOME_CONSENT_VERSION, region),
      );
    } catch {
      setState({ s: "error", key: "Errors.client_defect" });
      return;
    }
    if (!r.ok) {
      setState({ s: "error", key: r.error.messageKey });
      return;
    }
    tokens.update((d) =>
      addToken(d, issued(r.data, language, localDate(), events)),
    );
    const qr = makeQr(qrAddress(r.data.qr_url, location.origin, r.data.token));
    onIssued(r.data.note, qr);
    setState(
      qr
        ? { s: "done", expires: r.data.expires_on }
        : { s: "error", key: "Note.qrTooLong" },
    );
  };

  return (
    <Card
      className="no-print"
      aria-labelledby="qr-title"
      data-testid="qr-optin"
    >
      <SectionTitle id="qr-title">{t("Note.qrTitle")}</SectionTitle>
      <p>{t("Note.qrIntro")}</p>
      <div className="flex flex-col gap-2 rounded-[var(--radius-button)] bg-chip p-3 text-chip-fg">
        <p className="font-bold">{t(`${c}.heading`)}</p>
        <p>{t(`${c}.asked`)}</p>
        <p>{t(`${c}.stored`)}</p>
        <p>{t(`${c}.howLong`)}</p>
        <p>{t(`${c}.withdraw`)}</p>
      </div>
      {FROM_USER[userRegion] ? null : (
        <fieldset className="flex flex-col gap-1">
          <legend className="font-bold">{t("Note.qrRegion")}</legend>
          {(["TR", "EU", "US"] as const).map((r) => (
            <label key={r} className="flex min-h-11 items-center gap-3">
              <input
                type="radio"
                name="qr-region"
                checked={region === r}
                onChange={() => setRegion(r)}
                className="size-5 accent-[var(--accent)]"
              />
              {t(`Common.region.${r}`)}
            </label>
          ))}
        </fieldset>
      )}
      <label className="flex min-h-11 items-center gap-3">
        <input
          type="checkbox"
          checked={accepted}
          onChange={(e) => setAccepted(e.target.checked)}
          className="size-5 accent-[var(--accent)]"
        />
        {t("Note.qrAccept")}
      </label>
      {session.demo ? <p className="text-sm">{t("Note.qrDemo")}</p> : null}
      <Button
        className="self-start"
        disabled={
          !accepted || !region || state.s === "busy" || state.s === "done"
        }
        onClick={make}
      >
        {state.s === "busy" ? t("Note.qrMaking") : t("Note.qrMake")}
      </Button>
      {state.s === "done" && state.expires ? (
        <p role="status">
          {t("Note.qrAdded", { date: formatDate(state.expires, locale) })}
        </p>
      ) : null}
      {state.s === "error" ? <p role="alert">{t(state.key)}</p> : null}
      {session.demo ? (
        <Link
          href="/demo/doctor"
          className="inline-flex min-h-11 items-center underline underline-offset-4"
        >
          {t("Shell.demoDoctor")}
        </Link>
      ) : (
        <Link
          href="/note/withdraw"
          className="inline-flex min-h-11 items-center underline underline-offset-4"
        >
          {t("Note.withdrawLink")}
        </Link>
      )}
    </Card>
  );
}
