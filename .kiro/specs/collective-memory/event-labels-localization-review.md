# Event label localization review (collective-memory)

- Date: 2026-11-08
- Reviewer: localization-reviewer (read-only; this report is the only file written)
- File read: `apps/api/janus/memory/memory_events.csv` (39 rows: 34 adverse, 5 benefit; columns label_en, label_tr, label_de, label_fr, label_es). Other columns ignored.
- Role file read: `.kiro/agents/localization-reviewer.md`. Rules applied: `.kiro/steering/medical-safety.md` rule 2 and the word lists in `apps/web/src/i18n/forbidden-phrases.ts`.
- Scope: clinical terms, register, grammar, ambiguity, parity with English, forbidden phrases. No file other than this report was changed, including the CSV.
- A review of this kind is done independently of the earlier run, whose text was lost.

Blocking fixes are marked **BLOCKING**. Everything else is advisory. All replacements are final text: NFC, no leading or trailing spaces, under 200 characters, and none speaks of people or patients.

## Findings

| key | language | current | verdict | replacement | reason |
|---|---|---|---|---|---|
| akathisia_tardive_movements | fr | Impatiences ou mouvements involontaires (akathisie, dyskinésie tardive) | **FIX (BLOCKING)** | Agitation intérieure ou mouvements involontaires (akathisie, dyskinésie tardive) | In French "impatiences" is the usual lay word for restless legs (impatiences des jambes). It does not mean inner restlessness, so a reader would think of a different condition. "Agitation intérieure" matches "Innere Unruhe" and "Inquietud interna". |
| oedema | tr | Sıvı tutulumu veya şişlik (ödem) | **FIX (BLOCKING)** | Vücutta sıvı tutulması veya şişlik (ödem) | "Tutulum" means involvement of an organ (akciğer tutulumu), not retention. "Fluid retention" is "sıvı tutulması" (lay) or "sıvı retansiyonu" (clinical). The current wording is a wrong term and reads oddly to a lay reader. |
| peripheral_oedema | tr | Ayak bileği veya bacaklarda şişlik (periferik ödem) | FIX | Ayak bileklerinde veya bacaklarda şişlik (periferik ödem) | Number mismatch: singular "ayak bileği" next to plural "bacaklarda". The plural is the natural form for "ankles". |
| insomnia | tr | Uyku sorunu (uykusuzluk) | FIX | Uyumakta zorluk (uykusuzluk) | "Uyku sorunu" is broader than "difficulty sleeping" (it also covers sleepiness, apnoea, restless sleep). The English and the PTs mean trouble falling or staying asleep. |
| insomnia | de | Schlafstörung (Schlaflosigkeit) | FIX | Schwierigkeiten beim Ein- oder Durchschlafen (Schlaflosigkeit) | "Schlafstörung" is a general term that includes sleep apnoea and excessive sleepiness. The PTs are insomnia only. |
| extrapyramidal_symptoms | tr | Sertlik, yavaşlama veya anormal hareketler (ekstrapiramidal belirtiler) | FIX | Kas sertliği, yavaşlamış veya anormal hareketler (ekstrapiramidal belirtiler) | Bare "sertlik" is vague, and in Turkish it is also the lay word for erection hardness, which sits next to the erectile dysfunction label in the same form. "Yavaşlama" is a noun for slowing of anything. "Yavaşlamış hareketler" matches the English adjective. |
| osteoporosis_fracture | tr | Zayıf kemikler (osteoporoz) | FIX | Kemik erimesi (osteoporoz) | "Zayıf kemikler" is a calque. "Kemik erimesi" is the established lay name for osteoporosis in Turkish. |
| seizures | tr | Nöbet | FIX | Nöbet geçirme (konvülsiyon) | "Nöbet" alone is ambiguous: duty shift (nöbetçi), panic attack, migraine or asthma attack. Adding "geçirme" and the term gives the seizure meaning, and it matches the Spanish "convulsiones". Epilepsy PTs are excluded, so "epileptik nöbet" would be too narrow. |
| seizures | en | Seizures (fits) | FIX | Seizures (convulsions) | "Fits" is British informal and can read as a fit of anger or a clothing term. Source change; the de, fr and es labels already match "convulsions". |
| hyperglycaemia | fr | Hyperglycémie (taux de sucre élevé dans le sang) | FIX | Taux de sucre élevé dans le sang (hyperglycémie) | Register and pattern: every other label puts the lay phrase first and the medical term in brackets. This one puts the clinical word first. |
| hypertension | fr | Hypertension artérielle | FIX | Tension artérielle élevée (hypertension) | Lay phrase first, with the term in brackets. It also matches "baisse de tension" in the dizziness label. |
| hypertension | es | Hipertensión (presión arterial alta) | FIX | Presión arterial alta (hipertensión) | Same pattern issue: the clinical word is first and the lay phrase second. |
| vitamin_mineral_deficiency | de | Niedriges Vitamin B12, Magnesium oder Eisen | FIX | Niedriger Spiegel an Vitamin B12, Magnesium oder Eisen | "Niedriges Eisen" is not idiomatic. A level (Spiegel) is low, not the substance. The PTs are laboratory decreases. |
| vitamin_mineral_deficiency | fr | Carence en vitamine B12, magnésium ou fer | FIX | Taux bas de vitamine B12, de magnésium ou de fer | "Carence" is deficiency, stronger than the English "low". Several PTs are plain decreases in a level. |
| arrhythmia | en | Irregular heartbeat (arrhythmia) | FIX | Fast or irregular heartbeat (arrhythmia) | The key includes Ventricular tachycardia, Ventricular fibrillation and Torsade de pointes. These are fast, and not always irregular. German "Herzrhythmusstörung" already covers them, so en, tr, fr and es are narrower than de. All four replacements below must be applied together. |
| arrhythmia | tr | Düzensiz kalp atışı (aritmi) | FIX | Hızlı veya düzensiz kalp atışı (aritmi) | Parity with the en change above. |
| arrhythmia | fr | Rythme cardiaque irrégulier (arythmie) | FIX | Rythme cardiaque rapide ou irrégulier (arythmie) | Parity with the en change above. |
| arrhythmia | es | Latido cardíaco irregular (arritmia) | FIX | Latido cardíaco rápido o irregular (arritmia) | Parity with the en change above. |
| tremor | tr | Ellerde veya vücutta titreme (tremor) | OK (doubtful) | none | "Titreme" alone also means shivering (from cold or fever). The words "ellerde" and "(tremor)" resolve it. Keep both. |
| tremor | fr | Tremblements | OK (doubtful) | none | Can also mean shivering or trembling with fear. Standard medical word for tremor; acceptable as a bare label. A native check is advised. |
| tremor | es | Temblor | OK (doubtful) | none | In parts of Latin America "temblor" is an earthquake. Medical context and the form make the meaning clear; keep. |
| tremor | de | Zittern (Tremor) | OK | none | "Zittern" also covers shivering; the bracketed term fixes it. |
| dizziness | tr, de, fr, es | (see CSV) | OK (doubtful) | none | "Schwindel" and "baş dönmesi" may mean spinning. The label adds the low-blood-pressure reading, so it covers both. French "étourdissements" is light-headedness; both senses are present. |
| rhinorrhoea | es | Secreción nasal | OK (doubtful) | none | Standard term. "Goteo nasal" or "moqueo" is more lay, and "secreción" could include congestion. Acceptable. |
| cognitive_impairment | fr, es | Troubles de la mémoire ou de la réflexion / Problemas de memoria o de pensamiento | OK (doubtful) | none | "Réflexion" and "pensamiento" are acceptable lay words for thinking. Neither implies a thought disorder strongly enough to change the meaning. |
| genital_fungal_infection | en | Genital yeast infection (thrush) | OK (doubtful) | none | English says "yeast", the other four say "fungal" (broader). The PTs are nearly all Candida, so the difference is small. |
| genital_fungal_infection | tr | Genital mantar enfeksiyonu | OK (doubtful) | none | "Genital bölgede mantar enfeksiyonu" would be more natural, but the current text is understandable. |
| gout_hyperuricaemia | fr | Goutte ou acide urique élevé | OK | none | "Goutte" is the correct word for gout. |
| gastritis | tr, fr, es | Mide iltihabı / Inflammation de l'estomac / Inflamación del estómago | OK (doubtful) | none | The English "lining" is dropped. These are the standard lay names for gastritis. |
| heart_failure | all | Heart failure and its translations | OK (doubtful) | none | Lay readers sometimes read "heart failure" as "heart stopped". The terms are standard in all five languages; a note on the screen may help. |

