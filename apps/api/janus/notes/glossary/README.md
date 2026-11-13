# Clinical glossary of the doctor note (doctor-loop design §5.1)

Six languages (en, tr, de, fr, es, pt). Only rows with `status = accepted` are used; until the owner has accepted the
review sheet (`.kiro/specs/doctor-loop/glossary-review.md`) no note language is available.

| File | Rows | Source |
|---|---|---|
| `ingredients.csv` | ingredient keys that can appear in a finding or an abrupt-stop warning | Wikidata labels of the name index (CC0); `J` keys from `data/janus_ingredients.csv`. No TİTCK string. |
| `cascades.csv` | the 65 PIPC rows: Drug A, adverse event, Drug B in tr, de, fr, es | English: the PIPC list as published (Rochon et al., Eur Geriatr Med 2025, CC BY 4.0), checked by `en_sha256`; translations drafted by the AI assistant and reviewed |
| `sentences.csv` | every template and fixed text of the note and the outcome page | Drafted by the AI assistant and reviewed; `shared` rows equal the message files in `apps/web/messages` |

Event names and safety lines come from `janus/memory/memory_events.csv` (already reviewed) and are not copied here.

Empty ingredient names of one language can be filled from a Wikidata run with
`pipelines/tools/glossary_fill_names.py` (accepted rows only, existing names never changed, checked labels; the row
note records the source and that native-speaker and expert review have not yet been done). Portuguese was filled this way
on 2026-11-13 (1,015 of 1,126 accepted rows now have a pt name).

When a name is missing in a language, the note prints the accepted English INN with "name not translated" and the ATC
code (owner decision 2026-11-08). Clinical terms are never machine-translated at run time.

Status: expert review has not yet been done; needs review by a pharmacist or physician and by native
speakers before any public claim (`docs/pre-launch-checklist.md`).
