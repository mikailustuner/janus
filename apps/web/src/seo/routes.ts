/**
 * The SEO decision for every public route: which pages are indexed (and so in the sitemap) and
 * which are not. A test walks src/app so a new page cannot be added without a decision here.
 * Paths are locale-less ("" is the home); the locale prefix is added by `localizedPath`.
 */
import { routing } from "@/i18n/routing";

export const SITE_URL = "https://janusmeds.org";

export type Locale = (typeof routing.locales)[number];
export const LOCALES: readonly Locale[] = routing.locales;
export const DEFAULT_LOCALE: Locale = routing.defaultLocale;

type Freq = "daily" | "weekly" | "monthly" | "yearly";

export type IndexedRoute = {
  /** Key of the page in the `Seo` messages (the description) and in tests. */
  id: string;
  path: string;
  /** Message key of the page title (an existing string where one exists). */
  title: string;
  changeFrequency: Freq;
  priority: number;
};

export const INDEXED: readonly IndexedRoute[] = [
  {
    id: "home",
    path: "",
    title: "Metadata.title",
    changeFrequency: "weekly",
    priority: 1,
  },
  {
    id: "about",
    path: "/about",
    title: "About.title",
    changeFrequency: "monthly",
    priority: 0.8,
  },
  {
    id: "demo",
    path: "/demo",
    title: "Demo.title",
    changeFrequency: "monthly",
    priority: 0.8,
  },
  {
    id: "cascades",
    path: "/cascades",
    title: "CascadeMap.footer",
    changeFrequency: "monthly",
    priority: 0.8,
  },
  {
    id: "passport",
    path: "/passport",
    title: "Passport.title",
    changeFrequency: "monthly",
    priority: 0.6,
  },
  {
    id: "openData",
    path: "/open-data",
    title: "OpenData.title",
    changeFrequency: "weekly",
    priority: 0.7,
  },
  {
    id: "privacy",
    path: "/privacy",
    title: "Privacy.title",
    changeFrequency: "yearly",
    priority: 0.5,
  },
  {
    id: "research",
    path: "/research",
    title: "Research.title",
    changeFrequency: "monthly",
    priority: 0.6,
  },
  {
    id: "forResearchers",
    path: "/research/for-researchers",
    title: "ForResearchers.title",
    changeFrequency: "monthly",
    priority: 0.6,
  },
  {
    id: "developers",
    path: "/research/developers",
    title: "Developers.title",
    changeFrequency: "monthly",
    priority: 0.5,
  },
  {
    id: "dataQuality",
    path: "/research/data-quality",
    title: "DataQuality.title",
    changeFrequency: "weekly",
    priority: 0.5,
  },
  {
    id: "faersOnset",
    path: "/research/faers-onset",
    title: "Onset.title",
    changeFrequency: "monthly",
    priority: 0.5,
  },
  {
    id: "timeMachine",
    path: "/research/time-machine",
    title: "TimeMachine.title",
    changeFrequency: "monthly",
    priority: 0.5,
  },
  {
    id: "seance",
    path: "/research/seance",
    title: "Seance.title.glass",
    changeFrequency: "monthly",
    priority: 0.5,
  },
  {
    id: "modelExplorer",
    path: "/research/model-explorer",
    title: "Simulation.explorer.title",
    changeFrequency: "monthly",
    priority: 0.4,
  },
  {
    id: "modelKit",
    path: "/research/model-kit",
    title: "ModelKit.title",
    changeFrequency: "monthly",
    priority: 0.4,
  },
  {
    id: "simulate",
    path: "/research/simulate",
    title: "Simulation.server.title",
    changeFrequency: "monthly",
    priority: 0.4,
  },
];

/**
 * Pages that are not indexed, with the reason. Their `robots` metadata says noindex and
 * robots.txt does not let crawlers in. Entries ending in "/*" are query- or fragment-driven
 * pages (an empty shell without the user's choice).
 */
export const NOINDEX: Readonly<Record<string, string>> = {
  "/scan": "user flow",
  "/start": "user flow",
  "/confirm": "user flow",
  "/settings": "per-user settings",
  "/results": "per-user results",
  "/results/finding": "per-user results",
  "/results/summary": "per-user results",
  "/memory": "collective-memory view of the user's list",
  "/medicines": "the user's medicine list",
  "/medicines/info": "medicine named by the URL fragment",
  "/timeline": "the user's medicine list",
  "/note": "doctor note of the user's list",
  "/note/withdraw": "user action",
  "/report": "report assistant over the user's list",
  "/donate": "consent flow",
  "/donate/delete": "user action",
  "/passport/item": "item named by the URL fragment",
  "/passport/products": "the user's products",
  "/demo/codes": "printable demo sheet",
  "/demo/doctor": "demo form",
  "/research/hypotheses": "repurposing candidates, researcher-facing",
  "/research/validation": "repurposing validation, researcher-facing",
  "/research/export": "dataset download",
  "/research/faers-onset/row": "query-driven detail",
  "/research/time-machine/cascade": "query-driven detail",
  "/research/time-machine/substance": "query-driven detail",
  "/research/model-kit/drug": "query-driven detail",
  "/research/model-kit/report": "query-driven detail",
};

/** `/en/privacy`; the home is `/en`. */
export function localizedPath(locale: string, path: string): string {
  return `/${locale}${path}`;
}

/** The hreflang map of one page: the five locales and `x-default` → the default locale. */
export function languageAlternates(path: string): Record<string, string> {
  return {
    ...Object.fromEntries(
      LOCALES.map((l) => [l, localizedPath(l, path)] as const),
    ),
    "x-default": localizedPath(DEFAULT_LOCALE, path),
  };
}
