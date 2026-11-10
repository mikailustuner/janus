# Implementation Plan: Medication Passport

> Scope: `apps/api/janus/passport/`, migration `0012_passport_presence_index`, two additive fields in
> `janus/resolution/model.py` and `service.py`, `data/dose_form_groups.csv`, `apps/web/src/passport/`, the `Passport`
> message namespace and the Cologne demo list. Requirement numbers refer to requirements.md; properties P1–P21 and
> decisions DP1–DP21 to design.md. Tasks 4 and 11 are hard stops for review; DP21 and OD5 need the owner's answer before
> tasks 9 and 10 use them (until then, build without manual entry and without fast-check-only tests).
> No health data in logs, fixtures or test output; tests use sentinel keys and invented names (never TİTCK strings).
> **Checkpoints** run every step: `uv run ruff check .`, `uv run ruff format --check .`, pyright strict, pytest with
> `HYPOTHESIS_PROFILE=ci` including the database tests against PostgreSQL 16 after `alembic upgrade head` on
> `janus_test`, vitest (`npm test`), web lint and typecheck (`npm run lint`, `npm run typecheck`); then commit, push and
> confirm GitHub CI is green. The full API suite takes 15 minutes or more: run it with `nohup`, one suite at a time.

- [x] 1. Index migration (`migrations/versions/0012_passport_presence_index.py`, design §4.1)
  - *Done 2026-11-08 (Claude Code): partial index; loader write of the 317,055 ingredient rows +1.0 s, recorded in §13.*
  - Partial index `res_product_ingredient_key`; downgrade drops it. Measure the loader time on the dev dataset before
    and after and record it in design §13.
  - [x] 1.1 *(`tests/test_passport_index.py`: reversible; index scan on a 40,000-product synthetic dataset.)* Migration upgrade → downgrade → upgrade on `janus_test`; the index exists only after upgrade; the plan of
    the §4.2 statement uses it (EXPLAIN check on a synthetic dataset). _Requirements: 13.1_

- [x] 2. Strength codes (`passport/strength.py`, design §5.1)
  - *Done 2026-11-08: coded share openFDA 59.7 %, BDPM 48.8 % (countable forms), CIMA and TİTCK 0 (review sheet A.3).*
  - Per-source grammars, exact `Decimal` conversion, canonical amount, cache; a report command printing the parsed share
    per source on the dev dataset (counts only).
  - [x] 2.1 *(`tests/test_passport_strength_properties.py`, Decimal reference.)* Property test P5: equal quantities equal codes; `None` cases; never raises; pattern of §3.1. _Requirements: 6.3, 6.4_

- [x] 3. Dose-form table (`passport/forms.py`, `passport/forms_draft.py`, `data/dose_form_groups.csv`, design §5.2)
  - *Done 2026-11-08: 927 rows, all `proposed`; 13 groups (owner decision 6 + Req 6.5); route column added (design §5.2,
    owner to accept); coverage openFDA 84.1 %, BDPM 97.2 %.*
  - Loader, closed group set, `COUNTABLE_GROUPS`, version hash; the draft command writes every distinct
    `(source_id, dosage_form)` of the current dataset (openFDA 142, BDPM 358) with product counts and a proposed group;
    commit the draft with every row marked `proposed` in `note`. `data/README.md` gains the licence and source line.
  - [x] 3.1 *(`tests/test_passport_forms_properties.py`, incl. the Req 6.5 check on the committed table.)* Property test P6: committed table loads; each injected defect named; `group()` total. _Requirements: 6.5_

- [x] 4. Dose-form and strength review **(review stop)**
  - *2026-11-08: pharmacologist pass (accept with changes R1–R3); owner answers in Part C, applied in Part D: 14 groups,
    DP22/DP23, `route_from_form`, 107 wildcard rows made route-specific, table packaged, 931 rows `accepted`.*
  - Run `agent://pharmacologist` (self-contained prompt: the draft table, the grammar table of §5.1, OD4) and write
    `dose-form-review.md` (flagged rows, granularity questions, EDQM terms question). Commit, push, CI green, then
    **stop and wait for the owner**. Apply the answers in one commit (rows accepted, groups final, OD4 closed in design).
    _Requirements: 6.4, 6.5_

