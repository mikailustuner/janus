/**
 * The séance calls (séance design §7.1) through the experience HTTP client (same-origin `/api`,
 * timeouts, no retry, typed errors), and the demo client: the catalogue and the two headline
 * pairs recorded from the real local API (`fixture.recorded.json`, scripts/record-seance.mjs),
 * answered with no network at all (experience Req 4.4). The pair travels in a POST body, never in
 * a URL.
 */
import { HttpClient, type Result } from "@/api/client";
import * as D from "@/api/decode";
import type { Route } from "@/api/errors";

import {
  catalogueOut,
  seanceOut,
  type CatalogueOut,
  type SeanceIn,
  type SeanceOut,
} from "./model";

export interface SeanceClient {
  /** The pairs this client can answer (demo mode); null means every catalogue pair. */
  only: readonly SeanceIn[] | null;
  catalogue(): Promise<Result<CatalogueOut>>;
  pair(p: SeanceIn): Promise<Result<SeanceOut>>;
}

const http = new HttpClient();

export const liveSeance: SeanceClient = {
  only: null,
  catalogue: () => http.call("seance/catalogue", "GET", null, catalogueOut),
  pair: (p) =>
    http.call(
      "seance/pair",
      "POST",
      { substance: p.substance, condition: p.condition },
      seanceOut,
    ),
};

export interface SeanceFixture {
  recorded: string;
  catalogue: unknown;
  pairs: { request: SeanceIn; answer: unknown }[];
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

/** Answers from the recorded fixture only; a pair that was not recorded is a client defect. */
export function demoSeance(fx: SeanceFixture): SeanceClient {
  return {
    only: fx.pairs.map((p) => p.request),
    catalogue: async () =>
      decoded("seance/catalogue", catalogueOut, fx.catalogue),
    pair: async (p) => {
      const hit = fx.pairs.find(
        (x) =>
          x.request.substance === p.substance &&
          x.request.condition === p.condition,
      );
      return hit
        ? decoded("seance/pair", seanceOut, hit.answer)
        : {
            ok: false,
            error: {
              kind: "build",
              route: "seance/pair",
              messageKey: "Errors.client_defect",
            },
          };
    },
  };
}

/** The recorded fixture, loaded on demand so it stays out of the route's first-load JS. */
export function loadSeanceFixture(): Promise<SeanceFixture> {
  return import("./fixture.recorded.json").then(
    (m) => m.default as unknown as SeanceFixture,
  );
}

/**
 * The pair a hypothesis card asked to open (kept in memory for the next séance screen, so the
 * pair never enters a URL). Read once.
 */
let requested: SeanceIn | null = null;
export function requestPair(p: SeanceIn): void {
  requested = p;
}
export function takeRequestedPair(): SeanceIn | null {
  const p = requested;
  requested = null;
  return p;
}
