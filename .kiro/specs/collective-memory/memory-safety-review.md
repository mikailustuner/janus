# Collective Memory: safety and privacy review

- Date: 2026-11-08
- Reviewer: safety-auditor (read-only; this report is the only file written)
- Role file read: `.kiro/agents/safety-auditor.md`
- Steering applied: `medical-safety.md` rules 1-10, `privacy.md`, `product.md` ("Claims we must not make"), and the owner's extra rules (counts are reports never people; no causal, probability, risk or normality words except `Memory.screening`).
- Files read:
  - Spec: `collective-memory/{requirements,design,tasks}.md`, `experience/requirements.md` (Requirement 7), `event-labels-localization-review.md`, parts of `event-mapping-pharmacologist-review.md`.
  - Strings: `apps/web/messages/{en,tr,de,fr,es}.json` (`Memory`, `Disclaimer`), `apps/api/janus/memory/messages.py`, `apps/web/src/i18n/{forbidden-phrases,memory-words}.ts`.
  - API: `memory/{router,service,schemas,shared,reader (parts),stats,evidence,vocabulary (parts),disclosure (parts)}.py`, `db/pool.py`.
  - Vocabulary: `memory/memory_events.csv` (39 rows).
- Run: scripts that apply the three word lists (`forbiddenPhrases`, `peopleWords`, `causalWords`, parsed from the .ts files) to every `Memory` value in five languages, to the five labels and every PT of all 39 keys, plus cross-language checks (each language's labels against the other four lists). Code-set parity across the five files. One call of `stats.evaluate` on a table with a = 2. No file other than this report was changed.
- Not checked: the client (not built), rendered screens, the doctor note, tests' pass/fail state (read, not run), real FAERS output, native-speaker quality of the translations (only the localization review exists).

## Findings

| id | severity | where | finding | recommended change |
|---|---|---|---|---|
| S1 | SHOULD FIX | `messages.py:125`, `en.json:56` (and tr/de/fr/es `urgent_care_heart`) | The line can be read as "palpitations alone need no care": the sentence names urgent care only for fainting, or for a fast or irregular heartbeat *together with* chest pain or breathlessness. It then says "Call emergency services" without saying when. Chest pain and breathlessness are the rule 10 emergency symptoms, yet the number comes second. A reader with palpitations only can take the line as a limit. | Number first, trigger explicit, palpitations kept in scope. EN: "Call emergency services (112 in Türkiye and the EU, 911 in the US) for chest pain, trouble breathing or fainting. A racing or irregular heartbeat also needs urgent medical care." Translate with the same order in tr, de, fr, es (owner and localization-reviewer). |
| S2 | SHOULD FIX | `messages.py:120`, `en.json:55` (all five) `urgent_care_skin` | Symptoms come first and the number is conditional on "if you feel very unwell", so a person with a blistering rash plus fever sees emergency services as optional. The line has no allergic-reaction signs although the key is a drug-rash key and rule 10 names severe allergic reaction. Content is otherwise safe and non-diagnostic. | EN: "Get urgent medical care for a rash that is severe, spreading or blistering, or that comes with fever or mouth sores. If your face or lips swell, you find it hard to breathe or you feel very unwell, call emergency services (112 in Türkiye and the EU, 911 in the US)." Mirror in four languages. |
| S3 | SHOULD FIX | `service.py:241,287`; `schemas.py:161,191` | `safety_line` is returned only when the request names a Janus key (`pair`, `regions`). A PT request (`{"pt":"Torsade de pointes"}`), and every event row of `combination` (`EventStatsOut` has no field), shows a covered PT without its line. A caregiver who opens a combination and sees "Torsade de pointes" or "Depression" gets the count with no line. Experience Requirement 7.1 says "an event whose Janus key has a `safety_line`"; the client cannot map a PT to a key. | Add `safety_line: str \| None` to `EventStatsOut` and `EventOut`, filled by a reverse PT-to-line lookup in `EventVocabulary` (active keys). Add a property test: every PT in a key with a line returns that line on every route. Record the rule for PTs shared by several keys (any line wins). |
| S4 | SHOULD FIX | `memory_events.csv:32,35,33` (`gastric_ulcer_bleed`, `seizures`, `heart_failure`), column `safety_line` | Recommendation only, the owner decides. These keys contain PTs that are emergency signs under rule 10 and have no line: Haematemesis, Melaena and the haemorrhage PTs (blood in vomit or black stools); convulsions; heart failure (sudden breathlessness). See area 4 for the full list. | `gastric_ulcer_bleed`: new line `urgent_care_bleeding`. `seizures`: new line `urgent_care_seizure`. `heart_failure`: reuse `urgent_care_heart` after S1 (breathing trouble is in its text). Drafts in area 4. Each new line needs five languages, `SAFETY_LINES` in `vocabulary.py:49`, and the same tests as the three existing lines. |
| S5 | SHOULD FIX | `stats.py:174-196`, `service.py:173-226`, `schemas.py:131` | A cell with 0 < a < 3 returns PRR, ROR, interval and χ² although its assessment is `insufficient_data` (checked: a = 2, b = 10, c = 5, d = 100,000 gives `insufficient_data` and PRR 3333.5). Requirements 1.3 and 10.3 forbid a sentence with a number from such a cell, but the API contract lets a client render the ratio. A PRR of 3,333 from two reports is the most alarming and least meaningful number in the product. Design §5.2 says `estimates` is null only when a = 0, so the code matches the design; the design is the problem. | Return `estimates = null` for `a < MIN_REPORTS` (primary and `sensitivity`) and update Requirement 1.2, design §3.1/§5.2 and P5. Counts a, b, c, d stay. This is a contract change, so the owner confirms before the code is touched. |
| S6 | SHOULD FIX | `service.py:334-340`, `service.py:313-327` (`regions` without `event`) | A regional breakdown without an event returns `reports` per region (possibly 0, for example TR) with `stats = null`, so no assessment, no `no_reports` code and no `absence_is_not_reassurance` notice (`assessments` is empty). A "0 reports" row for TR with no caveat is the false-reassurance case of rule 3. | Add `absence_is_not_reassurance` to `extra` whenever any row has `reports == 0` in the no-event branch. Add a property test. |
| S7 | SHOULD FIX | `schemas.py:228-244` (`CombinationOut`, `PairGroupOut`, `SingleGroupOut`, `IngredientCountOut`, `MemberAloneOut`), `RegionsOut.unknown/basis` | Counts without a citation: `combination.reports`, `ingredients[].reports`, `pairs[].reports`, `singles[].reports`, `members_alone[].reports`, and the UNKNOWN share. Only `events[].citation` and `rows[].citation` exist. Requirement 10.5 says every statistic carries `citation`; rule 5 says a claim without evidence is removed, so a client following the rule must drop the headline count of a combination. | Add `citation` (locator with `event=` empty, as `RegionsOut` rows already do) to `CombinationOut` for the set count and to each group object; or state in Requirement 10.5 that group counts inherit the response-level citation and add that field. |
| S8 | SHOULD FIX | `messages.py` (no code), Requirement 3.4 | Requirement 3.4 requires, for TR, a statement that the reports are a small, self-selected set and no picture of medicine use in Türkiye. No code and no message exists in the closed set or in the five files. TR has 3,720 mapped reports, so the omission matters. | New notice `tr_reports_small_self_selected`, added by `regions` and `pair` when `region == "TR"`. EN: "Reports from Türkiye are few and are sent by choice. They do not show how medicines are used in Türkiye." Translate to four languages and pass the word lists (no people noun). |
| S9 | NOTE | `Memory` namespace | No string gives the 95% interval, the Evans criteria name, "reports" as a unit, or the statement that "other reports" include reports where the medicine is only concomitant (Requirement 1.7), or the "Yates form cited from secondary use" note (Requirement 1.6). These belong to the client, but the catalogue is the checked place. | Add them to `Memory` when the experience spec renders them, so the word lists run over them. Not a defect of the strings that exist. |
| S10 | NOTE | `messages.py:19`, `en.json` `Memory.meddra` | Notice reads "MedDRA® is a registered trademark of ICH". The MedDRA owner's text names IFPMA acting for ICH (to be checked against the current MSSO wording, which this review did not fetch). The text is also English in all five files. | Check the exact required wording and whether translation is allowed; this item is already on `docs/pre-launch-checklist.md`, add the IFPMA point. |
| S11 | NOTE | `messages.py:30` `spontaneous_reporting` | "are not checked" overstates in one direction: FDA processes the reports; they are not verified. Safe as written, slightly less precise than "are not verified". | Optional: "Reports are sent voluntarily and are not verified." and the four translations. |
| S12 | NOTE | `messages.py:111` `hidden_under_20_noise_added` | "Hidden under 20" does not say 20 of what. Requirement 5.10 counts donated reports. | Optional: "Hidden when fewer than 20 donated reports; noise added to the others." Check the word lists (no people noun) and translate. |
| S13 | NOTE | `messages.py:116` `crisis_support` (all five) | Safe and calm. Two points. "self-harm" alone may under-name suicidal thoughts. "a crisis line in your region" has no number, which Experience 7.3 already assigns to a curated, verified list. | Optional EN: "If there are thoughts of harming yourself or of ending your life, call your local emergency number (112 ..., 911 ...) or a crisis line in your region." Keep impersonal: "someone", "person" are on the people-word list. Pre-launch list: US 988 and the national lines, verified. |
| S14 | NOTE | `Memory.codes` in `tr`, `de`, `fr`, `es` | "Türkiye" is used in fr and es, "Türkei" in de, "Türkiye" in tr (correct). Local forms are "Turquie", "Turquía". Cosmetic, but the same line in the same app should follow one rule per language. DE `urgent_care_*`: "Rufen Sie den Notruf" is acceptable, "Wählen Sie den Notruf" is more usual. | Localization-reviewer to settle; native check stays on the pre-launch list. |
| S15 | NOTE | `design.md:377-379` vs `messages.py` | Design §7.1 lists `many_pairs_examined` and `corrected_estimate`; neither exists. `weak` and `weak_pattern` have the same text. | Align the design list with the code. |
| S16 | NOTE | `router.py` `_faers` / `service.regions:283` | A benefit key gives 200 `not_available` on `/memory/pair` but 422 `event.key` on `/memory/regions`. Not a leak, just inconsistent. | Return `not_available` in both. |
| S17 | NOTE | Client duty, `medical-safety.md` rule 4 | The `depression` screen will often show an antidepressant. The API sends no abrupt-stop flag and the safety line does not carry it. | Experience spec: the abrupt-stop line is shown next to any antidepressant, beta-blocker, and so on, on the same screen as `crisis_support`. |

No BLOCKING finding. S1-S8 should be settled before the experience spec consumes the API; S3 and S7 become blocking at that point.

## Area 1: strings (five languages and `messages.py`)

Checked:
- Forbidden phrases of rule 2 in all five lists, whole-word, case-insensitive, on all 36 codes plus `screening`, `attribution`, `meddra` in en, tr, de, fr, es. Also each language's strings against the other four lists. No hit.
- People words and causal/probability/risk/safe/normal/interaction words (lists in `memory-words.ts`). No hit; `Memory.screening` is the only value that contains a causal word and it equals `allowedScreening[locale]` in all five files and equals `SCREENING_SENTENCE` in `messages.py`.
- Parity: the five files carry the same keys (36 codes, no extra, no missing, none empty). Messages in `messages.py` and `en.json` agree for the codes read.
- Rule 1: no sentence tells the reader to start, stop or change a medicine. The only imperatives are "call" and "treat as a weak pattern".
- Rule 3: `absence_is_not_reassurance` ("does not mean ... free of problems") and `not_disproportionate` ("This does not mean there is no association") are present and translated with the same meaning. No "safe", "all clear" or "no problem" anywhere.
- Rule 6: FAERS described as voluntary, not incidence, merged by case version only; counts are "reports" in all five languages; the window sentence includes follow-up versions.
- Rule 9: `Disclaimer.text` exists in all five languages; `messages.py` `DISCLAIMER` is the English line, attached to every FAERS and shared response.
- Product claims: no "people like you", "first", "cure", "diagnosis" or "mined" in strings.

The three safety lines (owner decision 2026-11-08, Experience 7):
- **Safe:** none diagnoses ("needs urgent medical care" names no condition), none advises a medicine action, none uses a forbidden or causal word. Tone is calm: no capitals, no exclamation, no "danger".
- **Accurate:** 112 for Türkiye and the EU, 911 for the US, in all five languages (matches rule 10). Symptoms are standard warning signs for severe skin reactions and for dangerous arrhythmia.
- **Emergency services first:** only `crisis_support` puts the number inside the first clause. `urgent_care_skin` and `urgent_care_heart` put symptoms first, and skin makes the call conditional (S1, S2). The five languages keep the same order and the same numbers, so they are consistent with each other.
- **Gaps:** palpitations-only reading in the heart line (S1), no allergic signs in the skin line (S2), "self-harm" and no named crisis number (S13). Experience 8.9 (emergency notice above any screen listing such events) remains a client duty.
- The lines are shown "whatever the counts are" only if the client gets them; S3 shows the API does not always provide them.

## Area 2: API behaviour

Checked and passed:
- Evidence: every statistic in `PairOut`, `events[]` and `rows[]` has `citation {evidence_id: "dataset:faers", locator}`; the id is a `Literal`; the locator function is pure, rejects bad parts and carries no date or run id. Gap: S7.
- Verdict reading: the assessment set is five classes with sentences that compare shares of reports; `disproportionate`'s sentence says "larger share", not risk. `evans_met` and `ror_signal` are booleans, not wording. Lists are ordered by reports then PT, never by assessment (Requirement 1.8). Gap: S5 (alarming number with `insufficient_data`).
- Nothing found: `absence_is_not_reassurance` is added by `_absence_notice` when any assessment is `no_reports`, `insufficient_data` or `not_disproportionate`, on `pair`, `regions` (with event) and `combination` (also when an ingredient has no reports, and when the pairwise or single level is shown). Gap: S6 (regions without event).
- Benefit keys: `pair` returns `not_available` with `benefit_not_in_faers`, no zero count.
- MedDRA: `meddra_notice` set when `has_pt` (pair with a PT or key; combination always; regions with an event). Absent only where no PT is returned.
- Fail closed: `CountsError` gives 503 with no numbers; inconsistent counts raise `InconsistentCountsError` and the message names nothing.
- Haldane and approximate interval: flagged with codes `estimate_uses_continuity_correction` and `interval_approximate`; `weak` adds `weak_pattern`; sensitivity difference adds `denominator_sensitive`. The sentence for the screening statistic is in `BASE_NOTICES` on every FAERS response.

## Area 3: privacy

Checked and passed:
- Routes: `pair`, `combination`, `regions`, `shared` are `POST` on the medical router with a JSON body; the 422 names fields only (`_field_names` hides unknown field names). Only `GET /memory/snapshot` is operational and returns no medicine or event data.
- Logging: no logger, `print` or log call in `router`, `service`, `shared`, `reader`, `stats`, `schemas`, `evidence`, `ladder`, `vocabulary`; the allowlist formatter is the only handler. DuckDB errors become `CountsError("a counts query failed")` with no parameters.
- No cache, no write: no `lru_cache` or file write in the request path; DuckDB is read-only with `max_temp_directory_size = 0GB` and `enable_external_access = false` (`reader.py:44`).
- k and noise: `shared` calls `release_table`; `k >= 20` is enforced there (`K_MIN`), suppression uses the true count; without a noise key or database the answer is `layer_unavailable` with `cells: []`; outcomes answer `not_available`, never zero.
- Sibling rule (`sibling_rule_count`): eligible only when `n >= k` and, for every other ingredient X, `n - m_X` is 0 or at least k. By induction on a chain S ⊂ S+X ⊂ ... this gives `n_S - n_T` of 0 or at least 20 for any superset T, because `n_T <= m_X`. An ineligible cell is passed with count 0 and is therefore the same `hidden` as a cell under k.
- Hidden equals zero: a missing cell, a count of 0 to 19 and an ineligible cell all give `{"region", "status": "hidden", "value": null}`. `total_of_released` sums released cells of one layer only.
- No cross-layer number: `SharedOut` has no FAERS field, FAERS responses have no user-layer field, and `shared` never receives a counts reader.
- Personal data: the contributor version is a SHA-256 over donation ids inside the server; it is never returned. No name, date, location or device field exists in any response model.
- Deletion: `_COUNTS` and `_SIBLINGS` run in one transaction opened with `REPEATABLE READ, READ ONLY` (`db/pool.py:40`), so n and m_X come from one snapshot and a deleted donation is absent from the next request.
- Residual limits stated in Requirement 5.9 (two-step differencing, padding before rate limiting) are accurate. This review has no finding on them; the privacy page must carry them (client).

## Area 4: event vocabulary (`memory_events.csv`)

Checked and passed:
- 39 rows, 5 labels each, all five languages. No forbidden phrase of any language in any label (same-language and cross-language scan). No people noun. No reassuring word.
- No PT contains a forbidden phrase. The labels are event names, not verdicts; the alarming words that appear are the events themselves ("bleeding" in `gastric_ulcer_bleed`, "crisis" as the Spanish medical term in "crisis convulsivas").
- The localization review's fixes are applied (checked: `oedema` tr, `akathisia` fr, `seizures` en/tr, `arrhythmia` four languages, `hypertension` fr/es).
- Safety-line assignment: `depression` (line 4) `crisis_support`, `rash` (line 15) `urgent_care_skin`, `arrhythmia` (line 18) `urgent_care_heart`. Matches the owner decision and `vocabulary.py:49`; an unknown code is rejected at load.
- `rash` note says SJS, TEN and DRESS are not counted and the screen must not read a rash count as covering them. Good and kept; it is why S2 matters.
- Depression PTs do not include suicidal ideation (`event-mapping-review.md:98` left it out). That is acceptable only because `crisis_support` is shown with the key; keep that link (S3).

Recommendation (owner decides) for further lines:

| key | reason | proposal |
|---|---|---|
| `gastric_ulcer_bleed` (CSV line 32) | PTs include Haematemesis, Melaena, Gastrointestinal haemorrhage and six haemorrhage PTs. Vomiting blood or black stools is an emergency sign. | New `urgent_care_bleeding`. EN draft: "Vomiting blood, or black or bloody stools, needs urgent medical care. Call emergency services (112 in Türkiye and the EU, 911 in the US) if you feel faint or very unwell." |
| `seizures` (CSV line 35) | A seizure is an emergency for a first event or one that lasts more than a few minutes. | New `urgent_care_seizure`. EN draft: "A seizure needs urgent medical care. Call emergency services (112 in Türkiye and the EU, 911 in the US) if it lasts more than 5 minutes, if another follows, or if this is the first one." |
| `heart_failure` (CSV line 33) | Sudden breathlessness is a rule 10 symptom. | Reuse `urgent_care_heart` once S1 is applied (it names trouble breathing). |
| `psychosis_hallucinations` (line 24) | Distress and risk to self or others. | Reuse `crisis_support`, or leave out; lower priority. |
| `dizziness` (line 3, includes Orthostatic hypotension) | Fainting. | Leave out; `urgent_care_heart` already covers fainting if the client shows it for this key's PT. Optional. |
| `urinary_retention` (line 28) | Inability to pass urine needs same-day care. | Optional; not an emergency-number case. |
| `hyperglycaemia`, `myalgia_myositis` | Very high sugar with vomiting; dark urine with severe muscle pain. | Not now; the PTs are mild. Re-check with the pharmacist. |

The count of lines grows the client's duty (Experience 7.1 lists three). Any new line is added to Experience Requirement 7 first.

## Area 5: claims we must not make

Checked the spec files and all strings for: "first AI prescribing-cascade detector", "first repurposing", "first retraction checker", "first data-mining of Islamic or Ottoman medicine", "cure", "diagnosis", "we solve a global problem", "N people like you". None present. FAERS counts are "reports" everywhere, including API field names (`reports`, never `people`). The screening sentence (`Memory.screening`) and `combination_caveat` ("does not show an effect of taking them together") keep the statistics from reading as a claim of effect. The only "first" strings are "first seed" and "first build" in the spec history.

## VERDICT: approved with changes

No blocking defect. Before the experience spec renders this API: apply S1-S2 (safety-line wording, owner and localization-reviewer), S3 and S7 (contract fields), S5 (owner confirms the contract change), S6 and S8 (notice codes). S4 is the owner's decision. S9-S17 are notes.
