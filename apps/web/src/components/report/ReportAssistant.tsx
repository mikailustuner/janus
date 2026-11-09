"use client";
/**
 * The Report Assistant (report-assistant design §4, Req 2–9): a draft of a suspected-side-effect
 * report for the official form of the chosen authority, built on the device from the list in the
 * browser (or the demo patient, or the doctor note's codes). Nothing is sent and nothing is
 * stored: the inputs live in this component's state (DP7, DP8). The person copies each value into
 * the official form and submits it themselves (DP1).
 */
import { useLocale } from "next-intl";
import { useEffect, useMemo, useState, type ReactNode } from "react";

import type { Locale } from "@/api/contracts";
import {
  GroupedList,
  LargeTitle,
  Row,
  SegmentedControl,
} from "@/components/cards";
import { EmergencyNotice } from "@/components/EmergencyNotice";
import { SelectField } from "@/components/Field";
import { DocIcon, PrintIcon } from "@/components/icons";
import { MonthPicker } from "@/components/MonthPicker";
import { candidateIngredients, keyName } from "@/components/names";
import { useUserRegion } from "@/components/region";
import { SafetyLine } from "@/components/SafetyLine";
import { StateView } from "@/components/StateView";
import { Button, Card } from "@/components/ui";
import { useSession } from "@/flow/janus";
import {
  channel as channelById,
  contactChannels,
  fieldList,
  FINDER_ID,
  formChannels,
  type Channel,
  type Country,
  type Region,
} from "@/report/channels";
import {
  buildDraft,
  copyAll,
  mappingFor,
  otherType,
  outcomeOptions,
  requiredParts,
  type DraftRow,
  type OtherType,
} from "@/report/draft";
import { parsePrefill, type Prefill } from "@/report/fragment";
import type { DraftKey } from "@/report/mapping";
import type { Item } from "@/store/list";
import { useT } from "@/theme/words";
import { eventKeyForRule, load, type Loaded } from "@/vocabulary";

const NS = "ReportAssistant";
const OPTION_SETS: Record<string, string> = {
  "tr-tufam-eform": "trEform",
  "tr-tufam-docx": "trDocx",
};
const EXTERNAL = {
  target: "_blank",
  rel: "noopener noreferrer",
} as const;

function useHashPrefill(): Prefill | null | undefined {
  const [p, setP] = useState<Prefill | null | undefined>(undefined);
  useEffect(() => {
    const read = () => setP(parsePrefill(location.hash));
    read();
    window.addEventListener("hashchange", read);
    return () => window.removeEventListener("hashchange", read);
  }, []);
  return p;
}

/** The vocabulary with an error state (Req 10.2); `useVocabulary` has none. */
function useVocab(locale: Locale) {
  const [state, setState] = useState<
    { s: "loading" } | { s: "ok"; v: Loaded } | { s: "error" }
  >({ s: "loading" });
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let live = true;
    load(locale).then(
      (v) => live && setState({ s: "ok", v }),
      () => live && setState({ s: "error" }),
    );
    return () => {
      live = false;
    };
  }, [locale, attempt]);
  return {
    state,
    retry: () => {
      setState({ s: "loading" });
      setAttempt((a) => a + 1);
    },
  };
}

interface Other {
  id: string;
  label: string;
  type: OtherType;
}

interface Init {
  mode: "patient" | "doctor";
  demo: boolean;
  suspect: number | null;
  box: string;
  ingredient: string;
  eventKey: string | null;
  others: Other[] | null;
}

function itemIngredients(v: Loaded, item: Item): string {
  return candidateIngredients(v, item.candidate, item.choices)
    .map((n) => n.name.text ?? n.published)
    .filter(Boolean)
    .join(", ");
}

function itemLabel(v: Loaded, item: Item): string {
  return item.boxName || itemIngredients(v, item);
}

