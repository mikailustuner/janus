/**
 * The API client (experience design §5, §5.5, DP15, DP16). Same-origin `/api/…` only, JSON bodies,
 * `credentials: "omit"`, `cache: "no-store"`, no referrer, a timeout on every call (10 s reads,
 * 20 s note and token) and no retry: a write is repeated only when the user asks (Req 22.1).
 *
 * `JanusReadClient` is what demo mode can answer from fixtures; `JanusLoopClient` holds the write
 * and loop routes, which `DemoClient` does not implement at all (P14).
 */
import { BuildError } from "./builders";
import type {
  CascadeResult,
  CombinationIn,
  CombinationOut,
  ContributionCreated,
  ContributionIn,
  DeletionDone,
  DeletionIn,
  EvaluateIn,
  EvidenceIn,
  EvidenceResolution,
  NdcIn,
  NoteIn,
  NoteOut,
  OutcomeFormOut,
  OutcomeIn,
  OutcomeStoredOut,
  PairIn,
  PairOut,
  ProductsIn,
  RegionsIn,
  RegionsOut,
  ResolutionResult,
  ScanIn,
  SearchIn,
  SharedIn,
  SharedOut,
  SnapshotOut,
  StorageInfo,
  TokenBodyIn,
  TokenIn,
  TokenOut,
  WithdrawnOut,
} from "./contracts";
import * as D from "./decode";
import { messageKeyFor, type ApiError, type Route } from "./errors";

export type Result<T> = { ok: true; data: T } | { ok: false; error: ApiError };

export interface JanusReadClient {
  resolveScan(body: ScanIn): Promise<Result<ResolutionResult>>;
  resolveNdc(body: NdcIn): Promise<Result<ResolutionResult>>;
  resolveSearch(body: SearchIn): Promise<Result<ResolutionResult>>;
  resolveProducts(body: ProductsIn): Promise<Result<ResolutionResult>>;
  evaluate(body: EvaluateIn): Promise<Result<CascadeResult>>;
  resolveEvidence(body: EvidenceIn): Promise<Result<EvidenceResolution>>;
  memoryPair(body: PairIn): Promise<Result<PairOut>>;
  memoryCombination(body: CombinationIn): Promise<Result<CombinationOut>>;
  memoryRegions(body: RegionsIn): Promise<Result<RegionsOut>>;
  memoryShared(body: SharedIn): Promise<Result<SharedOut>>;
  memorySnapshot(): Promise<Result<SnapshotOut>>;
  noteDocument(body: NoteIn): Promise<Result<NoteOut>>;
  privacyStorage(): Promise<Result<StorageInfo>>;
}

export interface JanusLoopClient {
  noteToken(body: TokenIn): Promise<Result<TokenOut>>;
  withdraw(body: TokenBodyIn): Promise<Result<WithdrawnOut>>;
  outcomeForm(body: TokenBodyIn): Promise<Result<OutcomeFormOut>>;
  outcomes(body: OutcomeIn): Promise<Result<OutcomeStoredOut>>;
  contribute(body: ContributionIn): Promise<Result<ContributionCreated>>;
  deleteContribution(body: DeletionIn): Promise<Result<DeletionDone>>;
}

export type JanusClient = JanusReadClient & JanusLoopClient;

type Fetch = (input: string, init: RequestInit) => Promise<Response>;

const READ_TIMEOUT_MS = 10_000;
const NOTE_TIMEOUT_MS = 20_000;

/** Turns any thrown value of a call into a typed error; never rethrows (P20). */
function thrown(route: Route, e: unknown): ApiError {
  if (e instanceof BuildError)
    return { kind: "build", route, messageKey: "Errors.client_defect" };
  if (e instanceof D.ContractError)
    return { kind: "contract", route, messageKey: "Errors.generic" };
  const name = (e as { name?: unknown } | null)?.name;
  if (name === "TimeoutError" || name === "AbortError")
    return { kind: "timeout", route, messageKey: "Errors.network" };
  return { kind: "network", route, messageKey: "Errors.network" };
}

