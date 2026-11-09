# CDS Hooks service and MCP wording: pharmacologist review

**Date:** 2026-11-09 · **Reviewer:** pharmacologist (`.kiro/agents/pharmacologist.md`), a separate read-only agent
pass over `apps/api/janus/cds/` (mapping, extraction, cards), the new repository queries, `design.md` and
`apps/mcp/janus_mcp/safety.py`, against `medical-safety.md`, `tech.md`, `data-sources.md`. No files edited by the
reviewer. Live observations given to the reviewer: RxNorm 308135 (135 products, one signature) and 310429 (92
products, 2 without ingredients) map; ATC N02BE01 (two keys) and C09BB03 (combination) are not checked.

| # | Finding | Severity | Action |
|---|---|---|---|
| P1 | An order coded only by ATC (e.g. S01ED01, timolol eye drops) mapped to the ingredient key, which carries every code of the substance (C07AA06 oral timolol too); the engine reads them all, so the eye-drop form was lost | blocking | **Fixed:** an ATC-coded order whose key's codes span more than one anatomical group is not checked (`form_mismatch`, `mapping._one_key_for_form`); test `test_form_of_an_atc_code_is_not_lost` |
| P2 | `form_confirmed` was not shown on the card, so a clinician could not tell a product-level match from an ingredient-level one | blocking | **Fixed:** "Dose form not confirmed: Janus matched X by ingredient only; the pattern may not apply to eye, skin or other local forms." on every card with an unconfirmed side (P4 property checks it) |
| P3 | The product list for an RxCUI was cut to 501 before empty products were dropped, so a code could be mapped after comparing only part of its products | blocking | **Fixed:** more than 500 products → `None` from the lookup → `ambiguous_code`; no partial comparison (`test_too_many_products_are_not_compared`) |
| P4 | The signature left out `atc_selection` and compared by position, so the same combination listed in another order was "ambiguous" and form-confirmed and unconfirmed products counted as equal | advisory | **Fixed:** sorted multiset of (status, key, rule codes, atc_selection) (`test_signature_ignores_ingredient_order`) |
| P5 | When the selected order is drug A and drug B is already listed, the published direction (A before B) may not hold | advisory | **Fixed with P6:** the timing line now says "The pattern applies only if B was started after A." The card stays (the clinician is about to add the index drug of a known pattern) |
| P6 | The timing line did not say why the order matters | advisory | **Fixed:** see P5 |
| P7 | On-hold requests were labelled "active", and the prefetch asked for `status=active` only | advisory | **Fixed:** label "current medication request (active or on hold)"; prefetch `status=active,on-hold` |
| P8 | The not-checked count left out the items the engine could not check (homeopathic, ambiguous positions, route) | advisory | **Fixed:** the count adds the distinct items of `result.not_checked`; wording "no code Janus could match to one ingredient, or an ingredient Janus cannot check" |
| P9 | When the selected order itself cannot be mapped, `{"cards": []}` cannot be told from "checked, no pattern" | advisory | **Not changed (owner requirement):** the owner specified "no card for lists without a cascade"; an EHR shows nothing for an empty list, so there is no reassuring text. Documented in `docs/cds-hooks.md`; listed for the clinical review on the pre-launch checklist |
| P10 | The same ingredient once as a product (NDC) and once as a key (RxCUI) becomes two items | advisory | **Not changed:** findings are de-duplicated by id, so a card is not repeated; the origin text may name one of the two. Left for the clinical review |
| P11 | The MCP wording explained `status` but not `form_confirmed` | advisory | **Fixed:** a `janus_check_cascades` line says that `form_confirmed: false` means the dose form was not confirmed and must be said |

**What holds (reviewer):** the coding order NDC → RxNorm → ATC (SCD/SBD carry the dose form, e.g. PIPC row 3); the
same-signature rule (not too loose; differences within one SCD come from route-filtered code selection, which must
be refused); leaving out products without ingredients; combinations broken into ingredients through the product and
combination ATC codes refused; homeopathic products in the signature and never evaluated; the patient and status
filters; the indicator rule (`info` without dates, never `critical`); the card wording (possible prescribing
cascade, pattern framing, medication-review line, abrupt-stop text word for word, PIPC citation, BMJ figure with
95% CI, disclaimer; no forbidden phrase, no verdict); the MCP safety texts.

**Not checked by the reviewer:** whether `res_ingredient` holds combination items with MIN/PIN RxCUIs (they would
reach the engine without codes: not dangerous); how `atc_selection` handles ophthalmic routes on real openFDA rows;
the PIPC texts and BMJ figures themselves; the tests (read-only pass). A pharmacist or physician review of the
mapping and wording is on the pre-launch checklist.
