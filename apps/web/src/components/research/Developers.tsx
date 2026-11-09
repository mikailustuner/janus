"use client";
/**
 * "For developers & clinicians" (research-tools Req 3): how to use Janus from other tools — the
 * MCP server (docs/mcp.md), the CDS Hooks service (docs/cds-hooks.md), the public read-only API
 * (docs/openapi-public.json) and the open data packages (data/open/) — with copyable snippets.
 * Static: no request. The snippets are code, shown verbatim in every language.
 */
import { useState, useSyncExternalStore, type ReactNode } from "react";

import { BackLink, LargeTitle, SummaryCard } from "@/components/cards";
import { Button } from "@/components/ui";
import { useT } from "@/theme/words";

const REPO = "https://github.com/mikailustuner/janus/blob/main";
const TREE = "https://github.com/mikailustuner/janus/tree/main";
const EXTERNAL = { target: "_blank", rel: "noopener noreferrer" } as const;

const CLAUDE_CODE = `claude mcp add janus -e JANUS_API_URL=http://127.0.0.1:8000 -- uv run --directory apps/mcp janus-mcp`;

const CLAUDE_DESKTOP = `{
  "mcpServers": {
    "janus": {
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path/to/janus/apps/mcp", "janus-mcp"],
      "env": { "JANUS_API_URL": "http://127.0.0.1:8000" }
    }
  }
}`;

const KIRO = `{
  "mcpServers": {
    "janus": {
      "command": "uv",
      "args": ["run", "--directory", "apps/mcp", "janus-mcp"],
      "env": { "JANUS_API_URL": "http://127.0.0.1:8000" },
      "disabled": false,
      "autoApprove": ["janus_cascade_package_rows", "janus_time_machine_catalogue", "janus_time_machine_cascade"]
    }
  }
}`;

const CDS_PREFETCH = `medicationRequests:   MedicationRequest?patient={{context.patientId}}&status=active,on-hold
medicationStatements: MedicationStatement?patient={{context.patientId}}&status=active,on-hold`;

const noSubscribe = () => () => {};

/** The API base of this deployment (`<origin>/api`), known only in the browser. */
function useApiBase(): string {
  return useSyncExternalStore(
    noSubscribe,
    () => `${location.origin}/api`,
    () => "https://<host>/api",
  );
}

/** A code block with a copy button; the block scrolls inside its own box (no page scroll). */
function Snippet({
  label,
  code,
  id,
}: {
  label: string;
  code: string;
  id: string;
}) {
  const t = useT();
  const [copied, setCopied] = useState<"idle" | "done" | "failed">("idle");
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied("done");
    } catch {
      setCopied("failed");
    }
  };
  return (
    <figure
      className="m-0 flex min-w-0 flex-col gap-2"
      data-testid={`dev-${id}`}
    >
      <figcaption className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-bold">{label}</span>
        <Button
          variant="secondary"
          onClick={copy}
          aria-describedby={`dev-${id}-status`}
          data-testid={`dev-copy-${id}`}
        >
          {t("Developers.copy")}
        </Button>
      </figcaption>
      <pre
        className="tile m-0 overflow-x-auto p-3 text-sm"
        tabIndex={0}
        aria-label={label}
      >
        <code className="mono">{code}</code>
      </pre>
      <p
        id={`dev-${id}-status`}
        className="text-sm text-muted"
        aria-live="polite"
      >
        {copied === "done"
          ? t("Developers.copied")
          : copied === "failed"
            ? t("Developers.copyFailed")
            : ""}
      </p>
    </figure>
  );
}

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

