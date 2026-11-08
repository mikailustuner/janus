# Localization review: doctor-note glossary (task 15)

Reviewer: localization-reviewer agent (read-only), 2026-11-08. Files reviewed: `apps/api/janus/notes/glossary/sentences.csv`
(112 rows), `cascades.csv` (65 rows), `ingredients.csv` (1,129 rows, checked by script), the formatting table in
`apps/api/janus/notes/render.py`, and `REASSURANCE` in `apps/api/janus/notes/phrases.py`. All rows are `proposed`.

Checks run by script (not committed): every `shared` row equals its key in `apps/web/messages/<lang>.json` (no
difference); placeholders are identical across the five languages of every row; no cell of `sentences.csv` or
`cascades.csv` contains a `FORBIDDEN` or `REASSURANCE` phrase of its language; a stem search for inflected and
near-synonym forms of rule 2 found only the abrupt-stop line and the outcome option "stopped" (both allowed: see S-OK).

A native-speaker clinical review (pharmacist or physician per language) is still needed for every language before any
public claim. Items marked **[native]** are ones this review cannot settle.

## Verdicts

| File | Verdict |
|---|---|
| `sentences.csv` | **Not ready.** The four disclaimers are correct. Fix the 7 blocking findings S1–S7 first. |
| `cascades.csv` | **Acceptable** with advisory changes. No blocking finding; terminology is consistent within each language. |
| `ingredients.csv` | **Not ready.** Some English cells, which are the fallback for every language, are not INNs, and some cells hold trade names, junk text or a different substance (I1–I3). Case and spelling need a mechanical pass (I4–I6). |
| `render.py` table | **Correct** for all five languages. Two advisory notes (R1–R2). |
| `REASSURANCE` | **Not ready for Turkish** (P1, blocking); other languages advisory (P2–P5). |

## sentences.csv

**Disclaimer (`disclaimer`, shared `Disclaimer.text`): accepted as is.** Each of the four translations keeps the
two claims and the hedging of the English text. Each uses its language's regulatory term: TR *tıbbi cihaz*, DE
*Medizinprodukt*, FR *dispositif médical*, ES *producto sanitario*. The punctuation follows each language's convention
(DE spaced en dash, ES colon). One optional French polish, not needed for acceptance: "… et non des conseils médicaux.
Prototype de recherche — et non un dispositif médical."

**S-OK (checked, no change).** The abrupt-stop line is present in all five languages and none of them matches a
forbidden phrase: TR "Bu ilacı aniden bırakmayın.", DE "Setzen Sie dieses Arzneimittel nicht plötzlich ab.", FR
"N'arrêtez pas ce médicament brutalement.", ES "No suspenda este medicamento de forma brusca." The rule-3 statement
`scope.no_pattern` keeps the meaning of the English in all languages. The outcome options (`outcome.option.*`) ask what
was done and give no advice. The emergency suffixes work with every value: TR "112'yi / 911'i / 988'i / 988'e" are
correct accusative and dative forms. The other emergency values also read correctly: FR "appelez d'abord le 112", ES
"llame primero al 112 / al número de emergencias local", and DE "wählen Sie zuerst die örtliche Notrufnummer".

### Blocking

**S1. Term for "report", FR and ES. Rows:** `statistics.heading`, `stat.reports_ratio`, `stat.coverage.no_reports`,
`stat.coverage.insufficient`, `statistics_unavailable`, `about.versions`, `about.faers`, `outcome.limits`. These rows
use FR *déclarations* and ES *notificaciones*. The shared Memory rows in the same statistics section use *signalements*
and *informes*, and so does the whole web app (FR 27, ES 26 occurrences). The result is two terms for one concept in
one section. Suggested fix: align these rows to the reviewed web terms, for example FR "{reports} signalements citent
…", "Signalements à la FDA AEMS (anciennement FAERS)", "nombres de signalements"; ES "{reports} informes citan …",
"Informes a FDA AEMS (antes FAERS)". **[native]** to confirm that *signalement* and *informe* are acceptable to French
and Spanish doctors; if not, change the web texts and these rows together.

