# How a GS1 DataMatrix carries the French CIP13 and the Spanish national code

> Research record, 2026-11-08. Input for the Phase 2 `eu_fr` and `eu_es` adapters of
> `drug-resolution` (Req 4.1, 4.2); nothing is built from it yet. No French or Spanish box was
> available, so every claim rests on official or semi-official documents and on the open data
> files themselves. Each claim has a status: **verified** (document and data agree), **document
> only**, or **not verified**. The pipelines that supply the lookup data are `eu_fr_bdpm` and
> `eu_es_cima` (`data-pipelines` Req 11, 12).

## Summary

| Question | Answer | Status |
|---|---|---|
| France: what is in AI (01)? | GTIN-14 = `0` + the 13-digit CIP13. CIP13 starts `3400`; the fifth digit `9` marks the presentation of an authorised specialty. | verified |
| France: does the check digit change? | No. The GS1 check digit of `0` + CIP13 equals the EAN-13 check digit of the CIP13 (a leading zero adds nothing to the sum). All 20,918 CIP13 in the BDPM pass both checks. | verified (data) |
| France: is CIP13 still what a serialised box carries? | Yes, per the national agency in 2025; the DataMatrix holds the CIP code with serial, lot and expiry. | document only (no box seen) |
| Spain: what is in AI (01)? | Either an **NTIN** = `0847000` + 6-digit national code (CN) + GS1 check digit, which embeds the CN; or a company **GTIN** with the CN given separately in AI (712). | verified |
| Spain: how long is the CN in AI (712)? | 7 digits: the 6-digit CN followed by its control digit, no dot or separator. | document only |
| Spain: can a GTIN be mapped to a CN without AI (712)? | Yes for most serialised presentations: AEMPS publishes the product codes (GTIN or NTIN) per CN in the Nomenclátor. | verified (data) |
| Spain: the CN control-digit algorithm | Not found in an official text. Not needed: the NTIN and GTIN have GS1 check digits, and the CN is looked up by its first six digits. | not verified |
| AI numbers 710 to 714 (national reimbursement numbers) | Five AIs are reserved for national healthcare reimbursement numbers; 712 is Spain's CN. 715 is the US NDC (GSCN 21-289, already used in `drug-resolution`). Which of 710, 711, 713 and 714 belongs to which country is not confirmed here. | 712 and 715 verified; others not verified |

## France

1. **CIP13 structure.** A CIP13 starts with `3400` in France; the digit after it says what the
   presentation is (9 = human-use presentation with a marketing authorisation; 1 to 5 homeopathic
   laboratories; 8 = hospital dispensing units). Sources: SNDS documentation (fiche médicament),
   which lists the digit values; ANS report on the codification of medicines (the code "commence
   par le préfixe 3 400 suivi du 9"). Data: all 20,918 CIP13 of `CIS_CIP_bdpm.txt` (BDPM of
   2026-11-07) start `34009`, are distinct and pass the EAN-13 check.
2. **GTIN-14 form.** The CIP Club's technical note of December 2008 (Cahier n°2) writes the
   DataMatrix content as `(01)0CIP13(17)YYMMDD(10)batch`: AI (01) holds a zero followed by the
   CIP13. A GTIN-14 is a 14-digit number whose first digit is the indicator digit; indicator `0`
   plus a GTIN-13 is the standard way to write a GTIN-13 as GTIN-14. Check digit: the GS1 mod-10
   rule weights digits from the right, so a leading zero does not change it. Verified on all
   20,918 CIP13 (`"0" + cip13` passes the GTIN-14 check).
3. **After EU serialisation (9 February 2019).** The Ordre national des pharmaciens states that
   the unique identifier contains serial number, CIP code, lot and expiry date, encoded in a
   DataMatrix. The ANS report (decision of the steering committee, 9 April 2025) says the
   DataMatrix holds the CIP code, that GS1 lets the GTIN structure be used for French codes, and
   that the current codification is kept. It also records that the agreement allowing the
   `3400` prefix ended at the end of 2021 and lists scenarios (GTIN plus a correspondence table)
   that were not chosen.
4. **Design input for the `eu_fr` adapter.**
   - Accept a GTIN-14 matching `^0(3400\d{9})$` whose check digit is valid; the key is the
     last 13 digits, looked up in `eu_fr_bdpm.cip13`.
   - Any other GTIN is not a French CIP: answer "not found" with the region and the BDPM date;
     do not guess.
   - If France ever moves to GTINs with a correspondence table, BDPM files carry no GTIN, so the
     adapter would need a new source. The risk is recorded in the ANS report.
   - BDPM names are French and give salt forms; the `FT` line of a composition (therapeutic
     fraction) is the moiety linked by number to its `SA` line (`data-pipelines` DP23).

## Spain

1. **National code (CN).** Six digits plus a control digit; AEMPS note MUH 04/2022 states that
   the CN (as NHRN) must always have 7 digits, the 6-digit CN followed by the control digit, and
   that six digits alone are invalid. The Nomenclátor `cod_nacion` holds the 6 digits only (all
   30,900 values on 2026-11-07).
2. **Two ways to carry the CN in the unique identifier.** AEMPS note MUH 10/2017 and MUH 04/2022:
   - product code is an **NTIN**: the CN is part of it, and AI (712) must not repeat it. The NTIN
     always starts `0847000`;
   - product code is a **GTIN**: the CN goes in AI (712), the fifth data element of the unique
     identifier.
   GS1 Spain describes the NTIN as prefix `847000`, then the CN, then a check digit, and shows
   the element order of a serialised Spanish pack: (01) GTIN, (17) expiry, (10) lot, (21) serial,
   (712) CN. GS1 Spain notes that the prefix belongs to Farmaindustria; AEMPS only calls it the
   NTIN prefix.