- [x] 5. Resolution fields (`resolution/model.py`, `resolution/service.py`)
  - *Done 2026-11-08: fields filled only from an accepted table (`app.state.dose_forms`); contract test lists the two
    additions. The `drug-resolution` open-items note is task 13.*
  - `ResolvedIngredient.strength_code: StrengthCodeOut | None = None`, `ProductCandidate.dose_form_group: str | None =
    None`, computed with the Passport functions on stored values; forms table passed through `app.state`. No other
    change. Note the change in `drug-resolution` open items (task 13).
  - [x] 5.1 *(`test_passport_resolution_fields_properties.py`.)* Property test P17: fields equal the pure functions; all other fields unchanged (snapshot). _Requirements: 6.6_

- [x] 6. Presence evaluation and repository (`passport/presence.py`, `passport/repository.py`, design §4.2, §5.3)
  - Signature building (strength codes, form groups, homeopathic decision with `is_homeopathic_name` for EU), the
    statement of §4.2 with `SET LOCAL statement_timeout`, `known_keys`, pure `evaluate`.
  - [x] 6.1 *(`test_passport_presence_properties.py`, plus a worked example.)* Property test P7: presence equals a brute-force model on synthetic datasets (DB). _Requirements: 2.4, 2.6, 2.7, 6.2_
  - [x] 6.2 Property test P3 (server part): no `matched` with an unknown side; `differs` only when all comparable. _Requirements: 2.2, 6.1, 6.2_
  - [x] 6.3 Property test P8: homeopathic parity with `/resolve/products`; SQL and Python patterns agree. _Requirements: 2.6, 1.5_
  - [x] 6.4 Property test P9: comparison counts and result function. _Requirements: 6.2_
  - [x] 6.5 Property test P10: order, repetition and split invariance. _Requirements: 4.4_

- [x] 7. Route (`passport/schemas.py`, `service.py`, `router.py`, `main.py`, `bench.py`)
  - *Done 2026-11-08: p95 267–332 ms (15 common items), 1,703–2,251 ms (50-key worst case, machine under load);
    recorded in design §13 with the variants tried.*
  - `POST /passport/presence` on `medical_router()`; strict body parsing as `resolution/router.py`; 422 / 503 of §3.3;
    source blocks with staleness from `repository.current`; register in `create_app`; benchmark (15 common items and the
    50-key worst case on the dev dataset) and record p50/p95 in design §13.
  - [x] 7.1 *(`test_passport_api_properties.py`.)* Property test P11: stateless, silent logs, closed schema, no echo. _Requirements: 4.1–4.3, 5.2, 9.1, 9.2_
  - [x] 7.2 Property test P12: validation bounds and boundary values. _Requirements: 5.1, 5.2_
  - [x] 7.3 Property test P13: every answer names its source; missing sources; Germany; staleness. _Requirements: 2.1, 5.4, 7.1, 7.4, 7.5_
  - [x] 7.4 Property test P14: 503 cases with nothing partial. _Requirements: 5.3_
  - [x] 7.5 Property test P15: constant statement budget for 1–50 items. _Requirements: 13.2_
  - [x] 7.6 *(15-item target met; worst case at the 2 s line under load, DP12 loader table left open for the owner.)*
    Benchmark meets Req 13.1 (p95 ≤ 500 ms for 15 items, ≤ 2 s worst case), else apply the DP12 fallback and
    measure again. _Requirements: 13.1_