function initFrom(
  p: Prefill | null,
  v: Loaded,
  items: Item[],
  demo: boolean,
): Init {
  if (p?.src === "doctor")
    return {
      mode: "doctor",
      // The fragment alone says whether the note is a demo (safety audit A4).
      demo: p.demo,
      suspect: null,
      box: "",
      ingredient: keyName(v, p.ingredient, null),
      eventKey: eventKeyForRule(v, p.rule),
      // Ingredient keys only: the product type is not known (3500B E11, DP13).
      others: p.others.map((k) => ({
        id: k,
        label: keyName(v, k, null),
        type: "unknown",
      })),
    };
  const event =
    p?.src === "finding" && p.event && v.vocab.events[p.event] ? p.event : null;
  const listed =
    p?.src === "finding" ? p.items.filter((i) => i < items.length) : [];
  const suspect = listed[0] ?? (items.length ? 0 : null);
  return {
    mode: "patient",
    demo,
    suspect,
    box: suspect !== null ? items[suspect]!.boxName : "",
    ingredient:
      p?.src === "finding" && listed.length
        ? keyName(v, p.ingredient, null)
        : suspect !== null
          ? itemIngredients(v, items[suspect]!)
          : "",
    eventKey: event,
    others: null,
  };
}

export function ReportAssistant() {
  const t = useT();
  const locale = useLocale() as Locale;
  const session = useSession();
  const vocab = useVocab(locale);
  const prefill = useHashPrefill();
  const userRegion = useUserRegion();

  if (vocab.state.s === "error")
    return (
      <StateView
        state="error"
        messageKey={`${NS}.states.vocabulary`}
        retry={vocab.retry}
      />
    );
  if (!session.ready || vocab.state.s !== "ok" || prefill === undefined)
    return <StateView state="loading" />;
  const v = vocab.state.v;
  const init = initFrom(prefill, v, session.items, session.demo !== null);
  const region: Region | null =
    userRegion === "TR" || userRegion === "EU" || userRegion === "US"
      ? userRegion
      : null;
  return (
    <Assistant
      // A new prefill (another finding) starts a new draft.
      key={`${location.hash}|${session.demo}`}
      t={t}
      v={v}
      init={init}
      items={init.mode === "doctor" ? [] : session.items}
      defaultRegion={region}
      locale={locale}
    />
  );
}