3. **NTIN as a GTIN-14.** `0` + `847000` + CN (6 digits) + check digit = 14 digits, so the CN
   sits at positions 8 to 13 of the AI (01) value. Data (Nomenclátor of 2026-11-07): 17,855 NTIN
   values; all pass the GS1 check; 17,853 start `0847000` and have 14 digits; 17,850 embed the
   presentation's own `cod_nacion`; 5 embed a different one; 2 NTINs are published on two
   presentations; 1 value has 13 digits and 1 has 14 digits without the prefix.
4. **GTIN packs.** The Nomenclátor lists 4,773 GTIN values (4,686 of 14 digits, 80 of 13, 7 of 12;
   all pass the check; none shared; 174 presentations list several; 210 presentations list both
   an NTIN and a GTIN; 8,703 list neither, for example products without serialisation). AEMPS
   states that the product code of each CN is published in the Nomenclátor XML.
5. **Design input for the `eu_es` adapter** (order of trust, never a guess):
   1. AI (01) found in the NTIN table: candidates = every presentation that publishes it
      (table lookup, because 5 NTINs embed another CN);
   2. else AI (01) found in the GTIN table (padded to 14 digits): candidates likewise;
   3. else AI (712) present: take the first six digits as the CN, look up `cn`, and label the
      match as coming from AI (712) (the seventh digit is not validated, see below);
   4. else AI (01) matches `^0847000\d{7}$` with a valid check digit: look up the CN from digits
      8 to 13 and label it as derived from the digits (less certain than the table);
   5. else "not found".
   The AEMPS Nomenclátor is refreshed daily; the adapter shows its date.
6. **Control digit of the CN: not verified.** Candidate rules tested against the 17,853 NTINs
   whose embedded CN equals `cod_nacion` (comparing with the last digit of the NTIN, which is a
   GS1 digit over 13 digits and so not the same quantity): GS1 weights over the six digits alone
   matched at most once; a position-weighted sum matched about 10 % (chance). No official algorithm
   was found. The adapter does not need it.

## Sources (read 2026-11-08)

France
- CIP ACL, *Implementation of traceability of medicinal products for human use – Questions and
  Answers*, Cahier n°2, December 2008:
  https://www.cipmedicament.org/wp-content/uploads/2018/01/CIP-Cahier-n%C2%B02-Mise-en-oeuvre-Tra%C3%A7abilit%C3%A9-V1.1-anglaise.pdf
- Agence du Numérique en Santé, *Codification du médicament* (impact study, decision of 9 April
  2025): https://esante.gouv.fr/produits-services/ci-sis/rapport-codification-du-m%C3%A9dicament
- Ordre national des pharmaciens, *Authentification des médicaments à usage humain : la
  « sérialisation » entre en application le 9 février 2019*:
  https://www.ordre.pharmacien.fr/les-communications/focus-sur/les-actualites/authentification-des-medicaments-a-usage-humain-la-serialisation-entre-en-application-le-9-fevrier-2019
- SNDS documentation, *Identification des médicaments (codes CIP)*:
  https://documentation-snds.health-data-hub.fr/snds/fiches/medicament
- BDPM download page and files (`CIS_bdpm.txt`, `CIS_CIP_bdpm.txt`, `CIS_COMPO_bdpm.txt`):
  https://base-donnees-publique.medicaments.gouv.fr/telechargement

Spain
- AEMPS, *La AEMPS actualiza la información a incluir en la aplicación de notificación de
  comercialización de medicamentos y sobre dispositivos de seguridad*, MUH 04/2022:
  https://www.aemps.gob.es/informa/la-aemps-actualiza-la-informacion-a-incluir-en-la-aplicacion-de-notificacion-de-comercializacion-de-medicamentos-y-sobre-dispositivos-de-seguridad/
- AEMPS, *Implementación de los dispositivos de seguridad en las autorizaciones de
  comercialización de los medicamentos de uso humano*, MUH 10/2017:
  https://www.aemps.gob.es/informa/notasinformativas/industria-2/2017/ni-muh_10-2017-implementacion/
- GS1 Spain, NTIN: https://www.gs1es.org/estandares-gs1-identificar/ntin/ and NHRN:
  https://www.gs1es.org/estandares-gs1-identificar/nhrn/
- AEMPS Nomenclátor de prescripción (daily): https://listadomedicamentos.aemps.gob.es/prescripcion.zip
- AEMPS, CIMA REST API v1.19: https://sede.aemps.gob.es/docs/CIMA-REST-API_1_19.pdf
- AEMPS legal notice (reuse with source and update date): https://www.aemps.gob.es/aviso-legal/

GS1
- GSCN 21-289 (AI 715, US NDC as NHRN), already cited in the design of `drug-resolution`. The
  GS1 General Specifications and gs1.org were not readable from the research environment, so the
  AI 710 to 714 assignments other than 712 remain to be confirmed from them.

## What would change this record
- A photo or scan of a real French or Spanish box (the owner has none); until then the adapters
  ship with the documented rules and the labelled lower-trust paths above.
- An AEMPS or GS1 document with the CN control-digit algorithm.
- The French codification scenario changing (ANS report); recheck at each yearly review.