- [x] 8. Checkpoint 1: server side
  - *2026-11-08: ruff, ruff format, pyright strict clean; pytest ci profile 863 passed, 8 skipped (database tests after
    `alembic upgrade head` on `janus_test`); vitest 78, web lint and typecheck green; API image (also the `migrate`
    image) rebuilt and the packaged table loads in it; log-guard and medical-language-guard clean. Committed on the
    worktree branch; not pushed (the owner's manager merges), so no CI run yet.*
  - All steps of the header green, including the database properties after `alembic upgrade head` on `janus_test`;
    rebuild the `api` and `migrate` images; the `log-guard` and `medical-language-guard` hooks report nothing. Commit,
    push, CI green.

- [x] 9. Client list logic (`apps/web/src/passport/`: `model.ts`, `identity.ts`, `merge.ts`, `duplicates.ts`,
  `request.ts`, `memory-keys.ts`, `entry.ts` if DP21 is accepted; `fast-check` dev dependency if OD5 is accepted)
  - *Done 2026-11-08 (Claude Code): DP21 and OD5 accepted by the owner; `fromListItem` reads the experience store;
    partly recognised items are not sent (DP24); ambiguous "1,000" refused in typed entry (DP25).*
  - Types mirror `schemas.py` (a Python test exports the literal sets to a JSON fixture the web tests read).
    *(`fixtures/schema-literals.json`; tests in `src/passport/list.test.ts`.)*
  - [x] 9.1 Property test P1: merge commutative, associative, idempotent but for counts, earliest month. _Requirements: 1.4_
  - [x] 9.2 Property test P2: duplicate groups iff shared key among checked items; nothing removed. _Requirements: 1.2, 1.3, 1.5, 1.6_
  - [x] 9.3 Property test P18: request bodies hold only keys and codes; limits; fan-back complete. _Requirements: 9.1, 4.3_
  - [x] 9.4 Property test P20: memory keys sorted, distinct, checked only; > 20 needs a selection. _Requirements: 11.1, 11.2_
  - [x] 9.5 *(`entry-cases.json`, 500 cases from `tests/test_passport_web_fixtures.py`.)* Property test P21: entry parity with the Python fixture (only with DP21). _Requirements: 6.7_

- [x] 10. Passport messages and word lists (`apps/web/messages/*.json` namespace `Passport`, `passport/words.ts`)
  - *Done 2026-11-08: 124 keys per locale (EN reference, TR/DE/FR/ES drafts); owner wording "as entered from the box";
    tests in `src/passport/messages.test.ts` (also the message part of P3: no "same" in could-not-compare texts).*
  - Draft all keys of design §7.1 in five languages (English reference texts of §7.2); word lists of §7.3; source names
    never translated; attribution sentences of Req 7.2.
  - [x] 10.1 Property test P4: no substitution, forbidden or reassurance word; removal list on duplicate texts; API body
    walk. _Requirements: 1.3, 8.1, 8.2_
  - [x] 10.2 Property test P16: every API code and origin has a key in five locales with the same parameters. _Requirements: 8.1, 8.3, 10.2_

- [x] 11. Wording review **(review stop)**
  - *2026-11-08: localization and safety passes (Claude Code, `.kiro/agents` roles) in `passport-wording-review.md`;
    L1, S1, S2 fixed; owner answered the ten decisions the same day; pharmacologist pass added (F1–F3); all applied in one commit.*
  - Run `agent://pharmacologist` and the localization reviewer (through `agent://wf-coder`, read-only role, report path)
    on the `Passport` texts and the word lists; write `passport-wording-review.md` (flagged strings per language,
    decisions needed). Commit, push, CI green, then **stop and wait for the owner**. Apply the answers in one commit.
    _Requirements: 8.4_

- [x] 12. Screens and demo (`passport/screens/`, `apps/web/src/demo/passport-cologne*.{ts,json}`, design §8, §9)
  - *Done 2026-11-08: `/passport` and `/passport/item#<id>`, navigation entry, link from each medicine, duplicate
    notice slot; Cologne list of 7 boxes; recorded answers for all three demo patients (DP26); typed entry (DP21);
    Playwright `e2e/passport.spec.ts` (axe, scroll, targets at 375/1280, both themes) and both routes in `routes.spec`.*
  - Content and states of the list and detail views with the `experience` components (coordinate mounting and routes
    with the `experience` author); the Cologne list; the recorded answer generated from the API by a script and
    committed; visual check at 375 px and 1280 px in both themes and large text; keyboard pass.
  - [x] 12.1 Property test P3 (client part): rendered rows never say "same" for `could_not_compare` or a missing side. _Requirements: 2.2, 6.1_
  - [x] 12.2 Property test P19: demo items never in donation/outcome bodies; recorded answer schema-valid; demo label on
    both screens. _Requirements: 9.3, 12_
  - [x] 12.3 State tests: loading (`aria-busy`, live region), empty, error with retry and no "not found", partial, long
    content (50 items, long names), not-checkable item; statuses carry text and icon, never `--risk`. _Requirements: 10.3–10.5_

- [x] 13. Cross-spec notes
  - *Done 2026-11-08: experience §20, drug-resolution §19, doctor-loop §15; owner's log in the Phase 3 draft.*
  - `experience` open items: screens to mount, list fields (`origin`, `boxes`, `demo`, strength/form origin), Cologne
    list, Memory selection prompt. `drug-resolution` open items: the two additive fields and migration `0012`.
    `doctor-loop` open items: the origin label in `product_name_slot`. Dated entry for the owner's log (not
    `docs/kiro-usage.md` unless the owner asks).

