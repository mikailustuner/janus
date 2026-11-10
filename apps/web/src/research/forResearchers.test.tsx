// Feature: for-researchers (requirements 2-4; design §4). The page is static; these tests check
// that its code is the code in the repository, that the route table is the one in the markdown
// twin, that the five catalogues have the same keys and the same placeholders, and that the wording
// rules hold (status line, "automated", nothing about the server or private folders).
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { ForResearchers } from "@/components/research/ForResearchers";
import {
  findForbiddenPhrases,
  forbiddenPhrases,
} from "@/i18n/forbidden-phrases";
import { routing } from "@/i18n/routing";

vi.mock("@/i18n/navigation", () => ({
  Link: ({ children }: { children: ReactNode }) => <a>{children}</a>,
}));

import {
  API_ROUTES,
  CITATION,
  CURL_EXAMPLES,
  MCP_RUN,
  ONSET_EXAMPLE,
  PIPELINE_RUN,
} from "./forResearchers";

type Locale = (typeof routing.locales)[number];
type Tree = { [key: string]: string | Tree };
const repo = (p: string) => join(import.meta.dirname, "../../../..", p);
const catalogues = Object.fromEntries(
  routing.locales.map((l) => [
    l,
    JSON.parse(
      readFileSync(
        join(import.meta.dirname, `../../messages/${l}.json`),
        "utf8",
      ),
    ) as Tree,
  ]),
) as Record<Locale, Tree>;

function flatten(tree: Tree, prefix = ""): Map<string, string> {
  const out = new Map<string, string>();
  for (const [key, value] of Object.entries(tree)) {
    const path = prefix ? `${prefix}.${key}` : key;
    if (typeof value === "string") out.set(path, value);
    else for (const [k, v] of flatten(value, path)) out.set(k, v);
  }
  return out;
}
const own = (l: Locale) =>
  new Map(
    [...flatten(catalogues[l])].filter(
      ([k]) =>
        k.startsWith("ForResearchers.") ||
        k.startsWith("Research.tools.forResearchers."),
    ),
  );
const args = (message: string) =>
  [...message.matchAll(/\{\s*([A-Za-z_]\w*)\s*(?:\}|,)/g)]
    .map((m) => m[1]!)
    .sort();
const html = (locale: Locale) =>
  renderToStaticMarkup(
    <NextIntlClientProvider
      locale={locale}
      messages={catalogues[locale] as never}
      timeZone="UTC"
    >
      <ForResearchers />
    </NextIntlClientProvider>,
  );
const text = (markup: string) =>
  markup
    .replace(/<[^>]+>/g, " ")
    .replace(/&#x27;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/&amp;/g, "&")
    .replace(/&gt;/g, ">")
    .replace(/\s+/g, " ");

const twin = readFileSync(repo("docs/for-researchers.md"), "utf8");

describe("code on the page is the code in the repository", () => {
  const script = readFileSync(repo("docs/examples/onset_summary.py"), "utf8");
  it("the worked example is the body of docs/examples/onset_summary.py", () => {
    expect(script.split('"""').slice(2).join('"""').trim()).toBe(ONSET_EXAMPLE);
  });
  it("the markdown twin carries the same example, commands and citation", () => {
    expect(twin).toContain(ONSET_EXAMPLE);
    for (const line of MCP_RUN.split("\n")) expect(twin).toContain(line);
    for (const line of PIPELINE_RUN.split("\n")) expect(twin).toContain(line);
    expect(twin.replace(/\s+/g, " ")).toContain(
      CITATION.replace(/ \(accessed.*$/, "").slice(0, 60),
    );
    for (const line of CURL_EXAMPLES.split("\n").filter((l) =>
      l.startsWith("curl"),
    ))
      expect(twin).toContain(line);
  });
  it("every listed route is in the markdown twin and in the public API docs", () => {
    const api = readFileSync(repo("docs/open-api.md"), "utf8");
    const openapi = readFileSync(repo("docs/openapi-public.json"), "utf8");
    for (const { routes } of API_ROUTES)
      for (const r of routes.replace(/^GET /, "").split(", ")) {
        const path = r.startsWith("/") ? r : "";
        if (!path) continue;
        expect(twin).toContain(path.replace(/\.csv$/, ""));
        const known = path.startsWith("/simulate/")
          ? api + twin
          : api + openapi;
        expect(known).toContain(path.replace(/\.csv$/, ""));
      }
  });
});

describe("catalogues", () => {
  const reference = own("en");
  it("have the same keys and placeholders in five languages", () => {
    expect(reference.size).toBeGreaterThan(80);
    for (const l of routing.locales) {
      const m = own(l);
      expect([...m.keys()].sort()).toEqual([...reference.keys()].sort());
      for (const [k, v] of m) {
        expect(v.trim(), `${l} ${k}`).not.toBe("");
        expect(args(v), `${l} ${k}`).toEqual(args(reference.get(k)!));
      }
    }
  });
});

describe.each(routing.locales)("rendered page, %s", (locale) => {
  const markup = html(locale);
  const plain = text(markup);
  const c = catalogues[locale] as Tree & { ForResearchers: Tree };
  it("says that expert review has not yet been done, in the page and the notes", () => {
    expect(plain).toContain((c.ForResearchers.status as string).slice(-30));
    expect(markup).toContain('data-testid="fr-notes-status"');
    expect(c.ForResearchers.notes as Tree).toHaveProperty("status");
  });
  it("has every section, the issues link and a copy button per code block", () => {
    for (const id of [
      "path",
      "data",
      "api",
      "example",
      "mcp",
      "cds",
      "pipelines",
      "notes",
      "limits",
      "cite",
    ])
      expect(markup).toContain(`data-testid="fr-${id}"`);
    expect(markup).toContain("https://github.com/mikailustuner/janus/issues");
    const blocks = markup.match(/<pre\b/g)?.length ?? 0;
    expect(blocks).toBe(8);
    expect(markup.match(/data-testid="dev-copy-fr-/g)?.length).toBe(blocks);
  });
  it("uses no forbidden phrase, no host details and no private folder", () => {
    expect(findForbiddenPhrases(plain, forbiddenPhrases[locale])).toEqual([]);
    expect(plain).not.toMatch(/\b(tailscale|ts\.net|docs\/internal)\b/i);
    expect(plain).not.toMatch(/\bAI\b|\byapay zeka\b|\bKI\b|\bIA\b/);
    expect(plain).not.toMatch(/\b\d{1,3}(\.\d{1,3}){3}\b(?!:8000)/);
  });
});
