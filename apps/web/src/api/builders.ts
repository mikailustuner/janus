/**
 * The only functions that build request bodies (experience design §5.1, P2). Each returns exactly
 * the fields of its route model, checks the patterns the server enforces, and throws `BuildError`
 * (a client defect) instead of sending a body the server would reject. No box name, ATC code,
 * image, recognised text as a whole or `demo` field can reach a body: the inputs are ids, keys,
 * codes, months and the user's chosen query only (Req 23.1, 23.2).
 */
import type {
  AnswerIn,
  CombinationIn,
  ContributionIn,
  DeletionIn,
  EvaluateIn,
  EvidenceIn,
  ItemIn,
  Locale,
  LoopRegion,
  MemoryRegion,
  NdcIn,
  NoteIn,
  OutcomeIn,
  PairIn,
  PinsIn,
  ProductsIn,
  RegionsIn,
  ScanIn,
  ScanRegion,
  SearchIn,
  SharedIn,
  TokenBodyIn,
  TokenIn,
  UserRegion,
} from "./contracts";

export class BuildError extends Error {
  constructor(readonly field: string) {
    super(`request field not valid: ${field}`);
    this.name = "BuildError";
  }
}

export const PATTERNS = {
  candidate: /^(TR|US|EU):[a-z_]+:[0-9]{1,9}$/,
  qid: /^(Q[1-9][0-9]{0,9}|J[1-9][0-9]{0,5})$/,
  month: /^\d{4}-(0[1-9]|1[0-2])$/,
  hex64: /^[0-9a-f]{64}$/,
  buildId: /^[0-9A-Za-z_.-]{1,80}$/,
  eventKey: /^[a-z0-9][a-z0-9_.-]{0,39}$/,
  consent: /^[a-z0-9][a-z0-9.-]{0,31}$/,
  token: /^[A-Za-z0-9_-]{40,4096}$/,
  deletionToken: /^jdt_[A-Za-z0-9_-]{43}$/,
  evidenceId: /^[a-z_]+:[A-Za-z0-9_.:\-/]+$/,
} as const;

const need = (ok: boolean, field: string) => {
  if (!ok) throw new BuildError(field);
};
const distinct = (xs: readonly string[]) => new Set(xs).size === xs.length;
const SCAN_REGIONS: readonly string[] = ["TR", "US", "EU"];
const LOOP_REGIONS: readonly string[] = ["TR", "EU", "US"];
const USER_REGIONS: readonly string[] = ["US", "TR", "EU", "OTHER", "UNKNOWN"];
const MEMORY_REGIONS: readonly string[] = [
  "ALL",
  "TR",
  "EU",
  "US",
  "OTHER",
  "UNKNOWN",
];
const LOCALES: readonly string[] = ["en", "tr", "de", "fr", "es"];

function withRegion<T extends object>(body: T, region: ScanRegion | null): T {
  if (region === null) return body;
  need(SCAN_REGIONS.includes(region), "region");
  return { ...body, region };
}

export function scanBody(content: string, region: ScanRegion | null): ScanIn {
  need(content.length >= 1 && content.length <= 512, "content");
  return withRegion({ content }, region);
}

export function ndcBody(ndc: string): NdcIn {
  need(ndc.length >= 1 && ndc.length <= 32, "ndc");
  return { ndc };
}

export function searchBody(
  query: string,
  region: ScanRegion | null,
  limit?: number,
): SearchIn {
  const q = query.trim();
  need(q.length >= 2 && q.length <= 100, "query");
  const body: SearchIn = withRegion({ query: q }, region);
  if (limit !== undefined) {
    need(Number.isInteger(limit) && limit >= 1 && limit <= 20, "limit");
    body.limit = limit;
  }
  return body;
}

export function productsBody(ids: readonly string[]): ProductsIn {
  need(ids.length >= 1 && ids.length <= 50, "candidate_ids");
  for (const id of ids) need(PATTERNS.candidate.test(id), "candidate_ids");
  return { candidate_ids: [...ids] };
}

