"use client";
/**
 * The medicine list (experience design §4, §9, Req 13.2, 13.5, 1.6): box name, ingredients by
 * the vocabulary, region and source with its date, start month, the abrupt-stop line after an
 * evaluation; edit start month and box name, remove. Demo lists are read-only and never stored.
 */
import { useLocale } from "next-intl";
import { useState } from "react";

import type { CascadeResult } from "@/api/contracts";
import { AbruptStopLine } from "@/components/AbruptStopLine";
import { formatMonth } from "@/components/format";
import { MonthPicker } from "@/components/MonthPicker";
import { candidateIngredients } from "@/components/names";
import { ItemBadges, ListSummaryExtra } from "@/components/passport/slots";
import { SourceAttribution } from "@/components/SourceAttribution";
import { FhirExport } from "@/components/medicines/FhirExport";
import { TimelineSummary } from "@/components/medicines/Timeline";
import { StateView } from "@/components/StateView";
import { Button, ButtonLink, Card, Chip, PageTitle } from "@/components/ui";
import { inputKey, MAX_ITEMS, toEvaluateIn } from "@/flow/evaluate";
import { resultCache, useSession } from "@/flow/janus";
import { listActions, type Item } from "@/store/list";
import { setPending } from "@/flow/pending";
import { resolverFor } from "@/flow/reresolve";
import { useRouter } from "@/i18n/navigation";
import { useSettings } from "@/store/hooks";
import { useT } from "@/theme/words";
import { sentence, type Loaded } from "@/vocabulary";
import { useVocabulary } from "@/vocabulary/use";

/** Confirm an item again after a dataset change: resolve its source key, then the confirm screen. */
function Reconfirm({ item }: { item: Item }) {
  const t = useT();
  const router = useRouter();
  const session = useSession();
  const { value } = useSettings();
  return (
    <Button
      variant="secondary"
      onClick={async () => {
        if (!session.client) return;
        const r = await resolverFor(
          session.client,
          value.scanRegion,
        )(item.sourceKey);
        if (!r.ok) return;
        const k = item.sourceKey;
        setPending({
          resolution: r.data,
          source:
            k.kind === "search"
              ? { kind: "search", query: k.query, region: k.region }
              : k,
          typed: k.kind === "search" ? k.query : null,
          replaces: item.id,
        });
        router.push("/confirm");
      }}
    >
      {t("Confirm.title")}
    </Button>
  );
}

function ItemRow({
  item,
  index,
  vocab,
  warned,
  readOnly,
}: {
  item: Item;
  index: number;
  vocab: Loaded;
  warned: boolean;
  readOnly: boolean;
}) {
  const t = useT();
  const locale = useLocale();
  const [editing, setEditing] = useState(false);
  const [confirmRemove, setConfirmRemove] = useState(false);
  const [started, setStarted] = useState(item.started);
  const [name, setName] = useState(item.boxName);
  const ingredients = candidateIngredients(vocab, item.candidate, item.choices);
  const c = item.candidate;
  return (
    <Card
      as="li"
      aria-labelledby={`item-${index}`}
      className="lg:grid lg:grid-cols-[minmax(0,15rem)_minmax(0,1fr)] lg:gap-x-6"
    >
      <div className="flex flex-wrap items-start justify-between gap-2 lg:flex-col lg:justify-start">
        <h2 id={`item-${index}`} className="text-lg leading-snug font-bold">
          {item.boxName}
        </h2>
        <ItemBadges item={item} />
        {item.needsConfirmation ? (
          <Chip>{t("Medicines.needsConfirmation")}</Chip>
        ) : null}
        {item.needsConfirmation && !readOnly ? <Reconfirm item={item} /> : null}
      </div>
      <div className="flex min-w-0 flex-col gap-3">
        <ul
          className="flex flex-col gap-1"
          aria-label={t("Medicines.ingredients")}
        >
          {ingredients.map((g, i) => (
            <li key={i} className="flex flex-wrap items-baseline gap-x-2">
              <span>{g.name.text ?? g.key}</span>
              {g.name.tag ? (
                <span className="text-sm text-muted">({g.name.tag})</span>
              ) : null}
              {g.codes.length ? (
                <span className="mono text-sm text-muted">
                  {g.codes.join(", ")}
                </span>
              ) : null}
              {g.combinationCode ? (
                <span className="text-sm text-muted">
                  {sentence(vocab, "name.combination_code")}
                </span>
              ) : null}
              {g.notChecked ? (
                <span className="text-sm font-bold">
                  {sentence(vocab, `not_checked.${g.notChecked}`)}
                </span>
              ) : null}
            </li>
          ))}
        </ul>
        {c.kind === "product" && c.ingredients.length > 1 && c.published_atc ? (
          <p className="text-sm text-muted">
            {t("Medicines.combinationCode", { code: c.published_atc })}
          </p>
        ) : null}
        {c.kind === "ingredient" ? (
          <p className="text-sm text-muted">{t("Medicines.byName")}</p>
        ) : null}
        <p className="text-sm text-muted">
          {t(
            `Common.region.${c.kind === "product" ? c.region : (item.sourceKey.kind === "search" && item.sourceKey.region) || "ALL"}`,
          )}
          {" · "}
          <SourceAttribution candidate={c} />
        </p>
        <p>
          {item.started
            ? t("Medicines.since", { month: formatMonth(item.started, locale) })
            : t("Medicines.startUnknown")}
        </p>
        {warned ? <AbruptStopLine vocab={vocab} /> : null}
        {readOnly ? null : editing ? (
          <div className="flex flex-col gap-3 border-t border-line pt-3">
            <MonthPicker value={started} onChange={setStarted} />
            <label className="flex flex-col gap-1">
              <span className="font-bold">{t("Medicines.boxName")}</span>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                maxLength={120}
                className="min-h-11 rounded-[var(--radius-button)] border-2 border-muted bg-surface px-3 text-fg"
              />
            </label>
            <div className="flex flex-wrap gap-3">
              <Button
                onClick={() => {
                  listActions().edit(item.id, {
                    started,
                    boxName: name.trim() || item.boxName,
                  });
                  setEditing(false);
                }}
              >
                {t("Common.save")}
              </Button>
              <Button variant="secondary" onClick={() => setEditing(false)}>
                {t("Common.cancel")}
              </Button>
            </div>
          </div>
        ) : confirmRemove ? (
          <div
            className="flex flex-wrap items-center gap-3"
            role="alertdialog"
            aria-label={t("Common.remove")}
          >
            <p className="font-bold">
              {t("Medicines.removeConfirm", { name: item.boxName })}
            </p>
            <Button onClick={() => listActions().remove(item.id)}>
              {t("Common.remove")}
            </Button>
            <Button variant="secondary" onClick={() => setConfirmRemove(false)}>
              {t("Common.cancel")}
            </Button>
          </div>
        ) : (
          <div className="flex flex-wrap gap-3">
            <Button variant="secondary" onClick={() => setEditing(true)}>
              {t("Common.edit")}
            </Button>
            <Button variant="quiet" onClick={() => setConfirmRemove(true)}>
              {t("Common.remove")}
            </Button>
          </div>
        )}
      </div>
    </Card>
  );
}

