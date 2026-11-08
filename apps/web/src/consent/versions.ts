/**
 * Versions of the consent texts the client shows (experience design DP24). Each must be listed
 * in the API's environment: DONATION_CONSENT_VERSION in JANUS_CONSENT_VERSIONS and
 * OUTCOME_CONSENT_VERSION in JANUS_OUTCOME_CONSENT_VERSIONS (.env.example). The texts are in the
 * catalogues under `Donate.consent.<version>` and `OutcomeConsent.<version>`.
 *
 * v2 (owner decision 2026-11-08, experience DP42): the outcome text names what is stored per
 * answered pattern; the donation text says "without my name or contact details" (pseudonymous, not
 * anonymous). The server keeps accepting v1 so tokens and donations made under it stay valid; the
 * v1 texts are in git history.
 */
export const DONATION_CONSENT_VERSION = "2026-11-v2";
export const OUTCOME_CONSENT_VERSION = "2026-11-v2";