- [x] 14. Final checkpoint
  - *Done 2026-11-08: ruff, format, pyright clean; web lint, typecheck, vitest 388 (FC_PROFILE=ci); Playwright passport +
    routes (en, de) 26 passed; CI green on the final commit. Counterexamples: "40,680" read as 40.68 (DP25), partial
    items read as present (DP24). Open: OD1 (drug-resolution follow-up), origin label in the note slot.*
  - Every step of the header green (API, web, CI); report what was built, the benchmark numbers, counterexamples the
    property tests found and how they were fixed, and the remaining open decisions (OD1–OD3).

---

# Extension 2026-11-10: products with the same active ingredient in another country

> Requirements 14–17, design §15, properties P22–P30, decisions DP27–DP33. Same checkpoints as above. Tests use
> sentinel keys and invented names; no TİTCK string in any file. Automated review passes only; expert review has
> not yet been done.

- [x] 15. Listing logic (`passport/listing.py`, design §15.4)
  - `LISTABLE_SOURCES`, `NOT_FINISHED_TYPES`, `marketed`, `compare_strength`, `compare_form`, `listing` (merge of
    identical entries, total order). `presence.comparable_form` made public for reuse.
  - [x] 15.1 Property tests P22–P24 (pure), P26 and the P23 examples. _Requirements: 14.1–14.8_
- [x] 16. Statement, schemas, service and route (`repository.py`, `schemas.py`, `service.py`, `router.py`)
  - `LISTING_SQL` (one source, grouped, parameterised, index `0012`), `ProductsIn` / `ProductsOut`,
    `service.products`, `POST /passport/products` sharing the body handling of the presence route.
  - [x] 16.1 Database and HTTP properties P22 (model, all pages), P25, P27. _Requirements: 15.1–15.8_
- [x] 17. Web contract and client (`apps/web/src/passport/products.ts`, `api/errors.ts`, `schema-literals.json`)
  - Decoder, request builder, loader with paging and the recorded lookup for demo mode.
  - [x] 17.1 fast-check P29 and the literal parity with the server models. _Requirements: 14.9, 15.4, 17.4_
- [x] 18. Messages (`apps/web/messages/*.json`, keys under `Passport.products` only)
  - [x] 18.1 P28: word lists and key parity in five locales. _Requirements: 16.1–16.5_
- [x] 19. Screen (`passport/screens/ProductsView.tsx`, route `passport/products`, entry on the item detail)
  - States of Req 17.2; `different` flag; attribution, data date, stale notice; demo recorded answer for Cologne
    (`scripts/record-passport-products.mjs`).
  - [x] 19.1 Render properties P30 and the state tests; Playwright with axe, 375 px and desktop, both themes, five
    locales. _Requirements: 14.5, 17.1–17.4_
- [x] 20. Automated review passes and checkpoint
  - Safety and localization passes with the `.kiro/agents` reviewer prompts over the new strings and screen;
    findings and fixes in `products-review.md`. CI-equivalent checks green locally.
    Expert review has not yet been done.
