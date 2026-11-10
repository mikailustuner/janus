/**
 * Typed API errors and the (route, status, code) → message-key map (experience design §5.3,
 * Req 22.4, P20). Messages are catalogue keys only: no field name or value of a request or a
 * response ever reaches a message. 422 bodies name fields only and are never shown raw.
 */

export type Route =
  | "resolve/scan"
  | "resolve/ndc"
  | "resolve/search"
  | "resolve/products"
  | "cascades/evaluate"
  | "evidence/resolve"
  | "evidence/changes"
  | "memory/pair"
  | "memory/combination"
  | "memory/regions"
  | "memory/shared"
  | "memory/snapshot"
  | "notes/document"
  | "notes/token"
  | "notes/withdraw"
  | "outcomes/form"
  | "outcomes"
  | "contributions"
  | "contributions/deletions"
  | "privacy/storage"
  | "passport/presence"
  | "passport/products"
  | "light/overview"
  | "light/cards"
  | "light/validation"
  | "light/export"
  | "seance/catalogue"
  | "seance/pair"
  | "timemachine/catalogue"
  | "timemachine/substance"
  | "timemachine/cascade"
  | "open/outcomes"
  | "open/data-quality"
  | "open/faers-onset"
  | "open/faers-onset/row"
  | "simulate"
  | "simulate/compounds"
  | "simulate/jobs"
  | "recalls/check"
  | "medicine-info";

export const ROUTES: readonly Route[] = [
  "resolve/scan",
  "resolve/ndc",
  "resolve/search",
  "resolve/products",
  "cascades/evaluate",
  "evidence/resolve",
  "evidence/changes",
  "memory/pair",
  "memory/combination",
  "memory/regions",
  "memory/shared",
  "memory/snapshot",
  "notes/document",
  "notes/token",
  "notes/withdraw",
  "outcomes/form",
  "outcomes",
  "contributions",
  "contributions/deletions",
  "privacy/storage",
  "passport/presence",
  "passport/products",
  "light/overview",
  "light/cards",
  "light/validation",
  "light/export",
  "seance/catalogue",
  "seance/pair",
  "timemachine/catalogue",
  "timemachine/substance",
  "timemachine/cascade",
  "open/outcomes",
  "open/data-quality",
  "open/faers-onset",
  "open/faers-onset/row",
  "simulate",
  "simulate/compounds",
  "simulate/jobs",
  "recalls/check",
  "medicine-info",
];

export type ApiError =
  | {
      kind: "http";
      route: Route;
      status: number;
      code: string | null;
      /** Field paths named by a 422 body; for the flow logic only, never displayed. */
      fields: string[];
      messageKey: MessageKey;
    }
  | { kind: "network"; route: Route; messageKey: "Errors.network" }
  | { kind: "timeout"; route: Route; messageKey: "Errors.network" }
  | { kind: "contract"; route: Route; messageKey: "Errors.generic" }
  | { kind: "build"; route: Route; messageKey: "Errors.client_defect" };

/** Every message key the map can return (P20 checks each exists in every locale). */
export const MESSAGE_KEYS = [
  "Errors.generic",
  "Errors.network",
  "Errors.client_defect",
  "Errors.resolution_unavailable",
  "Errors.cascades_unavailable",
  "Errors.dataset_changed",
  "Errors.dataset_changed_again",
  "Scan.errors.unreadable",
  "Scan.errors.gtin_check_digit",
  "Scan.errors.ndc_malformed",
  "Evidence.unavailable",
  "Memory.codes.memory_unavailable",
  "Note.version_changed",
  "Note.language_unavailable",
  "Note.unavailable",
  "Note.qr_no_findings",
  "Note.qr_unavailable",
  "Doctor.errors.invalid_token",
  "Doctor.errors.token_expired",
  "Doctor.errors.token_not_usable",
  "Doctor.errors.token_used",
  "Doctor.errors.unavailable",
  "Withdraw.errors.invalid_token",
  "Withdraw.errors.unavailable",
  "Donate.errors.unavailable",
  "Donate.errors.consent_changed",
  "Donate.delete.not_found",
  "Donate.delete.invalid_token",
  "Passport.states.error",
  "Passport.products.error",
  "Light.errors.unavailable",
  "Seance.errors.unavailable",
  "TimeMachine.errors.unavailable",
  "TimeMachine.errors.unknown",
  "OpenData.errors.unavailable",
  "DataQuality.errors.unavailable",
  "Onset.errors.unavailable",
  "Onset.errors.unknown",
  "Simulation.errors.unavailable",
  "Simulation.errors.queueFull",
  "Simulation.errors.rateLimited",
  "Simulation.errors.unknownJob",
  "Simulation.errors.demoOnly",
  "Recall.errors.unavailable",
  "PlainInfo.errors.unavailable",
] as const;

export type MessageKey = (typeof MESSAGE_KEYS)[number];

const isMemory = (r: Route) => r.startsWith("memory/");
const isResolve = (r: Route) => r.startsWith("resolve/");
const isDoctor = (r: Route) => r === "outcomes/form" || r === "outcomes";

