# Wording review: Passport texts and word lists (medication-passport, task 11) — review stop

**Date:** 2026-11-08. **Scope:** the `Passport` namespace of `apps/web/messages/{en,tr,de,fr,es}.json` (124 keys per
locale; English is the reference of design §7.2, TR/DE/FR/ES are AI drafts), the word lists of
`apps/web/src/passport/words.ts`, and the client code that decides what is sent (`request.ts`, `entry.ts`, `model.ts`).
**Passes:** two separate passes, run by Claude Code following `.kiro/agents/localization-reviewer.md` and
`.kiro/agents/safety-auditor.md` (read-only role; fixes listed under "Fixed before the stop"). tasks.md also names a
pharmacologist pass; it was not run (decision 3). The screens do not exist yet (task 12), so texts were read as strings
and rendered with generated parameters (`messages.test.ts`), not in context.

**Mechanical checks (all green):** key parity and identical ICU arguments in five locales; no substitution word
(design §7.3) in any Passport string, no removal word in `Passport.duplicate.*`, no rule-2 forbidden phrase, no rule-3
reassurance word, also after rendering every plural branch (P4); every API code, origin, country, form group, unit and
basis has a key (P16, against the literals exported from `schemas.py`); "could not compare" texts never contain the
word for "same" (P3, message part); source names identical in all locales and the four Req 7.2 attribution sentences
present with `{date}`; owner word decisions (TR "bildirim", ES "notificación", DE "Meldung", FR "signalement"; no
"anonymous" in any form).

## Pass 1: localization-reviewer

| # | Key | Lang | Issue | Suggested wording | Severity |
|---|---|---|---|---|---|
| L1 | `compare.strength.differs` | es | "dosis" is both the label for strength and the word in the caveat ("no demuestra una dosis diferente"), so the caveat contradicts itself. | "… así que esto no demuestra que la cantidad de principio activo sea diferente." | blocking — **fixed** |
| L2 | `status.*`, `open`, `detail.*` | all | One verb and one noun per language for "lists / listing": TR listeliyor / kayıt, DE führt / Eintrag, FR liste / inscription, ES registra / registro. FR "inscription" can be read as a marketing authorisation; "répertorie / présence dans la liste" is closer. | decision 5 | advisory |
| L3 | `nav` | de | "Pass" is short enough for the bottom bar at 375 px but vague; "Medikamentenpass" (16 letters) may not fit five tabs. | decision 4 | advisory |
| L4 | `compare.*.matched` | tr | "bu kutuyla aynı belirtilen miktarla" is understandable but stiff. | "…, bu kutudakiyle aynı miktar belirtilerek listeleniyor ({strength})." (native review) | advisory |
| L5 | `status.not_in_source` | tr | "bulunmadığını" can mean "not found" or "not available". | "… şu ülkede piyasada olmadığını göstermez: {country}." (native review) | advisory |
| L6 | `origin.US` vs `country.US` | tr | "ABD'den kutu" next to "Amerika Birleşik Devletleri". | Accept (label short, sentence formal) or use one form. | advisory |
| L7 | `compareReason.*` | de | Capitalised after the colon ("Wirkstärke nicht verglichen: Der Wert …"), lowercase in the other languages. Correct German for a full sentence; noted for parity only. | none | advisory |
| L8 | long words | de | "Darreichungsform", "Humanarzneimittel", "Arzneimitteldaten", "Wirkstärke und Darreichungsform zusammen" at 375 px. | Screens must wrap (`overflow-wrap: anywhere`, design §8); check in task 12. | advisory |
| L9 | `attribution.titck` | all | The TİTCK list is named by its Turkish title in TR and by a translated description elsewhere; the other three sources keep their published names in every language (Req 7.2). | decision 6 | advisory |
| L10 | `duplicate.chip/text` | all | "under two names" (design §6.3) became "under different names" and the "Both stay" sentence is a plural select ("All of them stay" for 3+ boxes), since a group can name three boxes. | decision 10 | advisory |
| L11 | `demo.intro` | tr | "uydurmadır" as in the reviewed `Demo.intro`; "kurgusaldır" is softer. | keep for consistency or change both | advisory |

Native-speaker review of TR, DE, FR and ES is still needed before launch (as for the other namespaces).

## Pass 2: safety-auditor

