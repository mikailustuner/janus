"use client";
/**
 * Medicine information in the interface language (plain-medicine-info design §8, Req 5): what
 * the medicine contains, what the group of each ingredient is used for, and what the official
 * source says. The medicine is named by the URL fragment (`/medicines/info#<id>`), so nothing
 * about it reaches a path.
 *
 * Three kinds of text, never mixed: the ingredient name by the vocabulary's rule; the group
 * name and sentence exactly as the API returns them (fixed texts, each with its review status);
 * the official label text as a quotation in its own language. The page gives no dose, does not
 * say how to take a medicine and makes no statement about the person. `--warn` for the
 * abrupt-stop line only; `--risk` only inside the emergency notice.
 */
import { useLocale } from "next-intl";

import type { Locale } from "@/api/contracts";
import { AbruptStopLine } from "@/components/AbruptStopLine";
import { BackLink, LargeTitle } from "@/components/cards";
import { EmergencyNotice } from "@/components/EmergencyNotice";
import { formatDate } from "@/components/format";
import type { ShownIngredient } from "@/components/names";
import { StateView } from "@/components/StateView";
import { ButtonLink, Card, Mono } from "@/components/ui";
import { useSession } from "@/flow/janus";
import { useHashId } from "@/passport/screens/PassportItemView";
import { demoInfo, liveInfo, type InfoCall } from "@/plaininfo/client";
import type {
  IngredientOut,
  LabelText,
  MedicineInfoOut,
  ProductPage,
} from "@/plaininfo/model";
import { infoQuery, type InfoQuery } from "@/plaininfo/query";
import { useMedicineInfo, type InfoState } from "@/plaininfo/useMedicineInfo";
import { useT } from "@/theme/words";
import { sentence, type Loaded } from "@/vocabulary";
import { useVocabulary } from "@/vocabulary/use";

const link =
  "inline-flex min-h-11 items-center self-start font-bold underline underline-offset-4";

function Groups({ answer }: { answer: IngredientOut }) {
  const t = useT();
  if (answer.status === "none")
    return <p data-testid="plain-info-no-group">{t("PlainInfo.group.none")}</p>;
  return (
    <>
      {answer.status === "mixed" ? <p>{t("PlainInfo.group.mixed")}</p> : null}
      <ul
        className="flex flex-col gap-3"
        aria-label={t("PlainInfo.group.label")}
      >
        {answer.groups.map((g) => (
          <li
            key={g.id}
            className="flex flex-col gap-1.5 rounded-[var(--radius-tile)] border border-line p-3"
            data-testid="plain-info-group"
            data-group={g.id}
          >
            <p className="text-sm text-muted">{t("PlainInfo.group.label")}</p>
            <h3 className="font-bold [overflow-wrap:anywhere]">{g.name}</h3>
            <p className="text-lg" data-testid="plain-info-sentence">
              {g.text}
            </p>
            <p className="text-sm text-muted">
              {t("PlainInfo.group.code")} <Mono>{g.codes.join(", ")}</Mono>
            </p>
            {g.review_status === "not_reviewed" ? (
              <p className="text-sm font-bold" data-testid="plain-info-review">
                {t("PlainInfo.review")}
              </p>
            ) : null}
          </li>
        ))}
      </ul>
      {answer.other_uses ? <p>{t("PlainInfo.group.otherUses")}</p> : null}
    </>
  );
}

function Ingredient({
  shown,
  answer,
  vocab,
}: {
  shown: ShownIngredient;
  answer: IngredientOut | null;
  vocab: Loaded;
}) {
  const t = useT();
  return (
    <Card as="li" data-testid="plain-info-ingredient">
      <p className="text-lg font-bold [overflow-wrap:anywhere]">
        {shown.name.text
          ? t("PlainInfo.contains.one", { name: shown.name.text })
          : t("PlainInfo.contains.unnamed")}
      </p>
      {shown.name.tag ? (
        <p className="text-sm text-muted">({shown.name.tag})</p>
      ) : null}
      {answer?.abrupt_stop ? <AbruptStopLine vocab={vocab} /> : null}
      {shown.notChecked ? (
        <p className="font-bold">
          {sentence(vocab, `not_checked.${shown.notChecked}`)}
        </p>
      ) : answer ? (
        <Groups answer={answer} />
      ) : null}
    </Card>
  );
}

