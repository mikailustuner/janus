/**
 * Re-resolution after a dataset change (experience design §5.4, DP20, Req 22.3, P5). Each item is
 * resolved again from its source key; it is replaced only when exactly one candidate of the new
 * response is equivalent, keeping its start month, box name and the choices still listed in the
 * new ingredient's `key_candidates`. Every other item is marked for confirmation. Pure apart from
 * the injected resolver.
 */
import { ndcBody, scanBody, searchBody } from "@/api/builders";
import type { JanusReadClient, Result } from "@/api/client";
import type { Candidate, ResolutionResult } from "@/api/contracts";
import type { Item, SourceKey } from "@/store/list";

export type Resolver = (key: SourceKey) => Promise<Result<ResolutionResult>>;

export function resolverFor(
  client: JanusReadClient,
  scanRegion: "TR" | "US" | "EU" | null,
): Resolver {
  return (key) => {
    try {
      if (key.kind === "scan")
        return client.resolveScan(scanBody(key.content, scanRegion));
      if (key.kind === "ndc") return client.resolveNdc(ndcBody(key.ndc));
      return client.resolveSearch(searchBody(key.query, key.region));
    } catch {
      return Promise.resolve({
        ok: false,
        error: {
          kind: "build",
          route: "resolve/search",
          messageKey: "Errors.client_defect",
        },
      });
    }
  };
}

export function equivalents(item: Item, r: ResolutionResult): Candidate[] {
  const k = item.sourceKey;
  if (k.kind === "search") {
    const pick = k.pick;
    return r.candidates.filter((c) =>
      pick.kind === "ingredient"
        ? c.kind === "ingredient" && c.ingredient_key.qid === pick.qid
        : c.kind === "product" &&
          c.source.source_id === pick.sourceId &&
          c.product_name === pick.productName,
    );
  }
  return r.candidates.filter(
    (c) =>
      c.kind === item.candidate.kind &&
      c.source.source_id === item.candidate.source.source_id,
  );
}

export async function reresolve(
  items: readonly Item[],
  resolve: Resolver,
): Promise<Item[]> {
  const out: Item[] = [];
  for (const item of items) {
    const r = await resolve(item.sourceKey);
    const eq = r.ok ? equivalents(item, r.data) : [];
    if (!r.ok || eq.length !== 1) {
      out.push({ ...item, needsConfirmation: true });
      continue;
    }
    const c = eq[0]!;
    const choices =
      c.kind === "product"
        ? item.choices.filter((ch) =>
            c.ingredients
              .find((g) => g.position === ch.position)
              ?.key_candidates.includes(ch.ingredient),
          )
        : [];
    out.push({
      ...item,
      candidate: c,
      datasetVersion: r.data.dataset_version,
      choices,
      needsConfirmation: false,
    });
  }
  // Never two dataset versions in one list: a straggler on another version is confirmed again.
  const versions = new Map<string, number>();
  for (const i of out)
    if (!i.needsConfirmation)
      versions.set(i.datasetVersion, (versions.get(i.datasetVersion) ?? 0) + 1);
  const main = [...versions].sort((a, b) => b[1] - a[1])[0]?.[0];
  return out.map((i) =>
    !i.needsConfirmation && i.datasetVersion !== main
      ? { ...i, needsConfirmation: true }
      : i,
  );
}
