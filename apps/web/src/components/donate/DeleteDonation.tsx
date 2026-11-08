"use client";
/** Delete a donation with its token (Req 20.6): pasted, or one kept on this device. */
import { useState, useSyncExternalStore } from "react";

import { deletionBody } from "@/api/builders";
import { StateView } from "@/components/StateView";
import { Button, Card, PageTitle } from "@/components/ui";
import { useSession } from "@/flow/janus";
import { tokens } from "@/store/tokens";
import { useT } from "@/theme/words";

export function DeleteDonation() {
  const t = useT();
  const session = useSession();
  const doc = useSyncExternalStore(
    tokens.subscribe,
    tokens.getSnapshot,
    () => null,
  );
  const [value, setValue] = useState("");
  const [phase, setPhase] = useState<
    { s: "edit" | "busy" | "done" } | { s: "error"; key: string }
  >({ s: "edit" });
  if (!session.ready || !doc) return <StateView state="loading" />;
  if (session.demo)
    return <StateView state="empty" message={t("Demo.neverDonated")} />;

  const del = async () => {
    if (!session.loop) return;
    let body;
    try {
      body = deletionBody(value.trim());
    } catch {
      setPhase({ s: "error", key: "Donate.delete.invalid_token" });
      return;
    }
    setPhase({ s: "busy" });
    const r = await session.loop.deleteContribution(body);
    if (r.ok || (r.error.kind === "http" && r.error.status === 404)) {
      tokens.update((d) => ({
        ...d,
        deletions: d.deletions.filter((x) => x.token !== body.deletion_token),
      }));
    }
    if (r.ok) setPhase({ s: "done" });
    else setPhase({ s: "error", key: r.error.messageKey });
  };

  return (
    <>
      <PageTitle>{t("Donate.delete.title")}</PageTitle>
      <p>{t("Donate.delete.intro")}</p>
      <Card>
        <label className="flex flex-col gap-1">
          <span className="font-bold">{t("Donate.delete.label")}</span>
          <input
            value={value}
            onChange={(e) => setValue(e.target.value)}
            autoComplete="off"
            spellCheck={false}
            className="mono min-h-11 rounded-[var(--radius-button)] border-2 border-muted bg-surface px-3 text-fg"
          />
        </label>
        {doc.deletions.length ? (
          <fieldset className="flex flex-col gap-1">
            <legend className="font-bold">{t("Donate.delete.kept")}</legend>
            {doc.deletions.map((d) => (
              <label key={d.token} className="flex min-h-11 items-center gap-3">
                <input
                  type="radio"
                  name="kept"
                  checked={value === d.token}
                  onChange={() => setValue(d.token)}
                  className="size-5 accent-[var(--accent)]"
                />
                {d.storedSummary.reportWeek} · {d.storedSummary.event}
              </label>
            ))}
          </fieldset>
        ) : null}
        <Button
          className="self-start"
          onClick={del}
          disabled={phase.s === "busy" || !value.trim()}
        >
          {phase.s === "busy"
            ? t("Donate.delete.working")
            : t("Donate.delete.submit")}
        </Button>
      </Card>
      {phase.s === "done" ? (
        <p role="status" className="card p-3 font-bold">
          {t("Donate.delete.done")}
        </p>
      ) : null}
      {phase.s === "error" ? (
        <StateView state="error" messageKey={phase.key} />
      ) : null}
    </>
  );
}