Everything not listed above is OK with no doubt: cough, erectile_dysfunction, constipation, urinary_incontinence, myalgia_myositis, nausea, rash, depression, diarrhoea, joint_pain, urinary_retention, gastrointestinal_upset, gastric_ulcer_bleed, dry_mouth, psychosis_hallucinations, gastritis (en, de), and the five benefit keys. The listed OK entries are the only places where I had a doubt.

## Cross-language consistency

- **Same meaning in all five languages for every key except:** insomnia (tr and de broader), arrhythmia (de broader than en, tr, fr, es), akathisia (fr said something else), oedema (tr wrong term), vitamin_mineral_deficiency (fr "carence" stronger than "low"), seizures (tr ambiguous). Replacements above fix each one.
- **Pattern "lay phrase (medical term)":** used in most labels. Exceptions are the hypertension labels in fr and es and the hyperglycaemia label in fr, which are fixed above. Keys with no bracket (cough, nausea, tremor in some languages) are lay-standard words and need none.
- **Spelling per language:** de (Ödem, Akathisie, Spätdyskinesie), fr (œdème, hyperglycémie, akathisie), es (edema, acatisia, discinesia), tr (ödem, akatizi, tardif diskinezi, miyalji, miyozit) are all each language's standard spelling. The English source uses British spelling in "oedema" (two labels) and "Diarrhoea". The app also serves the US, where "edema" and "diarrhea" are standard. Not an error, since MedDRA uses the British forms; the owner should decide whether en labels follow en-US. If yes: "Swollen ankles or legs (peripheral edema)", "Fluid retention or swelling (edema)", "Diarrhea".
- **Number and gender:** checked. Fr "Chevilles ou jambes gonflées" and "Douleurs ou inflammation musculaires" agree. Es "Tobillos o piernas hinchados" and "Vitamina B12, magnesio o hierro bajos" use the masculine plural, which is correct for mixed nouns. De "Niedriges Vitamin B12, Magnesium oder Eisen" agrees in the neuter, but the wording is fixed above for idiom.
- **Benefit labels:** same meaning in all five. Style in Turkish alternates between "Ağrıda azalma" / "Şişlikte azalma" and "Daha az mide bulantısı". Both are correct. For uniformity, the owner could use "Daha az ağrı" and "Daha az şişlik" (optional, no change required).
- **Label versus PT scope (outside language review, for the owner):** gastric_ulcer_bleed says "stomach ulcer" but its PTs also include duodenal and peptic ulcer, and the three Gastritis PTs overlap with the gastritis key. cognitive_impairment excludes dementia, and "Memory or thinking problems" does not say so. This does not affect translation parity.
- **People and patients:** no label refers to people, persons or patients in any language.