| # | Where | Rule | Lang | Issue | Fix / owner | Severity |
|---|---|---|---|---|---|---|
| S1 | `attribution.bdpm` | Licence ouverte (no implied endorsement) | fr | "la BDPM n'approuve pas Janus" reads as disapproval, not as "no endorsement". | "Affiché tel que publié, sans approbation de Janus par la BDPM." | blocking — **fixed** |
| S2 | `attribution.openfda` | parity, claim accuracy | tr | "FDA onayı değildir" reads as "not FDA approved" (drug approval), not "not an endorsement". | "FDA tarafından desteklendiği anlamına gelmez." | blocking — **fixed** |
| S3 | `compare.*.matched` with typed values | Req 6.7, owner decision 1 | all | "the same stated strength as this box" must say "as entered from the box" when the box value was typed (TİTCK, German boxes). The text has no slot for it; the screen must add `Passport.entered` next to the box value and in the comparison row. | task 12 render test (P3 client part) | blocking for task 12 |
| S4 | `status.present` | rule 1, DP3 | all | "lists N products" can be read as "available / can be bought". `not_in_source` already says listing ≠ availability; `present` does not say the converse. | decision 8 | advisory |
| S5 | `entry.hint` | privacy.md | all | Says only codes are sent, never the box name: true for `request.ts` (P18 checks it). An earlier draft idea "stays on this device" would have been false (codes are sent) and was not used. | none | checked |
| S6 | `request.ts` | Req 2.2, 6.1, DP11 | — | An item with one unrecognised ingredient would have been sent with its recognised keys only, so a combination box could read "present" from single-ingredient products. | not sent, reason `partial` (DP24) | blocking — **fixed in task 9**, owner to confirm (decision 1) |
| S7 | `entry.ts` / `strength.py` | Req 6.1 | all | "1,000 mg" / "1.000 mg" mean 1000 or 1 depending on the language; a misread typed strength could produce a false "same stated strength". | refused with a hint (DP25) | blocking — **fixed in task 9**, owner to confirm (decision 2) |
| S8 | `compare.strength.differs` | Req 6.3 | all | Salt/base caveat present in all five (ES fixed by L1). | none | checked |
| S9 | `reason.no_open_product_database`, `germanyByName` | Req 7.5 | all | Germany never worded as "not found"; says nothing was checked. | none | checked |
| S10 | `duplicate.*` | Req 1.3, DP14 | all | Informational only; ends with the allowed framing; no removal word (also in TR/DE/FR/ES inflections read by hand: çıkar-, sil-, entfern-, supprim-, retir-, elimin-, quit-). | none | checked |
| S11 | all Passport strings | rules 2, 3, 9 | all | No forbidden phrase, no reassurance; rule-9 disclaimer is the shell footer, `listingsOnly` must be on the detail screen (task 12, P16 render part). | task 12 | checked |

Could not check: the texts in context (no screens yet), large-text mode, screen-reader reading of the table captions.

## Fixed before the stop
L1 (ES caveat), S1 (FR BDPM line), S2 (TR openFDA line); S6 and S7 in task 9 (DP24, DP25). Tests green after the fixes.

## Decisions for the owner
1. **DP24:** items with an unrecognised ingredient are not sent for presence ("Cannot be checked: Janus could not
   recognise every active ingredient of this box"), but still count for duplicate flags. Accept?
2. **DP25:** typed amounts like "1,000" / "1.000" are refused with "type it without thousands separators". Accept?
3. **Pharmacologist pass** (tasks.md task 11) was not run on these texts: run it before task 12, or accept these two
   passes?
4. **Navigation label:** DE "Pass" or "Medikamentenpass"; titles TR "İlaç pasaportu", DE "Medikamentenpass", FR
   "Passeport médicaments", ES "Pasaporte de medicamentos".
5. **"Lists / listing" per language:** keep TR listeliyor/kayıt, DE führt/Eintrag, FR liste/inscription, ES
   registra/registro, or FR "répertorie / présence"?
6. **TİTCK name:** Turkish title in TR and a translated description elsewhere (current), or "TİTCK Ruhsatlı Beşeri Tıbbi
   Ürünler Listesi" in every language like the other source names?
7. **Smaller batch** (accept as a block or pick): L4, L5, L6, L11.
8. **Present ≠ on sale:** add to `status.present` "Being listed does not show that it is on sale" (all five), or keep?
9. **Word lists** (design §7.3) as implemented, prefix match, plus the "same" list for could-not-compare texts
   (EN same, TR aynı, DE gleich/dieselbe/denselben/derselben/dasselbe, FR même, ES mismo/misma): accept?
10. **Duplicate wording:** "Same active ingredient under different names" with "Both / All of them stay on your list"
    instead of "under two names … Both stay". Accept?
