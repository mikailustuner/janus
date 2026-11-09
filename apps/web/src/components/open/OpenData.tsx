"use client";
/**
 * The Open data page (open-data Req 3, 8; design §8): the open outcome dataset as a public
 * aggregate dashboard — released cells per layer as tiles and tables, or the honest empty state
 * "no released cells yet" (no example number, no large zero) — the release rule, the downloads
 * (CSV, JSON) with version, snapshot date and CC BY 4.0, then the cascade data package and the
 * public API. Demo mode answers from the recorded file with no request.
 */
import { useLocale } from "next-intl";
import { useEffect, useMemo, useState, useSyncExternalStore } from "react";

import {
  GroupedList,
  LargeTitle,
  Row,
  StatGrid,
  StatTile,
  SummaryCard,
} from "@/components/cards";
import { DownloadIcon } from "@/components/icons";
import { keyName } from "@/components/names";
import { StateView } from "@/components/StateView";
import { useDemo } from "@/demo/session";
import { useCall } from "@/flow/useCall";
import {
  byLayer,
  demoOpenData,
  liveOpenData,
  loadOpenFixture,
  type OpenDataClient,
  type OpenFixture,
  type OpenOutcomes,
} from "@/open/model";
import summary from "@/open/package-summary.json";
import { useT } from "@/theme/words";
import { useVocabulary } from "@/vocabulary/use";

const REPO = "https://github.com/mikailustuner/janus/blob/main";
const EXTERNAL = { target: "_blank", rel: "noopener noreferrer" } as const;
const noSubscribe = () => () => {};

function useOpenClient(): {
  client: OpenDataClient | null;
  recorded: string | null;
} {
  const demo = useDemo();
  const mounted = useSyncExternalStore(
    noSubscribe,
    () => true,
    () => false,
  );
  const [fx, setFx] = useState<OpenFixture | null>(null);
  useEffect(() => {
    let live = true;
    if (demo) loadOpenFixture().then((f) => live && setFx(f));
    return () => {
      live = false;
    };
  }, [demo]);
  const client = useMemo(
    () =>
      !mounted ? null : demo ? (fx ? demoOpenData(fx) : null) : liveOpenData,
    [mounted, demo, fx],
  );
  return { client, recorded: demo ? (fx?.recorded ?? null) : null };
}

export function OpenData() {
  const t = useT();
  const { client, recorded } = useOpenClient();
  const call = useCall(client ? () => client.outcomes() : null, [client]);
  return (
    <>
      <LargeTitle title={t("OpenData.title")} summary={t("OpenData.summary")} />
      <p className="max-w-[72ch]">{t("OpenData.intro")}</p>
      {recorded ? (
        <p className="chip self-start" data-testid="open-demo">
          {t("OpenData.demo", { date: recorded })}
        </p>
      ) : null}
      <div className="grid gap-group lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)] lg:items-start">
        <div className="flex min-w-0 flex-col gap-group">
          {call.status === "error" ? (
            <StateView
              state="error"
              messageKey={call.error.messageKey}
              retry={call.retry}
            />
          ) : call.status !== "ok" || !client ? (
            <StateView state="loading" label={t("OpenData.loading")} />
          ) : (
            <Dataset o={call.data} client={client} />
          )}
        </div>
        <div className="flex min-w-0 flex-col gap-group">
          <Package />
        </div>
      </div>
    </>
  );
}

