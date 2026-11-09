/**
 * The time-machine calls (time-machine design §10; experience Req 30): GET only, no body, through
 * the experience HTTP client (same-origin `/api`, timeout, no retry, typed errors). Demo mode
 * answers from the fixture recorded from the real local API (`fixture.recorded.json`,
 * scripts/record-timemachine.mjs) with no request at all (experience Req 4.4).
 */
import { HttpClient, type Result } from "@/api/client";
import * as D from "@/api/decode";
import type { Route } from "@/api/errors";

import {
  cascadeOut,
  catalogue,
  substanceOut,
  type CascadeOut,
  type Catalogue,
  type SubstanceOut,
} from "./model";

export interface TimeMachineClient {
  catalogue(): Promise<Result<Catalogue>>;
  substance(id: string): Promise<Result<SubstanceOut>>;
  cascade(id: string): Promise<Result<CascadeOut>>;
}

/** Ids are snake_case codes (design §10); anything else never reaches a URL. */
export const ID = /^[a-z][a-z0-9_]{0,63}$/;

const http = new HttpClient();

function badId<T>(route: Route): Result<T> {
  return {
    ok: false,
    error: { kind: "build", route, messageKey: "Errors.client_defect" },
  };
}

export const liveTimeMachine: TimeMachineClient = {
  catalogue: () => http.call("timemachine/catalogue", "GET", null, catalogue),
  substance: async (id) =>
    ID.test(id)
      ? http.call(
          "timemachine/substance",
          "GET",
          null,
          substanceOut,
          undefined,
          `timemachine/substance/${id}`,
        )
      : badId("timemachine/substance"),
  cascade: async (id) =>
    ID.test(id)
      ? http.call(
          "timemachine/cascade",
          "GET",
          null,
          cascadeOut,
          undefined,
          `timemachine/cascade/${id}`,
        )
      : badId("timemachine/cascade"),
};

export interface TimeMachineFixture {
  recorded: string;
  catalogue: unknown;
  substances: Record<string, unknown>;
  cascades: Record<string, unknown>;
}

function decoded<T>(route: Route, d: D.Decoder<T>, value: unknown): Result<T> {
  const r = D.decode(d, value);
  return r.ok
    ? { ok: true, data: r.value }
    : {
        ok: false,
        error: { kind: "contract", route, messageKey: "Errors.generic" },
      };
}

const unknown = <T>(route: Route): Result<T> => ({
  ok: false,
  error: {
    kind: "http",
    route,
    status: 404,
    code:
      route === "timemachine/cascade" ? "unknown_cascade" : "unknown_substance",
    fields: [],
    messageKey: "TimeMachine.errors.unknown",
  },
});

/** Answers from the recorded fixture only. */
export function demoTimeMachine(fx: TimeMachineFixture): TimeMachineClient {
  return {
    catalogue: async () =>
      decoded("timemachine/catalogue", catalogue, fx.catalogue),
    substance: async (id) =>
      Object.hasOwn(fx.substances, id)
        ? decoded("timemachine/substance", substanceOut, fx.substances[id])
        : unknown("timemachine/substance"),
    cascade: async (id) =>
      Object.hasOwn(fx.cascades, id)
        ? decoded("timemachine/cascade", cascadeOut, fx.cascades[id])
        : unknown("timemachine/cascade"),
  };
}

/** The recorded fixture, loaded on demand so it stays out of the routes' first-load JS. */
export function loadTimeMachineFixture(): Promise<TimeMachineFixture> {
  return import("./fixture.recorded.json").then(
    (m) => m.default as unknown as TimeMachineFixture,
  );
}

/**
 * Every cascade of the catalogue (the patient gate, design §10.5). All of them are fetched, so the
 * requests say nothing about the person's medicines.
 */
export async function allCascades(
  client: TimeMachineClient,
): Promise<Result<CascadeOut[]>> {
  const cat = await client.catalogue();
  if (!cat.ok) return cat;
  const answers = await Promise.all(
    cat.data.cascade_ids.map((id) => client.cascade(id)),
  );
  const out: CascadeOut[] = [];
  for (const a of answers) {
    if (!a.ok) return a;
    out.push(a.data);
  }
  return { ok: true, data: out };
}
