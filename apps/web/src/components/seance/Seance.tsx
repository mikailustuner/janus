"use client";
/**
 * The séance screen (séance design §7.3, Req 7; experience Req 24, DP48): the pair picker, the
 * substance with its identification label and hazard flag, the count as "n of 3 witnesses" (never
 * a score), the missing witnesses, and the three seats in their fixed order, each with its own
 * confidence and items or its localised missing reason. Glass Janus calls it "evidence summary".
 * Demo mode answers from the recorded fixture with no request at all. Loading, empty, error and
 * long-content states; Arabic quotations wrap (no horizontal scroll at 375 px).
 */
import { useLocale } from "next-intl";
import { useEffect, useMemo, useState, useSyncExternalStore } from "react";

import { StateView } from "@/components/StateView";
import { CiBar } from "@/components/memory/CiBar";
import { formatDate } from "@/components/format";
import {
  BackLink,
  LargeTitle,
  SegmentedControl,
  StatGrid,
  StatTile,
} from "@/components/cards";
import { Card, Chip, SectionTitle } from "@/components/ui";
import { useDemo } from "@/demo/session";
import { useCall } from "@/flow/useCall";
import {
  demoSeance,
  liveSeance,
  loadSeanceFixture,
  takeRequestedPair,
  type SeanceClient,
  type SeanceFixture,
} from "@/seance/client";
import {
  HEADLINE_REASONS,
  type PastItem,
  type SeanceIn,
  type SeanceOut,
  type Substance,
} from "@/seance/model";
import {
  choices,
  doiUrl,
  initialPair,
  locatorValues,
  missingInOrder,
  seats,
  showableTitle,
  withSubstance,
  type Choice,
  type Seat,
} from "@/seance/view";
import { useT, useThemeWord } from "@/theme/words";

const KINDS = [
  "plant",
  "mineral",
  "plant_resin",
  "animal_product",
  "preparation",
];

const noSubscribe = () => () => {};

/**
 * The live client, or the demo client once the fixture is loaded. Nothing is chosen before the
 * first client render: during hydration the demo session reads as "none", and a live request
 * must never leave in demo mode.
 */
function useSeanceClient(): {
  client: SeanceClient | null;
  recorded: string | null;
} {
  const demo = useDemo();
  const mounted = useSyncExternalStore(
    noSubscribe,
    () => true,
    () => false,
  );
  const [fx, setFx] = useState<SeanceFixture | null>(null);
  useEffect(() => {
    let live = true;
    if (demo) loadSeanceFixture().then((f) => live && setFx(f));
    return () => {
      live = false;
    };
  }, [demo]);
  const client = useMemo(
    () => (!mounted ? null : demo ? (fx ? demoSeance(fx) : null) : liveSeance),
    [mounted, demo, fx],
  );
  return { client, recorded: demo ? (fx?.recorded ?? null) : null };
}

function Picker({
  list,
  value,
  onChange,
}: {
  list: Choice[];
  value: SeanceIn;
  onChange: (p: SeanceIn) => void;
}) {
  const t = useT();
  const current = list.find((c) => c.substance.id === value.substance);
  return (
    <fieldset className="card flex min-w-0 flex-col gap-3 p-4">
      <legend className="sr-only">{t("Seance.pick.legend")}</legend>
      <label className="flex flex-col gap-1 font-semibold">
        {t("Seance.pick.substance")}
        <select
          className="min-h-11 w-full rounded-[var(--radius-button)] border-2 border-muted bg-surface px-3 font-normal text-fg"
          value={value.substance}
          onChange={(e) => {
            const next = withSubstance(list, e.target.value, value.condition);
            if (next) onChange(next);
          }}
        >
          {list.map((c) => (
            <option
              key={c.substance.id}
              value={c.substance.id}
              className="bg-bg text-fg"
            >
              {c.substance.name_en} ({c.substance.transliteration})
            </option>
          ))}
        </select>
      </label>
      <SegmentedControl
        legend={t("Seance.pick.condition")}
        legendVisible
        name="seance-condition"
        variant="pills"
        value={value.condition}
        onChange={(condition) =>
          onChange({ substance: value.substance, condition })
        }
        options={(current?.pairs ?? []).map((p) => ({
          value: p.condition,
          label: (
            <>
              {t(`Seance.condition.${p.condition}`)}{" "}
              <span className="text-sm font-normal">
                (
                {t("Seance.pick.pairInfo", {
                  passages: p.past_passages,
                  studies: p.science_studies,
                })}
                )
              </span>
            </>
          ),
        }))}
      />
    </fieldset>
  );
}

