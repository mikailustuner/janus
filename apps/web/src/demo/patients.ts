/** Static facts of the three demo patients (design §13.1); the recorded data are in fixtures/. */
import type { Locale, UserRegion } from "@/api/contracts";

import type { PatientId } from "./session";

export const PATIENT_FACTS: Record<
  PatientId,
  {
    userRegion: Exclude<UserRegion, "OTHER" | "UNKNOWN">;
    noteLanguage: Locale;
    items: number;
  }
> = {
  istanbul: { userRegion: "TR", noteLanguage: "tr", items: 9 },
  cologne: { userRegion: "EU", noteLanguage: "de", items: 4 },
  ohio: { userRegion: "US", noteLanguage: "en", items: 4 },
};
