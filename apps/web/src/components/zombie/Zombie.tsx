"use client";
/**
 * Zombie Alert screens (zombie-alert Req 3–6): the watcher mounted in the shell, the alert card
 * (home, results, note), "What changed" on the note, the Settings switch and the demo button.
 * Red (`--risk`) only on the "Retracted" label and its icon (design.md: retracted evidence).
 */
import { useLocale } from "next-intl";
import { useEffect, useId, useState } from "react";

import { HttpClient } from "@/api/client";
import { Switch } from "@/components/Field";
import { AlertIcon } from "@/components/icons";
import { Button, ButtonLink, Card, SectionTitle } from "@/components/ui";
import { demoPatient, useDemo } from "@/demo/session";
import {
  canSimulate,
  dismissAlerts,
  dismissUpdate,
  notify,
  runCheck,
  setNotify,
  simulate,
  useNotifyOptIn,
  useZombie,
} from "@/flow/useZombie";
import { DAY, HOUR, isDue, type Alert } from "@/flow/zombie";
import { zombie } from "@/store/zombie";
import { useT, useThemeWord } from "@/theme/words";

const http = new HttpClient();

/** Checks on open and once a day while visible (Req 2.1, 2.2, 2.7, DP4); renders nothing. */
export function ZombieWatch() {
  const demo = useDemo();
  const t = useT();
  const locale = useLocale();
  const body = t("ZombieAlert.notification");
  const url = `/${locale}/note`;
  useEffect(() => {
    if (demo) return;
    const run = (gap: number) => {
      // Read the session directly: during hydration the hook value may still be the default.
      if (demoPatient() || document.visibilityState !== "visible") return;
      if (!isDue(zombie.get().checkedAt, Date.now(), gap)) return;
      void runCheck(http).then((alerts) => {
        if (alerts.length && zombie.get().notify) void notify(body, url);
      });
    };
    run(HOUR);
    const timer = setInterval(() => run(DAY), HOUR);
    const onVisible = () => run(DAY);
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [demo, body, url]);
  return null;
}

function Retracted({ simulated }: { simulated: boolean }) {
  const w = useThemeWord();
  const t = useT();
  return (
    <span
      className="mono inline-flex w-max items-center rounded-sm border-2 border-risk px-1.5 py-0.5 text-xs font-bold tracking-wider text-risk uppercase"
      data-testid="zombie-retracted"
    >
      {simulated ? t("ZombieAlert.simulatedStamp") : w("Evidence.stamp")}
    </span>
  );
}

const doiUrl = (doi: string) => `https://doi.org/${encodeURI(doi)}`;
/** The Crossref test prefix of the demo notice does not resolve: shown as text, not a link. */
const resolvable = (doi: string) => !doi.startsWith("10.5555/");

function Source({ a }: { a: Alert }) {
  const t = useT();
  const n = a.notice;
  return (
    <li className="flex min-w-0 flex-col gap-1 border-t border-line pt-2">
      {/* Safety audit A1: in the demo the label comes first, before the real paper's title. */}
      {a.simulated ? (
        <p className="text-sm font-bold" data-testid="zombie-simulated">
          {t("ZombieAlert.simulated")}
        </p>
      ) : null}
      <Retracted simulated={a.simulated} />
      <p className="font-bold [overflow-wrap:anywhere]">
        {a.title ?? a.evidenceId}
      </p>
      {a.doi ? (
        <a
          href={doiUrl(a.doi)}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex min-h-11 w-max max-w-full items-center underline underline-offset-4 [overflow-wrap:anywhere]"
        >
          {t("ZombieAlert.doi", { doi: a.doi })}
        </a>
      ) : null}
      {n?.url || n?.doi ? (
        n.url || (n.doi && resolvable(n.doi)) ? (
          <a
            href={n.url ?? doiUrl(n.doi!)}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex min-h-11 w-max max-w-full items-center underline underline-offset-4 [overflow-wrap:anywhere]"
          >
            {t("ZombieAlert.notice", { doi: n.doi ?? n.url! })}
          </a>
        ) : (
          <p className="mono text-sm [overflow-wrap:anywhere]">
            {t("ZombieAlert.notice", { doi: n.doi! })}
          </p>
        )
      ) : null}
    </li>
  );
}

/**
 * The alert (Req 3.3–3.5). On the note screen it carries "Update the note"; elsewhere it opens
 * the note screen.
 */
export function ZombieAlertCard({
  onUpdate,
  busy = false,
}: {
  onUpdate?: () => void;
  busy?: boolean;
}) {
  const t = useT();
  const w = useThemeWord();
  const id = useId();
  const { ready, demo, doc } = useZombie();
  if (!ready || doc.alerts.length === 0) return null;
  return (
    <Card aria-labelledby={id} data-testid="zombie-alert" className="no-print">
      <div className="flex items-start gap-3">
        <AlertIcon className="mt-1 shrink-0 text-risk" />
        <div className="flex min-w-0 flex-col gap-2">
          <h2 id={id} className="text-xl leading-snug font-semibold">
            {doc.alerts.some((a) => a.simulated)
              ? t("ZombieAlert.simulatedTitle")
              : w("ZombieAlert.title")}
          </h2>
          <p>{t("ZombieAlert.body")}</p>
        </div>
      </div>
      <ul className="flex flex-col gap-2">
        {doc.alerts.map((a) => (
          <Source key={a.key} a={a} />
        ))}
      </ul>
      <p className="text-sm text-muted">{t("ZombieAlert.noChange")}</p>
      <div className="flex flex-wrap gap-3">
        {onUpdate ? (
          <Button onClick={onUpdate} disabled={busy}>
            {busy ? t("ZombieAlert.updating") : t("ZombieAlert.update")}
          </Button>
        ) : (
          <ButtonLink href="/note">{t("ZombieAlert.openNote")}</ButtonLink>
        )}
        <Button variant="quiet" onClick={() => dismissAlerts(demo)}>
          {t("ZombieAlert.dismiss")}
        </Button>
      </div>
    </Card>
  );
}

/** "What changed" after the update (Req 5.2, 5.5). */
export function ZombieChanges() {
  const t = useT();
  const id = useId();
  const { ready, demo, doc } = useZombie();
  const u = doc.update;
  if (!ready || !u) return null;
  const none = u.removed.length === 0 && u.changed.length === 0;
  return (
    <Card
      aria-labelledby={id}
      data-testid="zombie-changes"
      className="no-print"
    >
      <SectionTitle id={id}>{t("ZombieAlert.changesTitle")}</SectionTitle>
      <p>{t("ZombieAlert.changesIntro")}</p>
      <p>{t("ZombieAlert.passOn")}</p>
      <ul className="flex flex-col gap-2">
        {u.alerts.map((a) => (
          <Source key={a.key} a={a} />
        ))}
      </ul>
      {none ? <p>{t("ZombieAlert.nothingElse")}</p> : null}
      {u.removed.length ? (
        <section className="flex flex-col gap-2">
          <h3 className="font-semibold">{t("ZombieAlert.removed")}</h3>
          <ul className="flex flex-col gap-2">
            {u.removed.map((s) => (
              <li
                key={s.id}
                lang={u.language}
                data-testid="zombie-removed"
                className="rounded-[var(--radius-button)] bg-chip px-3 py-2 text-chip-fg"
              >
                <del className="decoration-1">{s.text}</del>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      {u.changed.length ? (
        <section className="flex flex-col gap-2">
          <h3 className="font-semibold">{t("ZombieAlert.changed")}</h3>
          <ul className="flex flex-col gap-3">
            {u.changed.map(({ before, after }) => (
              <li
                key={before.id}
                data-testid="zombie-changed"
                className="flex flex-col gap-1"
              >
                <p className="text-sm text-muted">{t("ZombieAlert.before")}</p>
                <p lang={u.language}>
                  <del className="decoration-1">{before.text}</del>
                </p>
                <p className="text-sm text-muted">{t("ZombieAlert.after")}</p>
                <p>{after.text}</p>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      <Button
        variant="quiet"
        className="self-start"
        onClick={() => dismissUpdate(demo)}
      >
        {t("ZombieAlert.dismiss")}
      </Button>
    </Card>
  );
}

/** Settings › Source updates (Req 4.1, 4.2, 4.5). */
export function ZombieSettings() {
  const t = useT();
  const id = useId();
  const on = useNotifyOptIn();
  const demo = !!useDemo();
  const [state, setState] = useState<"denied" | "unsupported" | null>(null);
  return (
    <Card aria-labelledby={id} data-testid="zombie-settings">
      <SectionTitle id={id}>{t("ZombieAlert.settingsTitle")}</SectionTitle>
      <p>{t("ZombieAlert.settingsBody")}</p>
      <Switch
        label={t("ZombieAlert.notify")}
        hint={t("ZombieAlert.notifyHint")}
        checked={on}
        onChange={async (v) => {
          const r = await setNotify(v, demo);
          setState(r === "denied" || r === "unsupported" ? r : null);
        }}
      />
      {state ? (
        <p role="status" className="text-sm font-bold">
          {t(
            state === "denied"
              ? "ZombieAlert.notifyDenied"
              : "ZombieAlert.notifyUnsupported",
          )}
        </p>
      ) : null}
    </Card>
  );
}

/** The demo note's button (Req 6.2, 6.5); nothing is sent. */
export function DemoRetraction() {
  const t = useT();
  const locale = useLocale();
  const { ready, demo, doc } = useZombie();
  const optIn = useNotifyOptIn();
  if (!ready || !demo || !canSimulate(doc)) return null;
  return (
    <Card className="no-print" data-testid="zombie-simulate">
      <Button
        variant="secondary"
        className="self-start"
        onClick={() => {
          if (simulate().length && optIn)
            void notify(t("ZombieAlert.notificationDemo"), `/${locale}/note`);
        }}
      >
        {t("ZombieAlert.simulate")}
      </Button>
      <p className="text-sm text-muted">{t("ZombieAlert.simulateHint")}</p>
    </Card>
  );
}