**S2. `stat.absence` (shared `Memory.codes.absence_is_not_reassurance`), all languages.** Inside a doctor note,
"…that your medicines are free of problems" refers to the doctor's own medicines. Suggested fix: use a note-only row
(drop `shared`) that follows `scope.no_pattern`:
EN "No reports, or a pattern that is not clear, does not mean there is no association or that the patient's medicines
are free of problems." TR "…ilişki olmadığı ya da hastanın ilaçlarında hiçbir sorun olmadığı anlamına gelmez." DE
"…oder dass die Arzneimittel der Patientin oder des Patienten frei von Problemen sind." FR "…ni que les médicaments du
patient sont exempts de problèmes." ES "…ni que los medicamentos del paciente estén libres de problemas."

**S3. `stat.denominator` (shared `Memory.codes.denominator_mapped_reports`), all languages.** The last sentence,
"Figures for all reports are shown beside these.", is false in the note. A `StatRow` carries one set of figures
(`build.py` `statistics()`). Suggested fix: use a note-only row that keeps the first two sentences and drops the third
in every language.

**S4. Safety section with shared patient texts (`safety.urgent_care_*`, `safety.crisis_support`), all languages.**
These texts speak to the patient ("If your face or lips swell, you find it hard to breathe…"; TR "Yüzünüz…", FR "si
vous avez du mal à respirer"). Under the heading "Urgent symptoms" a doctor reads them as addressed to the doctor.
Keep the shared texts (one reviewed source) and change only the note's `safety.heading`:
EN "Urgent symptoms: information shown to the patient"; TR "Acil belirtiler: hastaya gösterilen bilgi"; DE "Warnzeichen:
Information für die Patientin oder den Patienten"; FR "Symptômes urgents : information destinée au patient"; ES
"Síntomas urgentes: información para el paciente".

**S5. `{event}` in `stat.reports_ratio`, `stat.coverage.no_reports` and `stat.coverage.insufficient`, all
languages.** `{event}` is filled with the lay event label from `memory_events.csv` (`build.py` line 320). These labels
are capitalized phrases in the nominative. German therefore breaks the case after *mit*: "zusammen mit Schwindel oder
niedriger Blutdruck beim Aufstehen" and "mit Hoher Blutzucker". EN, TR, FR and ES put a capital letter mid-sentence,
for example "with Swollen ankles or legs (peripheral edema)". Suggested fix: quote the label as the name of an event.
EN "… name {ingredient} with the event “{event}”". TR "… {ingredient} ile “{event}” olayı birlikte yer almaktadır". DE
"… nennen {ingredient} zusammen mit dem Ereignis „{event}“". FR "… citent {ingredient} avec l'événement « {event} »".
ES "… citan {ingredient} junto con el evento «{event}»". The pharmacologist may prefer the clinical cascade name from
`cascades.csv` here instead of the lay label. That change would also remove the register gap, for example DE
*Obstipation* in the finding line and *Verstopfung* in the statistic line.

**S6. `header.prepared`, DE.** "Von Janus im 03.2026 … erstellt" is ungrammatical: *im* needs a month name. Suggested:
"Erstellt von Janus (Stand {month}) aus den von der Patientin, dem Patienten oder einer betreuenden Person eingegebenen
Arzneimitteln."

**S7. `outcome_loop.how` and `outcome.stored_fields`, DE.** *Daten* means both "data" and "dates". As written, "ohne
Namen oder Daten" and "keine genauen Daten" say that no data is stored, which is false. Suggested: "… ohne Namen und
ohne genaues Datum." and "Keine Namen, kein genaues Datum und nichts über Sie." Also align EN `outcome_loop.how`
("without names or dates") with `outcome.stored_fields` by writing "without names or exact dates".

### Advisory

**S8. `finding.cascade`, en/tr/fr/es.** The sentence starts with `{index}`. A lower-case INN therefore opens the
sentence ("amlodipine followed by …"). Suggested: EN "Starting {index} and then {marker} matches …"; TR "Önce {index},
ardından {marker} başlanması, yayımlanmış bir reçeteleme kaskadı örüntüsüyle örtüşmektedir: {drug_a} → {event} →
{drug_b} (PIPC listesi, satır {row})."; FR "Séquence observée : {index}, puis {marker} ; elle correspond au schéma
publié …" (avoids "de" + vowel elision); ES "El inicio de {index} seguido de {marker} coincide …". DE is unaffected
because German nouns are capitalized.

**S9. `outcome_loop.coverage`, de/fr/es.** With `{covered}` = 1 the text reads "die ersten 1", "les 1 premiers", "los
primeros 1". Suggested wording, as in design §4.4: EN "The QR code covers patterns 1 to {covered} of {total}."; DE "Der
QR-Code umfasst die Muster 1 bis {covered} von {total}."; FR "Le code QR couvre les schémas 1 à {covered} sur {total}.";
ES "El código QR cubre los patrones 1 a {covered} de {total}."; TR "QR kod, {total} örüntüden 1 ile {covered} arasındakileri kapsar."

**S10. `stat.reports_ratio`, ES and parity.** ES *razón de probabilidades* means "ratio of probabilities", which is a
different quantity. Suggested: "razón de odds de notificación (ROR)". Only TR adds "(ROR)". Add "(ROR)" in all five
languages for parity (EN "reporting odds ratio (ROR)", FR "rapport de cotes de signalement (ROR)"). **[native]**

**S11. `finding.priority.*`, FR and ES.** "intervalle de confiance {low} à {high}" lacks *de*; use "intervalle de
confiance de {low} à {high}" and ES "intervalo de confianza de {low} a {high}".

**S12. `header.title`, `header.purpose` and `about.heading`, DE and FR.** DE *Hinweis* means a notice or hint.
Suggested: "Information zur Medikationsprüfung für die behandelnde Ärztin oder den behandelnden Arzt", with
"Diese Information …" and "Über diese Information" to match. FR: the established term is *revue de la médication*;
suggested title "Note de revue de la médication à l'attention du médecin". **[native]**

**S13. `header.prepared`, FR and ES.** "Préparée en 03/2026" and "Preparada en 03/2026" are understandable but
awkward. Suggested: FR "Préparée par Janus ({month}) à partir des médicaments …"; ES "Preparada por Janus ({month})
a partir de …".

**S14. FR *schéma* for "pattern" (all FR rows).** In French clinical writing *schéma* usually means a regimen (*schéma
posologique*), so a doctor may misread it. Options: keep it, or use "profil de cascade de prescription". **[native]**

**S15. DE: *Verschreibungskaskade* and *Verordnungssequenzstudien* are used together.** The German text mixes
*Verschreibung* and *Verordnung*. Pick one term: German geriatric literature also uses *Verordnungskaskade*. **[native]**

**S16. Clinical register in `finding.form_extension` and `findings_form_unconfirmed.*`.** Suggested changes:
- "can act in the whole body" → EN "can have systemic effects", DE "systemisch wirken kann", FR "peut avoir un effet
  systémique", ES "puede tener efecto sistémico", TR "sistemik etki gösterebilen".
- "product form" → FR *forme galénique*, ES *forma farmacéutica*.

**S17. `not_checked.*`, FR.** "…, ne peut pas être vérifiée" has no clear subject in some rows. Suggested uniform
tail: "…, vérification impossible".

**S18. `abrupt_stop`, TR.** The note uses two verbs for "stop" in Turkish: *bırakmak* here and *kesmek* in
`outcome.option.stopped` ("İlaç kesildi"). Patient leaflets use *kesmek*. Suggested: "Bu ilacı aniden kesmeyin." This
form does not match the forbidden phrase "ilacınızı kesin".

**S19. Minor wording.**
- `outcome.limits`: TR adds "yanıttan" (groups of 20 *answers*); add the noun in EN ("groups of at least 20 answers")
  and in the other languages.
- `stat.pts`, DE: German MedDRA uses *Bevorzugte Begriffe* ("MedDRA-Preferred-Terms (bevorzugte Begriffe)").
- `stat.source_may_be_outdated` (shared) says "FAERS", while the heading says "FDA AEMS (formerly FAERS)". This is
  acceptable; align it when the web text is next revised.
- `safety.heading`, DE: *Warnzeichen* reads more clinical than *Dringende Beschwerden* (see S4).

## cascades.csv

Terms are consistent within each language: one term per drug class across rows. Examples: TR *inhibitörü*, DE
*-Hemmer*, FR *Inhibiteur de …*, ES *Inhibidor de …*; NSAID as NSAİİ / NSAR / AINS / AINE; hypertension as
*Hipertansiyon* / *Hypertonie* / *Hypertension artérielle* / *Hipertensión*. The register is clinical. Turkish
mirrors the lay English items ("Cough remedy" → *Öksürük ilacı*), which is acceptable. No forbidden or reassurance
phrase was found. All findings below are advisory.

**C1. Rows 2 and 56, FR.** "dizziness" is translated as *vertiges* (vertigo). The reviewed event label uses
*étourdissements*. Suggested: "Hypotension orthostatique/étourdissements" and "Hypotension orthostatique,
étourdissements".

**C2. Row 20 ("tardive movements"), all four languages.** FR *mouvements tardifs* and ES *movimientos tardíos* read as
"late movements". The event label uses *dyskinésie tardive* / *discinesia tardía* / *tardif diskinezi* /
*Spätdyskinesie*. Suggested: FR "Akathisie ou mouvements anormaux tardifs", ES "Acatisia o movimientos anormales
tardíos", TR "Akatizi veya tardif hareket bozuklukları"; DE is acceptable. **[native]**

**C3. Rows 10, 48 and 65, FR.** *Supplément* is an anglicism. Suggested: "Complément minéral", "Complément
vitaminique", "Supplémentation en fer". **[native]**

**C4. Row 56 ("Vestibular suppressant").** DE *Vestibuläres Sedativum* → *Antivertiginosum*; ES *Supresor vestibular*
→ *Sedante vestibular (antivertiginoso)*; TR *Vestibüler baskılayıcı* → *Vestibüler supresan*. FR *Antivertigineux* is
acceptable. **[native]**

**C5. Row 57, TR.** *Tükürük yerine geçen ürün* → *Yapay tükürük*.

**C6. Rows 44 and 54, ES.** The rows write *cardiaca*, while the reviewed event label writes *cardíaca*. Both
spellings are correct, but the note should use one; suggested: *cardíaca*.

**C7. Row 15.** FR *Corticoïde local* → *Dermocorticoïde*. ES *Exantema* differs from the event label and safety line
(*erupción cutánea*); this is acceptable in clinical register, but confirm. **[native]**

**C8. Row 49.** Drug B equals the adverse event ("Vitamin or Mineral Deficiency") as published, and the translations
copy it faithfully. The note line will read "PPI → deficiency → deficiency". This is a pharmacologist decision: keep
the text as published, with a footnote, or not.

**C9. Minor wording.**
- Row 23, TR: *Bilişsel bozulma* → *Bilişsel bozukluk*.
- Row 62, TR: *kandidiyaz* → *kandidiyazis*.
- Row 41, FR and ES: "SGLT2" drops the hyphen of "SGLT-2"; this is acceptable.

## ingredients.csv (script check)

Coverage of non-empty cells: en 1,129; tr 447; de 770; fr 840; es 710. Every row is `proposed`, `en_alt` is empty
everywhere, and no row has a note.

### Blocking

**I1. English cells that are not INNs (54 with stereo or locant prefixes).** English is the fallback printed in every
language (DP16), so these cells reach every note. Examples:
- Q3515 "(RS)-rabeprazole", Q409468 "(RS)-metoprolol", Q326224 "(S)-(−)-colchicine", Q413994 "(S)-(−)-timolol" and
  Q407646 "D-(-)-mannitol" should drop the prefix.
- Q417227 "(S)-etiracetam" should be *levetiracetam*, an antiepileptic on the abrupt-stop list.
- Q402633 "(±)-deprenyl" should be *selegiline*, but the racemate is not the same substance as the INN. The
  pharmacologist must confirm the key identity.
- Q598713 "(Z)-dothiepin" → *dosulepin*; Q2608288 "(Z)-thiothixene" → *tiotixene*; Q238544 "5-HTP" → *oxitriptan*.
- Q423809 holds Wikidata note text inside the label ("… according to WHO INN RL 40, conflated wikidata").

DE has 53 cells with the same prefixes and FR 36 (for example Q409468 DE "(RS)-Metoprolol"). Suggested fix: strip the
descriptors at review, set INN-differing US names in `en_alt` (for example Q386441 *meclizine* → en *meclozine*,
en_alt *meclizine*), and use *acetylsalicylic acid* for Q18216 (see I2).

**I2. Trade names, junk text or a different substance in a cell.** Reject or replace these cells; trade names are not
quoted here:
- Trade names in place of the INN: en Q2034113, Q29006606, Q139890384, Q139890449; tr Q409468, Q55186498; es Q1060922.
  Q18216 en and tr hold a common name that is a trademark in some countries instead of *acetylsalicylic acid*.
- Corrupted or extra text: tr Q417884 (extra word and digit after the INN), tr Q422071 (not a Turkish name; →
  *guar zamkı*), de Q1452256 ("levo", truncated; → *Levosulpirid*), de Q5404460 ("Ethyl Ioflazepat", capital I for l;
  → *Ethylloflazepat*).
- Inflected form: tr Q411932 "duloksetinin" (genitive) → *duloksetin*.
- Wrong substance or chemistry: tr Q214863 "Demir tuzu" ("iron salt") → *demir(II) sülfat*; fr Q413739
  "pentahydroxyéthanoate de calcium" → *gluconate de calcium*; fr Q414547 "salicyclate" → *salicylate de sodium*.
- Q579348 is labelled "Prostaglandin E1" in tr, de and fr, while PIPC row 4 names *alprostadil*. Use *alprostadil* in
  every language.
- tr Q152763 "Lityum (ilaç)" carries a Wikipedia disambiguation tag → *lityum*.

**I3. Labels in the wrong language.**
- tr cells in English: Q204954, Q421291, Q416237, Q3563148, Q2062094. Turkish forms: *çinko sülfat*, *demir glukonat*,
  *flunarizin*, *vortioksetin*, *pramlintid*.
- es cells in English or French (11): Q58375, Q198473, Q250442, Q411932, Q416545 (French), Q593166, Q600951, Q904011,
  Q2787672, Q3836403, Q4708345. Spanish forms: *tioridazina*, *ziconotida*, *metilcobalamina*, *duloxetina*,
  *asenapina*, *molindona*, *xipamida*, *desonida*, *tebacona*, *lofexidina*, *alaproclato*.
- fr cells without the French ending: Q166476, Q409558, Q409595, Q409898, Q5030940. French forms: *darifénacine*,
  *méthyprylone*, *isocarboxazide*, *dapagliflozine*, *canagliflozine*.

The 98 tr and 349 fr cells that equal the English spelling are mostly correct, since many INNs are spelled the same.
Only the cells listed above are wrong.

### Advisory

**I4. Capitalization.**
- Upper-case first letter where lower case is the convention: tr 366 of 447 (for example "Metformin", "Kalsiyum
  Karbonat"), es 476 of 710 ("Nifedipina"), fr 102 of 840 ("Metformine", "Sildénafil"), en 23 of 1,129 (Q847560,
  Q3492616 "Insulin Lispro"; botanical binomials such as Q158289 are correct).
- de: lower-case first letter in 2 of 770 cells (Q290001 "gliclazid", Q1452256).
- Suggested: one mechanical pass at review, lower case except binomials and acronyms. In Turkish, use Turkish case
  rules ("İ" → "i", "I" → "ı"); Python `str.lower()` turns "İ" into "i̇".

**I5. Format.**
- es Q155472 and Q410074 hold two names in one cell ("valsartán, valsartano"); keep one (AEMPS: *valsartán*,
  *losartán*).
- tr "İnsülin - Degludec" pattern (Q410965, Q417317, Q16252338) → *insülin detemir/glarjin/degludek*.
- de Q15628111 "Eisen(III) citrat" → *Eisen(III)-citrat*; de Q214863 "Eisen-sulfat" → *Eisen(II)-sulfat*.
- de Q607349 "Fluorometholone" → *Fluorometholon*; de Q188154 "Pektine" (plural) → *Pektin*.

**I6. Greek letters and digits.** These are acceptable as chemical names: 1 Greek-letter cell each in de, fr and es
(Δ-9-…), and digits in 14 de, 8 en, 5 fr, 3 tr and 3 es cells. Q419020 is a synthetic cannabinoid code. The
pharmacologist should confirm that it belongs in a cascade class.

## render.py formatting table

The table matches CLDR conventions:
- Decimal separators: en ".", the others ",".
- Grouping: en ","; tr and de "."; fr U+202F; es "." from 5 digits (CLDR minimum grouping 2).
- Percent: en "11.9%"; tr "%11,9" (sign first, correct for Turkish); de and es "11,9 %" with NBSP; fr "11,9 %" with
  U+202F.
- Numeric months (MM/YYYY, MM.YYYY) and day-first dates are correct for tr, de, fr and es. ISO dates in English are a
  sound choice for a readership split between US and UK conventions.

**R1 (advisory).** Quarter values (`quarter` type, `stat.window`) pass through unlocalized, for example "2025Q3". That
is acceptable because the shared web text does the same. Localized forms would be DE "Q3/2025", FR "T3 2025", ES
"T3 2025", TR "2025/3. çeyrek". Change them together with the web if wanted.

**R2 (advisory).** Months in running prose need a template that tolerates a numeral; see S6 and S13. No change to
`render.py` is needed.

## REASSURANCE (phrases.py)

Whole-word matching (the same as `findForbiddenPhrases`) misses inflected forms. Any word added to a list must not
match a required rule-3 statement. Today `stat.absence` TR contains *sorunsuz* and `scope.no_pattern` FR contains
*sans problème*.

**P1 (blocking), TR.** The Turkish list misses the predicative and suffixed forms that Turkish uses in almost every
statement: "güvenlidir", "güvenle", "zararsızdır", "sorun yoktur", "sorun bulunmamaktadır", "risk yok", "risksiz",
"tehlikesiz", "endişelenecek bir şey yok". Add these as explicit forms. Do not switch to prefix matching: the prefix
*tanı* (forbidden list) would then block *tanınan*, *tanınmadı* and *tanımlanmaktadır*, which appear in five current
rows, and *güvenli* would block *güvenliği* ("safety"). Add *sorunsuz* only after rewording the TR `stat.absence` text
(for example "…ilaçlarında hiçbir sorun olmadığı…", as S2 already proposes).

**P2, EN.** Add "no problem" (singular), "no issues", "safely", "risk-free", "no risk", "nothing wrong", "no cause
for concern", "no need to worry".

**P3, DE.** Add the adjective endings "sichere", "sicheren", "sicheres", "unbedenkliche", "unbedenklichen",
"harmlose", "harmlosen", plus "ungefährlich", "unproblematisch", "kein Problem", "keine Bedenken", "kein Risiko",
"risikolos", "bedenkenlos", "alles in Ordnung", "kein Grund zur Sorge". Note that "sicher" also blocks the hedge "nicht
sicher" (uncertain); writers must use *eindeutig*, as the drafts already do.

**P4, FR.** Add "sûre", "sûrs", "sûres", "inoffensive", "inoffensifs", "inoffensives", "sans risque", "aucun risque",
"pas de problème", "rien à craindre", "rien d'inquiétant". Add "sans problème" after `scope.no_pattern` FR is reworded
to "…sont exempts de problèmes" (matching `stat.absence`). "sûr" also blocks "pas sûr"; acceptable.

**P5, ES.** Add "segura", "seguros", "seguras", "inocuo", "inocua", "inocuos", "inocuas", "inofensiva",
"inofensivos", "inofensivas", "sin riesgo", "sin riesgos", "sin problema", "ningún problema", "no hay problema", "nada
de qué preocuparse", "todo en orden". "seguro" also blocks the hedge "no es seguro que…" and the noun "seguro médico";
writers must use *con certeza*, as the drafts do.

**P6 (advisory, steering owner).** The forbidden lists have the same whole-word gap, and changing them requires a
change to `medical-safety.md` and `forbidden-phrases.ts` (parity test). Examples:
- DE "absetzen Sie" never matches the main-clause order "Setzen Sie … ab". A pattern rule would need an exception for
  the negated abrupt-stop line.
- TR "ilacı bırakınız", "ilacı kesin" and "tanısı" are not caught.
- FR "cessez de prendre" and ES "suspenda el tratamiento" / "interrumpa" are not caught.

No current row uses any of these forms.

## Native-speaker clinical review still needed

Before any public claim, every language needs a native-speaker clinical review. In particular:
- FR and ES report terms (S1);
- the ROR terms (S10);
- the DE title and the *Verordnung* / *Verschreibung* choice (S12, S15);
- FR *schéma* (S14);
- cascade rows 15, 20, 56 and the French supplement terms (C2–C4, C7);
- the Turkish name of row 57 (C5);
- every ingredient cell after the mechanical pass (I4).
