# Wording review: safety audit (experience, task 22)

**Date:** 2026-11-08
**Reviewer:** safety-auditor (`.kiro/agents/safety-auditor.md`), run as a separate read-only agent pass; no files edited by the reviewer.

## Scope and method

- **Scope (`apps/web`):** all namespaces of `messages/{en,tr,de,fr,es}.json`; `src/doctor/messages.json`; `src/vocabulary/*.json`; `src/demo/fixtures/*.json`; the screens in `src/components/**` and `src/doctor/**`; `src/flow/*`, `src/api/builders.ts`, `client.ts`, `src/scan/gs1.ts`, `ocr-extract.ts`, `ocr.ts`, `src/note/*`, `src/store/*`; `public/sw.js`, `next.config.ts`, `src/proxy.ts`, the layouts under `src/app/`.
- **Rules:** `medical-safety.md` rules 1–10, `privacy.md`, `product.md`, experience `requirements.md` (Req 7, 14–24).
- **Method:** the five catalogues side by side, key by key, against EN; a whole-word, case-insensitive scan of every user-facing string with the lists of `forbidden-phrases.ts` and `reassurance.ts` (0 hits; theme words only in `*.twoFaces` keys); every screen and flow module read, following each request body, URL, storage write and external load. Snapshot: files as of about 17:56 CET, including two changes made during the audit (re-checked).

## Summary

| Severity | Count | Fixed before the stop |
|---|---|---|
| Blocking | 2 | 2 (B1, B2) |
| Advisory | 13 | 3 (A5, A8, A11) |

## Findings

| # | path:line or message key | Rule | Language(s) | Issue | Suggested fix | Severity | Status |
|---|---|---|---|---|---|---|---|
| B1 | `src/components/memory/MemoryPage.tsx` (combination event rows, event picker, shared panels, page start) | rule 10; Req 7.1, 7.5, 7.8 | all | The Collective Memory screen shows events but never their safety line or the emergency notice (combination rows ignore `e.safety_line`; the picker shows e.g. "Stomach ulcer or bleeding…" → `urgent_care_gi` in the Cologne demo). Every other screen with events does this. | Emergency notice before the title when any shown event has a safety line; `SafetyLine` next to the chosen event and each combination row that has one. | Blocking | **Fixed** 2026-11-08 |
| B2 | `src/components/ReadAloud.tsx`; `Settings.readAloudHint` | privacy.md; claim accuracy | all | The voice was the first with a matching `lang`, not checked for `localService`; Chrome's network voices would send the finding text (box names, ingredients, event) to a speech service, making "Nothing is sent to a server" false. | Only voices with `localService === true`; otherwise hide the control. | Blocking | **Fixed** 2026-11-08 |
| A1 | `src/components/memory/PairPanel.tsx` | rule 6; Req 16.3 | all | Count, ratio and CI bar always visible; limits, screening sentence and weak-pattern label only in a collapsed section. | Show `spontaneous_reporting`, `not_incidence` and `weak` / `weak_pattern` outside the fold (statistician to confirm). | Advisory | Owner decision |
| A2 | `Findings.status.probable` / `.possible`, chip on the finding card | rule 1 | all | Bare "Probable" next to "Ghost: a prescribing-cascade pattern" reads as a verdict. | "Timing fits the pattern (probable)" / "Order not clear (possible)" (same as pharmacologist B1). | Advisory | Owner decision |
| A3 | `FindingCard.tsx` (`Findings.pattern`) | rules 1, 5 | all | "described in the literature" without naming the source on the card. | Add "PIPC list, row {row}" (and the supporting list). | Advisory | Owner decision |
| A4 | `NotePage.tsx` title vs preview | rule 10; Req 7.8 | all | The note preview can hold urgent-care lines (Cologne `safety:urgent_care_gi`); the screen-level emergency notice is not first. | Emergency notice before the title when the note has a non-empty `safety` section. | Advisory | Open (small change, task 23) |
| A5 | `src/note/layout.ts`; `src/note/pdf.tsx` | rule 9 | all | The PDF footer disclaimer was found by block id only; a renamed id would print pages without it, silently. | Contract error when no disclaimer block is found. | Advisory | **Fixed** 2026-11-08 |
| A6 | `NotePage.tsx` (`window.print()`); `globals.css` print rules | rule 9; Req 17.7, 17.10 | all | Browser print shows the disclaimer and demo label once and no page numbers; only the PDF repeats them. | Repeating print footer, or Print opens the PDF. | Advisory | Owner decision |
| A7 | `src/app/not-found.tsx` | rule 9 | EN | The global 404 page (unsupported locale) has no disclaimer (no medical content). | Add the EN disclaimer line. | Advisory | Open (task 23) |
| A8 | `src/scan/gs1.ts` `classifyTyped`; `Privacy.sent.body` | privacy.md | all | A typed or pasted element string `(01)…(21)SERIAL(10)LOT`, or a printed "GTIN … SN … LOT" line, fell through to name search with serial and lot. | Run such input through the outbound filter; property test. | Advisory | **Fixed** 2026-11-08 (`classifyTyped`, test "typed element strings") |
| A9 | `Note.intro`, `OutcomeConsent.2026-11-v1.stored` | privacy-page honesty | all | "The (medicine) list stays on this device", while making the note sends ids and start months (not stored). | "The list is not stored by Janus; the names on the boxes never leave this device"; bump the consent version (see pharmacologist B3). | Advisory | Owner decision |
| A10 | `Settings.readAloud`, `Demo.intro` | rule 1 | DE | "Befunde" has a diagnostic sense. | "Ergebnisse". | Advisory | Owner decision (wording batch) |
| A11 | `Emergency.text` | rule 10 ("first"); parity | TR | The interim TR rewording said "hemen" (immediately) instead of "first". | Restore the order word. | Advisory | **Fixed**: "…acil yardım için önce {emergency} arayın." (native check pending) |
| A12 | `Memory.codes.urgent_care_gi` | parity with Req 7.1 ("faintness") | DE, FR, ES | "schwindelig" / "vertiges" / "mareado" mean dizzy, not faint; same in the API note phrases. | "einer Ohnmacht nahe" / "sensation d'évanouissement" / "sensación de desmayo"; align the API phrases. | Advisory | Owner decision (`Memory` and glossary are reviewed texts) |
| A13 | `Memory.codes.memory_unavailable` (TR), `Memory.codes.*` (ES), `Memory.codes.tr_reports_small_self_selected` (DE/FR/ES), `Withdraw.none` (EN) | parity | TR, ES, DE/FR/ES, EN | Terms differ within one language ("Kolektif Hafıza"/"Bellek"; "informes"/"notificaciones"; "Türkiye"/"Türkei"; "outcome-loop token"/"note token"). | One term per language. | Advisory | Owner decision |

