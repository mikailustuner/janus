"use client";
/**
 * "Janus for researchers" (spec for-researchers): one static page that says what a researcher can
 * use and how to start in ten minutes — open data, public read-only API, MCP server, CDS Hooks
 * service, pipelines, research notes, a worked example, limits and how to cite. Every statement
 * is backed by a file in the repository (docs/for-researchers.md is the English twin). No request.
 */
import type { ReactNode } from "react";

import { BackLink, LargeTitle, SummaryCard } from "@/components/cards";
import { KIRO, Snippet } from "@/components/research/Developers";
import {
  API_ROUTES,
  CITATION,
  CURL_EXAMPLES,
  DATA_PACKAGES,
  MCP_RUN,
  ONSET_EXAMPLE,
  ONSET_OUTPUT,
  PIPELINE_RUN,
  REPO,
  SITE,
} from "@/research/forResearchers";
import { useT } from "@/theme/words";

const BLOB = `${REPO}/blob/main`;
const TREE = `${REPO}/tree/main`;
const EXTERNAL = { target: "_blank", rel: "noopener noreferrer" } as const;

function DocLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a
      className="inline-flex min-h-11 items-center self-start font-bold"
      href={href}
      {...EXTERNAL}
    >
      {children}
    </a>
  );
}

export function ForResearchers() {
  const t = useT();
  return (
    <>
      <BackLink href="/research">{t("Research.title")}</BackLink>
      <LargeTitle
        title={t("ForResearchers.title")}
        summary={t("ForResearchers.summary")}
      />
      <p className="max-w-[72ch]">{t("ForResearchers.intro")}</p>
      <p className="card p-4 font-bold" data-testid="fr-status">
        {t("ForResearchers.status")}
      </p>
      <SummaryCard
        id="fr-path"
        title={t("ForResearchers.path.title")}
        summary={t("ForResearchers.path.summary")}
        data-testid="fr-path"
      >
        <ol className="m-0 flex list-decimal flex-col gap-2 pl-6">
          {([1, 2, 3, 4] as const).map((n) => (
            <li key={n}>{t(`ForResearchers.path.s${n}`)}</li>
          ))}
        </ol>
      </SummaryCard>
      <div className="grid gap-group lg:grid-cols-2 lg:items-start">
        <div className="flex min-w-0 flex-col gap-group">
          <SummaryCard
            id="fr-data"
            title={t("ForResearchers.data.title")}
            summary={t("ForResearchers.data.summary")}
            data-testid="fr-data"
          >
            <ul className="grouped-plain">
              {DATA_PACKAGES.map((p) => (
                <li key={p.key} className="flex min-w-0 flex-col gap-0.5">
                  <a
                    className="mono inline-flex min-h-11 items-center font-bold break-all"
                    href={`${TREE}/${p.path}`}
                    {...EXTERNAL}
                  >
                    {p.path}
                  </a>
                  <span className="text-sm text-muted">
                    {t(`ForResearchers.data.${p.key}`)}
                  </span>
                </li>
              ))}
              <li className="flex min-w-0 flex-col gap-0.5">
                <span className="mono font-bold break-all">
                  GET /open/outcomes
                </span>
                <span className="text-sm text-muted">
                  {t("ForResearchers.data.outcomes")}
                </span>
              </li>
            </ul>
            <p className="text-sm">{t("ForResearchers.data.licences")}</p>
            <DocLink href={`${BLOB}/docs/open-data.md`}>
              {t("ForResearchers.data.doc")}
            </DocLink>
          </SummaryCard>
          <SummaryCard
            id="fr-api"
            title={t("ForResearchers.api.title")}
            summary={t("ForResearchers.api.summary")}
            data-testid="fr-api"
          >
            <p>{t("ForResearchers.api.body", { base: `${SITE}/api` })}</p>
            <ul className="grouped-plain">
              {API_ROUTES.map((r) => (
                <li key={r.key} className="flex min-w-0 flex-col gap-0.5">
                  <span className="mono font-bold break-all">{r.routes}</span>
                  <span className="text-sm text-muted">
                    {t(`ForResearchers.api.routes.${r.key}`)}
                  </span>
                </li>
              ))}
            </ul>
            <Snippet
              id="fr-curl"
              label={t("ForResearchers.api.examples")}
              code={CURL_EXAMPLES}
            />
            <p className="text-sm" data-testid="fr-rate">
              {t("ForResearchers.api.rate")}
            </p>
            <p className="text-sm">{t("ForResearchers.api.noPost")}</p>
            <DocLink href={`${BLOB}/docs/openapi-public.json`}>
              {t("ForResearchers.api.openapi")}
            </DocLink>
            <DocLink href={`${BLOB}/docs/open-api.md`}>
              {t("ForResearchers.api.doc")}
            </DocLink>
          </SummaryCard>
          <SummaryCard
            id="fr-example"
            title={t("ForResearchers.example.title")}
            summary={t("ForResearchers.example.summary")}
            data-testid="fr-example"
          >
            <p>{t("ForResearchers.example.body")}</p>
            <Snippet
              id="fr-example-code"
              label={t("ForResearchers.example.code")}
              code={ONSET_EXAMPLE}
            />
            <Snippet
              id="fr-example-output"
              label={t("ForResearchers.example.output")}
              code={ONSET_OUTPUT}
            />
            <p className="text-sm">{t("ForResearchers.example.caveat")}</p>
            <DocLink href={`${BLOB}/docs/examples/onset_summary.py`}>
              {t("ForResearchers.example.file")}
            </DocLink>
          </SummaryCard>
        </div>
        <div className="flex min-w-0 flex-col gap-group">
          <SummaryCard
            id="fr-mcp"
            title={t("ForResearchers.mcp.title")}
            summary={t("ForResearchers.mcp.summary")}
            data-testid="fr-mcp"
          >
            <p>{t("ForResearchers.mcp.body")}</p>
            <Snippet
              id="fr-mcp-run"
              label={t("ForResearchers.mcp.run")}
              code={MCP_RUN}
            />
            <Snippet
              id="fr-mcp-kiro"
              label={t("ForResearchers.mcp.kiro")}
              code={KIRO}
            />
            <DocLink href={`${BLOB}/docs/mcp.md`}>
              {t("ForResearchers.mcp.doc")}
            </DocLink>
          </SummaryCard>
          <SummaryCard
            id="fr-cds"
            title={t("ForResearchers.cds.title")}
            summary={t("ForResearchers.cds.summary")}
            data-testid="fr-cds"
          >
            <p className="font-bold">{t("ForResearchers.cds.sandbox")}</p>
            <p>{t("ForResearchers.cds.body")}</p>
            <Snippet
              id="fr-cds-discovery"
              label={t("ForResearchers.cds.discovery")}
              code={`GET ${SITE}/api/cds-services\nPOST ${SITE}/api/cds-services/janus-cascade`}
            />
            <p className="text-sm">{t("ForResearchers.cds.noAuth")}</p>
            <DocLink href={`${BLOB}/docs/cds-hooks.md`}>
              {t("ForResearchers.cds.doc")}
            </DocLink>
          </SummaryCard>
          <SummaryCard
            id="fr-pipelines"
            title={t("ForResearchers.pipelines.title")}
            summary={t("ForResearchers.pipelines.summary")}
            data-testid="fr-pipelines"
          >
            <p>{t("ForResearchers.pipelines.body")}</p>
            <Snippet
              id="fr-pipelines-run"
              label={t("ForResearchers.pipelines.run")}
              code={PIPELINE_RUN}
            />
            <p className="text-sm">{t("ForResearchers.pipelines.notes")}</p>
            <DocLink href={`${BLOB}/pipelines/sources.toml`}>
              sources.toml
            </DocLink>
            <DocLink href={`${BLOB}/NOTICE`}>NOTICE</DocLink>
            <DocLink href={`${BLOB}/pipelines/README.md`}>
              {t("ForResearchers.pipelines.doc")}
            </DocLink>
          </SummaryCard>
          <SummaryCard
            id="fr-notes"
            title={t("ForResearchers.notes.title")}
            summary={t("ForResearchers.notes.summary")}
            data-testid="fr-notes"
          >
            <p className="font-bold" data-testid="fr-notes-status">
              {t("ForResearchers.notes.status")}
            </p>
            <DocLink
              href={`${BLOB}/docs/research/httk-pop-older-adult-exposure.md`}
            >
              {t("ForResearchers.notes.httk")}
            </DocLink>
            <DocLink href={`${BLOB}/docs/research/negative-results.md`}>
              {t("ForResearchers.notes.negative")}
            </DocLink>
          </SummaryCard>
        </div>
      </div>
      <SummaryCard
        id="fr-limits"
        title={t("ForResearchers.limits.title")}
        summary={t("ForResearchers.limits.summary")}
        data-testid="fr-limits"
      >
        <ul className="m-0 flex list-disc flex-col gap-2 pl-6">
          {([1, 2, 3, 4] as const).map((n) => (
            <li key={n}>{t(`ForResearchers.limits.l${n}`)}</li>
          ))}
        </ul>
        <p>{t("ForResearchers.limits.report")}</p>
        <DocLink href={`${REPO}/issues`}>
          {t("ForResearchers.limits.issues")}
        </DocLink>
        <DocLink href={`${BLOB}/docs/contributing-corrections.md`}>
          {t("ForResearchers.limits.corrections")}
        </DocLink>
      </SummaryCard>
      <SummaryCard
        id="fr-cite"
        title={t("ForResearchers.cite.title")}
        summary={t("ForResearchers.cite.summary")}
        data-testid="fr-cite"
      >
        <p>{t("ForResearchers.cite.body")}</p>
        <Snippet
          id="fr-cite-text"
          label={t("ForResearchers.cite.example")}
          code={CITATION}
        />
        <p className="text-sm">{t("ForResearchers.cite.pipc")}</p>
        <p className="mono text-sm break-words">
          Rochon PA et al. Eur Geriatr Med 2025;16(5):1573-1584.
          doi:10.1007/s41999-025-01215-x
        </p>
      </SummaryCard>
    </>
  );
}