export class HttpClient implements JanusClient {
  constructor(
    private readonly fetchImpl: Fetch = (input, init) => fetch(input, init),
    private readonly base = "/api",
  ) {}

  /** One call: request, status, decode. All failures become `ApiError`. */
  async call<T>(
    route: Route,
    method: "GET" | "POST",
    body: unknown,
    decoder: D.Decoder<T>,
    timeoutMs = READ_TIMEOUT_MS,
  ): Promise<Result<T>> {
    let res: Response;
    try {
      res = await this.fetchImpl(`${this.base}/${route}`, {
        method,
        headers:
          method === "POST" ? { "content-type": "application/json" } : {},
        body: method === "POST" ? JSON.stringify(body) : undefined,
        credentials: "omit",
        cache: "no-store",
        referrerPolicy: "no-referrer",
        signal: AbortSignal.timeout(timeoutMs),
      });
    } catch (e) {
      return { ok: false, error: thrown(route, e) };
    }
    let json: unknown = null;
    try {
      const textBody = await res.text();
      json = textBody ? JSON.parse(textBody) : null;
    } catch (e) {
      if (!res.ok) json = null;
      else
        return {
          ok: false,
          error:
            (e as Error)?.name === "TimeoutError"
              ? thrown(route, e)
              : { kind: "contract", route, messageKey: "Errors.generic" },
        };
    }
    if (!res.ok) {
      const { error, fields } = D.errorBody(json);
      return {
        ok: false,
        error: {
          kind: "http",
          route,
          status: res.status,
          code: error,
          fields,
          messageKey: messageKeyFor(route, res.status, error, fields),
        },
      };
    }
    const decoded = D.decode(decoder, json);
    if (!decoded.ok)
      return {
        ok: false,
        error: { kind: "contract", route, messageKey: "Errors.generic" },
      };
    return { ok: true, data: decoded.value };
  }

  resolveScan = (b: ScanIn) =>
    this.call("resolve/scan", "POST", b, D.resolutionResult);
  resolveNdc = (b: NdcIn) =>
    this.call("resolve/ndc", "POST", b, D.resolutionResult);
  resolveSearch = (b: SearchIn) =>
    this.call("resolve/search", "POST", b, D.resolutionResult);
  resolveProducts = (b: ProductsIn) =>
    this.call("resolve/products", "POST", b, D.resolutionResult);
  evaluate = (b: EvaluateIn) =>
    this.call("cascades/evaluate", "POST", b, D.cascadeResult);
  resolveEvidence = (b: EvidenceIn) =>
    this.call("evidence/resolve", "POST", b, D.evidenceResolution);
  memoryPair = (b: PairIn) => this.call("memory/pair", "POST", b, D.pairOut);
  memoryCombination = (b: CombinationIn) =>
    this.call("memory/combination", "POST", b, D.combinationOut);
  memoryRegions = (b: RegionsIn) =>
    this.call("memory/regions", "POST", b, D.regionsOut);
  memoryShared = (b: SharedIn) =>
    this.call("memory/shared", "POST", b, D.sharedOut);
  memorySnapshot = () =>
    this.call("memory/snapshot", "GET", null, D.snapshotOut);
  noteDocument = (b: NoteIn) =>
    this.call("notes/document", "POST", b, D.noteOut, NOTE_TIMEOUT_MS);
  privacyStorage = () =>
    this.call("privacy/storage", "GET", null, D.storageInfo);
  noteToken = (b: TokenIn) =>
    this.call("notes/token", "POST", b, D.tokenOut, NOTE_TIMEOUT_MS);
  withdraw = (b: TokenBodyIn) =>
    this.call("notes/withdraw", "POST", b, D.withdrawnOut);
  outcomeForm = (b: TokenBodyIn) =>
    this.call("outcomes/form", "POST", b, D.outcomeFormOut);
  outcomes = (b: OutcomeIn) =>
    this.call("outcomes", "POST", b, D.outcomeStoredOut);
  contribute = (b: ContributionIn) =>
    this.call("contributions", "POST", b, D.contributionCreated);
  deleteContribution = (b: DeletionIn) =>
    this.call("contributions/deletions", "POST", b, D.deletionDone);
}
