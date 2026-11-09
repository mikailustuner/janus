"use client";
/**
 * The data-quality report page (research-tools Req 1; data-quality design §9): the latest run with
 * its counts per class (stat tiles) and per class × status (new, persisting, resolved), a filtered
 * list of findings with their evidence links, how to report upstream, downloads (CSV, JSON,
 * Markdown) and the sources. Codes, counts and English Wikidata labels only: the report holds no
 * TİTCK row, product name or barcode and the page never asks for one. Demo mode answers from the
 * recorded file with no request.
 */
import { useLocale } from "next-intl";
import { useMemo, useState } from "react";

import {
  BackLink,
  Disclosure,
  GroupedList,
  LargeTitle,
  Row,
  SegmentedControl,
  StatGrid,
  StatTile,
  SummaryCard,
} from "@/components/cards";
import { DownloadIcon } from "@/components/icons";
import { StateView } from "@/components/StateView";
import { Button } from "@/components/ui";
import { useCall } from "@/flow/useCall";
import {
  classStatusCounts,
  CLASSES,
  demoDataQuality,
  evidenceLink,
  filterFindings,
  liveDataQuality,
  loadDataQualityFixture,
  STATUSES,
  upstreamTarget,
  whoccGroup,
  type DataQualityClient,
  type DataQualityReport,
  type Filter,
  type Finding,
} from "@/research/dataQuality";
import { useT } from "@/theme/words";

import { useDemoClient } from "./useDemoClient";

const REPO = "https://github.com/mikailustuner/janus/blob/main";
const EXTERNAL = { target: "_blank", rel: "noopener noreferrer" } as const;
const PAGE = 30;
const SOURCES = [
  "titck",
  "eu_es_cima",
  "eu_fr_bdpm",
  "wikidata",
  "openfda_ndc",
  "titck+eu_es_cima",
] as const;

/** A source id as a translated name; an unknown id is shown as the code. */
function useSourceName() {
  const t = useT();
  return (id: string) =>
    (SOURCES as readonly string[]).includes(id)
      ? t(`DataQuality.source.${id.replace("+", "_")}`)
      : id;
}

export function DataQuality() {
  const t = useT();
  const { client, recorded, failed } = useDemoClient(
    liveDataQuality,
    loadDataQualityFixture,
    demoDataQuality,
  );
  const call = useCall(client ? () => client.report() : null, [client]);
  const locale = useLocale();
  const summary =
    call.status === "ok"
      ? t("DataQuality.summary", {
          count: call.data.summary.findings,
          date: new Intl.DateTimeFormat(locale, {
            dateStyle: "long",
            timeZone: "UTC",
          }).format(new Date(`${call.data.run_date}T00:00:00Z`)),
        })
      : undefined;
  return (
    <>
      <BackLink href="/research">{t("Research.title")}</BackLink>
      <LargeTitle
        title={t("DataQuality.title")}
        summary={summary}
        summaryTestId="dq-summary"
      />
      <p className="max-w-[72ch]">{t("DataQuality.intro")}</p>
      <div className="flex flex-col gap-2">
        <p className="card p-4 font-bold" data-testid="dq-codes-only">
          {t("DataQuality.codesOnly")}
        </p>
        <p className="text-sm text-muted" role="note" data-testid="dq-review">
          {t("DataQuality.review")}
        </p>
        {recorded ? (
          <p className="chip self-start" data-testid="dq-demo">
            {t("DataQuality.demo", { date: recorded })}
          </p>
        ) : null}
      </div>
      {failed ? (
        <StateView state="error" messageKey="Errors.generic" />
      ) : call.status === "error" ? (
        <StateView
          state="error"
          messageKey={call.error.messageKey}
          retry={call.retry}
        />
      ) : call.status !== "ok" || !client ? (
        <StateView state="loading" label={t("DataQuality.loading")} />
      ) : (
        <Report r={call.data} client={client} />
      )}
    </>
  );
}

