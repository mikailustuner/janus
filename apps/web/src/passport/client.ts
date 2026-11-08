/**
 * The presence call (medication-passport design §3, §6.4, §9, DP17, DP26). Same-origin `/api`,
 * through the experience HTTP client (timeouts, no retry, typed errors). The list is split into
 * requests by `buildPresenceRequests`; any failed request fails the whole answer (nothing
 * partial, Req 5.3).
 *
 * Demo mode never calls the API (experience Req 4.3, 4.4, check C4; DP26): the demo patients'
 * answers were recorded from the real API (`scripts/record-passport.mjs`) and are shown with
 * "Recorded answer of <date>". A recorded answer is used only when it holds every query built.
 */
import { HttpClient, type Result } from "@/api/client";
import type { ApiError } from "@/api/errors";

import {
  presenceOut,
  type ItemOut,
  type PassportItem,
  type PresenceIn,
  type PresenceOut,
} from "./model";
import {
  buildPresenceRequests,
  fanBack,
  type BuiltRequests,
  type ItemAnswer,
} from "./request";

export type PresenceCall = (body: PresenceIn) => Promise<Result<PresenceOut>>;

const http = new HttpClient();
export const livePresence: PresenceCall = (body) =>
  http.call("passport/presence", "POST", body, presenceOut);

export interface Recorded {
  recorded: { date: string; dataset_version: string };
  request: PresenceIn;
  response: unknown;
}

export type PresenceState =
  | {
      status: "ok";
      built: BuiltRequests;
      answers: Map<string, ItemAnswer>;
      recordedOn: string | null;
    }
  | { status: "error"; error: ApiError | null };

/** The recorded answer rearranged for `body`, or null when a query was not recorded. */
export function fromRecorded(
  rec: Recorded,
  body: PresenceIn,
): PresenceOut | null {
  const out = presenceOut(rec.response, "$");
  const byQuery = new Map<string, ItemOut>();
  rec.request.items.forEach((q, i) => {
    const it = out.items.find((x) => x.item === i);
    if (it) byQuery.set(JSON.stringify(q), it);
  });
  const items: ItemOut[] = [];
  for (const [i, q] of body.items.entries()) {
    const it = byQuery.get(JSON.stringify(q));
    if (!it) return null;
    items.push({ ...it, item: i });
  }
  return { ...out, items };
}

export async function loadPresence(
  list: readonly PassportItem[],
  call: PresenceCall | null,
  recorded: Recorded | null = null,
): Promise<PresenceState> {
  const built = buildPresenceRequests(list);
  if (built.bodies.length === 0)
    return { status: "ok", built, answers: new Map(), recordedOn: null };
  if (!call) {
    const outs = recorded
      ? built.bodies.map((b) => fromRecorded(recorded, b))
      : [];
    if (outs.length === 0 || outs.some((o) => o === null))
      return { status: "error", error: null };
    return {
      status: "ok",
      built,
      answers: fanBack(built, outs as PresenceOut[]),
      recordedOn: recorded!.recorded.date,
    };
  }
  const results = await Promise.all(built.bodies.map((b) => call(b)));
  const failed = results.find((r) => !r.ok);
  if (failed && !failed.ok) return { status: "error", error: failed.error };
  return {
    status: "ok",
    built,
    answers: fanBack(
      built,
      results.map((r) => (r as { data: PresenceOut }).data),
    ),
    recordedOn: null,
  };
}
