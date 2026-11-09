# Historian review pass — Time Machine

> **AI review pass**, not a human review. Performed by the `historian` agent profile
> (`.kiro/agents/historian.md`) on 2026-11-09 against the pinned OpenITI text
> (`0428IbnSina.QanunFiTibb.Shamela0010706-ara1`, commit 81d1d9e0, CC BY-NC-SA 4.0), the séance
> package, and the built artifact. Verdicts: **accept**, **correct**, **reject**.

## Scope reviewed
Which substances were taken forward and why, the dose statements read out of Book 2, the
conversion of historical units, the condition bridges, and every claim about what the Canon says.

## Verdicts

### 1. Substance choice — **correct**
St John's wort and vinegar come from the séance's `matches_gold` identifications, which is the
right basis. Rhubarb and anise were added because their entries state a dose — a legitimate
reason, but it means two of the four substances were **not** part of the séance's reviewed
identification set and have had no identification pass of their own.
**Correction:** rhubarb (`rawand`, `canon.b2.h0693`) and anise (`anisun`, `canon.b2.h0027`) need
the same identification treatment as the séance substances: a Janus identification, a gold
comparison where one exists, and an uncertainty label. `rawand` in particular is not a settled
identification — the Canon's own entry says it is brought from China and discusses adulteration,
and the medieval `rawand` covers *Rheum palmatum*, *R. officinale* and probably *R. ribes*
depending on region. Treating it as *R. palmatum* / *R. officinale* (the two the EMA monograph
covers) is defensible but must be labelled uncertain. Added to the checklist.

### 2. The dose statements — accept
Both readings are correct against the pinned text. Rhubarb, `canon.b2.h0693`, section
`آلات المفاصل` (joints): *"قال الخوزي: والشربة درهمان في طلاء ممزوج"* — "al-Khuzi said: the dose
is two dirhams in a mixed syrup", in the context of falls, blows, muscle tears and ruptures.
Anise, `canon.b2.h0027`, closing line: *"والشربة التامة مفردا نصف درهم"* — "the full dose on its
own is half a dirham". Both are machine translations and are labelled as such. Accept.

### 3. Attribution inside the text — **correct**
The rhubarb dose is explicitly attributed by Ibn Sina to **al-Khuzi**, not asserted in his own
voice. That matters for a feature whose premise is "what the Canon says": this is the Canon
reporting an earlier authority.
**Correction:** the artifact note for the rhubarb scenario should name al-Khuzi as the authority
the Canon cites. Added to the checklist (a one-line note, no code change).

### 4. Unit conversion — accept with the caveat kept visible
Carrying a range rather than one value is the right decision, and the range is well chosen:
2.80–3.30 g for the dirham spans the Umayyad coin standard through the later Persian weight
unit, with the central 2.975 g derived correctly as 7/10 of the 4.25 g mithqal (Bates 1995).
Two caveats are correctly recorded and must stay: the Hinz values (3.125 g, 4.464 g) were
verified only from indexed footnote snippets of Bos 1996, not from the article itself; and
Bates states plainly that the weight-dirham was often not the coin-dirham, so an 11th-century
*medical* dirham is not pinned down by coin evidence at all. The range absorbs this, but the
uncertainty is real and should not shrink later without a source.

### 5. "Sharba" treated as a drink, not a unit — accept
Correct. `الشربة` is the draught or dose, not a defined mass, and the build does not model it as
one. The only verifiable reading is the one used: the amount named in dirhams *within* the
sharba phrase.

### 6. Condition bridges — **correct**
The bridges are labelled interpretive, which is right, but two are weaker than the table admits.
- Rhubarb's dose sits in the **joints** section and the text names falls, blows, muscle tears
  and hernia — mapping that to modern oral NSAIDs for musculoskeletal pain is reasonable.
- Anise: the Canon's `أعضاء النفض` and wind/colic material is a carminative use. Mapping it to
  **dicyclomine and hyoscyamine for irritable bowel syndrome** imports a modern diagnostic
  category that has no counterpart in the Canon. IBS is a 20th-century construct; "wind and
  colic" is a symptom description.
**Correction:** the anise bridge note must say the modern comparator is matched on *symptom*
(gut spasm and wind), not on a shared diagnosis, and that IBS has no Canon counterpart. Added to
the checklist.
- St John's wort's sciatica material (`آلات المفاصل`: *"ينفع من وجع الورك وعرق النسا"*, and the
  forty-day regimen) is correctly read, and the bridge to neuropathic pain is correctly flagged
  interpretive. Note the Canon claims a cure here (*"فإنه يبرىء عرق النسا"*) — the build must
  never repeat that as a claim, and it does not: St John's wort has no dose scenario and no
  verdict.

### 7. Licensing of the ancient material — accept
Nothing derived from the OpenITI text was written under `data/`. The new tables hold only
substance ids, entry ids, amounts and units — facts about where a statement sits, not the text.
No Arabic text and no Hamdard material entered the Time Machine's own files; the quotations in
this review are short and cited, which the licence allows. The CC BY-NC-SA package remains the
only home of the text. Accept.

### 8. Framing of the whole feature — accept
The direction is right: the Canon statement is the *starting point* of a modern in-silico
question, never evidence for a modern conclusion. The output contains no claim that an ancient
remedy works, no "treatment for", and no cure language. The one patient-facing sentence concerns
modern adverse-event reports only and says nothing about history at all, which is the correct
separation. "Time machine" as a name is a presentation device, not a claim of continuity.

### 9. What this pass could not check
Whether the two added substances' identifications match any gold table (no gold rows exist for
rhubarb or anise in PMC3941892); whether `rawand` in Ibn Sina's sources means the same plant the
EMA monograph covers; and the Hinz values at source. All three are expert items.

## Summary
Accept 4, correct 4, reject 0. The build does not overstate what the Canon says, and the
licensing is clean. The required changes are labelling, not retraction: identify the two added
substances properly with uncertainty, name al-Khuzi as the cited authority for the rhubarb dose,
and stop implying the Canon knew irritable bowel syndrome.
