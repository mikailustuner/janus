# Review: products with the same active ingredient in another country (2026-11-10)

Two automated review passes over Requirements 14–17, design §15, the new code and the `Passport.products` messages
in five languages, run with the reviewer definitions of `.kiro/agents/safety-auditor.md` and
`.kiro/agents/localization-reviewer.md` (read-only). **Expert review has not yet been done**: no pharmacist,
physician or native-speaker clinical reviewer has read these texts or the comparison rules.

## Safety pass

| # | Finding | Severity | Outcome |
|---|---|---|---|
| S1 | ES used "dosis" for the listed strength ("Misma dosis indicada"), which reads as "same dose". | blocking | Fixed: the new ES strings say "cantidad" ("Misma cantidad en el listado"), also in the caution text, the counts, the entry count and the automated-comparison note. The existing keys of the detail screen still use "dosis" (not changed here; see open items). |
| S2 | Req 16.3: the salt and base note was only in the aside, below the rows on a phone. | advisory | Fixed: the note is shown with the counts, above the rows, whenever products are listed (render test). |
| S3 | Nothing on screen explained the order of the list. | advisory | Fixed: `notes.order` in five languages ("The order is not a recommendation."). |
| S4 | The caution title "Before you take a product from this list" presupposed taking one. | advisory | Fixed: "Before you use this list" in five languages. |
| S5 | A product without a published name would show an empty bold line. | advisory | Fixed: "not stated" is shown instead. |

Checked without findings: `same` and `different` only with codes on both sides; the "different" flag is text with its
own icon; the pharmacist-or-doctor sentence and "no dosing advice, no dose conversion" precede the list in every
state; no substitution, reassurance or forbidden word; "automated", never another term; the disclaimer; request
content (keys, codes, target, page); no logging; TİTCK is not a target and no TİTCK content is in the recorded demo
file; attribution with the data date wherever products are listed.

## Localization pass

No blocking finding. Applied: DE `caution.notSame` ("Das macht es noch nicht zum selben Medikament"), DE
`caution.confirm` (one construction; "anwenden", since the list can hold products that are not swallowed), DE
"Darreichungsform nicht verglichen", "Abweichende Formgruppe", "Rohware", "automatisiert"; ES "automatizada", "sin
dato"; FR plural for "non comparé(s)", "aucune indication", "substances actives" twice, "D'autres produits …"; TR
"diğer bileşenleri", "doz dönüşümü yapmaz", "listede gösterilmez".

## Open items
- The existing key `Passport.compareReason.not_known_in_source` is composed into the new "not compared" lines; in DE
  and ES its pronoun does not agree with the noun before the colon ("Wirkstärke … gibt ihn", "Dosis … no lo
  indica"). Not changed here: this branch only adds message keys, other branches edit the same files.
- ES: the detail screen's existing keys call the strength "dosis"; the product list now says "cantidad". One term
  should be chosen for both.
- `.kiro/steering/product.md` item 6 says "the equivalent ingredient"; the screens say "the same active ingredient".
- Coined terms ("form group" and its translations) and the lay words for strength (TR "miktar") need a
  native-speaker clinical reviewer.