/** One evaluation item: exactly one of product / ingredient; choices only with a product. */
export function itemIn(item: {
  product?: string;
  ingredient?: string;
  choices?: readonly { position: number; ingredient: string }[];
  started: string | null;
}): ItemIn {
  const out: ItemIn = {};
  need(
    (item.product === undefined) !== (item.ingredient === undefined),
    "items.kind",
  );
  if (item.product !== undefined) {
    need(PATTERNS.candidate.test(item.product), "items.product");
    out.product = item.product;
  } else {
    need(PATTERNS.qid.test(item.ingredient ?? ""), "items.ingredient");
    out.ingredient = item.ingredient;
  }
  const choices = item.choices ?? [];
  if (choices.length > 0) {
    need(out.product !== undefined && choices.length <= 10, "items.choices");
    need(distinct(choices.map((c) => String(c.position))), "items.choices");
    out.choices = choices.map((c) => {
      need(
        Number.isInteger(c.position) && c.position >= 0 && c.position <= 49,
        "items.choices",
      );
      need(PATTERNS.qid.test(c.ingredient), "items.choices");
      return { position: c.position, ingredient: c.ingredient };
    });
  }
  if (item.started !== null) {
    need(PATTERNS.month.test(item.started), "items.started");
    out.started = item.started;
  }
  return out;
}

export function evaluateBody(
  datasetVersion: string,
  items: readonly ItemIn[],
): EvaluateIn {
  need(PATTERNS.hex64.test(datasetVersion), "dataset_version");
  need(items.length >= 1 && items.length <= 50, "items");
  return {
    dataset_version: datasetVersion,
    items: items.map((i) => ({ ...i })),
  };
}

export function evidenceBody(ids: readonly string[]): EvidenceIn {
  need(ids.length >= 1 && ids.length <= 200 && distinct(ids), "evidence_ids");
  for (const id of ids) need(PATTERNS.evidenceId.test(id), "evidence_ids");
  return { evidence_ids: [...ids] };
}

const keys = (ingredients: readonly string[], min: number, field: string) => {
  need(
    ingredients.length >= min &&
      ingredients.length <= 20 &&
      distinct(ingredients),
    field,
  );
  for (const k of ingredients) need(PATTERNS.qid.test(k), field);
  return [...ingredients];
};

export function pairBody(
  ingredient: string,
  eventKey: string,
  region: MemoryRegion = "ALL",
): PairIn {
  need(PATTERNS.qid.test(ingredient), "ingredient");
  need(PATTERNS.eventKey.test(eventKey), "event.key");
  need(MEMORY_REGIONS.includes(region), "region");
  return { ingredient, event: { key: eventKey }, region, scope: "suspect" };
}

export function combinationBody(ingredients: readonly string[]): CombinationIn {
  return { ingredients: keys(ingredients, 2, "ingredients") };
}

export function regionsBody(
  ingredients: readonly string[],
  eventKey?: string,
): RegionsIn {
  const body: RegionsIn = { ingredients: keys(ingredients, 1, "ingredients") };
  if (eventKey !== undefined) {
    need(PATTERNS.eventKey.test(eventKey), "event.key");
    body.event = { key: eventKey };
  }
  return body;
}

export function sharedBody(
  layer: "contributions" | "outcomes",
  ingredients: readonly string[],
  eventKey: string,
  direction: "adverse" | "benefit",
): SharedIn {
  need(layer === "contributions" || layer === "outcomes", "layer");
  need(PATTERNS.eventKey.test(eventKey), "event");
  need(direction === "adverse" || direction === "benefit", "direction");
  return {
    layer,
    ingredients: keys(ingredients, 1, "ingredients"),
    event: eventKey,
    direction,
  };
}

