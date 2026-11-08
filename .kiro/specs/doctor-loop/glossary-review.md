# Glossary review sheet (doctor-loop task 15): waiting for the owner

Files: `apps/api/janus/notes/glossary/ingredients.csv` (1,129 rows), `cascades.csv` (65 rows), `sentences.csv` (112 rows).
All rows are `proposed`; no note language is available until the owner accepts them. Full reviews:
`glossary-pharmacologist-review.md` (pharmacologist agent) and `glossary-localization-review.md` (localization
reviewer, run read-only through `wf-coder`). Both were written on 2026-11-08 and changed no other file.

Status line (kept): reviewed by the project owner with AI assistance; needs review by a pharmacist or physician and by
native speakers before any public claim.

## Verdicts
| File | Pharmacologist | Localization reviewer |
|---|---|---|
| `ingredients.csv` | approve with changes (F1–F4 blocking) | not ready (I1–I3 blocking) |
| `cascades.csv` | approve with changes (advisory only) | acceptable (advisory only) |
| `sentences.csv` | approve with changes (S1, S2 blocking) | not ready (S1–S7 blocking) |
| `render.py` formatting table | – | correct |
| `REASSURANCE` lists (`phrases.py`) | – | not ready for Turkish (P1 blocking) |
| The four disclaimer translations | – | accepted as they are |
| `abrupt_stop` in five languages | correct | correct |

## What the reviews found (blocking items, both reviews merged)

**ingredients.csv** (Wikidata labels; English is the fallback in every language, so English errors reach every note)
- Wrong substance or meaning: about 19 cells, for example cortisol for hydrocortisone, a racemate or isomer name for
  selegiline and doxepin, rebamipide labelled as rabeprazole in Spanish, alprostadil labelled "Prostaglandin E1",
  truncated or garbled cells (pharmacologist F1, localization I2).
- Brand or product names in 9 cells and 5 keys that are product items duplicating a substance key (F2, I2).
- Wrong English cells: carbamazepin, ropinirol, a cell holding Wikidata note text (F3, I1).
- Misspellings in other languages: 10 cells (F4).
- Wrong-language labels: 5 Turkish, 11 Spanish, 5 French cells (F7, I3).
- Advisory: 147 cells with stereo descriptors such as `(RS)-` (F5, I1); salts or esters on base-substance keys (F6);
  45 proposed `en_alt` US names (F8); capitalization (en 74, tr 367, fr 134, es 478 cells start upper case; F9, I4).

**sentences.csv**
- `finding.cascade` says "{index} followed by {marker}" also when the order is unknown (same month, date unknown);
  proposed: state the match there and the order in the timing sentences (pharmacologist S1). This changes the
  parameters of `finding.timing.*` in `janus/notes/templates.py`.
- `finding.timing.after_window` mentions the window without citing the window paper (pharmacologist S2).
- French and Spanish use two words for "report" in one section (*déclarations* against the reviewed *signalements*;
  *notificaciones* against *informes*) (localization S1).
- Shared texts that do not fit a doctor note: `stat.absence` says "your medicines"; `stat.denominator` says "figures for
  all reports are shown beside these", which the note does not do (localization S2, S3; pharmacologist S6). Proposed:
  note-only rows instead of the shared ones.
- The safety lines speak to the patient; proposed heading "Urgent symptoms: information shown to the patient"
  (localization S4).
- `{event}` is the lay label, capitalized and in the nominative, which breaks German case and puts capitals mid-sentence
  (localization S5); alternative: use the clinical cascade name.
- German: `header.prepared` ungrammatical with a numeric month; *Daten* reads as "data" in "ohne Namen oder Daten"
  (localization S6, S7).

**REASSURANCE lists**: Turkish misses the predicative and suffixed forms (*güvenlidir*, *zararsızdır*, *sorun yoktur*,
*risksiz* …) (localization P1). Advisory additions for the other languages (P2–P5).

## Found outside the glossary (blocks issuing real notes)
Wikidata gives some ingredient keys a code of another substance: ketoconazole carries ketoprofen's `M01AE03` (enters the
NSAID classes, rows 9, 40, 51–54), mefenamic acid carries tramadol's `N02AX02` (opioid class, row 55, and the opioid
abrupt-stop warning), esomeprazole carries the old pregabalin code `N03AX16` (gabapentinoid class, row 31, and its
warning), and five more keys carry a wrong but harmless code (pharmacologist F13). These codes reach the engine for
name-search and ingredient-choice items (form-unconfirmed findings) and are printed in the note. This belongs to
`drug-resolution` and the cascade engine, not to this spec.

## Decisions for the owner
1. **Fix policy for wrong non-English ingredient cells**: clear them (the note prints the English INN with "name not
   translated" and the ATC code), as both reviewers propose under the no-AI-translation rule; the national forms the
   localization reviewer names (for example *levetiracetam*, Spanish *duloxetina*) would be accepted only as mechanical
   source fixes, or left for a native reviewer.
2. **English cells**: accept the pharmacologist's INN fixes (F1, F3, F5, F6) and the `en_alt` US names (F8).
3. **Capitalization**: edit the file (lower case except German nouns, binomials and acronyms, Turkish-correct casing),
   or lower-case at render time and keep the file equal to the source labels.
4. **Product keys** (5): rename to the substance INN here and hand the key merge to `drug-resolution`.
5. **Wrong ATC codes** (F13): approve a curated per-key code-exclusion file and an RxClass cross-check of all in-scope
   keys in `drug-resolution`, before any note is issued.
6. **Templates**: accept the rewording of `finding.cascade` and the timing sentences (with the window citation), the
   BMJ priority sentences after checking "Ontario" and the incidence definition against the abstract, the note-only
   versions of `stat.absence` and `stat.denominator`, and the French and Spanish word for "report" (align to the web
   texts, or change both).
7. **`{event}` in statistic sentences**: quoted lay label, or the clinical cascade name.
8. **Row 49** (Drug B published as "Vitamin or Mineral Deficiency"): print "(as published)", add a sentence on what
   Janus checks (B12, magnesium, oral iron), or leave it.
9. **Outcome page**: ingredient names in the action labels; one action per finding (Requirement 3.1) or more.
10. **J1 and J2**: tag `source` as `janus_curated` and accept the curated labels; for J2 print no code or label
    `J01DH51` as the combination code.
11. **TİTCK-equal cells**: 212 of 447 Turkish and 216 of 1,129 English cells equal (case-folded) an ingredient string of
    the TİTCK list; they come from Wikidata. The pharmacologist sees no clinical reason to drop them (a correct INN
    spelling matches the regulator's). Keep or drop.
12. **Reassurance lists**: accept the Turkish additions (P1) and the advisory additions for the other languages.

After the answers, task 16 applies them in one commit, sets the statuses and checks that five languages are available.