function Assistant({
  t,
  v,
  init,
  items,
  defaultRegion,
  locale,
}: {
  t: ReturnType<typeof useT>;
  v: Loaded;
  init: Init;
  items: Item[];
  defaultRegion: Region | null;
  locale: Locale;
}) {
  const hcp = init.mode === "doctor";
  const [region, setRegion] = useState<Region | null>(defaultRegion);
  const [euCountry, setEuCountry] = useState<Country>("DE");
  const country: Country | null =
    region === "EU" ? euCountry : (region as Country | null);
  const forms = useMemo(
    () => (country ? formChannels(country) : []),
    [country],
  );
  const [channelId, setChannelId] = useState<string | null>(null);
  const channel: Channel | null =
    forms.find((c) => c.id === channelId) ?? forms[0] ?? null;

  const [suspect, setSuspect] = useState<number | null>(init.suspect);
  const [box, setBox] = useState(init.box);
  const [ingredient, setIngredient] = useState(init.ingredient);
  const events = useMemo(
    () =>
      Object.entries(v.vocab.events)
        .filter(([, e]) => e.direction === "adverse")
        .sort(([, a], [, b]) => a.label.localeCompare(b.label, locale)),
    [v, locale],
  );
  const [eventKey, setEventKey] = useState<string | null>(init.eventKey);
  const [eventText, setEventText] = useState(
    init.eventKey ? (v.vocab.events[init.eventKey]?.label ?? "") : "",
  );
  const [onset, setOnset] = useState<string | null>(null);
  const [outcome, setOutcome] = useState<{
    option: number | null;
    text: string;
  }>({ option: null, text: "" });
  const [unticked, setUnticked] = useState<ReadonlySet<string>>(new Set());
  const [status, setStatus] = useState("");

  const others: Other[] =
    init.others ??
    items.flatMap((item, i) =>
      i === suspect
        ? []
        : [
            {
              id: item.id,
              label: itemLabel(v, item),
              type: otherType(
                item.candidate.kind === "product"
                  ? item.candidate.product_type
                  : null,
              ),
            },
          ],
    );
  const options = channel ? outcomeOptions(channel, hcp) : [];
  const optionSet = channel
    ? OPTION_SETS[fieldList(channel)?.source.id ?? ""]
    : undefined;
  const draft = channel
    ? buildDraft({
        channel,
        demo: init.demo,
        hcp,
        medicine: { box, ingredient },
        event: eventText,
        onset,
        outcome,
        others: others.map((o) => ({
          label: o.label,
          ticked: !unticked.has(o.id),
          type: o.type,
        })),
      })
    : null;
  const safety = eventKey
    ? (v.vocab.events[eventKey]?.safety_line ?? null)
    : null;
  const lang = channel?.languages[0] ?? "en";
  const translate = channel ? !channel.languages.includes(locale) : false;
  const janusLabel = (k: DraftKey) => t(`${NS}.janus.${k}`);

  const copy = async (text: string, done: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setStatus(done);
    } catch {
      setStatus(t(`${NS}.draft.copyFailed`));
    }
  };

  const rowLabel = (r: DraftRow) => r.field ?? janusLabel(r.key);

  return (
    <div className="report-assistant flex flex-col gap-section">
      <div className="no-print flex max-w-[760px] flex-col gap-group">
        <EmergencyNotice />
        {safety ? <SafetyLine code={safety} /> : null}
        {init.demo ? (
          <p className="chip" data-testid="report-demo-top">
            {t(`${NS}.draft.demo`)}
          </p>
        ) : null}
        <LargeTitle title={t(`${NS}.title`)} summary={t(`${NS}.summary`)} />
        <Card className="gap-stack sm:p-5">
          <p>{t(`${NS}.intro.choice`)}</p>
          <p>{t(`${NS}.intro.what`)}</p>
          <div className="flex flex-col gap-1 border-t border-line pt-3 text-sm text-muted">
            <p className="text-fg" data-testid="under-reporting">
              {t(`${NS}.intro.fact`)}
            </p>
            <p>{t(`${NS}.intro.caveat`)}</p>
            <p>
              {t(`${NS}.intro.cite`)}{" "}
              <a
                href="https://doi.org/10.2165/00002018-200629050-00003"
                data-inline="true"
                className="mono"
                {...EXTERNAL}
              >
                {t(`${NS}.intro.doi`)}
              </a>
            </p>
          </div>
        </Card>
      </div>

      <div className="grid gap-group lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)] lg:items-start">
        <div className="no-print flex min-w-0 flex-col gap-group">
          <Card className="gap-stack sm:p-5">
            <h2 className="font-body text-lg font-bold">
              {t(`${NS}.where.title`)}
            </h2>
            <SegmentedControl
              legend={t(`${NS}.where.region`)}
              legendVisible
              name="report-region"
              options={(["TR", "EU", "US"] as const).map((r) => ({
                value: r,
                label: t(`Common.region.${r}`),
              }))}
              value={region}
              onChange={(r) => {
                setRegion(r);
                setChannelId(null);
              }}
              variant="pills"
            />
            {region === null ? (
              <p className="text-muted">{t(`${NS}.where.noRegion`)}</p>
            ) : null}
            {region === "EU" ? (
              <SegmentedControl
                legend={t(`${NS}.where.country`)}
                legendVisible
                name="report-country"
                options={(["DE", "FR", "ES", "EU"] as const).map((c) => ({
                  value: c,
                  label: t(`${NS}.where.countries.${c}`),
                }))}
                value={euCountry}
                onChange={(c) => {
                  setEuCountry(c);
                  setChannelId(null);
                }}
                variant="pills"
              />
            ) : null}
            {forms.length > 1 ? (
              <SegmentedControl
                legend={t(`${NS}.where.form`)}
                legendVisible
                name="report-form"
                options={forms.map((c) => ({
                  value: c.id,
                  label: t(`${NS}.where.kind.${c.kind}`),
                }))}
                value={channel?.id}
                onChange={(id) => {
                  setChannelId(id);
                  setOutcome((o) => ({ ...o, option: null }));
                }}
              />
            ) : null}
            {country === "EU" ? (
              <p className="text-sm">
                {t(`${NS}.where.otherEu`)}{" "}
                <a
                  href={channelById(FINDER_ID)!.url}
                  data-testid="finder-link"
                  data-inline="true"
                  className="font-bold"
                  {...EXTERNAL}
                >
                  {t(`${NS}.where.finder`)}
                </a>
              </p>
            ) : null}
            {hcp && country ? <HcpNote t={t} country={country} /> : null}
          </Card>

          <Card className="gap-stack sm:p-5">
            <h2 className="font-body text-lg font-bold">
              {t(`${NS}.what.title`)}
            </h2>
            {hcp ? (
              <p className="text-sm text-muted">{t(`${NS}.hcp.prefilled`)}</p>
            ) : null}
            <fieldset className="flex min-w-0 flex-col gap-3">
              <legend className="mb-1 font-bold">
                {t(`${NS}.what.medicine`)}
              </legend>
              {!hcp && items.length > 0 ? (
                <SelectField
                  label={t(`${NS}.what.choose`)}
                  value={suspect === null ? "" : String(suspect)}
                  options={items.map((item, i) => ({
                    value: String(i),
                    label: itemLabel(v, item),
                  }))}
                  onChange={(s) => {
                    const i = Number(s);
                    setSuspect(i);
                    setBox(items[i]!.boxName);
                    setIngredient(itemIngredients(v, items[i]!));
                  }}
                />
              ) : !hcp ? (
                <p className="text-sm text-muted">{t(`${NS}.what.noList`)}</p>
              ) : null}
              <TextField
                label={t(`${NS}.what.box`)}
                hint={t(`${NS}.what.boxHint`)}
                value={box}
                onChange={setBox}
              />
              {ingredient ? (
                <p className="text-sm" data-testid="report-ingredient">
                  {t(`${NS}.what.ingredient`, { name: ingredient })}
                </p>
              ) : null}
            </fieldset>
            <fieldset className="flex min-w-0 flex-col gap-3 border-t border-line pt-4 [&>legend]:float-left [&>legend]:w-full [&>legend+*]:clear-both">
              <legend className="mb-1 font-bold">
                {t(`${NS}.what.event`)}
              </legend>
              <SelectField
                label={t(`${NS}.what.eventPick`)}
                value={eventKey ?? ""}
                options={[
                  { value: "", label: t(`${NS}.what.eventOwn`) },
                  ...events.map(([k, e]) => ({ value: k, label: e.label })),
                ]}
                onChange={(k) => {
                  setEventKey(k || null);
                  if (k) setEventText(v.vocab.events[k]?.label ?? "");
                }}
              />
              <TextField
                label={t(`${NS}.what.eventText`)}
                hint={t(`${NS}.what.eventHint`)}
                value={eventText}
                onChange={setEventText}
                multiline
              />
            </fieldset>
            <div className="border-t border-line pt-3">
              <MonthPicker
                value={onset}
                onChange={setOnset}
                legend={t(`${NS}.what.onset`)}
              />
            </div>
            <fieldset className="flex min-w-0 flex-col gap-2 border-t border-line pt-4 [&>legend]:float-left [&>legend]:w-full [&>legend+*]:clear-both">
              <legend className="mb-1 font-bold">
                {t(`${NS}.what.outcome`)}
              </legend>
              {options.length && optionSet ? (
                <>
                  <p className="text-sm text-muted">
                    {t(`${NS}.what.outcomeOptions`)}
                  </p>
                  {[null, ...options.map((_, i) => i)].map((i) => (
                    <label
                      key={i ?? "none"}
                      className="flex min-h-11 cursor-pointer items-center gap-3 rounded-[var(--radius-button)] px-2 hover:bg-chip"
                    >
                      <input
                        type="radio"
                        name="report-outcome"
                        checked={outcome.option === i}
                        onChange={() =>
                          setOutcome((o) => ({ ...o, option: i }))
                        }
                        className="size-5 shrink-0 accent-[var(--accent)]"
                      />
                      {i === null ? (
                        <span>{t(`${NS}.what.outcomeNone`)}</span>
                      ) : (
                        <span className="flex flex-col">
                          <span lang={lang}>{options[i]}</span>
                          {translate ? (
                            <span className="text-sm text-muted">
                              {t(`${NS}.options.${optionSet}.${i}`)}
                            </span>
                          ) : null}
                        </span>
                      )}
                    </label>
                  ))}
                </>
              ) : (
                <TextField
                  label={t(`${NS}.what.outcome`)}
                  labelHidden
                  hint={t(`${NS}.what.outcomeFree`)}
                  value={outcome.text}
                  onChange={(text) => setOutcome((o) => ({ ...o, text }))}
                  multiline
                />
              )}
            </fieldset>
            <fieldset className="flex min-w-0 flex-col gap-1 border-t border-line pt-4 [&>legend]:float-left [&>legend]:w-full [&>legend+*]:clear-both">
              <legend className="mb-1 font-bold">
                {t(`${NS}.what.others`)}
              </legend>
              {others.length ? (
                <>
                  <p className="text-sm text-muted">
                    {t(`${NS}.what.othersHint`)}
                  </p>
                  {others.map((o) => (
                    <label
                      key={o.id}
                      className="flex min-h-11 cursor-pointer items-center gap-3 rounded-[var(--radius-button)] px-2 hover:bg-chip"
                    >
                      <input
                        type="checkbox"
                        checked={!unticked.has(o.id)}
                        onChange={(e) =>
                          setUnticked((s) => {
                            const n = new Set(s);
                            if (e.target.checked) n.delete(o.id);
                            else n.add(o.id);
                            return n;
                          })
                        }
                        className="size-5 shrink-0 accent-[var(--accent)]"
                      />
                      <span className="min-w-0 break-words">{o.label}</span>
                    </label>
                  ))}
                </>
              ) : (
                <p className="text-sm text-muted">
                  {t(`${NS}.what.othersNone`)}
                </p>
              )}
            </fieldset>
          </Card>
        </div>

        <div className="flex min-w-0 flex-col gap-group lg:sticky lg:top-4">
          {channel && draft ? (
            <section
              aria-labelledby="report-draft-title"
              className="report-print paper flex min-w-0 flex-col gap-stack rounded-[var(--radius-card)] border border-line bg-bg p-4 text-fg sm:p-5"
              data-testid="report-draft"
            >
              {draft.demo ? (
                <p className="chip" data-testid="report-demo">
                  {t(`${NS}.draft.demo`)}
                </p>
              ) : null}
              <header className="flex flex-col gap-1">
                <p className="text-sm text-muted">{channel.authority}</p>
                <h2
                  id="report-draft-title"
                  className="font-display text-xl leading-snug font-semibold"
                >
                  {t(`${NS}.draft.title`)}
                </h2>
                <p className="font-bold" lang={lang}>
                  {channel.name}
                </p>
                <ChannelFacts t={t} channel={channel} locale={locale} />
              </header>
              <p className="font-bold" data-testid="report-not-sent">
                {t(`${NS}.summary`)}
              </p>
              <ChannelNotes t={t} channel={channel} hcp={hcp} />
              {draft.rows.length === 0 ? (
                <p className="text-muted">{t(`${NS}.draft.empty`)}</p>
              ) : (
                <ol
                  className="grouped-plain border-y border-line"
                  data-testid="report-rows"
                >
                  {draft.rows.map((r, i) => (
                    <li
                      key={`${r.key}-${i}`}
                      className="flex min-w-0 flex-col gap-1"
                      data-key={r.key}
                    >
                      <div className="flex min-w-0 items-start justify-between gap-3">
                        <div className="flex min-w-0 flex-col">
                          {r.section ? (
                            <span className="text-sm text-muted" lang={lang}>
                              {r.section}
                            </span>
                          ) : null}
                          <span
                            className="font-bold break-words"
                            lang={r.label ? lang : undefined}
                            data-testid="report-label"
                          >
                            {rowLabel(r)}
                          </span>
                          {r.label && r.id && translate ? (
                            <span className="text-sm text-muted">
                              {t(`${NS}.labels.${r.id}`)}
                            </span>
                          ) : null}
                          {!r.label ? (
                            <span className="text-sm text-muted">
                              {t(`${NS}.draft.noField`)}
                            </span>
                          ) : null}
                        </div>
                        <Button
                          variant="secondary"
                          className="no-print shrink-0 px-3"
                          aria-label={t(`${NS}.draft.copyLabel`, {
                            label: rowLabel(r),
                          })}
                          onClick={() =>
                            copy(
                              r.value,
                              t(`${NS}.draft.copied`, { label: rowLabel(r) }),
                            )
                          }
                        >
                          {t(`${NS}.draft.copy`)}
                        </Button>
                      </div>
                      <p
                        className="whitespace-pre-wrap break-words"
                        data-testid="report-value"
                      >
                        {r.value}
                      </p>
                      {r.key === "others" || r.key === "othersOtc" ? (
                        <p className="text-sm text-muted">
                          {t(`${NS}.draft.othersEach`)}
                        </p>
                      ) : null}
                      {r.key === "others" && draft.typeUnknown.length ? (
                        <p
                          className="text-sm text-muted"
                          data-testid="report-type-unknown"
                        >
                          {t(`${NS}.draft.typeUnknown`, {
                            count: draft.typeUnknown.length,
                            names: draft.typeUnknown.join("; "),
                          })}
                        </p>
                      ) : null}
                    </li>
                  ))}
                </ol>
              )}
              <p
                role="status"
                aria-live="polite"
                className="no-print min-h-6 text-sm font-bold"
              >
                {status}
              </p>
              <div className="no-print flex flex-wrap gap-3">
                <a
                  href={channel.url}
                  data-testid="report-open"
                  className="inline-flex min-h-11 items-center justify-center gap-2 rounded-[var(--radius-button)] bg-accent px-4 py-2.5 font-bold text-on-accent no-underline hover:opacity-90"
                  {...EXTERNAL}
                >
                  <DocIcon size={18} />
                  {t(
                    `${NS}.draft.${channel.kind === "guidance" ? "openGuidance" : "open"}`,
                  )}
                  <span className="sr-only"> ({t(`${NS}.draft.opens`)})</span>
                </a>
                <Button
                  variant="secondary"
                  disabled={draft.rows.length === 0}
                  onClick={() =>
                    copy(
                      copyAll(draft, t(`${NS}.draft.demo`), janusLabel),
                      t(`${NS}.draft.copiedAll`),
                    )
                  }
                >
                  {t(`${NS}.draft.copyAll`)}
                </Button>
                <Button variant="secondary" onClick={() => window.print()}>
                  <PrintIcon size={18} />
                  {t(`${NS}.draft.print`)}
                </Button>
              </div>
              {draft.missingRequired.length ? (
                <section className="flex flex-col gap-1 text-sm">
                  <h3 className="font-body font-bold">
                    {t(`${NS}.draft.missingTitle`)}
                  </h3>
                  <p className="text-muted">{t(`${NS}.draft.missingHint`)}</p>
                  <ul className="list-disc ps-5" data-testid="report-missing">
                    {draft.missingRequired.map((r) => {
                      const parts = requiredParts(r).map((x) =>
                        x.split(" > ").pop()!,
                      );
                      return parts.length > 1 ? (
                        <li key={r}>
                          {t(`${NS}.draft.oneOf`, {
                            fields: parts.join(" / "),
                          })}
                        </li>
                      ) : (
                        <li key={r} lang={lang}>
                          {parts[0]}
                        </li>
                      );
                    })}
                  </ul>
                </section>
              ) : null}
              <p className="border-t border-line pt-3 text-sm text-muted">
                {t("Disclaimer.text")}
              </p>
            </section>
          ) : null}
          {country ? <Contacts t={t} country={country} /> : null}
        </div>
      </div>
    </div>
  );
}

