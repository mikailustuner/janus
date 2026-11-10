"use client";
/**
 * Products with the same active ingredients in another country (design §15.5, Req 14–17). The box
 * is named by the URL fragment (`/passport/products#<id>`). The caution text comes before any
 * product: containing the same active ingredient does not make two products the same medicine.
 * Every row shows the name, strengths and form exactly as the source publishes them (in the
 * source's language) and, per row, whether the listed strength and the form group are the same,
 * different or not compared; "different" is a text flag with its own icon shape, never a colour.
 * States: loading (`aria-busy`, a polite announcement when done), error with retry, nothing
 * listed (a statement about the source data), source unavailable, not checkable, demo.
 */
import { useLocale } from "next-intl";
import { useEffect, useState } from "react";

import { formatDate } from "@/components/format";
import { StateView } from "@/components/StateView";
import {
  BackLink,
  GroupedList,
  LargeTitle,
  Row,
  SegmentedControl,
} from "@/components/cards";
import { Button, ButtonLink } from "@/components/ui";
import { COLOGNE_PRODUCTS } from "@/demo/passport-products";
import { useT, type Translate } from "@/theme/words";

import { itemKeys } from "../identity";
import type { CmpResult, PassportItem } from "../model";
import {
  buildProductsRequest,
  LISTABLE,
  liveProducts,
  loadMore,
  loadProducts,
  TARGET_COUNTRY,
  TARGET_LANG,
  type Level,
  type ListedProduct,
  type ProductsState,
  type Target,
} from "../products";
import { notSentReason } from "../request";
import { ResultIcon, StatusIcon } from "./icons";
import { boxValues, useHashId } from "./PassportItemView";
import { usePassport } from "./usePassport";

const ICON: Record<Level, CmpResult> = {
  same: "matched",
  different: "differs",
  unknown: "could_not_compare",
};

function LevelLine({
  t,
  field,
  level,
  reason,
  group,
  value,
  lang,
}: {
  t: Translate;
  field: "strength" | "dose_form";
  level: Level;
  reason: string | null;
  group: string;
  /** The published value, or null when the source states none. */
  value: string | null;
  lang: string;
}) {
  return (
    <div
      className="flex items-start gap-2"
      data-field={field}
      data-level={level}
    >
      <ResultIcon result={ICON[level]} />
      <p className="min-w-0">
        {level === "different" ? (
          <span className="chip me-2 align-baseline" data-testid="different">
            {t("Passport.products.flag")}
          </span>
        ) : null}
        <span className={level === "different" ? "font-bold" : undefined}>
          {t(`Passport.products.${field}.${level}`, {
            group,
            reason: reason ? t(`Passport.compareReason.${reason}`) : "",
          })}
        </span>{" "}
        {value === null ? (
          t("Passport.products.notStated")
        ) : (
          <span lang={lang}>{value}</span>
        )}
      </p>
    </div>
  );
}

function ProductRow({
  t,
  item,
  product,
  lang,
}: {
  t: Translate;
  item: PassportItem;
  product: ListedProduct;
  lang: string;
}) {
  const single = product.ingredients.length === 1;
  const stated = product.ingredients.filter(
    (g) => g.strength_published !== null,
  );
  const strength =
    stated.length === 0
      ? null
      : single
        ? stated[0]!.strength_published
        : product.ingredients
            .map((g) =>
              t("Passport.products.ingredientValue", {
                name:
                  item.ingredients.find((i) => i.key === g.key)?.label ?? g.key,
                value: g.strength_published ?? t("Passport.products.notStated"),
              }),
            )
            .join(", ");
  return (
    <Row
      className="gap-2 [overflow-wrap:anywhere]"
      data-testid="listed-product"
    >
      <p className="font-bold" lang={lang}>
        {product.name}
      </p>
      <LevelLine
        t={t}
        field="strength"
        level={product.strength}
        reason={product.strength_reason}
        group=""
        value={strength}
        lang={lang}
      />
      <LevelLine
        t={t}
        field="dose_form"
        level={product.dose_form}
        reason={product.dose_form_reason}
        group={
          product.dose_form_group
            ? t(`Passport.form.${product.dose_form_group}`)
            : ""
        }
        value={product.dose_form_published}
        lang={lang}
      />
      {product.marketed !== "not_stated" ? (
        <p className="text-sm text-muted">
          {t(`Passport.products.marketed.${product.marketed}`)}
        </p>
      ) : null}
      {product.listings > 1 ? (
        <p className="text-sm text-muted">
          {t("Passport.products.listings", { count: product.listings })}
        </p>
      ) : null}
    </Row>
  );
}