/** The message key for an HTTP error answer. Total: unknown combinations give the generic key. */
export function messageKeyFor(
  route: Route,
  status: number,
  code: string | null,
  fields: readonly string[] = [],
): MessageKey {
  if (
    status === 422 &&
    (code === "invalid_request" || code === "gs1_serial_not_accepted")
  )
    return "Errors.client_defect";
  if (isResolve(route)) {
    if (status === 503 && code === "resolution_unavailable")
      return "Errors.resolution_unavailable";
    if (route === "resolve/scan" && status === 422) {
      if (code === "gtin_check_digit") return "Scan.errors.gtin_check_digit";
      if (code === "gtin_missing" || code?.startsWith("gs1_"))
        return "Scan.errors.unreadable";
    }
    if (route === "resolve/ndc" && status === 422 && code === "ndc_malformed")
      return "Scan.errors.ndc_malformed";
  }
  if (route === "cascades/evaluate") {
    if (status === 409 && code === "dataset_version_mismatch")
      return "Errors.dataset_changed";
    if (status === 503 && code === "cascades_unavailable")
      return "Errors.cascades_unavailable";
  }
  if (
    route === "evidence/resolve" &&
    status === 503 &&
    code === "integrity_unavailable"
  )
    return "Evidence.unavailable";
  if (isMemory(route) && status === 503 && code === "memory_unavailable")
    return "Memory.codes.memory_unavailable";
  if (route === "notes/document" || route === "notes/token") {
    if (
      status === 409 &&
      (code === "version_mismatch" || code === "dataset_version_mismatch")
    )
      return "Note.version_changed";
    if (status === 422 && code === "note_language_unavailable")
      return "Note.language_unavailable";
    if (route === "notes/token" && status === 422 && code === "no_findings")
      return "Note.qr_no_findings";
    if (status === 503 && code === "notes_unavailable")
      return route === "notes/token"
        ? "Note.qr_unavailable"
        : "Note.unavailable";
  }
  if (isDoctor(route)) {
    if (status === 400 && code === "invalid_token")
      return "Doctor.errors.invalid_token";
    if (status === 410 && code === "token_expired")
      return "Doctor.errors.token_expired";
    if (status === 410 && code === "token_not_usable")
      return "Doctor.errors.token_not_usable";
    if (status === 409 && code === "token_used")
      return "Doctor.errors.token_used";
    if (status === 503) return "Doctor.errors.unavailable";
  }
  if (route === "notes/withdraw") {
    if (status === 400 || status === 410)
      return "Withdraw.errors.invalid_token";
    if (status === 503) return "Withdraw.errors.unavailable";
  }
  if (route === "contributions") {
    if (status === 503 && code === "donations_unavailable")
      return "Donate.errors.unavailable";
    if (status === 422 && code === "invalid_donation")
      return fields.includes("consent.version")
        ? "Donate.errors.consent_changed"
        : "Errors.client_defect";
    if (status === 422) return "Errors.client_defect";
  }
  if (route === "contributions/deletions") {
    if (status === 404 && code === "no_donation_for_token")
      return "Donate.delete.not_found";
    if (status === 422 && code === "invalid_deletion")
      return "Donate.delete.invalid_token";
    if (status === 503) return "Donate.errors.unavailable";
  }
  // medication-passport §3.3: no partial answer; the screen offers a retry, never "not found".
  if (route === "passport/presence" && status === 503)
    return "Passport.states.error";
  if (route === "passport/products" && status === 503)
    return "Passport.products.error";
  // light-face design §9: no build or no integrity snapshot (fail closed).
  if (
    route.startsWith("light/") &&
    status === 503 &&
    code === "light_unavailable"
  )
    return "Light.errors.unavailable";
  // séance design §7.1: the Canon package is not installed.
  if (
    route.startsWith("seance/") &&
    status === 503 &&
    code === "seance_unavailable"
  )
    return "Seance.errors.unavailable";
  // time-machine design §10: the artifact is not installed (503) or the id is unknown (404).
  if (route.startsWith("timemachine/")) {
    if (status === 503 && code === "time_machine_not_installed")
      return "TimeMachine.errors.unavailable";
    if (
      status === 404 &&
      (code === "unknown_substance" || code === "unknown_cascade")
    )
      return "TimeMachine.errors.unknown";
  }
  // open-data design §4: no database or no noise key, the dataset is never served without the rule.
  if (
    route === "open/outcomes" &&
    status === 503 &&
    code === "open_data_unavailable"
  )
    return "OpenData.errors.unavailable";
  // research-tools Req 1-2: the data-quality report or the onset table is not installed (503),
  // or a PIPC position is unknown (404).
  if (
    route === "open/data-quality" &&
    status === 503 &&
    code === "data_quality_unavailable"
  )
    return "DataQuality.errors.unavailable";
  if (route.startsWith("open/faers-onset")) {
    if (status === 503 && code === "onset_table_unavailable")
      return "Onset.errors.unavailable";
    if (status === 404 && code === "unknown_position")
      return "Onset.errors.unknown";
  }
  // simulation-service design §2: switched off, queue full, rate limited, expired job.
  if (route.startsWith("simulate")) {
    if (status === 503 && code === "simulation_unavailable")
      return "Simulation.errors.unavailable";
    if (status === 429 && code === "queue_full")
      return "Simulation.errors.queueFull";
    if (status === 429 && code === "rate_limited")
      return "Simulation.errors.rateLimited";
    if (status === 404 && code === "unknown_job")
      return "Simulation.errors.unknownJob";
  }
  // recall-check Req 4.6: no `us_recalls` run is installed.
  if (
    route === "recalls/check" &&
    status === 503 &&
    code === "recalls_unavailable"
  )
    return "Recall.errors.unavailable";
  // plain-medicine-info Req 4.4: the group table or the abrupt-stop list is not loaded.
  if (
    route === "medicine-info" &&
    status === 503 &&
    code === "medicine_info_unavailable"
  )
    return "PlainInfo.errors.unavailable";
  return "Errors.generic";
}
