"use client";
/** The in-app reminder 28 days after a note with a QR code (DP23, Req 18.4); never a push. */
import { useLocale } from "next-intl";
import { useSyncExternalStore } from "react";

import { formatDate } from "@/components/format";
import { ButtonLink, Card } from "@/components/ui";
import { Button } from "@/components/ui";
import { useDemo } from "@/demo/session";
import { dismiss } from "@/flow/loop";
import { dueReminders, localDate } from "@/store/reminders";
import { tokens } from "@/store/tokens";
import { useT } from "@/theme/words";

export function ReminderCard() {
  const t = useT();
  const locale = useLocale();
  const demo = useDemo();
  const doc = useSyncExternalStore(
    tokens.subscribe,
    tokens.getSnapshot,
    () => null,
  );
  const ready = useSyncExternalStore(
    () => () => {},
    () => true,
    () => false,
  );
  if (!ready || !doc || demo) return null;
  const due = dueReminders(doc.notes, localDate());
  return (
    <>
      {due.map((n) => (
        <Card key={n.token} role="status" data-testid="reminder">
          <p className="font-bold">{t("Reminder.title")}</p>
          <p>{t("Reminder.body", { date: formatDate(n.issuedOn, locale) })}</p>
          <div className="flex flex-wrap gap-3">
            <ButtonLink
              href={{
                pathname: "/donate",
                hash: n.events?.[0] ? `event=${n.events[0]}` : "",
              }}
            >
              {t("Reminder.report")}
            </ButtonLink>
            <Button
              variant="quiet"
              onClick={() => tokens.update((d) => dismiss(d, n.token))}
            >
              {t("Reminder.dismiss")}
            </Button>
          </div>
        </Card>
      ))}
    </>
  );
}
