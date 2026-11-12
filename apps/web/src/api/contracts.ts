/**
 * Request and response types of the routes the client calls (experience design §5.1), written
 * from the Pydantic models in apps/api. Response types are inferred from the decoders so the two
 * cannot drift apart; request types are written out, and only `builders.ts` constructs them.
 */
import type * as D from "./decode";
import type { Infer } from "./decode";

export type Locale = "en" | "tr" | "de" | "fr" | "es" | "pt";
export type ScanRegion = "TR" | "US" | "EU";
export type UserRegion = "US" | "TR" | "EU" | "OTHER" | "UNKNOWN";
export type LoopRegion = "TR" | "EU" | "US";
export type MemoryRegion = "ALL" | "TR" | "EU" | "US" | "OTHER" | "UNKNOWN";

// --- responses ---------------------------------------------------------------------------------
export type SourceRef = Infer<typeof D.sourceRef>;
export type IngredientKey = Infer<typeof D.ingredientKey>;
export type ResolvedIngredient = Infer<typeof D.resolvedIngredient>;
export type ProductCandidate = Infer<typeof D.productCandidate>;
export type IngredientCandidate = Infer<typeof D.ingredientCandidate>;
export type Candidate = ProductCandidate | IngredientCandidate;
export type ResolutionResult = Infer<typeof D.resolutionResult>;
export type Finding = Infer<typeof D.finding>;
export type CascadeResult = Infer<typeof D.cascadeResult>;
export type NotCheckedReason = Infer<typeof D.notCheckedReason>;
export type EvidenceItem = Infer<typeof D.evidenceItem>;
export type EvidenceResolution = Infer<typeof D.evidenceResolution>;
export type ChangesResult = Infer<typeof D.changesResult>;
export type EvidenceChange = ChangesResult["changes"][number];
export type Assessment = Infer<typeof D.assessment>;
export type Stats = Infer<typeof D.stats>;
export type PairOut = Infer<typeof D.pairOut>;
export type CombinationOut = Infer<typeof D.combinationOut>;
export type RegionsOut = Infer<typeof D.regionsOut>;
export type SharedOut = Infer<typeof D.sharedOut>;
export type SnapshotOut = Infer<typeof D.snapshotOut>;
export type Sentence = Infer<typeof D.sentence>;
export type MedicineRow = Infer<typeof D.medicineRow>;
export type StatRow = Infer<typeof D.statRow>;
export type NoteBlock = Sentence | MedicineRow | StatRow;
export type NoteDocument = Infer<typeof D.noteDocument>;
export type NoteSection = NoteDocument["sections"][number];
export type NoteOut = Infer<typeof D.noteOut>;
export type TokenOut = Infer<typeof D.tokenOut>;
export type OutcomeFormOut = Infer<typeof D.outcomeFormOut>;
export type OutcomeStoredOut = Infer<typeof D.outcomeStoredOut>;
export type WithdrawnOut = Infer<typeof D.withdrawnOut>;
export type ContributionCreated = Infer<typeof D.contributionCreated>;
export type DeletionDone = Infer<typeof D.deletionDone>;
export type StorageInfo = Infer<typeof D.storageInfo>;

// --- requests (exact fields of the route models; `extra="forbid"` on the server) -------------
export interface ScanIn {
  content: string;
  region?: ScanRegion;
}
export interface NdcIn {
  ndc: string;
}
export interface SearchIn {
  query: string;
  region?: ScanRegion;
  limit?: number;
}
export interface ProductsIn {
  candidate_ids: string[];
}
export interface ChoiceIn {
  position: number;
  ingredient: string;
}
export interface ItemIn {
  product?: string;
  ingredient?: string;
  choices?: ChoiceIn[];
  started?: string;
}
export interface EvaluateIn {
  dataset_version: string;
  items: ItemIn[];
}
export interface EvidenceIn {
  evidence_ids: string[];
}
export interface ChangesIn {
  since?: string;
  limit?: number;
}
export interface EventRefIn {
  key: string;
}
export interface PairIn {
  ingredient: string;
  event: EventRefIn;
  region: MemoryRegion;
  scope: "suspect" | "any";
}
export interface CombinationIn {
  ingredients: string[];
  region?: MemoryRegion;
  scope?: "suspect" | "any";
  top_events?: number;
}
export interface RegionsIn {
  ingredients: string[];
  event?: EventRefIn;
  scope?: "suspect" | "any";
}
export interface SharedIn {
  layer: "contributions" | "outcomes";
  ingredients: string[];
  event: string;
  direction: "adverse" | "benefit";
}
export interface PinsIn {
  rule_base_version?: string;
  integrity_version?: string;
  counts_build_id?: string;
}
export interface NoteIn {
  evaluation: EvaluateIn;
  pins: PinsIn;
  languages: Locale[];
  region: UserRegion;
  statistics_region?: LoopRegion;
}
export interface TokenIn {
  note: NoteIn;
  consent_version: string;
  outcome_region: LoopRegion;
}
export interface TokenBodyIn {
  token: string;
}
export interface AnswerIn {
  ref: number;
  assessment: "confirmed" | "not_a_cascade";
  action?: "dose_changed" | "medicine_changed" | "stopped" | "no_change";
  action_on?: "index" | "marker";
}
export interface OutcomeIn {
  token: string;
  answers: AnswerIn[];
}
export interface ContributionIn {
  consent: { version: string; explicit: true };
  age_band: number;
  sex?: "female" | "male";
  region: LoopRegion;
  ingredients: string[];
  event: string;
  direction: "adverse" | "benefit";
}
export interface DeletionIn {
  deletion_token: string;
}