function SubstanceCard({ s }: { s: Substance }) {
  const t = useT();
  const kind = s.kind.replace(/ /g, "_");
  return (
    <Card as="section" aria-labelledby="seance-substance">
      <header className="flex flex-col gap-1">
        <h2
          id="seance-substance"
          className="text-xl leading-snug font-semibold break-words"
        >
          {s.name_en}{" "}
          <span className="text-base font-normal text-muted">
            ({s.transliteration},{" "}
            {KINDS.includes(kind) ? t(`Seance.substance.kind.${kind}`) : s.kind}
            )
          </span>
        </h2>
        <p>
          <span className="text-sm text-muted">
            {t("Seance.substance.heading")}:{" "}
          </span>
          <span lang="ar" dir="rtl" className="text-lg">
            {s.heading_ar}
          </span>
        </p>
      </header>
      <p>
        <Chip>
          {s.identification_label === "identified"
            ? t("Seance.substance.identified")
            : t("Seance.substance.uncertain")}
        </Chip>
      </p>
      <p className="break-words">
        {t("Seance.substance.identification", { name: s.identification })}
      </p>
      <p className="text-sm break-words">
        {s.gold
          ? t("Seance.substance.gold", { name: s.gold.scientific_name })
          : t("Seance.substance.notInGold")}
      </p>
      {s.hamdard_ref ? (
        <p className="text-sm break-words">
          {t("Seance.substance.hamdard", { ref: s.hamdard_ref })}
        </p>
      ) : null}
      {s.note ? (
        <p className="text-sm break-words">
          {t("Seance.substance.note", { text: s.note })}
        </p>
      ) : null}
      {s.hazard ? (
        <p className="font-bold text-warn" role="note" data-testid="hazard">
          {t(`Seance.substance.hazard.${s.hazard}`)}
        </p>
      ) : null}
    </Card>
  );
}

function PastItemView({ item }: { item: PastItem }) {
  const t = useT();
  const loc = locatorValues(item);
  return (
    <li className="flex flex-col gap-2 border-t border-line pt-3 first:border-t-0 first:pt-0">
      <figure className="flex flex-col gap-2">
        <blockquote
          lang="ar"
          dir="rtl"
          className="text-lg leading-relaxed [overflow-wrap:anywhere]"
          data-testid="arabic-span"
        >
          {item.arabic_span}
        </blockquote>
        <figcaption className="text-sm text-muted">
          {t("Seance.past.arabic")}
        </figcaption>
      </figure>
      <p>
        <span className="chip mb-1 inline-block" data-testid="mt-label">
          {t("Seance.past.mt")}
        </span>
        <br />
        <span lang="en" className="break-words">
          {item.translation}
        </span>
      </p>
      <p className="text-sm font-semibold" data-testid="review-label">
        {item.expert_review === "pending"
          ? t("Seance.past.aiReviewed")
          : t("Seance.past.expertReviewed")}
      </p>
      <p className="text-sm break-words">
        {t("Seance.past.summary", { text: item.use_en })}
      </p>
      <p className="mono text-sm break-words" data-testid="locator">
        {loc.page
          ? t("Seance.past.locator", loc)
          : t("Seance.past.locatorNoPage", loc)}
      </p>
    </li>
  );
}