function ChannelFacts({
  t,
  channel,
  locale,
}: {
  t: ReturnType<typeof useT>;
  channel: Channel;
  locale: Locale;
}) {
  const unverified = (s: string) =>
    /UNVERIFIED/.test(s) ? t(`${NS}.channel.unverified`) : s;
  const date = new Intl.DateTimeFormat(locale, {
    dateStyle: "long",
    timeZone: "UTC",
  }).format(new Date(`${channel.checkedOn}T00:00:00Z`));
  const version = channel.formVersion ? unverified(channel.formVersion) : null;
  return (
    <div className="flex flex-col gap-0.5 text-sm text-muted">
      {channel.formId && version ? (
        <p className="mono">
          {t(`${NS}.channel.version`, { id: channel.formId, version })}
        </p>
      ) : version ? (
        <p>{t(`${NS}.channel.versionOnly`, { version })}</p>
      ) : null}
      <p>
        {t(
          `${NS}.channel.${mappingFor(channel, false) ? "checked" : "checkedAddress"}`,
          { date },
        )}{" "}
        <a href={channel.sourceUrl} data-inline="true" {...EXTERNAL}>
          {t(`${NS}.channel.source`)}
        </a>
      </p>
    </div>
  );
}

function ChannelNotes({
  t,
  channel,
  hcp,
}: {
  t: ReturnType<typeof useT>;
  channel: Channel;
  hcp: boolean;
}) {
  const fl = fieldList(channel);
  const m = mappingFor(channel, hcp);
  const notes: ReactNode[] = [];
  if (!m)
    notes.push(
      t(
        `${NS}.channel.noFields.${
          fl && hcp
            ? "hcp"
            : channel.fieldsStatus === "partial"
              ? "partial"
              : "unverified"
        }`,
      ),
    );
  else if (m.borrowed) notes.push(t(`${NS}.channel.borrowed`));
  else if (m.source.fieldsStatus === "derived")
    notes.push(t(`${NS}.channel.derived`));
  return notes.length ? (
    <div
      className="flex flex-col gap-1 text-sm"
      data-testid="report-channel-note"
    >
      {notes.map((n, i) => (
        <p key={i}>{n}</p>
      ))}
    </div>
  ) : null;
}

