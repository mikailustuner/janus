/**
 * The donation form state → `POST /contributions` (experience design §12, Req 20.2, 20.3, 20.8,
 * P28). The request exists only with the explicit consent ticked and never in demo mode; it holds
 * exactly the stored fields: an adult age band, optional sex, region TR/EU/US, 1–20 distinct
 * ingredient keys chosen from the list, one event key and the direction.
 */
import { contributionBody } from "@/api/builders";
import type { ContributionIn, LoopRegion } from "@/api/contracts";
import { DONATION_CONSENT_VERSION } from "@/consent/versions";

export interface DonationForm {
  event: string | null;
  direction: "adverse" | "benefit";
  ingredients: string[];
  ageBand: number | null;
  sex: "female" | "male" | null;
  region: LoopRegion | null;
  consent: boolean;
}

export type DonationRequest =
  | { ok: true; body: ContributionIn }
  | { ok: false; reason: "demo" | "consent" | "fields" };

export function donationRequest(
  form: DonationForm,
  listKeys: readonly string[],
  demo: boolean,
): DonationRequest {
  if (demo) return { ok: false, reason: "demo" };
  if (!form.consent) return { ok: false, reason: "consent" };
  const chosen = [...new Set(form.ingredients)].filter((k) =>
    listKeys.includes(k),
  );
  if (
    !form.event ||
    form.ageBand === null ||
    !form.region ||
    chosen.length < 1 ||
    chosen.length > 20
  )
    return { ok: false, reason: "fields" };
  try {
    return {
      ok: true,
      body: contributionBody({
        consentVersion: DONATION_CONSENT_VERSION,
        consentTicked: form.consent,
        ageBand: form.ageBand,
        sex: form.sex,
        region: form.region,
        ingredients: chosen,
        event: form.event,
        direction: form.direction,
      }),
    };
  } catch {
    return { ok: false, reason: "fields" };
  }
}
