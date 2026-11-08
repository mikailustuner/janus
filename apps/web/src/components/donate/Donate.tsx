"use client";
/**
 * Donation with consent (design §12, Req 20): the emergency notice first, the event picker with
 * its safety line, the fields that are stored and nothing else, "what will be stored", the
 * versioned consent text with an explicit checkbox, then the deletion token shown once. In demo
 * the whole screen is replaced by one sentence: demo data is never donated.
 */
import { useMemo, useState, useSyncExternalStore } from "react";

import type { ContributionCreated, LoopRegion } from "@/api/contracts";
import { AGE_BANDS } from "@/api/builders";
import { EmergencyNotice } from "@/components/EmergencyNotice";
import { keyName } from "@/components/names";
import { useUserRegion } from "@/components/region";
import { SafetyLine } from "@/components/SafetyLine";
import { StateView } from "@/components/StateView";
import {
  Button,
  ButtonLink,
  Card,
  PageTitle,
  SectionTitle,
} from "@/components/ui";
import { DONATION_CONSENT_VERSION } from "@/consent/versions";
import { donationRequest, type DonationForm } from "@/flow/donate";
import { useSession } from "@/flow/janus";
import { listIngredientKeys } from "@/store/list";
import { tokens } from "@/store/tokens";
import { useT } from "@/theme/words";
import { useVocabulary } from "@/vocabulary/use";

