/**
 * The Cologne demo patient's Passport list (medication-passport design §9, Req 12): Turkish boxes
 * by code and German boxes typed by name, invented product names, real ingredient keys. It shows
 * the duplicate flag (amlodipine in the Turkish combination and a German box), a homeopathic
 * German box (not checked) and strengths and forms typed from the box. Every item is `demo`.
 * `RECORDED` holds each demo patient's answer recorded from the real API
 * (`scripts/record-passport.mjs`); demo mode shows only these (DP26).
 */
import type { Recorded } from "@/passport/client";
import type { PassportItem } from "@/passport/model";

import data from "./passport-cologne.json";
import cologne from "./passport-cologne.recorded.json";
import istanbul from "./passport-istanbul.recorded.json";
import ohio from "./passport-ohio.recorded.json";

export const COLOGNE_PASSPORT = data.items as PassportItem[];
export const RECORDED: Record<string, Recorded> = {
  cologne: cologne as unknown as Recorded,
  istanbul: istanbul as unknown as Recorded,
  ohio: ohio as unknown as Recorded,
};
export const COLOGNE_RECORDED = RECORDED.cologne!;
