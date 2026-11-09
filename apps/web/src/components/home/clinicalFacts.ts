/**
 * The figures the Glass Janus home shows (experience Req 31.5, DP70). Each one is the recorded
 * Istanbul demo (`src/demo/fixtures/istanbul.json`); the pattern count is `PATTERNS` (Home.tsx, checked in render.test.tsx); `clinicalFacts.test.ts`
 * fails when a figure drifts from them. Never an invented number (medical-safety rule 6).
 */
/** The demo finding of the hero card: PIPC row 5, amlodipine (index) then furosemide (marker). */
export const DEMO_FINDING = {
  findingId: "pipc:5:Q411347:Q388801",
  /** Months between the two start months of the demo list. */
  monthsBetween: 5,
  /** Sources of the finding's evidence resolution, in total (the integrity line's first figure). */
  sources: 4,
} as const;
