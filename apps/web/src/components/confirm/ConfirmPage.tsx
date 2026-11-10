"use client";
/**
 * Confirm a medicine (design §9, Req 12, P21): every candidate with region and source, the
 * product text as published, the ingredients with their names and codes, the product code as
 * published, the less-certain note for digit matches, status strings, homeopathic and
 * component-code labels; ambiguous positions answered by the user; box name and "since when".
 * Nothing is preselected and nothing enters the list before the user confirms.
 */
import { useLocale } from "next-intl";
import { useState } from "react";

import type { Candidate } from "@/api/contracts";
import { formatDate } from "@/components/format";
import { MonthPicker } from "@/components/MonthPicker";
import { candidateIngredients, keyName } from "@/components/names";
import { RecallCheck } from "@/components/recall/RecallCheck";
import { SourceAttribution } from "@/components/SourceAttribution";
import { StateView } from "@/components/StateView";
import { Button, ButtonLink, Card, PageTitle } from "@/components/ui";
import { confirmView, readyToAdd, type CardView } from "@/flow/confirm";
import { useSession } from "@/flow/janus";
import { setPending, usePending, type Pending } from "@/flow/pending";
import { useRouter } from "@/i18n/navigation";
import { recallQuery } from "@/recall/query";
import { listActions, type Item, type SourceKey } from "@/store/list";
import { useT } from "@/theme/words";
import { sentence, type Loaded } from "@/vocabulary";
import { useVocabulary } from "@/vocabulary/use";

function sourceKeyFor(p: Pending, c: Candidate): SourceKey {
  if (p.source.kind !== "search") return p.source;
  return {
    kind: "search",
    query: p.source.query,
    region: p.source.region,
    pick:
      c.kind === "ingredient"
        ? { kind: "ingredient", qid: c.ingredient_key.qid }
        : {
            kind: "product",
            sourceId: c.source.source_id,
            productName: c.product_name,
          },
  };
}

function defaultBoxName(c: Candidate, typed: string | null, v: Loaded): string {
  if (c.kind === "product")
    return c.brand_name ?? c.product_name ?? typed ?? "";
  return typed ?? keyName(v, c.ingredient_key.qid, c.ingredient_key.label_en);
}

function CandidateCard({
  card,
  vocab,
  chosen,
  onChoose,
}: {
  card: CardView;
  vocab: Loaded;
  chosen: boolean;
  onChoose: () => void;
}) {
  const t = useT();
  const locale = useLocale();
  const c = card.candidate;
  const ingredients = candidateIngredients(vocab, c);
  return (
    <Card
      as="li"
      className={chosen ? "outline-3 outline-accent" : ""}
      data-testid="candidate"
    >
      {c.kind === "product" ? (
        <>
          <h2 className="text-lg font-bold">
            {c.brand_name ?? c.product_name}
          </h2>
          {c.product_name && c.product_name !== c.brand_name ? (
            <p>{c.product_name}</p>
          ) : null}
          {c.generic_name ? (
            <p className="text-sm text-muted">{c.generic_name}</p>
          ) : null}
        </>
      ) : (
        <h2 className="text-lg font-bold">
          {keyName(vocab, c.ingredient_key.qid, c.ingredient_key.label_en)}
        </h2>
      )}
      <ul className="flex flex-col gap-1">
        {ingredients.map((g, i) => (
          <li key={i} className="flex flex-wrap items-baseline gap-x-2">
            <span>{g.name.text ?? g.published}</span>
            {g.name.tag ? (
              <span className="text-sm text-muted">({g.name.tag})</span>
            ) : null}
            {g.codes.length ? (
              <span className="mono text-sm">{g.codes.join(", ")}</span>
            ) : null}
            {g.combinationCode ? (
              <span className="text-sm text-muted">
                ({t("Confirm.combinationCode")})
              </span>
            ) : null}
            {g.notChecked && g.notChecked !== "ambiguous" ? (
              <span className="text-sm font-bold">
                {t("Confirm.cannotCheck", {
                  reason: sentence(vocab, `not_checked.${g.notChecked}`),
                })}
              </span>
            ) : null}
          </li>
        ))}
      </ul>
      {card.publishedAtc ? (
        <p className="text-sm text-muted">
          {t("Confirm.publishedAtc", { code: card.publishedAtc })}
        </p>
      ) : null}
      {card.homeopathic ? (
        <p className="font-bold">{t("Confirm.homeopathic")}</p>
      ) : null}
      {card.digitsNote ? (
        <p className="text-sm">{t("Confirm.matchedDigits")}</p>
      ) : null}
      {card.notInWikidata ? (
        <p className="text-sm">{t("Confirm.notInWikidata")}</p>
      ) : null}
      {card.status.map((s, i) =>
        s.kind === "fr" ? (
          <p key={i} className="text-sm">
            {t("Confirm.status", { status: s.text })}
          </p>
        ) : (
          <p key={i} className="text-sm">
            {s.code === "raw"
              ? t("Confirm.status", { status: s.value ?? "" })
              : t(`Confirm.statusEs.${s.code}`, {
                  code: s.value ?? "",
                  date: s.date ?? "",
                })}
          </p>
        ),
      )}
      {card.marketingEnd ? (
        <p className="text-sm">
          {t("Confirm.marketingEnd", {
            date: formatDate(card.marketingEnd, locale),
          })}
        </p>
      ) : null}
      <p className="text-sm text-muted">
        {t(`Common.region.${c.kind === "product" ? c.region : "ALL"}`)}
        {c.kind === "product" && c.country ? ` (${c.country})` : ""} ·{" "}
        <SourceAttribution candidate={c} />
      </p>
      {c.source.source_id === "eu_fr_bdpm" ? (
        <p className="text-xs text-muted">{t("Confirm.bdpm")}</p>
      ) : null}
      {c.source.source_id === "eu_es_cima" ? (
        <p className="text-xs text-muted">{t("Confirm.cima")}</p>
      ) : null}
      <Button
        variant={chosen ? "primary" : "secondary"}
        aria-pressed={chosen}
        className="self-start"
        onClick={onChoose}
      >
        {chosen ? t("Confirm.chosen") : t("Confirm.choose")}
      </Button>
    </Card>
  );
}

