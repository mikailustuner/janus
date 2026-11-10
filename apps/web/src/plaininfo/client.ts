/**
 * The medicine information call (plain-medicine-info design §6, §8). Same-origin `/api`,
 * through the experience HTTP client (timeout, no retry, typed errors). Demo mode never calls:
 * it answers from the recorded group answers of the demo lists' ATC codes (C4), and has no
 * official part because the demo products are invented.
 */
import { HttpClient, type Result } from "@/api/client";
import { decode } from "@/api/decode";

import {
  ingredient,
  medicineInfoOut,
  type MedicineInfoIn,
  type MedicineInfoOut,
} from "./model";

export type InfoCall = (
  body: MedicineInfoIn,
) => Promise<Result<MedicineInfoOut>>;

const contract = {
  ok: false,
  error: {
    kind: "contract",
    route: "medicine-info",
    messageKey: "Errors.generic",
  },
} as const;

export function infoCall(http: HttpClient): InfoCall {
  return (body) => http.call("medicine-info", "POST", body, medicineInfoOut);
}

export const liveInfo: InfoCall = infoCall(new HttpClient());

export interface Recorded {
  groups_version: string;
  /** language → ATC codes of one ingredient, sorted and joined with a space → the API's answer. */
  ingredients: Record<string, Record<string, unknown>>;
}

/** Answers from a recorded file; a code set that was not recorded is an error, never a guess. */
export function recordedCall(load: () => Promise<Recorded>): InfoCall {
  return async (body) => {
    if (body.product) return contract;
    const recorded = await load().catch(() => null);
    const byCodes = recorded?.ingredients[body.language];
    if (!recorded || !byCodes) return contract;
    const ingredients = [];
    for (const i of body.ingredients) {
      const found = decode(ingredient, byCodes[i.atc_codes.join(" ")]);
      if (!found.ok) return contract;
      ingredients.push(found.value);
    }
    return {
      ok: true,
      data: {
        language: body.language,
        groups_version: recorded.groups_version,
        ingredients,
        official: null,
        official_status: "not_asked",
        notices: [],
      },
    };
  };
}

export const demoInfo: InfoCall = recordedCall(() =>
  import("@/demo/plain-info.recorded.json").then(
    (m) => m.default as unknown as Recorded,
  ),
);