function Dataset({ o, client }: { o: OpenOutcomes; client: OpenDataClient }) {
  const t = useT();
  const locale = useLocale();
  const vocab = useVocabulary();
  const nf = new Intl.NumberFormat(locale);
  const layers = byLayer(o);
  const date = new Intl.DateTimeFormat(locale, {
    dateStyle: "long",
    timeZone: "UTC",
  }).format(new Date(`${o.snapshot_date}T00:00:00Z`));
  return (
    <>
      <SummaryCard
        id="open-dataset"
        title={t("OpenData.dataset.title")}
        summary={
          o.cells.length
            ? t("OpenData.dataset.cellsLine", { count: o.cells.length })
            : undefined
        }
        data-testid="open-dataset"
      >
        {o.cells.length === 0 ? (
          <p className="font-bold" data-testid="open-empty">
            {t("OpenData.dataset.empty")}
          </p>
        ) : (
          <>
            {/* No large zero (janus-report DP9): only layers with released cells get a tile. */}
            <StatGrid>
              {layers
                .filter((l) => l.cells.length > 0)
                .map((l) => (
                  <StatTile
                    key={l.layer}
                    value={nf.format(l.cells.length)}
                    label={`${t(`OpenData.dataset.layer.${l.layer}`)} · ${t("OpenData.dataset.layerTile", { count: l.cells.length })}`}
                  />
                ))}
            </StatGrid>
            {layers
              .filter((l) => l.cells.length > 0)
              .map((l) => (
                <div key={l.layer} className="flex min-w-0 flex-col gap-2">
                  <h3 className="font-body font-bold">
                    {t(`OpenData.dataset.layer.${l.layer}`)}
                  </h3>
                  <div
                    className="overflow-x-auto"
                    tabIndex={0}
                    role="region"
                    aria-label={t("TimeMachine.tableRegion")}
                  >
                    <table className="tm-table" data-testid="open-cells">
                      <thead>
                        <tr>
                          <th scope="col">
                            {t("OpenData.dataset.cols.ingredients")}
                          </th>
                          <th scope="col">
                            {t("OpenData.dataset.cols.event")}
                          </th>
                          <th scope="col">
                            {t("OpenData.dataset.cols.direction")}
                          </th>
                          <th scope="col">
                            {t("OpenData.dataset.cols.region")}
                          </th>
                          <th scope="col">
                            {t("OpenData.dataset.cols.value")}
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {l.cells.map((c) => (
                          <tr
                            key={`${c.ingredients.join("|")}-${c.event}-${c.direction}-${c.region}`}
                          >
                            <th scope="row">
                              {vocab
                                ? c.ingredients
                                    .map((k) => keyName(vocab, k, null))
                                    .join(" + ")
                                : c.ingredients.join(" + ")}
                            </th>
                            <td>
                              {vocab?.vocab.events[c.event]?.label ?? c.event}
                            </td>
                            <td>
                              {t(`OpenData.dataset.direction.${c.direction}`)}
                            </td>
                            <td>{t(`OpenData.dataset.region.${c.region}`)}</td>
                            <td className="mono">{nf.format(c.value)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ))}
          </>
        )}
        {o.withheld_layers.length ? (
          <p className="text-sm" data-testid="open-withheld">
            {t("OpenData.dataset.withheld", {
              layers: o.withheld_layers
                .map((l) => t(`OpenData.dataset.layer.${l}`))
                .join(", "),
            })}
          </p>
        ) : null}
        <p className="text-sm font-bold" role="note" data-testid="open-notices">
          {t("OpenData.rule.notices")}
        </p>
      </SummaryCard>

      <GroupedList
        header={t("OpenData.rule.title")}
        headingId="open-rule"
        data-testid="open-rule"
      >
        <Row>{t("OpenData.rule.k", { k: o.release_rule.k })}</Row>
        <Row>
          {t("OpenData.rule.noise", { epsilon: o.release_rule.epsilon })}
        </Row>
        <Row>{t("OpenData.rule.sibling", { k: o.release_rule.k })}</Row>
        <Row>{t("OpenData.rule.hidden")}</Row>
      </GroupedList>

      <GroupedList
        header={t("OpenData.files.title")}
        headingId="open-files"
        data-testid="open-files"
        footer={
          <>
            <p className="mono break-all">
              {t("OpenData.files.version", { version: o.version })}
            </p>
            <p>{t("OpenData.files.snapshot", { date })}</p>
            <p>{t("OpenData.files.licence", { attribution: o.attribution })}</p>
          </>
        }
      >
        {(["csv", "json"] as const).map((kind) => (
          <li key={kind} className="row-link">
            <a
              href={client.download(kind)}
              download={`janus-open-outcomes-${o.snapshot_date}.${kind}`}
              data-testid={`open-download-${kind}`}
            >
              <DownloadIcon size={18} className="shrink-0" />
              <span className="min-w-0 flex-1">
                {t(`OpenData.files.${kind}`)}
              </span>
            </a>
          </li>
        ))}
        <li className="row-link">
          <a href={`${REPO}/docs/open-data.md`} {...EXTERNAL}>
            <span className="flex min-w-0 flex-1 flex-col gap-0.5">
              <span>{t("OpenData.files.dictionary")}</span>
              <span className="text-sm font-normal text-muted">
                {t("OpenData.files.dictionaryBody")}
              </span>
            </span>
          </a>
        </li>
      </GroupedList>
    </>
  );
}

function Package() {
  const t = useT();
  const locale = useLocale();
  const date = new Intl.DateTimeFormat(locale, {
    dateStyle: "long",
    timeZone: "UTC",
  }).format(new Date(`${summary.created}T00:00:00Z`));
  return (
    <>
      <SummaryCard
        id="open-package"
        title={t("OpenData.package.title")}
        summary={t("OpenData.package.summary", {
          version: summary.version,
          date,
        })}
        data-testid="open-package"
      >
        <p>{t("OpenData.package.body")}</p>
        <ul className="grouped-plain">
          {summary.resources.map((r) => (
            <li key={r.path} className="flex min-w-0 flex-col gap-0.5">
              <span className="mono break-all">{r.path}</span>
              <span className="text-sm text-muted">
                {t("OpenData.package.rows", { rows: r.rows })} ·{" "}
                {r.licenses.join(", ")}
              </span>
            </li>
          ))}
        </ul>
      </SummaryCard>
      <GroupedList data-testid="open-links">
        <li className="row-link">
          <a href={`${REPO}/data/open/cascade-package`} {...EXTERNAL}>
            <span className="min-w-0 flex-1">{t("OpenData.package.open")}</span>
          </a>
        </li>
        <li className="row-link">
          <a href={`${REPO}/docs/open-api.md`} {...EXTERNAL}>
            <span className="flex min-w-0 flex-1 flex-col gap-0.5">
              <span>{t("OpenData.package.api")}</span>
              <span className="text-sm font-normal text-muted">
                {t("OpenData.package.apiBody")}
              </span>
            </span>
          </a>
        </li>
        <li className="row-link">
          <a href={`${REPO}/docs/contributing-corrections.md`} {...EXTERNAL}>
            <span className="flex min-w-0 flex-1 flex-col gap-0.5">
              <span>{t("OpenData.package.corrections")}</span>
              <span className="text-sm font-normal text-muted">
                {t("OpenData.package.correctionsBody")}
              </span>
            </span>
          </a>
        </li>
      </GroupedList>
    </>
  );
}