## Checked, no finding

**Medical safety:** rule 2 (no forbidden phrase in any language across catalogues, vocabulary, doctor messages and fixtures); rule 3 (`Findings.noPattern`, `absence_is_not_reassurance`; no reassurance words; nothing shown for `rule_base_unavailable`); rule 1 (pattern and discuss sentences; no start/stop/change advice; the doctor form asks what was done); rule 4 (abrupt-stop sentence once per warned item on results, list, detail, note); rule 6 (ranges with every ratio, CI bar with "1 = no difference" and "over 1,000", reports never people, layers never summed, "Hidden under 20, noise added"); rule 10 (emergency notice first on home, donation, results with safety lines and finding detail; numbers outside sentences, valid for every region); rule 9 (disclaimer in every shell footer, doctor page, note header and every PDF page); rule 7 (research rule-7 sentence, Phase 4 empty states); Glass without theme words; retracted stamp only on excluded sources.

**Privacy:** GS1 filter (only (01)/(17)/(712) or bare GTIN digits; demo codes caught first); OCR on the device, only chosen words or an NDC chip sent; builders emit only route fields (no box name, ATC code or image); donation fields exactly the allowed set, explicit tick, never in demo, server-set week, token shown once; nothing medical in paths or queries (fragments only); QR token only in `/o#…`, JSON bodies and local storage, no referrer, `/o` outside the locale middleware; no `console.*`; CSP `connect-src 'self'`, fonts, wasm and tessdata self-hosted; headers (no-referrer, camera self only, nosniff); service worker never handles `/api/`, "delete everything" clears `janus*` caches and storage; privacy page makes no certification or compliance claim, no formal-DP claim, states residual limits, does not guess the region in demo.

## Could not check

- Native-speaker fluency and register in TR, DE, FR, ES (A11–A13 especially).
- Real devices and browsers: which voices are local (B2), camera behaviour, PDF font embedding and pages, print layout.
- Live API: server-side wording of note blocks and doctor-form texts beyond the fixtures; that `qr_url` always has the `/o#` form; server-side logging and "requests are not stored".
- Regulatory review of the "anonymous" donation wording and the GDPR Art. 9(2)(a) / KVKK citations.
- Rule 8 (ancient texts): nothing in Phase 3 scope.
