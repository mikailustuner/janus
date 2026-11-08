# Implementation Plan: Doctor Note and Outcome Loop, Phase 2 (server side)

> Scope: `apps/api` (`janus/notes/`, migration `0011`, small changes in `cascades/`, `integrity/`, `main.py`,
> `settings.py`) and the glossary files with their review sheets. Requirement numbers refer to requirements.md;
> properties P1–P34 and decisions DP1–DP31 to design.md. Owner decisions of 2026-11-08 are applied (DP1, DP2 as a token
> carrying the finding codes, DP11, DP13, DP16, DP18). Task 15 is a hard stop for the owner's glossary review.
> No health data in logs, fixtures or test output; tests use sentinel values and invented names (never TİTCK strings).
> Checkpoints run every lint, format, type-check and test step (`uv run ruff check .`, `uv run ruff format --check .`,
> pyright strict, pytest with `HYPOTHESIS_PROFILE=ci` including database tests against PostgreSQL 16 after
> `alembic upgrade head` on `janus_test`, vitest and web lint), then commit, push and confirm GitHub CI passes. The full API
> suite takes 15 minutes or more: run it with `nohup`, one suite at a time.

- [x] 1. Settings, token payload and QR size (`settings.py`, `notes/token.py`, `notes/qr.py`, design §3, §6)
  - `JANUS_NOTE_KEYS`, `JANUS_NOTE_SIGNING_KEY_ID`, `JANUS_OUTCOME_CONSENT_VERSIONS`, `JANUS_PUBLIC_BASE_URL`; `Keyring`;
    `Payload`, `encode`/`decode`, `sign`, `verify`, `expiry_for`, `TokenError` codes; QR capacity table, `qr_version`,
    `outcome_url`, `fit_findings`; `.env.example` with empty values and a comment on rotation.
  - Done 2026-11-08. Final token sizes (design §6.6): realistic worst case 18 findings, 658 characters, QR version 21;
    every field at its maximum, 11 findings in 989 of 997 bytes.
  - [x] 1.1 Property test P1: round trip and field bounds. _Requirements: 2.1_
  - [x] 1.2 Property test P2: every mutation gives `invalid_token`. _Requirements: 2.1, 2.2, 2.4_
  - [x] 1.3 Property test P3: key rotation as a state machine. _Requirements: 2.4_
  - [x] 1.4 Property test P4: Monday expiry, 28–35 days, boundary day. _Requirements: 2.6_
  - [x] 1.5 Property test P5: non-canonical and near-miss strings rejected. _Requirements: 2.2_
  - [x] 1.6 Property test P6: one `compare_digest` call per verification; AST scan of `token.py`. _Requirements: 2.5_
  - [x] 1.7 Property test P9: settings defects named without key material. _Requirements: 2.3_
  - [x] 1.8 Property test P34: payload codec, size formula, strict parsing. _Requirements: 2.1, 2.2_
  - [x] 1.9 Property test P33: QR fit, at least 11 findings, capacity table; the measured realistic worst case recomputed
    with the final encoder and recorded in design §6.6. _Requirements: 2.1_
  - [x] 1.10 Property test P32 (pure part): `outcome_url` puts the token only in the fragment. _Requirements: 2.1, 13.2_

- [x] 2. Phrase lists and the disclaimer (`notes/phrases.py`, DP18)
  - Python mirror of `forbidden-phrases.ts`, the proposed reassurance lists (design §5.4), `find_phrases()` with the
    TS matching semantics. Cascades and integrity import `DISCLAIMER` from `memory/messages.py` (em dash); record the
    change as a one-line DP note in the cascade-engine and evidence-integrity designs.
  - [x] 2.1 Property test P23 (phrase and disclaimer parity with the web files). _Requirements: 14.1, 14.2_
  - [x] 2.2 Property test P31 (baseline): cascades and integrity bodies differ only in the dash. _Requirements: 14.3_

- [x] 3. Glossary model and loader (`notes/glossary.py`, design §5.1, §5.6, §5.7)
  - Parsers and validator for the three files, statuses, shared-row parity, `en_sha256` check against the rule base,
    `available_languages()`, `name()` fallback, `version()`. Empty committed files with headers and `README.md`
    (status line, sources: Wikidata CC0, PIPC CC BY 4.0). Loaded once at startup; a defect stops startup.
  - [x] 3.1 Property test P20: valid synthetic glossaries load; each single defect is named. _Requirements: 7.5_
  - [x] 3.2 Property test P19 (pure part): only accepted rows used; fallback exact; availability rule. _Requirements: 1.5, 7.3, 7.4_

- [x] 4. Formatting (`notes/render.py`, DP26)
  - The table of design §5.3; `fill()` with typed params returning text and `numbers`.
  - Done 2026-11-08. Counterexamples found by the tests and fixed: a ratio of 0.005 printed as `0.00` (half-even
    rounding to zero; now `<0.01`); 99.95 printed as `100,0` (decimals now chosen on the rounded value, `100`).
  - [x] 4.1 Property test P13 (pure part): numerals equal formatted params; boundary values; hand-checked examples per
    language. _Requirements: 5.2, 5.3_