## Forbidden-phrase scan

Method: a small Python script read the CSV with the csv module and the five word lists parsed from `apps/web/src/i18n/forbidden-phrases.ts`. It tested all five label columns for every row (39 rows).

1. **Exact scan, whole words, case-insensitive,** with the same boundary rule as `findForbiddenPhrases` (not preceded or followed by a letter).
   - en: stop taking, you should stop, discontinue, unnecessary medicine, cure, cures, treatment for, diagnosis, you have, safe to stop, your medicines are safe
   - tr: ilacı bırakın, ilacınızı kesin, gereksiz ilaç, tedavi eder, tanı, ilaçlarınız güvenli
   - de: absetzen Sie, nicht mehr einnehmen, unnötiges Medikament, heilt, Diagnose
   - fr: arrêtez de prendre, médicament inutile, guérit, diagnostic
   - es: deje de tomar, medicamento innecesario, cura, diagnóstico
   - Result: 0 hits.
2. **Stem scan (substring, lower case) for inflected and near-synonym forms:**
   - en: cure, curing, treat, diagnos, you have, your medicines, stop, discontinu, safe, all clear, no problem, should, people, patient, person
   - tr: tanı, teşhis, tedavi, bırak, "kes ", kesin, gereksiz, güvenli, insan, hasta, kişi, iyileş
   - de: absetz, einnehm, unnötig, heil, diagnos, sicher, menschen, patient, person, behandl
   - fr: arrêt, inutile, guéri, diagnos, sûr, personne, patient, traite, gens
   - es: deje, innecesari, cura, diagnós, seguro, personas, paciente, trata, gente
   - Result: 0 hits.
3. **Format checks:** NFC, no leading or trailing whitespace, no double spaces or line breaks, length at most 200. Result: 0 problems. Counts: 39 rows, 34 adverse, 5 benefit.
4. **Manual read:** no label says "you have", reassures, diagnoses, or advises starting, stopping or changing a medicine. Labels name events only. Depression, arrhythmia, seizures and skin rash use event words, not diagnostic statements, and the safety lines are handled outside these labels.
5. Limits: the scan covers only the five label columns. The replacements above were written to avoid every scanned word and stem.

## Needs a native speaker

- tr: "Vücutta sıvı tutulması", "Kemik erimesi", "Nöbet geçirme (konvülsiyon)", "Uyumakta zorluk", "Kas sertliği" (register for older adults), and whether "sanrı" and "tardif diskinezi" are understood by a lay reader or need a plainer gloss.
- de: "Niedriger Spiegel an …" for older adults; "Spätdyskinesie" and "Knochenschwund" as lay terms.
- fr: "Agitation intérieure" for akathisia; "Troubles de l'érection" versus "Difficultés d'érection"; "Rythme cardiaque rapide ou irrégulier".
- es: usage of "Temblor" for tremor in US Spanish; "Secreción nasal" versus "Goteo nasal"; regional choice between "presión arterial alta" and "tensión alta".
- All languages: whether bare "Heart failure" and its translations frighten or mislead older readers.
- Pre-launch checklist: native clinical check of all 39 rows in each language stays required. This review cannot replace it.

## Summary of blocking items

1. fr `akathisia_tardive_movements`: replace "Impatiences" with "Agitation intérieure".
2. tr `oedema`: replace "Sıvı tutulumu" with "Vücutta sıvı tutulması".

All other findings are advisory.

VERDICT: approved with changes