export function Medicines() {
  const t = useT();
  const session = useSession();
  const vocab = useVocabulary();
  if (!session.ready || !vocab) return <StateView state="loading" />;
  const { items, readOnly, fixture } = session;
  const built = toEvaluateIn(items);
  const key = built.ok ? inputKey(built.body) : null;
  const result = key ? resultCache.get<CascadeResult>(key) : undefined;
  const outOfDate = resultCache.last !== null && resultCache.last !== key;
  const warned = new Set(result?.item_warnings.map((w) => w.item) ?? []);

  return (
    <>
      <PageTitle eyebrow={t("Medicines.count", { count: items.length })}>
        {t("Medicines.title")}
      </PageTitle>
      {fixture ? (
        <p className="text-sm text-muted">
          {t("Demo.recorded", {
            date: fixture.recorded.date,
            rules: fixture.recorded.rule_base_version.slice(0, 8),
            dataset: fixture.recorded.dataset_version.slice(0, 8),
            integrity: fixture.recorded.integrity_version.slice(0, 8),
          })}
        </p>
      ) : null}
      {readOnly ? (
        <p className="text-sm text-muted">{t("Medicines.demoReadOnly")}</p>
      ) : null}
      {outOfDate && !result ? (
        <p role="status" className="card p-3 font-bold">
          {t("Medicines.outOfDate")}
        </p>
      ) : null}
      {items.length > MAX_ITEMS ? (
        <p role="alert" className="card p-3 font-bold">
          {t("Medicines.tooMany")}
        </p>
      ) : null}
      <ListSummaryExtra items={items} />
      {items.length === 0 ? (
        <StateView
          state="empty"
          message={t("Medicines.empty")}
          action={<ButtonLink href="/scan">{t("Medicines.add")}</ButtonLink>}
        />
      ) : (
        <>
          <div className="flex flex-wrap gap-3">
            <ButtonLink href="/results">{t("Medicines.check")}</ButtonLink>
            <ButtonLink href="/timeline" variant="secondary">
              {t("Medicines.timeline")}
            </ButtonLink>
          </div>
          {/* Desktop (Req 27): the list as rows, the timeline beside it. */}
          <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(280px,340px)] lg:items-start">
            <div className="flex min-w-0 flex-col gap-5">
              <ul className="flex min-w-0 flex-col gap-3">
                {items.map((item, i) => (
                  <ItemRow
                    key={item.id}
                    item={item}
                    index={i}
                    vocab={vocab}
                    warned={warned.has(i)}
                    readOnly={readOnly}
                  />
                ))}
              </ul>
              <FhirExport
                items={items}
                vocab={vocab}
                demo={session.demo !== null}
              />
            </div>
            {/* Desktop only: the phone keeps the timeline on its own screen, as before. */}
            <aside className="hidden min-w-0 flex-col gap-5 lg:sticky lg:top-4 lg:flex">
              <TimelineSummary items={items} result={result ?? null} />
            </aside>
          </div>
        </>
      )}
    </>
  );
}