- [x] 5. Document builder (`notes/model.py`, `notes/build.py`, design §4.3, §4.4)
  - Pure `build_document` from an engine result, engine items, stat results, integrity line, glossary, vocabulary,
    language, region and optional QR coverage; sections in the order of §4.4.
  - Done 2026-11-08. Found while testing P12: numerals of months (`11.2026` against `11/2026`) split differently per
    language, so `numbers` now holds the rendered parameters and the auditor removes them from the text before looking
    for digits (design §5.3, §5.5).
  - [x] 5.1 Property test P10: every claim carries citable ids; retraction only removes. _Requirements: 1.3, 5.1, 10.1_
  - [x] 5.2 Property test P11: disclaimer, no forbidden or reassurance phrase per language. _Requirements: 1.4, 1.10, 14.1, 14.2_
  - [x] 5.3 Property test P12: language invariance. _Requirements: 1.5, 1.6, 4.5_
  - [x] 5.4 Property test P15: medicine rows and the abrupt-stop line once per warned item. _Requirements: 1.1, 8.1, 8.3_
  - [x] 5.5 Property test P16: each finding in exactly one findings section. _Requirements: 8.2_
  - [x] 5.6 Property test P18: safety section first, region numbers. _Requirements: 9.5_
  - [x] 5.7 Property test P13 (document part). _Requirements: 5.2_

- [x] 6. Auditor (`notes/audit.py`, design §5.5)
  - [x] 6.1 Property test P14: exact removals in all languages, idempotent, fixed-text defect raises. _Requirements: 5.3–5.5_

- [x] 7. Note document route (`cascades/service.derive`, `notes/service.py`, `schemas.py`, `router.py`)
  - Split `derive()` out of `evaluate_request` (DP25); `POST /notes/document`; pins and 409; statistics through
    `memory.service.pair`; `statistics_unavailable`; `note_language_unavailable`; route classification.
  - Done 2026-11-08. Bench (dev database, real counts file): 16 medicines, 9 findings, 12 statistic rows, two languages:
    p50 306 ms, p95 345 ms. The dev database had no `dataset:faers` record until the integrity loader was rerun on the
    current artifacts (78 records), so statistics were missing at first.
  - [x] 7.1 Property test P22: findings equal `POST /cascades/evaluate`; pins; byte-identical repeats. _Requirements: 4.3, 4.5_
  - [x] 7.2 Property test P17: stat rows equal `POST /memory/pair`; a < 3 without numbers; MedDRA notice; no counts file. _Requirements: 9.1–9.4, 9.7, 4.6_
  - [x] 7.3 Property test P21 (document route): stateless, silent, closed schema. _Requirements: 1.2, 4.1, 4.7, 13_
  - [x] 7.4 Property test P24: statement budget independent of the number of languages. _Requirements: 15.2_
  - [x] 7.5 Property test P31 again after the split: the cascades route is unchanged. _Requirements: 14.3_
  - [x] 7.6 Local benchmark `python -m janus.notes.bench` (15 items, 10 findings, two languages, real data); record p50/p95
    in design §1. _Requirements: 15.1_

- [x] 8. Checkpoint 1: token, glossary mechanism, builder, auditor, document route
  - Run together with checkpoint 2 (2026-11-08): the first full run was stopped because tasks 9-12 had started
    meanwhile, so one full run covers both checkpoints.
  - All steps green; real glossary files still empty (no language available); the `log-guard` and
    `medical-language-guard` hooks report nothing. Commit, push, CI passes.

- [x] 9. Outcome store (migration `0011`, `notes/repository.py`, `notes/outcomes.py`)
  - Tables `used_note_tokens` and `outcomes` of design §7.1 with CHECKs; `write_tx` allowlist gains
    `notes/repository.py`; `LogEvent.note_purge`.
  - [x] 9.1 Migration upgrade → downgrade → upgrade; column lists equal the allowed fields. _Requirements: 3.2, 12.2_

- [x] 10. Token issue (`POST /notes/token`, read-only) and withdrawal (`POST /notes/withdraw`)
  - Consent list, `no_findings`, one derivation for the token and the returned note, `outcome_loop` section, `qr_url`.
  - [x] 10.1 Property test P25: token payload equals the note's covered findings; allowed fields only; nothing written. _Requirements: 2.1, 12.1, 12.2_
  - [x] 10.2 Property test P27: withdrawal deletes exactly that token's outcomes and blocks it. _Requirements: 12.4_