function Report({
  r,
  client,
}: {
  r: DataQualityReport;
  client: DataQualityClient;
}) {
  const t = useT();
  const locale = useLocale();
  const nf = new Intl.NumberFormat(locale);
  const counts = classStatusCounts(r.findings);
  const sourceName = useSourceName();
  return (
    <div className="grid gap-group lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)] lg:items-start">
      <div className="flex min-w-0 flex-col gap-group">
        <SummaryCard
          id="dq-run"
          title={t("DataQuality.run.title")}
          summary={
            r.previous_run_id
              ? t("DataQuality.run.previous")
              : t("DataQuality.run.first")
          }
          data-testid="dq-run"
        >
          <StatGrid>
            {CLASSES.map((c) => (
              <StatTile
                key={c}
                value={nf.format(r.summary.by_class[c])}
                label={t(`DataQuality.class.${c}`)}
                sentence={t("DataQuality.run.tile", {
                  count: r.summary.by_class[c],
                  klass: t(`DataQuality.class.${c}`),
                })}
              />
            ))}
          </StatGrid>
          <p className="text-sm" data-testid="dq-class-meaning">
            {t("DataQuality.classMeaning")}
          </p>
          <div
            className="overflow-x-auto"
            tabIndex={0}
            role="region"
            aria-label={t("DataQuality.run.tableLabel")}
          >
            <table className="tm-table nowrap" data-testid="dq-class-status">
              <caption className="sr-only">
                {t("DataQuality.run.tableLabel")}
              </caption>
              <thead>
                <tr>
                  <th scope="col">{t("DataQuality.filter.class")}</th>
                  {STATUSES.map((s) => (
                    <th key={s} scope="col">
                      {t(`DataQuality.status.${s}`)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {CLASSES.map((c) => (
                  <tr key={c}>
                    <th scope="row">{t(`DataQuality.class.${c}`)}</th>
                    {STATUSES.map((s) => (
                      <td key={s} className="mono">
                        {nf.format(counts[c][s])}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-sm text-muted">
            {t("DataQuality.run.upstream", {
              still: r.summary.confirmed_errors_still_published,
              resolved: r.summary.confirmed_errors_resolved_upstream,
            })}
          </p>
        </SummaryCard>
        <Findings findings={r.findings} />
      </div>
      <div className="flex min-w-0 flex-col gap-group">
        <Upstream />
        <GroupedList
          header={t("DataQuality.files.title")}
          headingId="dq-files"
          data-testid="dq-files"
          footer={
            <>
              <p className="mono break-all">
                {t("DataQuality.files.version", { version: r.version })}
              </p>
              <p>{t("DataQuality.files.licence")}</p>
              <p className="break-words" lang="en">
                {r.attribution}
              </p>
            </>
          }
        >
          {(["csv", "json", "md"] as const).map((kind) => (
            <li key={kind} className="row-link">
              <a
                href={client.download(kind)}
                download={`janus-data-quality-${r.run_date}.${kind}`}
                data-testid={`dq-download-${kind}`}
              >
                <DownloadIcon size={18} className="shrink-0" />
                <span className="min-w-0 flex-1">
                  {t(`DataQuality.files.${kind}`)}
                </span>
              </a>
            </li>
          ))}
          <li className="row-link">
            <a href={`${REPO}/docs/open-data.md`} {...EXTERNAL}>
              <span className="min-w-0 flex-1">
                {t("DataQuality.files.dictionary")}
              </span>
            </a>
          </li>
        </GroupedList>
        <GroupedList
          header={t("DataQuality.sources.title")}
          headingId="dq-sources"
          data-testid="dq-sources"
          footer={<p>{t("DataQuality.sources.footer")}</p>}
        >
          {Object.entries(r.sources).map(([id, s]) => (
            <Row key={id}>
              <span className="font-bold">{sourceName(id)}</span>
              <span className="text-sm text-muted">
                {t("DataQuality.sources.line", {
                  date: s.snapshot_date.slice(0, 10),
                })}
              </span>
              <span className="text-sm break-words" lang="en">
                {s.license}
              </span>
            </Row>
          ))}
        </GroupedList>
      </div>
    </div>
  );
}

function Findings({ findings }: { findings: readonly Finding[] }) {
  const t = useT();
  const [filter, setFilter] = useState<Filter>({
    klass: "all",
    status: "all",
    query: "",
  });
  const [shown, setShown] = useState(PAGE);
  const list = useMemo(
    () => filterFindings(findings, filter),
    [findings, filter],
  );
  const set = (f: Partial<Filter>) => {
    setFilter((x) => ({ ...x, ...f }));
    setShown(PAGE);
  };
  return (
    <section
      className="flex min-w-0 flex-col gap-3"
      aria-labelledby="dq-findings"
      data-testid="dq-findings"
    >
      <h2 id="dq-findings" className="group-header">
        {t("DataQuality.findings.title")}
      </h2>
      <SegmentedControl
        legend={t("DataQuality.filter.class")}
        legendVisible
        name="dq-class"
        variant="pills"
        value={filter.klass}
        onChange={(klass) => set({ klass })}
        options={[
          { value: "all", label: t("DataQuality.filter.all") },
          ...CLASSES.map((c) => ({
            value: c,
            label: t(`DataQuality.class.${c}`),
          })),
        ]}
      />
      <SegmentedControl
        legend={t("DataQuality.filter.status")}
        legendVisible
        name="dq-status"
        variant="pills"
        value={filter.status}
        onChange={(status) => set({ status })}
        options={[
          { value: "all", label: t("DataQuality.filter.all") },
          ...STATUSES.map((s) => ({
            value: s,
            label: t(`DataQuality.status.${s}`),
          })),
        ]}
      />
      <label className="flex flex-col gap-1">
        <span className="font-bold">{t("DataQuality.filter.search")}</span>
        <input
          type="search"
          className="min-h-11 w-full rounded-[var(--radius-button)] border border-line bg-surface px-3 py-2 text-fg"
          value={filter.query}
          maxLength={60}
          autoComplete="off"
          spellCheck={false}
          onChange={(e) => set({ query: e.target.value })}
          data-testid="dq-search"
        />
      </label>
      <p
        className="text-sm text-muted"
        aria-live="polite"
        data-testid="dq-count"
      >
        {t("DataQuality.findings.count", {
          shown: Math.min(shown, list.length),
          count: list.length,
        })}
      </p>
      {list.length === 0 ? (
        <StateView state="empty" message={t("DataQuality.findings.empty")} />
      ) : (
        <ul className="grouped" data-testid="dq-list">
          {list.slice(0, shown).map((f) => (
            <FindingRow key={f.id} f={f} />
          ))}
        </ul>
      )}
      {list.length > shown ? (
        <Button
          variant="secondary"
          className="self-start"
          onClick={() => setShown((s) => s + PAGE)}
          data-testid="dq-more"
        >
          {t("DataQuality.findings.more", {
            count: Math.min(PAGE, list.length - shown),
          })}
        </Button>
      ) : null}
    </section>
  );
}

function FindingRow({ f }: { f: Finding }) {
  const t = useT();
  const sourceName = useSourceName();
  const wikidata = evidenceLink(f.wikidata_url);
  const whocc = f.whocc_group_urls
    .map((u) => ({ href: evidenceLink(u), group: whoccGroup(u) }))
    .filter((x): x is { href: string; group: string } => !!x.href && !!x.group);
  return (
    <li data-testid="dq-finding" data-class={f.class}>
      <Disclosure
        summary={
          <span className="flex min-w-0 flex-col gap-0.5">
            <span className="font-bold break-words">
              <span lang="en">{f.label_en ?? f.key}</span>{" "}
              <span className="mono">{f.code.split("|").join(", ")}</span>
            </span>
            <span className="text-sm text-muted">
              {sourceName(f.source)} · {t(`DataQuality.class.${f.class}`)} ·{" "}
              {t(`DataQuality.status.${f.status}`)}
            </span>
          </span>
        }
      >
        <dl className="grid grid-cols-1 gap-x-4 gap-y-1 text-sm sm:grid-cols-[auto_1fr]">
          <dt className="text-muted">{t("DataQuality.finding.check")}</dt>
          <dd>{t(`DataQuality.check.${f.check}`)}</dd>
          <dt className="text-muted">{t("DataQuality.finding.key")}</dt>
          <dd className="mono">{f.key}</dd>
          <dt className="text-muted">{t("DataQuality.finding.compared")}</dt>
          <dd className="mono break-words">
            {f.compared_codes.length ? f.compared_codes.join(", ") : "—"}
          </dd>
          <dt className="text-muted">{t("DataQuality.finding.products")}</dt>
          <dd>
            {t("DataQuality.finding.productsValue", { count: f.products })}
          </dd>
          <dt className="text-muted">{t("DataQuality.finding.reasons")}</dt>
          <dd>
            <ul className="list-disc ps-5">
              {f.reasons.map((r) => (
                <li key={r}>{reasonText(t, r)}</li>
              ))}
            </ul>
          </dd>
          {f.other_keys.length ? (
            <>
              <dt className="text-muted">
                {t("DataQuality.finding.otherKeys")}
              </dt>
              <dd className="mono">{f.other_keys.join(", ")}</dd>
            </>
          ) : null}
          {f.upstream ? (
            <>
              <dt className="text-muted">
                {t("DataQuality.finding.upstream")}
              </dt>
              <dd>{t(`DataQuality.upstreamStatus.${f.upstream}`)}</dd>
            </>
          ) : null}
          {f.class_changed_from ? (
            <>
              <dt className="text-muted">
                {t("DataQuality.finding.changedFrom")}
              </dt>
              <dd>{t(`DataQuality.class.${f.class_changed_from}`)}</dd>
            </>
          ) : null}
          <dt className="text-muted">{t("DataQuality.finding.reportTo")}</dt>
          <dd>{t(`DataQuality.upstream.target.${upstreamTarget(f)}`)}</dd>
        </dl>
        <p className="text-sm font-bold">{t("DataQuality.finding.evidence")}</p>
        <ul className="flex flex-wrap gap-2" data-testid="dq-evidence">
          {wikidata ? (
            <li>
              <a
                className="chip inline-flex min-h-11 items-center"
                href={wikidata}
                {...EXTERNAL}
              >
                {t("DataQuality.finding.wikidata", { key: f.key })}
              </a>
            </li>
          ) : null}
          {whocc.map((w) => (
            <li key={w.href}>
              <a
                className="chip mono inline-flex min-h-11 items-center"
                href={w.href}
                {...EXTERNAL}
              >
                {t("DataQuality.finding.whocc", { group: w.group })}
              </a>
            </li>
          ))}
        </ul>
        <p className="text-sm break-words">
          <span className="text-muted">
            {t("DataQuality.finding.howToFind")}:{" "}
          </span>
          <span lang="en">{f.how_to_find}</span>
        </p>
      </Disclosure>
    </li>
  );
}

const REASONS = new Set([
  "both_regulators_publish_it",
  "code_of_other_substance",
  "combination_code_on_single_ingredient_product",
  "group_differs",
  "item_agrees_with_cima",
  "item_agrees_with_titck",
  "no_longer_published",
  "not_a_medicine",
  "old_code",
  "one_substance_code_two_keys",
  "regulators_differ",
  "same_level2_group",
  "still_published",
  "wrong_substance",
]);

/** A reason code as text; a code the web app does not know yet is shown as the code. */
function reasonText(t: ReturnType<typeof useT>, code: string) {
  return REASONS.has(code) ? t(`DataQuality.reason.${code}`) : code;
}

function Upstream() {
  const t = useT();
  return (
    <SummaryCard
      id="dq-upstream"
      title={t("DataQuality.upstream.title")}
      data-testid="dq-upstream"
    >
      <p className="font-bold">{t("DataQuality.upstream.pharmacist")}</p>
      <ol className="flex list-decimal flex-col gap-2 ps-5">
        <li>{t("DataQuality.upstream.steps.wikidata")}</li>
        <li>{t("DataQuality.upstream.steps.titck")}</li>
        <li>{t("DataQuality.upstream.steps.cima")}</li>
        <li>{t("DataQuality.upstream.steps.janus")}</li>
      </ol>
      <p className="text-sm text-muted">
        {t("DataQuality.upstream.nothingSent")}
      </p>
      <a
        className="inline-flex min-h-11 items-center self-start font-bold"
        href={`${REPO}/docs/contributing-corrections.md`}
        {...EXTERNAL}
      >
        {t("DataQuality.upstream.guide")}
      </a>
    </SummaryCard>
  );
}
