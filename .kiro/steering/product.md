---
inclusion: always
---

# Product: Janus — the two faces of a side effect

Janus reads the medicines in a person's home — by scanning the code on the box or the pharmacy label, or by name — in **three regions: Türkiye, the European Union and the United States**, and:

1. **Shadow face — Ghost Diseases.** Finds prescribing cascades: a side effect of drug A mistaken for a new condition and treated with drug B. Produces a one-page, fully cited note for the patient's doctor, in the doctor's language.
2. **Collective Memory.** Shows how often the same medicines and events appear together in public adverse-event reports (FDA FAERS from day one), plus consented, pseudonymous Janus contributions (shown only as noisy counts of groups of at least 20) and outcomes reported through doctor notes (not verified) — always as **reports**, never as "people like you".
3. **Light face — Dead Drugs Rise.** For researchers: turns the same side-effect knowledge around to surface drug-repurposing **hypotheses**, and proves its method by rediscovering known repurposings.
4. **The Séance — Three Witnesses.** A hypothesis is strong only when three independent witnesses agree: the past (Ibn Sina's Canon, Book 2, and sampled Ottoman texts), the present (Collective Memory) and science (molecular evidence).
5. **Evidence Integrity — no zombie evidence.** Every source Janus cites is checked against retraction data (Crossref / Retraction Watch) and stamped with its version date. Janus never warns a patient on the basis of a retracted paper.
6. **Passport — one medicine list across borders.** The same list works with boxes from Türkiye, the EU and the US mixed together; Janus shows the equivalent ingredient in the other regions and writes the doctor note in the doctor's language (EN, TR, DE, FR, ES).

Vision line: *"Billions of people take medicine combinations at home every day — the largest clinical trial in history. Nobody reads the results. Janus reads them, starting with the moment a side effect is mistaken for a new disease."*

## Regions
- **Türkiye:** İTS DataMatrix → TİTCK list.
- **United States:** DSCSA DataMatrix / NDC → openFDA NDC directory; pharmacy-label OCR and name search (most patients receive vials, not boxes).
- **European Union:** country adapters. France (BDPM, CIP13) and Spain (CIMA, national code) resolve codes from open data; Germany and other countries resolve by on-device OCR and name search (no open product-code database found).
- Ingredient identity across regions uses one shared key: Wikidata item (CC0) linked to ATC and RxNorm.

## Users
- Caregiver of an older relative on many medicines (primary), in any of the three regions.
- Older adult (large text, voice, simple steps).
- People living across borders (e.g. Turkish families in Germany) and travellers with boxes from two countries.
- Family doctor (reads the note in 2 minutes, in their own language; reports the outcome via QR without an account).
- Researcher (repurposing hypotheses, open dataset of aggregated counts).
- Hackathon judge (a built-in demo mode with sample codes; judges will not have Turkish boxes).

## Product rules
- Janus **informs; it never diagnoses or treats.** Every screen and the doctor note say so.
- Janus is a **research prototype, not a medical device** (not FDA-cleared, not CE-marked). See `medical-safety.md` for the regulatory language rules.
- Every finding is linked to evidence (rule, paper, statistic, text). No evidence, no sentence. Retracted evidence is never used for a patient-facing finding.
- Repurposing outputs are researcher-facing and always labelled **"candidate worth investigating — not a treatment"**.
- Website first: works in a mobile browser with nothing to install (PWA).
- Halloween theme is functional, not decoration: ghosts = cascades, two-faced mask = shadow/light switch, séance table = evidence synthesis, zombie stamp = retracted evidence. Tone is mysterious and reassuring, never frightening for patients. Avoid a "flashlight in the dark" motif (SpookBnB, Kiroween 2025).

## Claims we must not make
- "First AI prescribing-cascade detector", "first repurposing from side effects / patient reports", "first retraction checker", "first data-mining of Islamic or Ottoman medicine", "we mined Ottoman manuscripts", "cure", "diagnosis", "we solve a global problem", "N people like you" (FAERS counts reports).
- Safe claim: *"To our knowledge, the first consumer product that detects prescribing cascades from the medicine box's code across Türkiye, the EU and the US, produces a cited doctor note in the doctor's language, and — with consent — returns people's experiences both to other patients and to drug-repurposing research."*
- Safe framing of impact: *"Medication harm is a global patient-safety problem (WHO). Cascade tools so far serve clinicians; Janus brings the same knowledge to the person at home and turns it into a note the doctor can read in two minutes."*