- [x] 11. Outcome form and submission (`POST /outcomes/form`, `POST /outcomes`)
  - [x] 11.1 Property test P30: form lists the token's findings in its language; read-only; error codes. _Requirements: 3.1, 2.2_
  - [x] 11.2 Property test P26: outcome rows and answer validation. _Requirements: 3.1, 3.2, 3.4_
  - [x] 11.3 Property test P7: single use and atomic submit (state machine with fault hook). _Requirements: 2.7, 3.2, 12.2_
  - [x] 11.4 Property test P8: concurrent submissions. _Requirements: 2.7_
  - [x] 11.5 Property test P21 and P32 (loop routes): silent logs, closed schemas, no path or query token, `demo` rejected. _Requirements: 2.1, 3.6, 13_

- [x] 12. Outcomes layer and purge (`notes/source.py`, `main.py`, `notes/purge.py`)
  - Register `OutcomesSource`; `/memory/snapshot` layer status; update `collective-memory` (DP10 closed, Req 4.7) and
    `experience` open items (contracts of design §9, the URL fragment, the QR size, the privacy-page limit).
  - [x] 12.1 Property test P29: outcomes layer equals brute force and follows the contributions release rules. _Requirements: 11_
  - [x] 12.2 Property test P28: purge of expired used-token rows and old outcomes. _Requirements: 3.5, 12.2_

- [x] 13. Checkpoint 2: outcome loop
  - Done 2026-11-08: 785 API tests passed, 10 skipped (local real-data tests), `HYPOTHESIS_PROFILE=ci`, PostgreSQL 16;
    ruff, ruff format, pyright strict clean; web lint, typecheck and 78 vitest tests green (the source scan now skips
    the Python mirror of the phrase list). Images `api` and `migrate` rebuilt; the dev database is at `0011`.
    Changed expectations in `collective-memory` tests: the outcomes layer now answers (`ok`, all cells hidden) instead
    of `not_available`; the snapshot reports `outcomes: ok | unavailable`.
  - All steps green, including database properties against PostgreSQL 16; rebuild the `api` and `migrate` images after
    migration `0011`. Commit, push, CI passes.

- [x] 14. Glossary draft (`notes/glossary_draft.py`, design §11)
  - Done 2026-11-08 (dev dataset `e9e55772…`, rule base `8d4881fc…`): `ingredients.csv` 1,129 rows, all `proposed`, names
    en 1,129, tr 447, de 770, fr 840, es 710 (Wikidata labels of the name index; none left out by a check);
    `cascades.csv` 65 rows (112 distinct PIPC texts translated into four languages); `sentences.csv` 112 rows (81 drafted
    in five languages, 30 shared rows copied from the message files, the long MedDRA notice in English). All files load;
    no language is available until the owner accepts the rows. TİTCK check (local list, counts only): 212 of the 447
    Turkish cells, and 216 of the 1,129 English cells, are equal (case-folded) to an ingredient string of the TİTCK list;
    they come from Wikidata, see `glossary-review.md`. Cascade names may be up to 200 characters (French and German PIPC
    texts with examples exceed 120).
  - Run the draft command on the dev database: `ingredients.csv` for the in-scope keys, all `proposed`; draft
    `cascades.csv` (65 rows, four languages) and `sentences.csv` (all templates of design §5.2, five languages; shared rows
    copied); loader checks pass; counts per language recorded; no TİTCK string (checked against the local list, counts
    only). _Requirements: 7.1, 7.2, 7.5_

- [x] 15. Glossary review and **review stop (owner)**
  - 2026-11-08: both reviews written (`glossary-pharmacologist-review.md`, `glossary-localization-review.md`); summary and
    twelve decisions in `glossary-review.md`; the owner answered the same day (task 16).
  - Run `agent://pharmacologist` and the localization reviewer (through `agent://wf-coder`, read-only role, report path)
    with self-contained prompts; write `glossary-pharmacologist-review.md`, `glossary-localization-review.md` and the
    summary `glossary-review.md` (counts, flagged rows, the four disclaimer translations, the formatting table, the
    reassurance lists, decisions needed). Commit, push, CI green, then **stop and wait for the owner**. No row becomes
    `accepted` before the owner's answer. _Requirements: 7.3, 7.7_

- [x] 16. Apply the owner's glossary decisions and finish
  - 2026-11-08: done in two parts. First the wrong ATC codes in `drug-resolution` (Req 15, DP45, `atc-code-review.md`,
    its own commit), then the glossary edits (all rows `accepted` except the three ingredient rows whose keys left the
    index), template and builder changes (DP32–DP39, P35–P38), the committed-glossary tests, the key rotation runbook
    (`docs/note-token-keys.md`), the pre-launch items, and example notes in `example-notes.md`.
  - Set statuses and edits in one commit; record decisions in `glossary-review.md`, requirements.md and design.md; a test
    loads the committed glossary (five languages available, 65 rows, in-scope coverage); example documents for a
    synthetic patient in five languages (invented product names) reviewed for wording; `docs/pre-launch-checklist.md`
    items of design §15; key rotation runbook in `docs/`; dated entry in `docs/kiro-usage.md`. _Requirements: 7.3, 7.7, 14_

- [ ] 17. Final checkpoint
  - Every step green (API, web, CI); report what was built, counterexamples the property tests found and how they were
    fixed, and the open items.
