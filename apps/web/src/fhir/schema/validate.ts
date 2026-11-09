/**
 * Test-only: validates JSON against the official FHIR R4 (4.0.1) JSON schema, committed here
 * gzipped (README.md; fhir-export DP10, DP11). Offline: nothing is fetched. Never imported by
 * the app.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { gunzipSync } from "node:zlib";

import Ajv, { type ErrorObject, type ValidateFunction } from "ajv";
import draft6 from "ajv/dist/refs/json-schema-draft-06.json";

export const SCHEMA_SHA256 =
  "2230406893b4cf002a4ee1e5e2bbeca22ac5d2d4931b3e9ef7b9594bbc376a01";

let cached: { all: ValidateFunction; statement: ValidateFunction } | null =
  null;

export function schemaText(): Buffer {
  return gunzipSync(
    readFileSync(join(import.meta.dirname, "fhir.schema.json.gz")),
  );
}

function validators() {
  if (cached) return cached;
  // The published file declares draft-06 but names its root id with the draft-04 keyword `id`;
  // Ajv 8 reads `$id` only, so that one key is renamed in memory. Nothing else is changed.
  const { id, ...rest } = JSON.parse(schemaText().toString("utf8")) as {
    id: string;
  } & Record<string, unknown>;
  const ajv = new Ajv({ strict: false, allErrors: true });
  ajv.addMetaSchema(draft6);
  const all = ajv.compile({ $id: id, ...rest });
  cached = {
    all,
    statement: ajv.getSchema(`${id}#/definitions/MedicationStatement`)!,
  };
  return cached;
}

const show = (errors: ErrorObject[] | null | undefined) =>
  (errors ?? [])
    .slice(0, 5)
    .map((e) => `${e.instancePath} ${e.message}`)
    .join("; ");

/** [] when valid; otherwise readable errors (each entry is also checked alone for a clear path). */
export function fhirSchemaErrors(json: unknown): string[] {
  const v = validators();
  if (v.all(json)) return [];
  const out = [`bundle: ${show(v.all.errors)}`];
  const entries = (json as { entry?: { resource?: unknown }[] }).entry ?? [];
  entries.forEach((e, i) => {
    if (!v.statement(e.resource))
      out.push(`entry[${i}]: ${show(v.statement.errors)}`);
  });
  return out;
}