function LabelQuote({
  label,
  outdated,
}: {
  label: LabelText;
  outdated: boolean;
}) {
  const t = useT();
  const locale = useLocale();
  const meta = [
    label.version
      ? t("PlainInfo.official.us.version", { version: label.version })
      : null,
    label.effective_date
      ? t("PlainInfo.official.us.dated", {
          date: formatDate(label.effective_date, locale),
        })
      : null,
    t("PlainInfo.official.us.data", {
      date: formatDate(label.source.snapshot_date, locale),
    }),
  ].filter(Boolean);
  return (
    <Card data-testid="plain-info-official" data-kind="label_text">
      <h3 className="font-bold">{t("PlainInfo.official.us.title")}</h3>
      <p className="font-bold" data-testid="plain-info-not-translated">
        {t("PlainInfo.official.us.language")}
      </p>
      <p className="text-sm text-muted">{t("PlainInfo.official.us.section")}</p>
      <blockquote
        lang="en"
        dir="ltr"
        className="flex flex-col gap-2 border-l-2 border-line pl-3 break-words whitespace-pre-line"
        data-testid="plain-info-quote"
      >
        {label.paragraphs.map((p, i) => (
          <p key={i}>{p}</p>
        ))}
      </blockquote>
      {label.truncated ? (
        <p className="text-sm font-bold">{t("PlainInfo.official.us.cut")}</p>
      ) : null}
      <a
        className={link}
        href={label.url}
        target="_blank"
        rel="noopener noreferrer"
      >
        {t("PlainInfo.official.us.open")}
      </a>
      <p className="text-sm text-muted">{t("PlainInfo.official.us.company")}</p>
      <p className="text-sm text-muted">{t("PlainInfo.official.us.differ")}</p>
      <p className="text-sm text-muted">
        {t("PlainInfo.official.us.notForYou")}
      </p>
      <p className="text-sm text-muted">{meta.join(" · ")}</p>
      {outdated ? (
        <p className="text-sm font-bold">
          {t("PlainInfo.official.us.outdated")}
        </p>
      ) : null}
    </Card>
  );
}

function PageLink({ page }: { page: ProductPage }) {
  const t = useT();
  const locale = useLocale();
  return (
    <Card data-testid="plain-info-official" data-kind="product_page">
      <h3 className="font-bold">
        {t(`PlainInfo.official.page.title.${page.country}`)}
      </h3>
      <p className="font-bold" data-testid="plain-info-not-translated">
        {t(`PlainInfo.official.page.language.${page.language}`)}
      </p>
      <a
        className={link}
        href={page.url}
        target="_blank"
        rel="noopener noreferrer"
        lang={page.language}
      >
        {t("PlainInfo.official.page.open")}
      </a>
      <p className="text-sm text-muted">
        {t("PlainInfo.official.page.found", {
          date: formatDate(page.source.snapshot_date, locale),
        })}
      </p>
    </Card>
  );
}

/** Why there is no official text or page, as a catalogue key. */
export function noOfficialKey(
  query: InfoQuery,
  data: MedicineInfoOut | null,
): string {
  const none = "PlainInfo.official.none";
  if (query.noProduct) return `${none}.${query.noProduct}`;
  const status = data?.official_status;
  if (status === "several_labels") return `${none}.several_labels`;
  if (status === "not_found")
    return query.body?.product?.country === "US"
      ? `${none}.not_found_us`
      : `${none}.not_found_page`;
  return `${none}.source_unavailable`;
}

