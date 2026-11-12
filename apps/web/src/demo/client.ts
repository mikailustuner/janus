/**
 * The demo client (experience design §13.3, DP11, P14): answers the read routes from the recorded
 * fixtures of one synthetic patient, with no network at all. It has no method for the write and
 * loop routes (contributions, deletions, note token, withdrawal, outcome form and outcomes), so
 * demo mode cannot reach them by construction. It decides nothing: it returns the recorded
 * response whose request equals the one asked, else an error.
 */
import type { JanusReadClient, Result } from "@/api/client";
import type {
  CascadeResult,
  CombinationOut,
  EvaluateIn,
  EvidenceResolution,
  NoteDocument,
  NoteOut,
  PairOut,
  RegionsOut,
  ResolutionResult,
  SharedOut,
  SnapshotOut,
} from "@/api/contracts";
import * as D from "@/api/decode";
import type { Route } from "@/api/errors";
import type { Item, SourceKey } from "@/store/list";

import { detectDemo } from "./codes";
import type { PatientId } from "./session";

export interface FixtureItem {
  demoCode: string;
  route: string;
  sourceKey: SourceKey;
  boxName: string;
  started: string | null;
  choices: { position: number; ingredient: string }[];
  resolution: unknown;
  scanResolution?: unknown;
}

export interface Fixture {
  patient: PatientId;
  userRegion: "TR" | "EU" | "US";
  noteLanguage: "en" | "tr" | "de" | "fr" | "es" | "pt";
  recorded: {
    date: string;
    dataset_version: string;
    rule_base_version: string;
    integrity_version: string;
    counts_build_id: string;
    glossary_version: string;
  };
  items: FixtureItem[];
  evaluation: unknown;
  evidence: Record<string, unknown>;
  memory: {
    snapshot: unknown;
    pairs: Record<string, unknown>;
    combination: unknown;
    regions: unknown;
    shared: Record<string, unknown>;
  };
  notes: Record<string, unknown>;
  doctorForm: unknown;
}

const loaders: Record<PatientId, () => Promise<{ default: unknown }>> = {
  istanbul: () => import("./fixtures/istanbul.json"),
  cologne: () => import("./fixtures/cologne.json"),
  ohio: () => import("./fixtures/ohio.json"),
};
const cache = new Map<PatientId, Promise<Fixture>>();

export function loadFixture(patient: PatientId): Promise<Fixture> {
  let p = cache.get(patient);
  if (!p) {
    p = loaders[patient]().then((m) => m.default as Fixture);
    p.catch(() => cache.delete(patient));
    cache.set(patient, p);
  }
  return p;
}

/** The demo patient's list items, as confirmed list items (never written to the store). */
export function demoItems(f: Fixture): Item[] {
  return f.items.map((it, i) => {
    const res = D.decode(D.resolutionResult, it.resolution);
    if (!res.ok || res.value.candidates.length !== 1)
      throw new D.ContractError(`items[${i}]`);
    return {
      id: `demo-${f.patient}-${i}`,
      sourceKey: it.sourceKey,
      datasetVersion: res.value.dataset_version,
      candidate: res.value.candidates[0]!,
      choices: it.choices,
      started: it.started,
      boxName: it.boxName,
      needsConfirmation: false,
    };
  });
}

const same = (a: unknown, b: unknown) =>
  JSON.stringify(a) === JSON.stringify(b);
const sortedSame = (a: readonly string[], b: readonly string[]) =>
  same([...a].sort(), [...b].sort());

function answer<T>(
  route: Route,
  decoder: D.Decoder<T>,
  value: unknown,
): Result<T> {
  if (value === undefined)
    return {
      ok: false,
      error: {
        kind: "http",
        route,
        status: 404,
        code: "demo_not_recorded",
        fields: [],
        messageKey: "Errors.generic",
      },
    };
  const r = D.decode(decoder, value);
  return r.ok
    ? { ok: true, data: r.value }
    : {
        ok: false,
        error: { kind: "contract", route, messageKey: "Errors.generic" },
      };
}

export class DemoClient implements JanusReadClient {
  constructor(private readonly f: Fixture) {}

  /** The evaluation input the fixture was recorded with (list order, ids, start months). */
  recordedEvaluateIn(): EvaluateIn {
    const items = demoItems(this.f).map((it) => {
      const c = it.candidate;
      const out: Record<string, unknown> =
        c.kind === "product"
          ? { product: c.candidate_id }
          : { ingredient: c.ingredient_key.qid };
      if (it.started) out.started = it.started;
      return out;
    });
    return {
      dataset_version: this.f.recorded.dataset_version,
      items,
    } as EvaluateIn;
  }

  private resolutionFor(
    text: string,
    route: Route,
  ): Promise<Result<ResolutionResult>> {
    const ref = detectDemo(text);
    const item =
      ref && ref.patient === this.f.patient
        ? this.f.items[ref.index]
        : undefined;
    return Promise.resolve(answer(route, D.resolutionResult, item?.resolution));
  }