function Listed({
  t,
  item,
  target,
  state,
  more,
  locale,
}: {
  t: Translate;
  item: PassportItem;
  target: Target;
  state: Extract<ProductsState, { status: "ok" }>;
  more: () => void;
  locale: string;
}) {
  const { out, products } = state;
  const source = out.source;
  const date = source.snapshot_date
    ? formatDate(source.snapshot_date, locale)
    : "";
  const ingredients = out.keys.length;
  if (out.status === "source_unavailable")
    return (
      <div className="card flex items-start gap-2 p-5" data-status={out.status}>
        <StatusIcon status={out.status} />
        <p>{t(`Passport.reason.${source.reason ?? "not_loaded"}`)}</p>
      </div>
    );
  return (
    <>
      <div className="card flex flex-col gap-2 p-5" data-status={out.status}>
        <div className="flex items-start gap-2">
          <StatusIcon status={out.status} />
          <p>
            {t(`Passport.status.${out.status}`, {
              source: source.attribution
                ? t(`Passport.sourceName.${source.attribution}`)
                : "",
              count: out.listings,
              ingredients,
              date,
              country: t(`Passport.country.${TARGET_COUNTRY[target]}`),
            })}
          </p>
        </div>
        {out.status === "present" ? (
          <>
            <p>
              {t("Passport.products.counts.strength", {
                ...out.counts.strength,
              })}
            </p>
            <p>
              {t("Passport.products.counts.dose_form", {
                ...out.counts.dose_form,
              })}
            </p>
          </>
        ) : null}
        {out.with_other_ingredients > 0 ? (
          <p className="text-muted">
            {t("Passport.detail.withOther", {
              count: out.with_other_ingredients,
              ingredients,
            })}
          </p>
        ) : null}
        {out.homeopathic_left_out > 0 ? (
          <p className="text-muted">
            {t("Passport.homeopathicLeftOut", {
              count: out.homeopathic_left_out,
            })}
          </p>
        ) : null}
        {out.not_finished_left_out > 0 ? (
          <p className="text-muted">
            {t("Passport.products.notFinished", {
              count: out.not_finished_left_out,
            })}
          </p>
        ) : null}
      </div>
      {products.length > 0 ? (
        <GroupedList
          header={t("Passport.products.listCaption", {
            country: t(`Passport.place.${TARGET_COUNTRY[target]}`),
          })}
          headingId="products-caption"
          footer={
            <>
              <p>
                {state.recordedOn && products.length < out.total
                  ? t("Passport.products.demoFirstPage", {
                      shown: products.length,
                      total: out.total,
                    })
                  : t("Passport.products.showing", {
                      shown: products.length,
                      total: out.total,
                    })}
              </p>
              {source.attribution && source.snapshot_date ? (
                <p>
                  {t(`Passport.attribution.${source.attribution}`, { date })}
                </p>
              ) : null}
              {source.stale ? (
                <p className="font-bold">{t("Passport.stale")}</p>
              ) : null}
              {state.recordedOn ? (
                <p>
                  {t("Passport.states.recorded", { date: state.recordedOn })}
                </p>
              ) : null}
            </>
          }
        >
          {products.map((p, i) => (
            <ProductRow
              key={i}
              t={t}
              item={item}
              product={p}
              lang={TARGET_LANG[target]}
            />
          ))}
        </GroupedList>
      ) : source.attribution && source.snapshot_date ? (
        <p className="group-footer">
          {t(`Passport.attribution.${source.attribution}`, { date })}
        </p>
      ) : null}
      {!state.recordedOn && products.length < out.total ? (
        <div className="flex flex-col items-start gap-2">
          {state.more === "error" ? (
            <p role="alert">{t("Passport.products.moreError")}</p>
          ) : null}
          <Button
            variant="secondary"
            onClick={more}
            disabled={state.more === "loading"}
            aria-busy={state.more === "loading"}
          >
            {t("Passport.products.more")}
          </Button>
        </div>
      ) : null}
    </>
  );
}