function PresentBody({ w }: { w: SeanceOut["witnesses"]["present"] }) {
  const t = useT();
  const locale = useLocale();
  const o = w.observed;
  return (
    <div className="flex flex-col gap-2">
      {o ? (
        <>
          <p>
            {t("Seance.present.observed", {
              both: o.reports_with_both,
              total: o.reports_with_ingredient,
              key: o.ingredient_key,
            })}
          </p>
          <p className="text-sm">
            {t(`Seance.present.match.${o.exposure_match}`)}
          </p>
          {o.ror !== null && o.ror_ci ? (
            <CiBar
              ratio={{ ror: o.ror, low: o.ror_ci.low, high: o.ror_ci.high }}
            />
          ) : null}
          <p className="text-sm">
            {t("Seance.present.snapshot", {
              date: formatDate(o.snapshot_date, locale),
            })}
          </p>
        </>
      ) : null}
      {w.items.map((i) => (
        <div key={i.ingredient_key} className="flex flex-col gap-1">
          <p>
            {t("Seance.present.item", {
              both: i.reports_with_both,
              total: i.reports_with_ingredient,
            })}
          </p>
          <CiBar
            ratio={{ ror: i.ror, low: i.ror_ci.low, high: i.ror_ci.high }}
          />
        </div>
      ))}
      {w.pts.length ? (
        <>
          <p className="text-sm break-words">
            {t("Seance.present.pts", { pts: w.pts.join(", ") })}
          </p>
          <p className="text-sm text-muted">{t("Memory.meddra")}</p>
        </>
      ) : null}
      {w.codes.length ? (
        <ul className="flex list-disc flex-col gap-1 ps-5 text-sm">
          {w.codes.map((c) => (
            <li key={c}>{t(`Seance.codes.${c}`)}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function ScienceBody({ w }: { w: SeanceOut["witnesses"]["science"] }) {
  const t = useT();
  return (
    <div className="flex flex-col gap-3">
      {w.items.length ? (
        <ul className="flex flex-col gap-3">
          {w.items.map((s) => (
            <li
              key={s.evidence_id}
              className="flex flex-col gap-1 border-t border-line pt-3 first:border-t-0 first:pt-0"
            >
              {showableTitle(s.title) ? (
                <p className="font-semibold break-words" lang="en">
                  {s.title}
                </p>
              ) : (
                <p className="font-semibold" data-testid="title-withheld">
                  {t("Seance.science.titleWithheld")}
                </p>
              )}
              <p className="flex flex-wrap gap-2 text-sm">
                <Chip>{t(`Seance.science.studyType.${s.study_type}`)}</Chip>
                <Chip>
                  {t(`Seance.science.integrity.${s.integrity_status}`)}
                </Chip>
              </p>
              <p className="text-sm break-words">
                {t("Seance.science.finding", { text: s.finding_en })}
              </p>
              <p className="text-sm break-words">
                DOI:{" "}
                <a
                  data-inline="true"
                  href={doiUrl(s.doi)}
                  rel="noreferrer noopener"
                  target="_blank"
                  className="mono underline"
                >
                  {s.doi}
                </a>
              </p>
            </li>
          ))}
        </ul>
      ) : null}
      {w.excluded.length ? (
        <p className="text-sm" data-testid="science-excluded">
          {t("Seance.science.excluded", { count: w.excluded.length })}
        </p>
      ) : null}
      <p className="text-sm text-muted">{t("Seance.science.targets")}</p>
    </div>
  );
}

function SeatView({ seat }: { seat: Seat }) {
  const t = useT();
  const w = seat.witness;
  const id = `seat-${seat.name}`;
  return (
    <Card
      as="li"
      aria-labelledby={id}
      data-testid={`seat-${seat.name}`}
      data-supports={w.supports ? "yes" : "no"}
    >
      <header className="flex flex-col gap-1">
        <h3 id={id} className="text-lg font-semibold">
          {t(`Seance.seat.${seat.name}.title`)}
        </h3>
        <p className="text-sm text-muted">
          {t(`Seance.seat.${seat.name}.source`)}
        </p>
        <p className="flex flex-wrap gap-2 text-sm">
          <Chip>
            {w.supports ? t("Seance.seat.speaks") : t("Seance.seat.silent")}
          </Chip>
          <Chip>
            {t("Seance.seat.confidence", {
              level: t(`Seance.confidence.${w.confidence}`),
            })}
          </Chip>
        </p>
      </header>
      {w.missing_reason ? (
        <p className="font-semibold" data-testid="missing-reason">
          {t(`Seance.missingReason.${w.missing_reason}`)}
        </p>
      ) : null}
      {seat.name === "past" && seat.witness.items.length ? (
        <ul className="flex flex-col gap-3">
          {seat.witness.items.map((i) => (
            <PastItemView key={i.claim_id} item={i} />
          ))}
        </ul>
      ) : null}
      {seat.name === "present" ? <PresentBody w={seat.witness} /> : null}
      {seat.name === "science" ? <ScienceBody w={seat.witness} /> : null}
    </Card>
  );
}

function Result({ out }: { out: SeanceOut }) {
  const t = useT();
  const w = useThemeWord();
  const missing = missingInOrder(out);
  const names = missing.map((m) => t(`Seance.witness.${m}`)).join(", ");
  const reasons = out.headline.reasons
    .filter((r) => (HEADLINE_REASONS as readonly string[]).includes(r))
    .map((r) => t(`Seance.headline.reason.${r}`))
    .join("; ");
  return (
    <section className="flex flex-col gap-4" aria-live="polite">
      <SubstanceCard s={out.substance} />
      <Card as="section" aria-labelledby="seance-count" className="sm:p-5">
        {/* The witness count large (never a score); the heading says the same (DP53). */}
        <StatGrid>
          <StatTile
            value={String(out.supporting_witnesses)}
            label={t("Cards.label.witnesses", {
              count: out.supporting_witnesses,
            })}
          />
        </StatGrid>
        <SectionTitle id="seance-count">
          {/* The tile above shows the count; the heading keeps the sentence for screen readers. */}
          <span data-testid="witness-count" className="sr-only">
            {t("Seance.count", { count: out.supporting_witnesses })}
          </span>
          <span className="sr-only"> · </span>
          {t(`Seance.condition.${out.condition}`)}
        </SectionTitle>
        <p className="text-sm">{t("Seance.countNote")}</p>
        <p data-testid="missing-witnesses">
          {out.supporting_witnesses === 0
            ? t("Seance.zero")
            : missing.length
              ? t("Seance.missing", { names })
              : t("Seance.noneMissing")}
        </p>
        <p className="font-bold" data-testid="framing">
          {t("Seance.framing")}
        </p>
        <p className="text-sm">
          {out.headline.eligible
            ? t("Seance.headline.eligible")
            : t("Seance.headline.notEligible", { reasons })}
        </p>
        {out.condition === "infection" ? (
          <p className="text-sm">{t("Seance.infectionBridge")}</p>
        ) : null}
      </Card>
      <section aria-labelledby="seance-table" className="flex flex-col gap-3">
        <SectionTitle id="seance-table">{w("Seance.table")}</SectionTitle>
        <ol className="flex flex-col gap-3" data-testid="seance-table">
          {seats(out).map((s) => (
            <SeatView key={s.name} seat={s} />
          ))}
        </ol>
      </section>
      <Card as="aside" className="text-sm">
        <h2 className="font-semibold">{t("Seance.sources")}</h2>
        <ul className="flex flex-col gap-2">
          {out.sources.map((s) => (
            <li key={s.id} className="break-words">
              {s.citation} {t("Seance.licence", { license: s.license })}
            </li>
          ))}
        </ul>
      </Card>
    </section>
  );
}

function PairView({ client, pair }: { client: SeanceClient; pair: SeanceIn }) {
  const t = useT();
  const call = useCall<SeanceOut>(
    () => client.pair(pair),
    [client, pair.substance, pair.condition],
  );
  if (call.status === "loading")
    return <StateView state="loading" label={t("Seance.loading")} />;
  if (call.status === "error")
    return (
      <StateView
        state="error"
        messageKey={call.error.messageKey}
        retry={call.retry}
      />
    );
  if (call.status !== "ok") return null;
  return <Result out={call.data} />;
}

function Body({ client }: { client: SeanceClient }) {
  const t = useT();
  const cat = useCall(() => client.catalogue(), [client]);
  const [wanted] = useState<SeanceIn | null>(() => takeRequestedPair());
  const [pair, setPair] = useState<SeanceIn | null>(null);
  const list = useMemo(
    () => (cat.status === "ok" ? choices(cat.data, client.only) : []),
    [cat, client.only],
  );
  if (cat.status === "loading")
    return <StateView state="loading" label={t("Seance.loading")} />;
  if (cat.status === "error")
    return (
      <StateView
        state="error"
        messageKey={cat.error.messageKey}
        retry={cat.retry}
      />
    );
  const chosen = pair ?? initialPair(list, wanted);
  if (!chosen) return <StateView state="empty" message={t("Seance.empty")} />;
  const notListed =
    !pair &&
    wanted !== null &&
    (wanted.substance !== chosen.substance ||
      wanted.condition !== chosen.condition);
  return (
    <>
      {notListed ? (
        <p className="card p-4" role="status" data-testid="not-listed">
          {t("Seance.notListed")}
        </p>
      ) : null}
      <Picker list={list} value={chosen} onChange={setPair} />
      <PairView client={client} pair={chosen} />
    </>
  );
}

export function Seance() {
  const t = useT();
  const w = useThemeWord();
  const locale = useLocale();
  const { client, recorded } = useSeanceClient();
  return (
    <>
      <nav aria-label={t("Light.nav.sections")}>
        <BackLink href="/research">{t("Research.title")}</BackLink>
      </nav>
      <LargeTitle title={w("Seance.title")} />
      <p className="max-w-[72ch]">{w("Seance.intro")}</p>
      <p className="card p-4 font-bold" data-testid="rule7">
        {t("Seance.framing")}
      </p>
      <p className="card p-4" role="note" data-testid="seance-review">
        {t("Seance.review")}
      </p>
      <p className="text-sm text-muted">{t("Seance.researcherOnly")}</p>
      {recorded ? (
        <p className="text-sm" data-testid="seance-demo">
          {t("Seance.demo", { date: formatDate(recorded, locale) })}
        </p>
      ) : null}
      {client ? (
        <Body key={client.only ? "demo" : "live"} client={client} />
      ) : (
        <StateView state="loading" label={t("Seance.loading")} />
      )}
    </>
  );
}
