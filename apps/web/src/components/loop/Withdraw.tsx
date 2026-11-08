"use client";
/**
 * Withdraw outcome-loop data (design §10.4, Req 18.5): the tokens kept on this device by month
 * and coverage; the same confirmation whether or not answers were stored; a token is removed only
 * after the API confirmed (P29). Not available in demo (no token exists there).
 */
import { useLocale } from "next-intl";
import { useState, useSyncExternalStore } from "react";

import { formatDate } from "@/components/format";
import { StateView } from "@/components/StateView";
import { Button, Card, PageTitle } from "@/components/ui";
import { useSession } from "@/flow/janus";
import { withdrawToken } from "@/flow/loop";
import { tokens } from "@/store/tokens";
import { useT } from "@/theme/words";

export function Withdraw() {
  const t = useT();
  const locale = useLocale();
  const session = useSession();
  const doc = useSyncExternalStore(
    tokens.subscribe,
    tokens.getSnapshot,
    () => null,
  );
  const [busy, setBusy] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  if (!session.ready || !doc) return <StateView state="loading" />;
  if (session.demo)
    return <StateView state="empty" message={t("Demo.neverDonated")} />;
  return (
    <>
      <PageTitle>{t("Withdraw.title")}</PageTitle>
      <p>{t("Withdraw.intro")}</p>
      {done ? (
        <p role="status" className="card p-3 font-bold">
          {t("Withdraw.done")}
        </p>
      ) : null}
      {error ? <StateView state="error" messageKey={error} /> : null}
      {doc.notes.length === 0 ? (
        <StateView state="empty" message={t("Withdraw.none")} />
      ) : (
        <ul className="flex flex-col gap-3">
          {doc.notes.map((n) => (
            <Card as="li" key={n.token}>
              <p>
                {t("Withdraw.item", {
                  date: formatDate(n.issuedOn, locale),
                  covered: n.findingsCovered,
                  total: n.findingsTotal,
                })}
              </p>
              <Button
                variant="secondary"
                className="self-start"
                disabled={busy !== null || !session.loop}
                onClick={async () => {
                  if (!session.loop) return;
                  setBusy(n.token);
                  setError(null);
                  const r = await withdrawToken(
                    tokens.get(),
                    n.token,
                    session.loop,
                  );
                  tokens.set(r.doc);
                  setBusy(null);
                  if (r.result.ok) setDone(true);
                  else setError(r.result.error.messageKey);
                }}
              >
                {busy === n.token
                  ? t("Withdraw.working")
                  : t("Withdraw.button")}
              </Button>
            </Card>
          ))}
        </ul>
      )}
    </>
  );
}