/** The body of the screen for one box, one target and one state (also used by tests). */
export function ProductsBody({
  item,
  target,
  onTarget,
  state,
  retry,
  more,
}: {
  item: PassportItem;
  target: Target;
  onTarget: (target: Target) => void;
  state: ProductsState;
  retry: () => void;
  more: () => void;
}) {
  const t = useT();
  const locale = useLocale();
  const reason = notSentReason(item);
  const keys = itemKeys(item);
  const names = new Intl.ListFormat(locale, { type: "conjunction" }).format(
    keys.map((k) => item.ingredients.find((g) => g.key === k)?.label ?? k),
  );
  const ok = state.status === "ok" ? state : null;
  const notices = ok
    ? ok.out.notices.filter(
        (n) =>
          n !== "unknown_ingredient_keys" || ok.out.unknown_keys.length > 0,
      )
    : [];
  return (
    <>
      <BackLink href={`/passport/item#${encodeURIComponent(item.id)}`}>
        {t("Passport.detail.title")}
      </BackLink>
      <LargeTitle
        eyebrow={t("Passport.products.title")}
        title={<span className="[overflow-wrap:anywhere]">{item.boxName}</span>}
        summary={
          reason
            ? undefined
            : t("Passport.products.summary", {
                ingredients: keys.length,
                names,
              })
        }
      />
      <p role="status" aria-live="polite" className="sr-only">
        {ok && !reason
          ? t("Passport.products.loaded", { count: ok.products.length })
          : ""}
      </p>
      {/* Before any product (Req 16.2): same ingredient is not the same medicine. */}
      <section
        aria-labelledby="products-caution"
        data-testid="products-caution"
        className="card flex flex-col gap-2 p-5"
      >
        <h2 id="products-caution" className="font-body font-bold">
          {t("Passport.products.caution.title")}
        </h2>
        <p>
          {t("Passport.products.caution.notSame", {
            ingredients: Math.max(keys.length, 1),
          })}
        </p>
        <p className="font-bold">{t("Passport.products.caution.confirm")}</p>
        <p>{t("Passport.products.caution.noDosing")}</p>
      </section>
      <div className="grid gap-group lg:grid-cols-[minmax(0,1fr)_minmax(280px,340px)] lg:items-start">
        <div className="flex min-w-0 flex-col gap-group">
          <GroupedList>
            <Row>
              <p>{boxValues(t, item, locale)}</p>
            </Row>
          </GroupedList>
          {reason === "homeopathic" ? (
            <p className="card p-5 font-bold">{t("Passport.homeopathic")}</p>
          ) : reason ? (
            <p className="card p-5 font-bold">
              {t(`Passport.notCheckable.${reason}`)}
            </p>
          ) : (
            <>
              <div className="flex flex-col gap-2">
                <SegmentedControl
                  legend={t("Passport.products.country")}
                  legendVisible
                  name="products-target"
                  value={target}
                  onChange={onTarget}
                  options={LISTABLE.map((value) => ({
                    value,
                    label: t(`Passport.place.${TARGET_COUNTRY[value]}`),
                  }))}
                />
                <p className="text-sm text-muted">
                  {t("Passport.products.notListed")}
                </p>
              </div>
              {state.status === "loading" ? (
                <div aria-busy="true" className="card flex flex-col gap-3 p-5">
                  <p>{t("Passport.products.loading")}</p>
                  {[0, 1, 2].map((i) => (
                    <div
                      key={i}
                      className="h-3 w-2/3 animate-pulse rounded-full bg-chip"
                    />
                  ))}
                </div>
              ) : state.status === "error" ? (
                <StateView
                  state="error"
                  messageKey="Passport.products.error"
                  retry={retry}
                />
              ) : state.status === "not_in_demo" ? (
                <p className="card p-5">{t("Passport.products.notInDemo")}</p>
              ) : (
                <Listed
                  t={t}
                  item={item}
                  target={target}
                  state={state}
                  more={more}
                  locale={locale}
                />
              )}
            </>
          )}
        </div>
        <aside className="flex min-w-0 flex-col gap-group lg:sticky lg:top-4">
          <section
            aria-labelledby="products-notes"
            className="flex flex-col gap-2"
          >
            <h2 id="products-notes" className="group-header">
              {t("Passport.products.notes.title")}
            </h2>
            <ul className="grouped text-sm">
              <li>{t("Passport.products.notes.automated")}</li>
              <li>{t("Passport.products.notes.salt")}</li>
              <li>{t("Passport.products.notes.group")}</li>
              <li>{t("Passport.presentNote")}</li>
              {ok?.products.some((p) => p.marketed === "not_stated") ? (
                <li>{t("Passport.products.marketed.not_stated")}</li>
              ) : null}
              {notices.map((n) => (
                <li key={n}>{t(`Passport.products.notice.${n}`)}</li>
              ))}
            </ul>
          </section>
          <p className="card p-5 font-bold">{t("Passport.listingsOnly")}</p>
        </aside>
      </div>
    </>
  );
}

