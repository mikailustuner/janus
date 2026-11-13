// Feature: model-kit Req 6. The live client asks the right routes and never sends an invalid key;
// the demo client answers contract errors for broken data; the axis handles empty and flat input.
import { afterEach, describe, expect, it, vi } from "vitest";

import { modelKitSet } from "@/test/fixtures/modelkit";

import {
  demoModelKit,
  liveModelKit,
  loadModelKitFixture,
  logAxis,
  NO_QUERY,
} from "./model";

const set = modelKitSet();

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("live client", () => {
  it("asks the list, report, drug and evidence routes and decodes the answers", async () => {
    const urls: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        urls.push(url);
        if (url.includes("/evidence"))
          return jsonResponse(set.raw.evidence.repaglinide);
        if (url.includes("/modelkit/drugs/"))
          return jsonResponse(set.raw.drug.repaglinide);
        if (url.includes("/modelkit/validation"))
          return jsonResponse(set.raw.validation);
        return jsonResponse(set.raw.drugs);
      }),
    );
    expect((await liveModelKit.drugs(NO_QUERY)).ok).toBe(true);
    expect((await liveModelKit.system()).ok).toBe(true);
    expect((await liveModelKit.drug("repaglinide")).ok).toBe(true);
    expect((await liveModelKit.evidence("repaglinide")).ok).toBe(true);
    expect(urls.some((u) => u.endsWith("/api/modelkit/validation"))).toBe(true);
    expect(
      urls.some((u) => u.endsWith("/api/modelkit/drugs/repaglinide")),
    ).toBe(true);
    expect(
      urls.some((u) => u.endsWith("/api/modelkit/drugs/repaglinide/evidence")),
    ).toBe(true);
  });

  it("refuses an invalid key without a request", async () => {
    const spy = vi.fn();
    vi.stubGlobal("fetch", spy);
    for (const key of ["../x", "Repaglinide", "a b", ""]) {
      const d = await liveModelKit.drug(key);
      const e = await liveModelKit.evidence(key);
      expect(d.ok || e.ok).toBe(false);
      if (!d.ok) expect(d.error.kind).toBe("build");
      if (!e.ok) expect(e.error.kind).toBe("build");
    }
    expect(spy).not.toHaveBeenCalled();
  });

  it("builds export links and allows downloads", () => {
    expect(liveModelKit.downloads).toBe(true);
    expect(liveModelKit.exportUrl("repaglinide", "mrgsolve")).toBe(
      "/api/modelkit/drugs/repaglinide/export/mrgsolve",
    );
  });
});

describe("demo client", () => {
  it("answers a contract error when the list or report does not decode", async () => {
    const c = demoModelKit({ ...set.raw, drugs: { nope: 1 }, validation: 7 });
    const list = await c.drugs(NO_QUERY);
    const system = await c.system();
    expect(list.ok).toBe(false);
    expect(system.ok).toBe(false);
    if (!list.ok) expect(list.error.kind).toBe("contract");
    if (!system.ok) expect(system.error.kind).toBe("contract");
  });

  it("answers a contract error for a drug page that does not decode", async () => {
    const c = demoModelKit({
      ...set.raw,
      drug: { ...set.raw.drug, broken: { summary: 1 } },
      evidence: { ...set.raw.evidence, broken: [] },
    });
    const d = await c.drug("broken");
    const e = await c.evidence("broken");
    expect(d.ok).toBe(false);
    expect(e.ok).toBe(false);
    if (!d.ok) expect(d.error.kind).toBe("contract");
    if (!e.ok) expect(e.error.kind).toBe("contract");
    expect(c.exportUrl("broken", "mrgsolve")).toBe("");
  });
});

describe("recorded file", () => {
  it("loads lazily as a fixture object", async () => {
    const fx = await loadModelKitFixture();
    expect(typeof fx.recorded).toBe("string");
    expect(Object.keys(fx.drug).length).toBeGreaterThan(0);
  });
});

describe("log axis edge cases", () => {
  it("falls back to one decade without positive values", () => {
    expect(logAxis([])).toEqual({ min: 1, max: 10, ticks: [1, 10] });
    expect(logAxis([0, -3, Number.NaN])).toEqual({
      min: 1,
      max: 10,
      ticks: [1, 10],
    });
  });

  it("is at least one decade wide for equal values", () => {
    const a = logAxis([100, 100]);
    expect(a.max / a.min).toBeGreaterThanOrEqual(10);
    expect(a.ticks.length).toBeGreaterThanOrEqual(2);
  });
});
