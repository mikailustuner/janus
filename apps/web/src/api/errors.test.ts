// Feature: experience, Property P20: every (route, status, code, body), timeout or network failure
// maps to a typed ApiError whose message key exists in every locale; no field value reaches a
// message; client defects and `resolution_unavailable` follow their rules; nothing throws.
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { check, fc } from "@/test/fc";
import { routing } from "@/i18n/routing";

import { HttpClient } from "./client";
import * as D from "./decode";
import { MESSAGE_KEYS, ROUTES, messageKeyFor, type Route } from "./errors";

type Tree = { [k: string]: string | Tree };
const has = (tree: Tree, key: string) => {
  let node: string | Tree | undefined = tree;
  for (const part of key.split("."))
    node = typeof node === "object" ? node[part] : undefined;
  return typeof node === "string" && node.trim() !== "";
};
const catalogues = Object.fromEntries(
  routing.locales.map((l) => [
    l,
    JSON.parse(
      readFileSync(
        join(import.meta.dirname, "../../messages", `${l}.json`),
        "utf8",
      ),
    ) as Tree,
  ]),
);

const KNOWN_CODES = [
  "invalid_request",
  "gs1_serial_not_accepted",
  "gs1_malformed",
  "gtin_missing",
  "gtin_check_digit",
  "ndc_malformed",
  "resolution_unavailable",
  "dataset_version_mismatch",
  "cascades_unavailable",
  "integrity_unavailable",
  "memory_unavailable",
  "version_mismatch",
  "note_language_unavailable",
  "no_findings",
  "notes_unavailable",
  "invalid_token",
  "token_expired",
  "token_not_usable",
  "token_used",
  "donations_unavailable",
  "invalid_donation",
  "demo_donation_rejected",
  "no_donation_for_token",
  "invalid_deletion",
  "internal_error",
];

const routeArb = fc.constantFrom(...ROUTES);
const statusArb = fc.constantFrom(400, 404, 409, 410, 422, 500, 503, 418);
const codeArb = fc.oneof(
  fc.constantFrom(...KNOWN_CODES),
  fc.string(),
  fc.constant(null),
);
const SENTINEL = "ZZVALUE-8680199094206";

describe("message keys", () => {
  it.each(routing.locales)("exist and are not empty in %s", (locale) => {
    for (const key of MESSAGE_KEYS)
      expect(has(catalogues[locale]!, key), key).toBe(true);
  });

  it("every combination maps to a listed key", () => {
    check(
      fc.property(
        routeArb,
        statusArb,
        codeArb,
        fc.array(fc.string()),
        (route, status, code, fields) => {
          expect(MESSAGE_KEYS).toContain(
            messageKeyFor(route, status, code, fields),
          );
        },
      ),
    );
  });

  it("follows the fixed rules", () => {
    for (const route of ROUTES) {
      expect(messageKeyFor(route, 422, "invalid_request")).toBe(
        "Errors.client_defect",
      );
    }
    expect(messageKeyFor("resolve/scan", 422, "gs1_serial_not_accepted")).toBe(
      "Errors.client_defect",
    );
    for (const route of [
      "resolve/scan",
      "resolve/ndc",
      "resolve/search",
      "resolve/products",
    ] as Route[])
      expect(messageKeyFor(route, 503, "resolution_unavailable")).toBe(
        "Errors.resolution_unavailable",
      );
    expect(
      messageKeyFor("contributions", 422, "invalid_donation", [
        "consent.version",
      ]),
    ).toBe("Donate.errors.consent_changed");
    expect(messageKeyFor("contributions", 422, "demo_donation_rejected")).toBe(
      "Errors.client_defect",
    );
    expect(messageKeyFor("notes/token", 422, "no_findings")).toBe(
      "Note.qr_no_findings",
    );
    expect(messageKeyFor("outcomes", 409, "token_used")).toBe(
      "Doctor.errors.token_used",
    );
  });
});

/** A fake fetch answering one scripted response. */
function fakeFetch(
  answer:
    | { kind: "response"; status: number; body: string }
    | { kind: "throw"; name: string },
) {
  return async () => {
    if (answer.kind === "throw") {
      const e = new Error("x");
      e.name = answer.name;
      throw e;
    }
    return new Response(answer.body, { status: answer.status });
  };
}

describe("HttpClient error handling", () => {
  const bodyArb = fc.oneof(
    fc
      .record({
        error: codeArb,
        fields: fc.constant([`items.0.product`, SENTINEL]),
      })
      .map((b) => JSON.stringify(b)),
    fc.constant("not json"),
    fc.constant(""),
    fc.constant(`{"error": "${SENTINEL}"}`),
  );
  const answerArb = fc.oneof(
    fc.record({
      kind: fc.constant("response" as const),
      status: statusArb,
      body: bodyArb,
    }),
    fc.record({
      kind: fc.constant("throw" as const),
      name: fc.constantFrom("TimeoutError", "AbortError", "TypeError"),
    }),
  );

  it("returns a typed error, never throws, never puts a value into the message", async () => {
    await check(
      fc.asyncProperty(answerArb, async (answer) => {
        const client = new HttpClient(fakeFetch(answer));
        const r = await client.resolveSearch({ query: "x" + SENTINEL });
        expect(r.ok).toBe(false);
        if (r.ok) return;
        expect(MESSAGE_KEYS).toContain(r.error.messageKey);
        expect(r.error.messageKey).not.toContain(SENTINEL);
        if (answer.kind === "throw")
          expect(["network", "timeout"]).toContain(r.error.kind);
        if (
          r.error.kind === "http" &&
          r.error.code === "resolution_unavailable"
        )
          expect(r.error.messageKey).not.toMatch(/not_found/);
      }),
    );
  });

  it("turns a 200 that does not match the contract into the generic error", async () => {
    const client = new HttpClient(
      fakeFetch({ kind: "response", status: 200, body: '{"findings": []}' }),
    );
    const r = await client.evaluate({
      dataset_version: "0".repeat(64),
      items: [{ ingredient: "Q1" }],
    });
    expect(r).toEqual({
      ok: false,
      error: {
        kind: "contract",
        route: "cascades/evaluate",
        messageKey: "Errors.generic",
      },
    });
  });

  it("sends JSON to the same origin with no credentials, no cache and no referrer", async () => {
    let seen: { url: string; init: RequestInit } | null = null;
    const client = new HttpClient(async (url, init) => {
      seen = { url, init };
      return new Response(
        JSON.stringify({
          donation_storage_region: null,
          in_eu: false,
          donations_enabled: false,
        }),
      );
    });
    const r = await client.privacyStorage();
    expect(r.ok).toBe(true);
    expect(seen!.url).toBe("/api/privacy/storage");
    expect(seen!.url).not.toContain("?");
    expect(seen!.init).toMatchObject({
      credentials: "omit",
      cache: "no-store",
      referrerPolicy: "no-referrer",
    });
    expect(seen!.init.signal).toBeInstanceOf(AbortSignal);
    expect(
      D.decode(D.storageInfo, { donation_storage_region: null, in_eu: false })
        .ok,
    ).toBe(false);
  });
});
