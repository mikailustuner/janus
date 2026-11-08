/** Shared Playwright helpers (experience design §17, C1–C4). */
import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, type Request } from "@playwright/test";

export const LOCALES = ["en", "tr", "de", "fr", "es"] as const;
export const THEMES = ["two-faces", "glass"] as const;
export type Theme = (typeof THEMES)[number];

/** Stores the theme setting before the first paint of every page of this context. */
export async function useTheme(page: Page, theme: Theme): Promise<void> {
  await page.addInitScript((t) => {
    try {
      const raw = localStorage.getItem("janus.v1.settings");
      const doc = raw ? JSON.parse(raw) : { v: 1 };
      localStorage.setItem(
        "janus.v1.settings",
        JSON.stringify({ ...doc, v: 1, theme: t }),
      );
    } catch {
      /* storage blocked: defaults apply */
    }
  }, theme);
}

type Stub = { status?: number; body: unknown };

/**
 * Answers every `/api/**` request from `stubs` (by path after `/api`); any request without a
 * stub fails the test. Returns the list of requests seen, for the network checks (C4).
 */
export async function stubApi(
  page: Page,
  stubs: Record<string, Stub | ((body: unknown) => Stub)> = {},
): Promise<Request[]> {
  const seen: Request[] = [];
  await page.route("**/api/**", async (route) => {
    const req = route.request();
    seen.push(req);
    const path = new URL(req.url()).pathname.replace(/^\/api/, "");
    const stub = stubs[path];
    if (!stub) {
      await route.fulfill({
        status: 599,
        body: JSON.stringify({ error: "no_stub" }),
      });
      return;
    }
    const answer = typeof stub === "function" ? stub(req.postDataJSON()) : stub;
    await route.fulfill({
      status: answer.status ?? 200,
      contentType: "application/json",
      body: JSON.stringify(answer.body),
    });
  });
  return seen;
}

/** Records every request of the page (any origin), for C4. */
export function recordRequests(page: Page): Request[] {
  const all: Request[] = [];
  page.on("request", (r) => all.push(r));
  return all;
}

/** C1: axe with the WCAG 2.2 A and AA rules reports no violation. */
export async function expectNoAxeViolations(page: Page): Promise<void> {
  const result = await new AxeBuilder({ page })
    .withTags([
      "wcag2a",
      "wcag2aa",
      "wcag21a",
      "wcag21aa",
      "wcag22a",
      "wcag22aa",
    ])
    .analyze();
  const summary = result.violations.map(
    (v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`,
  );
  expect(summary, summary.join("\n")).toEqual([]);
}

/** C2: no horizontal scroll at the current viewport. */
export async function expectNoHorizontalScroll(page: Page): Promise<void> {
  const overflow = await page.evaluate(() => {
    const el = document.scrollingElement ?? document.documentElement;
    return el.scrollWidth - el.clientWidth;
  });
  expect(overflow, "horizontal overflow in px").toBeLessThanOrEqual(0);
}

/** C2: every visible interactive element is at least 44 × 44 px. */
export async function expectTouchTargets(page: Page): Promise<void> {
  const small = await page.evaluate(() =>
    [
      ...document.querySelectorAll<HTMLElement>(
        "a[href], button, input:not([type=hidden]), select, textarea, [role=button], summary",
      ),
    ]
      .filter((el) => {
        const r = el.getBoundingClientRect();
        const style = getComputedStyle(el);
        if (r.width === 0 || style.visibility === "hidden") return false;
        // Visually hidden until focused (the skip link): measured when shown.
        if (
          style.clipPath.includes("inset(50%)") ||
          style.clip.startsWith("rect(0")
        )
          return false;
        // Inline links inside running text are exempt (WCAG 2.5.8 inline exception).
        if (el.tagName === "A" && el.dataset.inline === "true") return false;
        // A radio or checkbox inside a label: the label is the target.
        const label = el.tagName === "INPUT" ? el.closest("label") : null;
        const box = label ? label.getBoundingClientRect() : r;
        return box.width < 44 || box.height < 44;
      })
      .map(
        (el) =>
          `${el.tagName.toLowerCase()} "${(el.textContent ?? "").trim().slice(0, 30)}" ${Math.round(el.getBoundingClientRect().width)}×${Math.round(el.getBoundingClientRect().height)}`,
      ),
  );
  expect(small, small.join("\n")).toEqual([]);
}