export function Developers() {
  const t = useT();
  const api = useApiBase();
  const curl = [
    `curl -s ${api}/open/faers-onset/5 | jq '.row.status, .row.median_days'`,
    `curl -s ${api}/open/data-quality | jq '.version, .summary.by_class'`,
    `curl -s -o pipc.json ${api}/open/cascade-package/pipc`,
  ].join("\n");
  return (
    <>
      <BackLink href="/research">{t("Research.title")}</BackLink>
      <LargeTitle
        title={t("Developers.title")}
        summary={t("Developers.summary")}
      />
      <p className="max-w-[72ch]">{t("Developers.intro")}</p>
      <p className="card p-4 font-bold" data-testid="dev-not-clinical">
        {t("Developers.notClinical")}
      </p>
      <div className="grid gap-group lg:grid-cols-2 lg:items-start">
        <div className="flex min-w-0 flex-col gap-group">
          <SummaryCard
            id="dev-mcp"
            title={t("Developers.mcp.title")}
            summary={t("Developers.mcp.summary")}
            data-testid="dev-mcp"
          >
            <p>{t("Developers.mcp.body")}</p>
            <p className="text-sm">{t("Developers.mcp.safety")}</p>
            <Snippet
              id="claude-code"
              label={t("Developers.mcp.claudeCode")}
              code={CLAUDE_CODE}
            />
            <Snippet
              id="claude-desktop"
              label={t("Developers.mcp.claudeDesktop")}
              code={CLAUDE_DESKTOP}
            />
            <Snippet id="kiro" label={t("Developers.mcp.kiro")} code={KIRO} />
            <p className="text-sm text-muted">{t("Developers.mcp.privacy")}</p>
            <DocLink href={`${REPO}/docs/mcp.md`}>
              {t("Developers.mcp.doc")}
            </DocLink>
          </SummaryCard>
          <SummaryCard
            id="dev-cds"
            title={t("Developers.cds.title")}
            summary={t("Developers.cds.summary")}
            data-testid="dev-cds"
          >
            <p className="font-bold">{t("Developers.cds.sandboxOnly")}</p>
            <p>{t("Developers.cds.body")}</p>
            <Snippet
              id="cds-discovery"
              label={t("Developers.cds.discovery")}
              code={`GET ${api}/cds-services\nPOST ${api}/cds-services/janus-cascade`}
            />
            <Snippet
              id="cds-prefetch"
              label={t("Developers.cds.prefetch")}
              code={CDS_PREFETCH}
            />
            <p className="text-sm">{t("Developers.cds.cards")}</p>
            <DocLink href={`${REPO}/docs/cds-hooks.md`}>
              {t("Developers.cds.doc")}
            </DocLink>
          </SummaryCard>
        </div>
        <div className="flex min-w-0 flex-col gap-group">
          <SummaryCard
            id="dev-api"
            title={t("Developers.api.title")}
            summary={t("Developers.api.summary")}
            data-testid="dev-api"
          >
            <p>{t("Developers.api.body")}</p>
            <Snippet
              id="curl"
              label={t("Developers.api.examples")}
              code={curl}
            />
            <p className="text-sm">{t("Developers.api.rules")}</p>
            <DocLink href={`${REPO}/docs/openapi-public.json`}>
              {t("Developers.api.openapi")}
            </DocLink>
            <DocLink href={`${REPO}/docs/open-api.md`}>
              {t("Developers.api.doc")}
            </DocLink>
          </SummaryCard>
          <SummaryCard
            id="dev-data"
            title={t("Developers.data.title")}
            summary={t("Developers.data.summary")}
            data-testid="dev-data"
          >
            <ul className="grouped-plain">
              {(
                ["cascade-package", "data-quality", "faers-onset"] as const
              ).map((p) => (
                <li key={p} className="flex min-w-0 flex-col gap-0.5">
                  <a
                    className="mono inline-flex min-h-11 items-center font-bold break-all"
                    href={`${TREE}/data/open/${p}`}
                    {...EXTERNAL}
                  >
                    data/open/{p}
                  </a>
                  <span className="text-sm text-muted">
                    {t(`Developers.data.${p}`)}
                  </span>
                </li>
              ))}
            </ul>
            <p className="text-sm">{t("Developers.data.frictionless")}</p>
            <DocLink href={`${REPO}/docs/open-data.md`}>
              {t("Developers.data.doc")}
            </DocLink>
          </SummaryCard>
        </div>
      </div>
    </>
  );
}
