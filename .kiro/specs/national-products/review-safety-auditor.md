# Review: safety-auditor pass (automated, read-only)

> Automated pass of `.kiro/agents/safety-auditor.md` over this change, 2026-11-10. Expert review has not yet been done.

| # | Finding | Result |
|---|---|---|
| 1 | `A (B)` with an unmapped `B` could drop a second substance | Fixed: only when `B` starts with the first word of `A` (a salt or form); otherwise left to the ladder. Test `test_n2_unmapped_parenthesis_must_name_a_form_of_the_outer_name` |
| 2 | Ingredient count never checked against the source's own | Fixed: DPD `NUMBER_OF_AIS` differing from the lines, and an AIFA pack text naming an ingredient the lines lack, add an unnamed ingredient (never exact). 3 DPD rows and 0 AIFA packs affected on the real data |
| 3 | DPD strength given as base or as equivalent compared with a salt strength | Fixed: `BASE = Y` (333 lines) and a non-empty `STRENGTH_TYPE` give no strength for comparison |
| 4 | AIFA `1.000` read as 1 or 1000 | Fixed: a whole part above zero with exactly three decimals gives no strength (293 lines) |
| 5 | UNIT versus IU, per mL / per g conversions | Checked: `UNIT` and `IU` never compare; conversions covered by N1 |
| 6 | Per-unit rule rests on the form group | Open, by design (DN5): no form rows for these sources until the owner reviews them, so per-unit strengths are not normalised |
| 7 | Text said "suspended packs" while all non-authorised packs are left out | Fixed in the texts, NOTICE (generated) and data-sources.md |
| 8-10 | DPD status wording, attribution, Canada never on the confirm screen | Checked, no change |