const hashEvent = () =>
  /(?:^|[#&])event=([a-z0-9_.-]{1,40})/.exec(
    typeof location === "undefined" ? "" : location.hash,
  )?.[1] ?? null;

export function Donate() {
  const t = useT();
  const session = useSession();
  const vocab = useVocabulary();
  const userRegion = useUserRegion();
  const preselected = useSyncExternalStore(
    () => () => {},
    hashEvent,
    () => null,
  );
  const keys = useMemo(
    () => listIngredientKeys(session.items),
    [session.items],
  );
  const [form, setForm] = useState<
    Omit<DonationForm, "event" | "region"> & {
      event: string | null | undefined;
      region: LoopRegion | null | undefined;
    }
  >({
    event: undefined,
    direction: "adverse",
    ingredients: [],
    ageBand: null,
    sex: null,
    region: undefined, // until chosen: the user region when it is TR, EU or US
    consent: false,
  });
  const [filter, setFilter] = useState("");
  const [phase, setPhase] = useState<
    | { s: "edit" }
    | { s: "sending" }
    | { s: "error"; key: string }
    | { s: "done"; out: ContributionCreated; kept: boolean; copied: boolean }
  >({ s: "edit" });
  const event = form.event === undefined ? preselected : form.event;
  const region =
    form.region === undefined
      ? (["TR", "EU", "US"] as string[]).includes(userRegion)
        ? (userRegion as LoopRegion)
        : null
      : form.region;

  if (!session.ready || !vocab) return <StateView state="loading" />;
  if (session.demo)
    return (
      <>
        <PageTitle>{t("Donate.title")}</PageTitle>
        <p className="card p-4" data-testid="demo-no-donation">
          {t("Demo.neverDonated")}
        </p>
      </>
    );
  if (keys.length === 0)
    return (
      <>
        <PageTitle>{t("Donate.title")}</PageTitle>
        <StateView
          state="empty"
          message={t("Donate.noItems")}
          action={<ButtonLink href="/scan">{t("Medicines.add")}</ButtonLink>}
        />
      </>
    );

  const events = Object.entries(vocab.vocab.events)
    .map(([k, e]) => ({ key: k, label: e.label, line: e.safety_line }))
    .filter((e) =>
      e.label.toLocaleLowerCase().includes(filter.toLocaleLowerCase()),
    )
    .sort((a, b) => a.label.localeCompare(b.label));
  const chosen = event ? vocab.vocab.events[event] : undefined;
  const set = (p: Partial<typeof form>) => setForm((f) => ({ ...f, ...p }));
  const bandText = (b: number) =>
    b === 90 ? t("Donate.age90") : t("Donate.age", { from: b, to: b + 4 });

  if (phase.s === "done") {
    const s = phase.out.stored;
    return (
      <>
        <PageTitle>{t("Donate.doneTitle")}</PageTitle>
        <Card>
          <p className="font-bold">{t("Donate.token")}</p>
          <p
            className="mono rounded bg-chip p-3 text-chip-fg"
            data-testid="deletion-token"
          >
            {phase.out.deletion_token}
          </p>
          <p>{t("Donate.tokenOnce")}</p>
          <p className="text-sm text-muted">
            {t("Donate.storedRecord", {
              summary: [
                s.report_week,
                bandText(s.age_band),
                s.sex ? t(`Donate.${s.sex}`) : t("Donate.notGiven"),
                t(`Common.region.${s.region}`),
                s.ingredients.map((k) => keyName(vocab, k, null)).join(", "),
                vocab.vocab.events[s.event]?.label ?? s.event,
                t(`Donate.${s.direction}`),
              ].join(" · "),
            })}
          </p>
          <div className="flex flex-wrap gap-3">
            <Button
              disabled={phase.kept}
              onClick={() => {
                tokens.update((d) => ({
                  ...d,
                  deletions: [
                    ...d.deletions,
                    {
                      token: phase.out.deletion_token,
                      storedSummary: {
                        reportWeek: s.report_week,
                        event: s.event,
                        direction: s.direction,
                      },
                    },
                  ],
                }));
                setPhase({ ...phase, kept: true });
              }}
            >
              {phase.kept ? t("Donate.kept") : t("Donate.keep")}
            </Button>
            <Button
              variant="secondary"
              onClick={async () => {
                try {
                  await navigator.clipboard.writeText(phase.out.deletion_token);
                  setPhase({ ...phase, copied: true });
                } catch {
                  /* the token stays on screen */
                }
              }}
            >
              {phase.copied ? t("Donate.copied") : t("Donate.copy")}
            </Button>
          </div>
        </Card>
      </>
    );
  }

  const submit = async () => {
    const r = donationRequest(
      { ...form, event: event ?? null, region },
      keys,
      false,
    );
    if (!r.ok)
      return setPhase({
        s: "error",
        key:
          r.reason === "consent" ? "Donate.needConsent" : "Donate.needFields",
      });
    if (!session.loop) return;
    setPhase({ s: "sending" });
    const out = await session.loop.contribute(r.body);
    if (out.ok)
      setPhase({ s: "done", out: out.data, kept: false, copied: false });
    else setPhase({ s: "error", key: out.error.messageKey });
  };

  const c = `Donate.consent.${DONATION_CONSENT_VERSION}`;
  return (
    <>
      <EmergencyNotice />
      <PageTitle>{t("Donate.title")}</PageTitle>
      <p>{t("Donate.intro")}</p>
      <Card>
        <fieldset className="flex flex-col gap-2">
          <legend className="font-bold">{t("Donate.event")}</legend>
          <label className="flex flex-col gap-1 text-sm">
            {t("Donate.eventSearch")}
            <input
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              className="min-h-11 rounded-[var(--radius-button)] border-2 border-muted bg-surface px-3 text-base text-fg"
            />
          </label>
          <div className="flex max-h-72 flex-col overflow-y-auto">
            {events.map((e) => (
              <label key={e.key} className="flex min-h-11 items-center gap-3">
                <input
                  type="radio"
                  name="event"
                  checked={event === e.key}
                  onChange={() => set({ event: e.key })}
                  className="size-5 shrink-0 accent-[var(--accent)]"
                />
                {e.label}
              </label>
            ))}
          </div>
          {chosen?.safety_line ? (
            <SafetyLine code={chosen.safety_line} />
          ) : null}
        </fieldset>
      </Card>
      <Card>
        <fieldset className="flex flex-col gap-1">
          <legend className="font-bold">{t("Donate.direction")}</legend>
          {(["adverse", "benefit"] as const).map((d) => (
            <label key={d} className="flex min-h-11 items-center gap-3">
              <input
                type="radio"
                name="direction"
                checked={form.direction === d}
                onChange={() => set({ direction: d })}
                className="size-5 accent-[var(--accent)]"
              />
              {t(`Donate.${d}`)}
            </label>
          ))}
        </fieldset>
        <fieldset className="flex flex-col gap-1">
          <legend className="font-bold">{t("Donate.ingredients")}</legend>
          {keys.map((k) => (
            <label key={k} className="flex min-h-11 items-center gap-3">
              <input
                type="checkbox"
                checked={form.ingredients.includes(k)}
                disabled={
                  !form.ingredients.includes(k) && form.ingredients.length >= 20
                }
                onChange={(e) =>
                  set({
                    ingredients: e.target.checked
                      ? [...form.ingredients, k]
                      : form.ingredients.filter((x) => x !== k),
                  })
                }
                className="size-5 accent-[var(--accent)]"
              />
              {keyName(vocab, k, null)}
            </label>
          ))}
        </fieldset>
        <label className="flex flex-col gap-1">
          <span className="font-bold">{t("Donate.ageBand")}</span>
          <select
            value={form.ageBand ?? ""}
            onChange={(e) =>
              set({ ageBand: e.target.value ? Number(e.target.value) : null })
            }
            className="min-h-11 rounded-[var(--radius-button)] border-2 border-muted bg-surface px-3 text-fg"
          >
            <option value="" className="bg-bg text-fg">
              —
            </option>
            {AGE_BANDS.map((b) => (
              <option key={b} value={b} className="bg-bg text-fg">
                {bandText(b)}
              </option>
            ))}
          </select>
        </label>
        <fieldset className="flex flex-col gap-1">
          <legend className="font-bold">{t("Donate.sex")}</legend>
          {(["female", "male", null] as const).map((x) => (
            <label
              key={x ?? "none"}
              className="flex min-h-11 items-center gap-3"
            >
              <input
                type="radio"
                name="sex"
                checked={form.sex === x}
                onChange={() => set({ sex: x })}
                className="size-5 accent-[var(--accent)]"
              />
              {x ? t(`Donate.${x}`) : t("Donate.notGiven")}
            </label>
          ))}
        </fieldset>
        <fieldset className="flex flex-col gap-1">
          <legend className="font-bold">{t("Donate.region")}</legend>
          {(["TR", "EU", "US"] as const).map((r) => (
            <label key={r} className="flex min-h-11 items-center gap-3">
              <input
                type="radio"
                name="region"
                checked={region === r}
                onChange={() => set({ region: r })}
                className="size-5 accent-[var(--accent)]"
              />
              {t(`Common.region.${r}`)}
            </label>
          ))}
        </fieldset>
      </Card>
      <Card aria-labelledby="stored">
        <SectionTitle id="stored">{t("Donate.storedTitle")}</SectionTitle>
        <ul className="list-disc pl-5 text-sm">
          <li>{t("Donate.storedEvent", { event: chosen?.label ?? "—" })}</li>
          <li>
            {t("Donate.storedDirection", {
              direction: t(`Donate.${form.direction}`),
            })}
          </li>
          <li>
            {t("Donate.storedIngredients", {
              list:
                form.ingredients
                  .map((k) => keyName(vocab, k, null))
                  .join(", ") || "—",
            })}
          </li>
          <li>
            {t("Donate.storedAge", {
              band: form.ageBand === null ? "—" : bandText(form.ageBand),
            })}
          </li>
          <li>
            {t("Donate.storedSex", {
              sex: form.sex ? t(`Donate.${form.sex}`) : t("Donate.notGiven"),
            })}
          </li>
          <li>
            {t("Donate.storedRegion", {
              region: region ? t(`Common.region.${region}`) : "—",
            })}
          </li>
          <li>{t("Donate.storedWeek")}</li>
          <li>{t("Donate.storedConsent")}</li>
        </ul>
        <p className="text-sm">{t("Donate.storedNothingElse")}</p>
      </Card>
      <Card aria-labelledby="consent">
        <SectionTitle id="consent">{t(`${c}.heading`)}</SectionTitle>
        <p>{t(`${c}.body`)}</p>
        <p>{t(`${c}.delete`)}</p>
        <label className="flex min-h-11 items-center gap-3 font-bold">
          <input
            type="checkbox"
            checked={form.consent}
            onChange={(e) => set({ consent: e.target.checked })}
            className="size-5 shrink-0 accent-[var(--accent)]"
          />
          {t(`${c}.check`)}
        </label>
      </Card>
      {phase.s === "error" ? (
        <StateView state="error" messageKey={phase.key} />
      ) : null}
      <div className="flex flex-wrap gap-3">
        <Button
          onClick={submit}
          disabled={phase.s === "sending"}
          data-testid="donate-submit"
        >
          {phase.s === "sending" ? t("Donate.sending") : t("Donate.submit")}
        </Button>
        <ButtonLink href="/donate/delete" variant="quiet">
          {t("Donate.deleteLink")}
        </ButtonLink>
      </div>
    </>
  );
}
