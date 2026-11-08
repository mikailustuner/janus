# Glossary review sheet (doctor-loop task 15): owner decisions recorded

Files: `apps/api/janus/notes/glossary/ingredients.csv` (1,129 rows), `cascades.csv` (65 rows), `sentences.csv` (112 rows).
All rows were `proposed` when the sheet went to the owner. Full reviews: `glossary-pharmacologist-review.md` and
`glossary-localization-review.md` (both 2026-11-08). The owner's answers of 2026-11-08 are in section 4; task 16 applies
them, after the wrong-ATC-code fix in `drug-resolution` (decision 5), which comes first.

Status line (kept): reviewed by the project owner with AI assistance; needs review by a pharmacist or physician and by
native speakers before any public claim (`docs/pre-launch-checklist.md`).

## 1. Verdicts
| File | Pharmacologist | Localization reviewer |
|---|---|---|
| `ingredients.csv` | approve with changes (F1–F4 blocking) | not ready (I1–I3 blocking) |
| `cascades.csv` | approve with changes (advisory only) | acceptable (advisory only) |
| `sentences.csv` | approve with changes (S1, S2 blocking) | not ready (S1–S7 blocking) |
| `render.py` formatting table | – | correct |
| `REASSURANCE` lists (`phrases.py`) | – | not ready for Turkish (P1 blocking) |
| The four disclaimer translations | – | accepted as they are |
| `abrupt_stop` in five languages | correct | correct |

## 2. What the reviews found (blocking items, merged)
- **ingredients.csv**: about 19 cells that name a different substance or a wrong meaning; brand names in 9 cells and 5
  product keys that duplicate a substance key; wrong English cells (these are the fallback in every language); 10
  misspellings; wrong-language labels (5 Turkish, 11 Spanish, 5 French); 147 cells with stereo descriptors; salts on
  base-substance keys; 45 proposed `en_alt` US names; capitalization (en 74, tr 367, fr 134, es 478 cells start upper
  case).
- **sentences.csv**: `finding.cascade` states an order of starts also when the order is unknown; the after-window
  sentence lacks the window citation; two words for "report" in French and Spanish; shared texts that do not fit a doctor
  note (`stat.absence`, `stat.denominator`); patient-addressed safety lines; `{event}` as a capitalized lay label breaks
  German case; German `header.prepared` and *Daten* ambiguity.
- **REASSURANCE**: Turkish misses predicative and suffixed forms.
- **Outside the glossary**: Wikidata gives some ingredient keys the ATC code of another substance (ketoconazole with
  ketoprofen's code, mefenamic acid with tramadol's, esomeprazole with the old pregabalin code, five more). They put
  those medicines into the wrong classes and abrupt-stop warnings.

## 3. Open points the reviews raised that need a check before acceptance
- The BMJ priority sentence says "Ontario" and speaks of "incidence": check both against the abstract (Crossref) before
  accepting the wording (decision 6).

## 4. Owner decisions (2026-11-08)
1. **Wrong non-English ingredient cells**: clear them. The note prints the English INN with "name not translated" and the
   ATC code. No national forms are added now; they wait for a native reviewer.
2. **English cells**: accept the INN fixes (F1, F3, F5, F6) and the `en_alt` US names (F8).
3. **Capitalization**: edit the file (lower case except German nouns, Latin binomials and acronyms; Turkish-correct
   casing), so what is reviewed is what is printed.
4. **Product keys**: rename to the substance INN here; the key merge is a `drug-resolution` follow-up.
5. **Wrong ATC codes (F13)**: a clinical correctness bug, done **first**, before task 16, in `drug-resolution`: a
   curated per-key code-exclusion file; a cross-check of every in-scope key's ATC codes (WHOCC names against the INN,
   RxClass for US keys where available); every mismatch listed in a review section; ketoconazole, mefenamic acid,
   esomeprazole and the five others fixed; cascade-engine gate 1 and the FAERS count build re-run and the exact changes
   recorded. Its own commit. No note is issued until it is done. (`.kiro/specs/drug-resolution/atc-code-review.md`.)
6. **Templates**: accept all rewording, including the window citation, the note-only `stat.absence` and
   `stat.denominator`, and the French and Spanish word for "report" aligned to the reviewed web texts (*signalements*,
   *notificaciones*). Check "Ontario" and the incidence definition of the BMJ sentence against the abstract first.
7. **`{event}` in statistic sentences**: the clinical cascade name (the note is for a doctor).
8. **Row 49**: print "(as published)" and add a sentence that Janus checks vitamin B12, magnesium and oral iron.
9. **Outcome page**: one action per finding, with the ingredient names in the action labels.
10. **J1 and J2**: `source` is `janus_curated`; the curated labels are accepted; J2 prints `J01DH51` labelled as the
    combination code.
11. **TİTCK-equal cells**: keep (they come from Wikidata and are correct INN spellings).
12. **Reassurance lists**: accept P1 and the advisory additions (P2–P5).
13. **Pre-launch**: the native-speaker review and the pharmacist or physician review stay on
    `docs/pre-launch-checklist.md`.

### Applied (2026-11-08)
All rows are `accepted` except the three ingredient rows whose keys left the index with the ATC exclusions (Q419020,
Q22075864, Q422241: `rejected`). Wrong ATC codes were fixed first, in `drug-resolution` (`atc-code-review.md`).

- **Point 6, Spanish.** The owner wrote "(signalements, notificaciones)". The reviewed web texts use *informes* in Spanish
  (26 uses, *notificaciones* once), so the note uses *informes*, and *signalements* in French. **To confirm with the
  owner.** "Ontario", the community-dwelling population and the incidence definition were checked against the Crossref
  abstract of BMJ e100499; the abstract gives no denominator for the incidence, and the sentence says none.
- **Example notes** (`example-notes.md`, synthetic patient, five languages) were read after the edits. Three wording
  defects were found and fixed: Turkish timing sentences began with a lower-case ingredient name (now "Ay sayısı, …"),
  the French timing sentence would have needed an elision before a vowel-initial name ("le début de amlodipine" →
  "les deux débuts (A, puis B)"), and the German purpose sentence used "Er" for a feminine noun.
- **Not changed:** the English MedDRA notice stays in English in every language (the ICH text).