/** The body of the page for one medicine and one answer state (also used by tests). */
export function MedicineInfoBody({
  boxName,
  query,
  state,
  vocab,
  retry,
}: {
  boxName: string;
  query: InfoQuery;
  state: InfoState | { status: "nothing" };
  vocab: Loaded;
  retry?: () => void;
}) {
  const t = useT();
  const data = state.status === "ok" ? state.data : null;
  const answers = query.asked.map((i) =>
    i === null ? null : (data?.ingredients[i] ?? null),
  );
  const settled = state.status === "ok" || state.status === "nothing";
  const hasGroup = answers.some((a) => a && a.groups.length > 0);
  const official = data?.official ?? null;
  return (
    <>
      <EmergencyNotice compact />
      <BackLink href="/medicines">{t("Medicines.title")}</BackLink>
      <LargeTitle
        eyebrow={t("PlainInfo.eyebrow")}
        title={<span className="[overflow-wrap:anywhere]">{boxName}</span>}
        summary={t("PlainInfo.summary")}
      />
      {state.status === "loading" ? (
        <StateView state="loading" label={t("PlainInfo.loading")} />
      ) : state.status === "error" ? (
        <StateView
          state="error"
          messageKey={state.error.messageKey}
          retry={retry}
        />
      ) : null}
      {settled && !hasGroup && !official ? (
        <Card data-testid="plain-info-nothing">
          <h2 className="text-xl leading-snug font-semibold">
            {t("PlainInfo.nothing.title")}
          </h2>
          <p>{t("PlainInfo.nothing.body")}</p>
        </Card>
      ) : null}
      {settled ? (
        <>
          <section
            aria-labelledby="plain-info-contains"
            className="flex min-w-0 flex-col gap-3"
          >
            <h2 id="plain-info-contains" className="group-header">
              {t("PlainInfo.contains.heading")}
            </h2>
            <ul className="flex min-w-0 flex-col gap-3">
              {query.shown.map((g, i) => (
                <Ingredient
                  key={i}
                  shown={g}
                  answer={answers[i] ?? null}
                  vocab={vocab}
                />
              ))}
            </ul>
            {hasGroup ? (
              <p className="group-footer" data-testid="plain-info-method">
                {t("PlainInfo.method")}
              </p>
            ) : null}
          </section>
          <Card
            aria-labelledby="plain-info-limits"
            data-testid="plain-info-limits"
          >
            <h2
              id="plain-info-limits"
              className="text-xl leading-snug font-semibold"
            >
              {t("PlainInfo.limits.heading")}
            </h2>
            <ul className="flex list-disc flex-col gap-2 ps-5">
              {hasGroup ? <li>{t("PlainInfo.limits.group")}</li> : null}
              <li>{t("PlainInfo.limits.dose")}</li>
              <li className="font-bold">{t("PlainInfo.limits.ask")}</li>
            </ul>
          </Card>
          <section
            aria-labelledby="plain-info-official-heading"
            className="flex min-w-0 flex-col gap-3"
          >
            <h2 id="plain-info-official-heading" className="group-header">
              {t("PlainInfo.official.heading")}
            </h2>
            {official?.kind === "label_text" ? (
              <LabelQuote
                label={official}
                outdated={!!data?.notices.includes("snapshot_outdated")}
              />
            ) : official?.kind === "product_page" ? (
              <PageLink page={official} />
            ) : (
              <p className="card p-4" data-testid="plain-info-no-official">
                {t(noOfficialKey(query, data))}
              </p>
            )}
          </section>
        </>
      ) : null}
    </>
  );
}

function Loaded_({
  boxName,
  query,
  call,
  demo,
  vocab,
}: {
  boxName: string;
  query: InfoQuery;
  call: InfoCall;
  demo: boolean;
  vocab: Loaded;
}) {
  const { retry, ...state } = useMedicineInfo(query.body, call, demo);
  return (
    <MedicineInfoBody
      boxName={boxName}
      query={query}
      state={state}
      vocab={vocab}
      retry={retry}
    />
  );
}

export function MedicineInfoView({ call }: { call?: InfoCall }) {
  const t = useT();
  const locale = useLocale() as Locale;
  const session = useSession();
  const vocab = useVocabulary();
  const id = useHashId();
  if (!session.ready || !vocab || id === undefined)
    return <StateView title={t("PlainInfo.eyebrow")} state="loading" />;
  const item = session.items.find((i) => i.id === id);
  if (!item)
    return (
      <StateView
        title={t("PlainInfo.eyebrow")}
        state="empty"
        message={t("PlainInfo.notFound")}
        action={
          <ButtonLink href="/medicines">{t("PlainInfo.back")}</ButtonLink>
        }
      />
    );
  const demo = session.demo !== null;
  return (
    <Loaded_
      boxName={item.boxName}
      query={infoQuery(vocab, item, locale, demo)}
      call={call ?? (demo ? demoInfo : liveInfo)}
      demo={demo}
      vocab={vocab}
    />
  );
}