export function ConfirmPage() {
  const t = useT();
  const locale = useLocale();
  const router = useRouter();
  const pending = usePending();
  const vocab = useVocabulary();
  const session = useSession();
  const [chosen, setChosen] = useState<number | null>(null);
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [boxName, setBoxName] = useState<string | null>(null);
  const [started, setStarted] = useState<string | null>(null);
  const [shown, setShown] = useState(10);
  const [warning, setWarning] = useState<string | null>(null);

  if (!vocab) return <StateView state="loading" label={t("Confirm.loading")} />;
  if (!pending)
    return (
      <StateView
        state="empty"
        message={t("Medicines.empty")}
        action={<ButtonLink href="/scan">{t("Confirm.back")}</ButtonLink>}
      />
    );
  const view = confirmView(pending.resolution, pending.prefer ?? null);
  const back = (
    <ButtonLink href="/scan" variant="secondary" className="self-start">
      {t("Confirm.back")}
    </ButtonLink>
  );
  // No candidate is never a dead end (ocr-first Req 1.3–1.5): the label photo and the name work
  // with a box from any country.
  const otherWays = (
    <div className="card flex flex-col gap-3 p-4" data-testid="other-ways">
      <p>{t("Confirm.tryOther")}</p>
      <div className="flex flex-wrap gap-3">
        <ButtonLink href={{ pathname: "/scan", hash: "label" }}>
          {t("Scan.wayLabel")}
        </ButtonLink>
        <ButtonLink
          href={{ pathname: "/scan", hash: "type" }}
          variant="secondary"
        >
          {t("Scan.wayType")}
        </ButtonLink>
      </div>
    </div>
  );
  if (view.kind === "no_open_database")
    return (
      <>
        <PageTitle>{t("Confirm.title")}</PageTitle>
        <p className="card p-4" data-testid="no-open-database">
          {t("Confirm.noOpenDatabase")}
        </p>
        {otherWays}
      </>
    );
  if (view.kind === "not_supported")
    return (
      <>
        <PageTitle>{t("Confirm.title")}</PageTitle>
        <p className="card p-4">{t("Confirm.regionNotSupported")}</p>
        {otherWays}
        {back}
      </>
    );
  if (view.kind === "not_found")
    return (
      <>
        <PageTitle>{t("Confirm.title")}</PageTitle>
        <div className="card flex flex-col gap-2 p-4" data-testid="not-found">
          <p>
            {t("Confirm.none", {
              regions: view.regions
                .map((r) => t(`Common.region.${r}`))
                .join(", "),
            })}
          </p>
          <p className="text-sm text-muted">
            {t("Confirm.sources", {
              sources: view.sources
                .map(
                  (s) =>
                    `${t(["titck", "openfda_ndc", "eu_fr_bdpm", "eu_es_cima", "wikidata"].includes(s.sourceId) ? `Common.source.${s.sourceId}` : "Common.source.other", { id: s.sourceId })} (${s.date})`,
                )
                .join(", "),
            })}
          </p>
        </div>
        {otherWays}
        {back}
      </>
    );

  // `chosen` is the candidate's index in the resolution; the cards may be in another order.
  const card =
    chosen !== null ? view.cards.find((v) => v.index === chosen) : undefined;
  const c = card?.candidate;
  const name = boxName ?? (c ? defaultBoxName(c, pending.typed, vocab) : "");
  // Recall check of the chosen US product (recall-check Req 6.1); never in demo mode.
  const recall =
    c && !session.demo ? recallQuery(c, sourceKeyFor(pending, c)) : null;

  const add = () => {
    if (!card || !c) return setWarning(t("Confirm.nothingChosen"));
    if (!readyToAdd(card, answers))
      return setWarning(t("Confirm.chooseAmbiguous"));
    if (session.readOnly) return setWarning(t("Confirm.demoNoAdd"));
    const item: Omit<Item, "id"> = {
      sourceKey: sourceKeyFor(pending, c),
      datasetVersion: pending.resolution.dataset_version,
      candidate: c,
      choices: Object.entries(answers)
        .filter(([, v]) => v !== "dont_know")
        .map(([position, ingredient]) => ({
          position: Number(position),
          ingredient,
        })),
      started,
      boxName: name.trim() || defaultBoxName(c, pending.typed, vocab),
      needsConfirmation: false,
      ...(pending.lot ? { lot: pending.lot } : {}),
    };
    if (pending.replaces) listActions().replace(pending.replaces, item);
    else listActions().add(item);
    setPending(null);
    router.push("/medicines");
  };

  return (
    <>
      <PageTitle>{t("Confirm.title")}</PageTitle>
      <p>{t("Confirm.intro")}</p>
      {view.notices.map((n) => (
        <p key={n} className="card p-3 text-sm" role="status">
          {n === "unmapped_ingredients"
            ? t("Confirm.unmapped")
            : n === "region_adapter_not_available"
              ? t("Confirm.regionNotSupported")
              : n === "unknown_candidate_ids"
                ? t("Confirm.unknownIds")
                : t("Confirm.outdated", {
                    source:
                      pending.resolution.notices.find((x) => x.code === n)
                        ?.source_id ?? "",
                  })}
        </p>
      ))}
      {view.expiry ? (
        <p className="text-sm text-muted">
          {t("Confirm.expiry", { date: formatDate(view.expiry, locale) })}
        </p>
      ) : null}
      <ul className="flex flex-col gap-3">
        {view.cards.slice(0, shown).map((cv) => (
          <CandidateCard
            key={cv.index}
            card={cv}
            vocab={vocab}
            chosen={chosen === cv.index}
            onChoose={() => {
              setChosen(cv.index);
              setAnswers({});
              setBoxName(null);
              setWarning(null);
            }}
          />
        ))}
      </ul>
      {view.cards.length > shown && shown < 20 ? (
        <Button
          variant="secondary"
          className="self-start"
          onClick={() => setShown(20)}
        >
          {t("Confirm.showMore")}
        </Button>
      ) : null}
      {recall ? (
        <Card as="aside" aria-label={t("Recall.listLabel")}>
          <RecallCheck query={recall} lot={pending.lot} />
        </Card>
      ) : null}
      {card && c ? (
        <Card>
          {card.ambiguous.map((a) => (
            <fieldset key={a.position} className="flex flex-col gap-1">
              <legend className="font-bold">{t("Confirm.ambiguous")}</legend>
              {[...a.keys, "dont_know"].map((k) => (
                <label key={k} className="flex min-h-11 items-center gap-3">
                  <input
                    type="radio"
                    name={`pos-${a.position}`}
                    checked={answers[a.position] === k}
                    onChange={() =>
                      setAnswers((s) => ({ ...s, [a.position]: k }))
                    }
                    className="size-5 accent-[var(--accent)]"
                  />
                  {k === "dont_know"
                    ? t("Confirm.ambiguousDontKnow")
                    : keyName(vocab, k, null)}
                </label>
              ))}
            </fieldset>
          ))}
          <label className="flex flex-col gap-1">
            <span className="font-bold">{t("Confirm.boxName")}</span>
            <input
              value={name}
              onChange={(e) => setBoxName(e.target.value)}
              maxLength={120}
              className="min-h-11 rounded-[var(--radius-button)] border-2 border-muted bg-surface px-3 text-fg"
            />
          </label>
          <MonthPicker value={started} onChange={setStarted} />
        </Card>
      ) : null}
      {warning ? (
        <p role="alert" className="font-bold">
          {warning}
        </p>
      ) : null}
      <Button className="self-start" onClick={add} data-testid="add-medicine">
        {t("Confirm.add")}
      </Button>
    </>
  );
}
