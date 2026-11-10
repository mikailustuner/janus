/**
 * `POST /recalls/check` (recall-check design §7): request type and strict response decoder,
 * written from the Pydantic models in apps/api/janus/recalls/router.py.
 */
import * as D from "@/api/decode";
import type { Infer } from "@/api/decode";

const DATE = /^\d{4}-\d{2}-\d{2}$/;
const date = D.pattern(DATE);

export interface RecallCheckIn {
  /** A hyphenated product NDC or an 11-digit package key. Never a lot (Req 5.2). */
  ndc: string;
}

export const NOTICES = [
  "us_records_only",
  "absence_is_not_clearance",
  "status_as_published",
  "records_without_ndc_not_searched",
  "lot_text_read_automatically",
  "not_an_alert_service",
  "snapshot_outdated",
] as const;

export const recallMatch = D.obj({
  recall_number: D.pattern(/^[A-Z][A-Z0-9-]{2,19}$/),
  classification: D.nullable(D.str),
  status: D.nullable(D.str),
  terminated: D.bool,
  recall_initiation_date: D.nullable(date),
  report_date: D.nullable(date),
  termination_date: D.nullable(date),
  reason_for_recall: D.nullable(D.str),
  product_description: D.nullable(D.str),
  code_info: D.nullable(D.str),
  code_info_truncated: D.bool,
  recalling_firm: D.nullable(D.str),
  ndc_match: D.lit("package", "product"),
  lot_codes: D.arr(D.pattern(/^[0-9A-Z]{3,20}$/)),
  record_url: D.pattern(/^https:\/\/api\.fda\.gov\/drug\/enforcement\.json\?/),
});

export const recallCheckOut = D.obj({
  region: D.lit("US"),
  source: D.obj({
    source_id: D.lit("openfda_enforcement"),
    run_id: D.str,
    snapshot_date: date,
    search_url: D.pattern(/^https:\/\/www\.accessdata\.fda\.gov\//),
    records: D.int,
    records_with_ndc: D.int,
  }),
  matches: D.arr(recallMatch, 0, 20),
  total_matches: D.int,
  truncated: D.bool,
  notices: D.arr(D.lit(...NOTICES)),
});

export type RecallMatch = Infer<typeof recallMatch>;
export type RecallCheckOut = Infer<typeof recallCheckOut>;
