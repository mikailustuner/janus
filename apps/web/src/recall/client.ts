/**
 * The recall check call (recall-check design §7, §9). Same-origin `/api`, through the experience
 * HTTP client (timeout, no retry, typed errors). The body is the NDC only: the lot is compared
 * on the device (`lot.ts`). Live only: demo products are invented, so demo mode never asks.
 */
import { HttpClient, type Result } from "@/api/client";

import { recallCheckOut, type RecallCheckOut } from "./model";

export type RecallCall = (ndc: string) => Promise<Result<RecallCheckOut>>;

const NDC = /^(\d{11}|\d{5}-\d{4})$/;

/** The call over a given HTTP client. Anything but an NDC is refused before a request is made. */
export function recallCall(http: HttpClient): RecallCall {
  return async (ndc) => {
    if (!NDC.test(ndc))
      return {
        ok: false,
        error: {
          kind: "build",
          route: "recalls/check",
          messageKey: "Errors.client_defect",
        },
      };
    return http.call("recalls/check", "POST", { ndc }, recallCheckOut);
  };
}

export const liveRecall: RecallCall = recallCall(new HttpClient());