function Contacts({
  t,
  country,
}: {
  t: ReturnType<typeof useT>;
  country: Country;
}) {
  const list = contactChannels(country);
  if (!list.length) return null;
  return (
    <GroupedList
      header={t(`${NS}.contacts.title`)}
      headingId="report-contacts"
      className="no-print"
    >
      {list.map((c) => (
        <Row key={c.id}>
          <a href={c.url} className="flex min-h-11 items-center font-bold">
            {c.kind === "email"
              ? t(`${NS}.contacts.email`, {
                  address: c.url.replace(/^mailto:/, ""),
                })
              : t(`${NS}.contacts.phone`, {
                  number: /[0-9][0-9 ]{6,}[0-9]/.exec(c.name)?.[0] ?? c.url,
                })}
          </a>
        </Row>
      ))}
    </GroupedList>
  );
}

function HcpNote({
  t,
  country,
}: {
  t: ReturnType<typeof useT>;
  country: Country;
}) {
  const link =
    country === "TR"
      ? channelById("tr-tufam-eform")!.sourceUrl
      : country === "US"
        ? channelById("us-fda-3500b-pdf")!.sourceUrl
        : null;
  return (
    <div
      className="flex flex-col gap-1 rounded-[var(--radius-tile)] bg-chip p-3 text-sm text-fg"
      data-testid="report-hcp"
    >
      <p className="font-bold">{t(`${NS}.hcp.title`)}</p>
      <p>
        {t(`${NS}.hcp.${country}`)}
        {link ? (
          <>
            {" "}
            <a href={link} data-inline="true" {...EXTERNAL}>
              {t(`${NS}.channel.source`)}
            </a>
          </>
        ) : null}
      </p>
    </div>
  );
}

function TextField({
  label,
  hint,
  value,
  onChange,
  multiline = false,
  labelHidden = false,
}: {
  label: string;
  hint?: string;
  value: string;
  onChange: (v: string) => void;
  multiline?: boolean;
  labelHidden?: boolean;
}) {
  const cls =
    "w-full min-h-11 rounded-[var(--radius-button)] border-2 border-muted bg-surface px-3 py-2 text-base text-fg";
  return (
    <label className="flex min-w-0 flex-col gap-1">
      <span className={labelHidden ? "sr-only" : "font-bold"}>{label}</span>
      {hint ? <span className="text-sm text-muted">{hint}</span> : null}
      {multiline ? (
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          rows={3}
          maxLength={2000}
          className={cls}
        />
      ) : (
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          maxLength={200}
          autoComplete="off"
          className={cls}
        />
      )}
    </label>
  );
}
