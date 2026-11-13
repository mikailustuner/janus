// Plan D1: the researcher area's groups and menu. Every hub entry is a real page with its title
// and body in every locale; every page belongs to exactly one group; the menu marks the page's
// group; the experimental pages are never reachable from the patient menu.
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { routing } from "@/i18n/routing";
import { check, fc } from "@/test/fc";

import {
  isResearchPath,
  RESEARCH_GROUPS,
  RESEARCH_NAV,
  researchNavKey,
} from "./sections";

const APP = join(__dirname, "../../app/[locale]");
const ENTRIES = RESEARCH_GROUPS.flatMap((g) =>
  g.entries.map((e) => ({ group: g.key, ...e })),
);

function lookup(messages: unknown, key: string): unknown {
  return key
    .split(".")
    .reduce<unknown>(
      (node, part) =>
        node && typeof node === "object"
          ? (node as Record<string, unknown>)[part]
          : undefined,
      messages,
    );
}

describe("research sections", () => {
  it("every hub entry is a page of the app, listed once", () => {
    const hrefs = ENTRIES.map((e) => e.href);
    expect(new Set(hrefs).size).toBe(hrefs.length);
    for (const href of hrefs) {
      expect(existsSync(join(APP, href, "page.tsx")), href).toBe(true);
    }
  });

  it("every research page of the app is on the hub or under an entry", () => {
    const hub = ENTRIES.map((e) => e.href);
    const pages: string[] = [];
    const walk = (dir: string, href: string) => {
      for (const d of readdirSync(dir, { withFileTypes: true })) {
        if (!d.isDirectory()) continue;
        const sub = `${href}/${d.name}`;
        if (existsSync(join(dir, d.name, "page.tsx"))) pages.push(sub);
        walk(join(dir, d.name), sub);
      }
    };
    for (const top of ["research", "cascades", "open-data"]) {
      if (existsSync(join(APP, top, "page.tsx"))) pages.push(`/${top}`);
      walk(join(APP, top), `/${top}`);
    }
    expect(pages.length).toBeGreaterThan(10);
    for (const page of pages) {
      if (page === "/research") continue;
      const covered = hub.some((h) => page === h || page.startsWith(`${h}/`));
      expect(covered, page).toBe(true);
      expect(isResearchPath(page), page).toBe(true);
    }
  });

  it("titles and bodies exist in every locale", () => {
    for (const locale of routing.locales) {
      const messages: unknown = JSON.parse(
        readFileSync(
          join(__dirname, `../../../messages/${locale}.json`),
          "utf8",
        ),
      );
      for (const e of ENTRIES) {
        const title = e.themeTitle
          ? lookup(messages, `${e.title}.twoFaces`)
          : lookup(messages, e.title);
        expect(typeof title, `${locale} ${e.title}`).toBe("string");
        expect(typeof lookup(messages, e.body), `${locale} ${e.body}`).toBe(
          "string",
        );
      }
      for (const g of RESEARCH_GROUPS) {
        expect(typeof lookup(messages, `Research.groups.${g.key}.title`)).toBe(
          "string",
        );
      }
      for (const n of RESEARCH_NAV) {
        expect(typeof lookup(messages, `Shell.researchNav.${n.key}`)).toBe(
          "string",
        );
      }
    }
  });

  it("the menu marks the entry's group, and the overview for the hub and experimental pages", () => {
    expect(researchNavKey("/research")).toBe("overview");
    for (const e of ENTRIES) {
      const expected = e.group === "experimental" ? "overview" : e.group;
      expect(researchNavKey(e.href), e.href).toBe(expected);
      expect(researchNavKey(`${e.href}/item`), e.href).toBe(expected);
    }
  });

  it("every menu item points to a page of its own group", () => {
    for (const n of RESEARCH_NAV) {
      expect(researchNavKey(n.href)).toBe(n.key);
    }
  });

  it("patient pages are never research pages (property)", () => {
    const patient = fc.constantFrom(
      "/",
      "/scan",
      "/medicines",
      "/medicines/info",
      "/results",
      "/results/finding",
      "/note",
      "/passport",
      "/settings",
      "/researchers",
      "/research-notes",
    );
    check(
      fc.property(patient, (p) => {
        expect(isResearchPath(p)).toBe(false);
        expect(researchNavKey(p)).toBeNull();
      }),
    );
  });
});