export function pinsIn(pins: {
  rule_base_version?: string | null;
  integrity_version?: string | null;
  counts_build_id?: string | null;
}): PinsIn {
  const out: PinsIn = {};
  if (pins.rule_base_version) {
    need(PATTERNS.hex64.test(pins.rule_base_version), "pins.rule_base_version");
    out.rule_base_version = pins.rule_base_version;
  }
  if (pins.integrity_version) {
    need(PATTERNS.hex64.test(pins.integrity_version), "pins.integrity_version");
    out.integrity_version = pins.integrity_version;
  }
  if (pins.counts_build_id) {
    need(PATTERNS.buildId.test(pins.counts_build_id), "pins.counts_build_id");
    out.counts_build_id = pins.counts_build_id;
  }
  return out;
}

export function noteBody(
  evaluation: EvaluateIn,
  pins: PinsIn,
  languages: readonly Locale[],
  region: UserRegion,
  statisticsRegion: LoopRegion | null,
): NoteIn {
  need(
    languages.length >= 1 && languages.length <= 2 && distinct(languages),
    "languages",
  );
  for (const l of languages) need(LOCALES.includes(l), "languages");
  need(USER_REGIONS.includes(region), "region");
  const body: NoteIn = {
    evaluation: evaluateBody(evaluation.dataset_version, evaluation.items),
    pins: { ...pins },
    languages: [...languages],
    region,
  };
  if (statisticsRegion !== null) {
    need(LOOP_REGIONS.includes(statisticsRegion), "statistics_region");
    body.statistics_region = statisticsRegion;
  }
  return body;
}

export function tokenBody(
  note: NoteIn,
  consentVersion: string,
  outcomeRegion: LoopRegion,
): TokenIn {
  need(note.languages.length === 1, "note.languages");
  need(PATTERNS.consent.test(consentVersion), "consent_version");
  need(LOOP_REGIONS.includes(outcomeRegion), "outcome_region");
  return {
    note,
    consent_version: consentVersion,
    outcome_region: outcomeRegion,
  };
}

export function tokenOnlyBody(token: string): TokenBodyIn {
  need(PATTERNS.token.test(token), "token");
  return { token };
}

const WITH_MEDICINE = new Set(["dose_changed", "medicine_changed", "stopped"]);

export function outcomesBody(
  token: string,
  answers: readonly AnswerIn[],
): OutcomeIn {
  need(PATTERNS.token.test(token), "token");
  need(answers.length >= 1 && answers.length <= 255, "answers");
  need(distinct(answers.map((a) => String(a.ref))), "answers");
  return {
    token,
    answers: answers.map((a) => {
      need(
        Number.isInteger(a.ref) && a.ref >= 0 && a.ref <= 254,
        "answers.ref",
      );
      const out: AnswerIn = { ref: a.ref, assessment: a.assessment };
      if (a.action !== undefined) out.action = a.action;
      need(
        WITH_MEDICINE.has(a.action ?? "") === (a.action_on !== undefined),
        "answers.action_on",
      );
      if (a.action_on !== undefined) out.action_on = a.action_on;
      return out;
    }),
  };
}

export const AGE_BANDS = [
  20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90,
] as const;

export function contributionBody(form: {
  consentVersion: string;
  consentTicked: boolean;
  ageBand: number;
  sex: "female" | "male" | null;
  region: LoopRegion;
  ingredients: readonly string[];
  event: string;
  direction: "adverse" | "benefit";
}): ContributionIn {
  need(form.consentTicked === true, "consent.explicit");
  need(PATTERNS.consent.test(form.consentVersion), "consent.version");
  need((AGE_BANDS as readonly number[]).includes(form.ageBand), "age_band");
  need(LOOP_REGIONS.includes(form.region), "region");
  need(/^[a-z0-9][a-z0-9_.-]{0,63}$/.test(form.event), "event");
  const body: ContributionIn = {
    consent: { version: form.consentVersion, explicit: true },
    age_band: form.ageBand,
    region: form.region,
    ingredients: keys(form.ingredients, 1, "ingredients"),
    event: form.event,
    direction: form.direction,
  };
  if (form.sex !== null) body.sex = form.sex;
  return body;
}

export function deletionBody(token: string): DeletionIn {
  need(PATTERNS.deletionToken.test(token), "deletion_token");
  return { deletion_token: token };
}
