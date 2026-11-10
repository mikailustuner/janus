/**
 * The safety check call (safety-check design §7, §8). Same-origin `/api`, through the experience
 * HTTP client (timeout, no retry, typed errors). The body is the evaluation body: candidate ids,
 * ingredient keys and start months; never a box name. Live only (design DP-S4).
 */
import { HttpClient, type Result } from "@/api/client";
import type { EvaluateIn } from "@/api/contracts";

import { safetyCheckOut, type SafetyCheckOut } from "./model";

export type SafetyCall = (body: EvaluateIn) => Promise<Result<SafetyCheckOut>>;

export function safetyCall(http: HttpClient): SafetyCall {
  return (body) => http.call("safety/check", "POST", body, safetyCheckOut);
}

export const liveSafety: SafetyCall = safetyCall(new HttpClient());