  resolveScan = (b: { content: string }) =>
    this.resolutionFor(b.content, "resolve/scan");
  resolveNdc = (b: { ndc: string }) => this.resolutionFor(b.ndc, "resolve/ndc");
  resolveSearch = (b: { query: string }) => {
    const item = this.f.items.find(
      (i) => i.sourceKey.kind === "search" && i.sourceKey.query === b.query,
    );
    return Promise.resolve(
      answer("resolve/search", D.resolutionResult, item?.resolution),
    );
  };
  resolveProducts = () =>
    Promise.resolve(
      answer<ResolutionResult>(
        "resolve/products",
        D.resolutionResult,
        undefined,
      ),
    );

  evaluate = (b: EvaluateIn): Promise<Result<CascadeResult>> =>
    Promise.resolve(
      answer(
        "cascades/evaluate",
        D.cascadeResult,
        same(b, this.recordedEvaluateIn()) ? this.f.evaluation : undefined,
      ),
    );

  resolveEvidence = (b: {
    evidence_ids: string[];
  }): Promise<Result<EvidenceResolution>> => {
    const ev = D.decode(D.cascadeResult, this.f.evaluation);
    const finding = ev.ok
      ? ev.value.findings.find((f) =>
          sortedSame(b.evidence_ids, [
            ...new Set([
              ...f.evidence_ids,
              ...f.excluded_evidence.map((e) => e.id),
            ]),
          ]),
        )
      : undefined;
    return Promise.resolve(
      answer(
        "evidence/resolve",
        D.evidenceResolution,
        finding ? this.f.evidence[finding.finding_id] : undefined,
      ),
    );
  };

  memoryPair = (b: {
    ingredient: string;
    event: { key: string };
    region: string;
    scope: string;
  }): Promise<Result<PairOut>> => {
    const locator = `faers:ingredient=${b.ingredient};event=${b.event.key};region=${b.region};scope=${b.scope}`;
    return Promise.resolve(
      answer("memory/pair", D.pairOut, this.f.memory.pairs[locator]),
    );
  };

  private recordedKeys(): string[] {
    const c = D.decode(D.combinationOut, this.f.memory.combination);
    return c.ok ? c.value.ingredients.map((i) => i.key) : [];
  }

  memoryCombination = (b: {
    ingredients: string[];
  }): Promise<Result<CombinationOut>> =>
    Promise.resolve(
      answer(
        "memory/combination",
        D.combinationOut,
        sortedSame(b.ingredients, this.recordedKeys())
          ? this.f.memory.combination
          : undefined,
      ),
    );

  memoryRegions = (b: {
    ingredients: string[];
    event?: unknown;
  }): Promise<Result<RegionsOut>> =>
    Promise.resolve(
      answer(
        "memory/regions",
        D.regionsOut,
        !b.event && sortedSame(b.ingredients, this.recordedKeys())
          ? this.f.memory.regions
          : undefined,
      ),
    );

  memoryShared = (b: {
    layer: string;
    event: string;
    ingredients: string[];
  }): Promise<Result<SharedOut>> => {
    const v = sortedSame(b.ingredients, this.recordedKeys())
      ? this.f.memory.shared[`${b.layer}:${b.event}`]
      : undefined;
    if (v && typeof v === "object" && "error_status" in v)
      return Promise.resolve({
        ok: false,
        error: {
          kind: "http",
          route: "memory/shared",
          status: (v as { error_status: number }).error_status,
          code: String((v as { error?: unknown }).error ?? ""),
          fields: [],
          messageKey: "Memory.codes.memory_unavailable",
        },
      });
    return Promise.resolve(answer("memory/shared", D.sharedOut, v));
  };

  memorySnapshot = (): Promise<Result<SnapshotOut>> =>
    Promise.resolve(
      answer("memory/snapshot", D.snapshotOut, this.f.memory.snapshot),
    );

  /**
   * Notes were recorded once per language with the same evaluation and pins; a two-language
   * request is answered with the two recorded documents in the asked order (design §13.3, DP34).
   */
  noteDocument = (b: {
    evaluation: EvaluateIn;
    languages: string[];
  }): Promise<Result<NoteOut>> => {
    if (!same(b.evaluation, this.recordedEvaluateIn()))
      return Promise.resolve(
        answer<NoteOut>("notes/document", D.noteOut, undefined),
      );
    const docs: NoteOut[] = [];
    for (const lang of b.languages) {
      const r = D.decode(D.noteOut, this.f.notes[lang]);
      if (!r.ok)
        return Promise.resolve(
          answer<NoteOut>("notes/document", D.noteOut, null),
        );
      docs.push(r.value);
    }
    const [first] = docs;
    if (!first)
      return Promise.resolve(
        answer<NoteOut>("notes/document", D.noteOut, undefined),
      );
    const documents: NoteDocument[] = docs.map((d) => d.documents[0]!);
    return Promise.resolve({ ok: true, data: { ...first, documents } });
  };

  privacyStorage = () =>
    Promise.resolve<Result<never>>({
      ok: false,
      error: {
        kind: "http",
        route: "privacy/storage",
        status: 503,
        code: "demo",
        fields: [],
        messageKey: "Errors.generic",
      },
    });
}
