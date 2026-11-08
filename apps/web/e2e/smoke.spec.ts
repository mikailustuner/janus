// Tasks 1.1 and 1.2: the home page renders; security headers on / and /o; /o is not redirected.
import { expect, test } from "@playwright/test";

test("home renders the disclaimer and the emergency notice", async ({
  page,
}) => {
  await page.goto("/en");
  await expect(page.getByTestId("disclaimer")).toHaveText(
    "Janus provides information, not medical advice. Research prototype — not a medical device.",
  );
  // The shell streams in (Suspense in the layout; React reveals it shortly after load), so the
  // fallback copy can still be in the DOM: look inside the real shell.
  await expect(
    page.locator("#content").getByTestId("emergency-notice"),
  ).toBeVisible();
});

for (const path of ["/en", "/o"]) {
  test(`headers of ${path}`, async ({ request }) => {
    const res = await request.get(path, { maxRedirects: 0 });
    expect(res.status()).not.toBe(307);
    expect(res.status()).not.toBe(308);
    const csp = res.headers()["content-security-policy"] ?? "";
    expect(csp).toContain("connect-src 'self'");
    expect(csp).toContain("font-src 'self'");
    expect(res.headers()["referrer-policy"]).toBe("no-referrer");
  });
}
