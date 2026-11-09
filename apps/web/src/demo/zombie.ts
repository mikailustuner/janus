/**
 * The one simulated evidence change of the demo (zombie-alert DP9, Req 6.2, 6.3), decoded with
 * the same decoder as a live `POST /evidence/changes` entry. No network.
 */
import type { EvidenceChange } from "@/api/contracts";
import * as D from "@/api/decode";
import type { Alert } from "@/flow/zombie";

import fixture from "./fixtures/zombie.json";

export const DEMO_CHANGE: EvidenceChange = D.evidenceChange(
  fixture.change,
  "zombie.change",
);

export const DEMO_NOTICE: NonNullable<Alert["notice"]> = {
  doi: fixture.notice.doi,
  url: fixture.notice.url,
};
