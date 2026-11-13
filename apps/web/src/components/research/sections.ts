/**
 * The researcher area's information architecture (plan D1, approved by the owner on 2026-11-13):
 * five groups on the /research hub, and the researcher menu that replaces the patient menu on
 * every researcher page. One table, so the hub and the menu cannot drift apart. Existing
 * addresses are kept; only the grouping is new.
 */

export type ResearchGroup =
  "methods" | "modelKit" | "data" | "developers" | "experimental";

/** One hub entry: its address and where its title and one-line body come from. */
export type ResearchEntry = {
  href: string;
  /** Message keys of the title and the body (existing keys, kept from the flat hub). */
  title: string;
  body: string;
  /** The séance title is a theme word (two names, one per theme). */
  themeTitle?: boolean;
};

export const RESEARCH_GROUPS: readonly {
  key: ResearchGroup;
  entries: readonly ResearchEntry[];
}[] = [
  {
    key: "methods",
    entries: [
      {
        href: "/research/validation-studies",
        title: "Research.tools.validationStudies.title",
        body: "Research.tools.validationStudies.body",
      },
      {
        href: "/research/data-quality",
        title: "Research.tools.dataQuality.title",
        body: "Research.tools.dataQuality.body",
      },
      {
        href: "/research/for-researchers",
        title: "Research.tools.forResearchers.title",
        body: "Research.tools.forResearchers.body",
      },
      {
        href: "/research/validation",
        title: "Research.entries.validation.title",
        body: "Research.entries.validation.body",
      },
    ],
  },
  {
    key: "modelKit",
    entries: [
      {
        href: "/research/model-kit",
        title: "Research.tools.modelKit.title",
        body: "Research.tools.modelKit.body",
      },
      {
        href: "/research/model-explorer",
        title: "Research.tools.modelExplorer.title",
        body: "Research.tools.modelExplorer.body",
      },
      {
        href: "/research/simulate",
        title: "Research.tools.simulate.title",
        body: "Research.tools.simulate.body",
      },
    ],
  },
  {
    key: "data",
    entries: [
      {
        href: "/research/faers-onset",
        title: "Research.tools.onset.title",
        body: "Research.tools.onset.body",
      },
      {
        href: "/cascades",
        title: "CascadeMap.entry.title",
        body: "CascadeMap.entry.body",
      },
      {
        href: "/open-data",
        title: "OpenData.entry.title",
        body: "OpenData.entry.body",
      },
      {
        href: "/research/export",
        title: "Research.entries.export.title",
        body: "Research.entries.export.body",
      },
    ],
  },
  {
    key: "developers",
    entries: [
      {
        href: "/research/developers",
        title: "Research.tools.developers.title",
        body: "Research.tools.developers.body",
      },
    ],
  },
  {
    key: "experimental",
    entries: [
      {
        href: "/research/hypotheses",
        title: "Research.entries.hypotheses.title",
        body: "Research.entries.hypotheses.body",
      },
      {
        href: "/research/seance",
        title: "Research.entries.seance.title",
        body: "Research.entries.seance.body",
        themeTitle: true,
      },
      {
        href: "/research/time-machine",
        title: "TimeMachine.entry.title",
        body: "TimeMachine.entry.body",
      },
    ],
  },
];

/** The researcher menu: the overview, then one item per group (experimental lives on the hub). */
export const RESEARCH_NAV = [
  { key: "overview", href: "/research" },
  { key: "methods", href: "/research/validation-studies" },
  { key: "modelKit", href: "/research/model-kit" },
  { key: "data", href: "/open-data" },
  { key: "developers", href: "/research/developers" },
] as const;

export type ResearchNavKey = (typeof RESEARCH_NAV)[number]["key"];

function under(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}

/** True on every researcher page: the researcher menu replaces the patient menu there. */
export function isResearchPath(pathname: string): boolean {
  return (
    under(pathname, "/research") ||
    under(pathname, "/cascades") ||
    under(pathname, "/open-data")
  );
}

/**
 * The researcher menu item a page belongs to: its group's item, or the overview for the hub and
 * the experimental pages. Null outside the researcher area.
 */
export function researchNavKey(pathname: string): ResearchNavKey | null {
  if (!isResearchPath(pathname)) return null;
  for (const group of RESEARCH_GROUPS) {
    if (group.key === "experimental") continue;
    if (group.entries.some((e) => under(pathname, e.href))) return group.key;
  }
  return "overview";
}