const cache = new Map<string, Extract<ProductsState, { status: "ok" }>>();

/** The list for one box and one target; kept in memory only, never persisted. */
function useProducts(
  item: PassportItem | undefined,
  target: Target,
  demo: string | null,
) {
  const body = item ? buildProductsRequest(item, target) : null;
  const key = body ? JSON.stringify(body) : "";
  const [state, setState] = useState<{
    key: string;
    value: ProductsState;
  } | null>(null);
  const [n, setN] = useState(0);
  useEffect(() => {
    if (!body || cache.has(key)) return;
    let live = true;
    loadProducts(
      body,
      demo ? null : liveProducts,
      demo === "cologne" ? COLOGNE_PRODUCTS : null,
    ).then((value) => {
      if (value.status === "ok") cache.set(key, value);
      if (live) setState({ key, value });
    });
    return () => {
      live = false;
    };
    // `body` is captured through `key`.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, demo, n]);
  const current: ProductsState =
    state && state.key === key
      ? state.value
      : (cache.get(key) ?? { status: "loading" });
  return {
    state: current,
    retry: () => {
      setState(null);
      setN((x) => x + 1);
    },
    more: () => {
      if (!body || current.status !== "ok" || current.more === "loading")
        return;
      setState({ key, value: { ...current, more: "loading" } });
      loadMore(current, body, liveProducts).then((value) => {
        if (value.more === "idle") cache.set(key, value);
        setState((s) => (s && s.key !== key ? s : { key, value }));
      });
    },
  };
}

export function ProductsView() {
  const t = useT();
  const view = usePassport();
  const id = useHashId();
  const [target, setTarget] = useState<Target>(LISTABLE[0]);
  const merged = id ? (view.resolveId(id) ?? id) : null;
  const item = view.ready ? view.items.find((i) => i.id === merged) : undefined;
  const products = useProducts(item, target, view.demo);
  if (!view.ready || id === undefined) return <StateView state="loading" />;
  if (!item)
    return (
      <StateView
        state="empty"
        message={t("Passport.products.title")}
        action={<ButtonLink href="/passport">{t("Passport.back")}</ButtonLink>}
      />
    );
  return (
    <ProductsBody
      item={item}
      target={target}
      onTarget={setTarget}
      state={products.state}
      retry={products.retry}
      more={products.more}
    />
  );
}
