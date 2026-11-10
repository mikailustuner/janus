# Review: safety-auditor pass (ocr-first)

> 2026-11-10. Automated review with the `.kiro/agents/safety-auditor.md` role, read-only, on the working tree
> before the first commit. Expert review has not yet been done.

## Findings and what was done
| # | Severity | Finding | Resolution |
|---|---|---|---|
| 1 | blocking | `ConfirmPage`: after the chosen ingredient is listed first, the card read with `view.cards[chosen]` (array position) was not the card the user tapped (`chosen` is the index in the resolution). A different candidate could be added. | Fixed: the card is found by its `index`. The e2e test now puts the chosen ingredient second in the API answer and checks the stored item's ingredient key. |
| 2 | blocking | "Delete everything on this device" left the label result (recognised words) in memory; the scan screen showed it again. | Fixed: `deleteEverything` clears the label result and the pending resolution; starting the demo clears the label result. Unit test added. |
| 3 | blocking | `Confirm.tryOther` promised success ("You can still add this box … Both work …"), also under a name search that had just found nothing. | Reworded in five languages: "There are other ways to try … These two ways do not depend on the country of the box." |
| 4 | blocking | "Any country" was untrue for boxes printed only in non-Latin scripts. | `Scan.anyCountry`, `Home.how1`, `Start.intro` now carry "printed in Latin letters"; `Scan.labelLead` says that Janus reads Latin letters only and can misread a word. Requirements Introduction and Req 1 updated. |
| 5 | advisory | Turkish "her kutuda işe yarar" was stronger than the other languages. | Reworded (also a localization finding). |
| 6 | advisory | `Start.intro`: "any other country" / "can be added" unconditional. | "A box from another country can be tried with …, if the name is printed in Latin letters", aligned in five languages. |
| 7 | advisory | `Scan.ocr.privacy`: "Only the name you choose is sent" left out chosen words and NDCs. | "Only the name, words or NDC you choose are sent." in five languages. |
| 8 | advisory | "reviewed names" in spec and comments could imply review by a person. | Wording changed to "accepted glossary names" (the glossary's status column) in the new texts. |
| 9 | advisory | `tasks.md` cited review and evaluation files that did not exist yet. | The files exist now. |
| 10 | advisory | A debugging test file was left in `src/scan/eval/`. | Removed. |

## Checked and found in order
Forbidden phrases in the new keys of five languages; no advice, reassurance or diagnosis; no "AI" and no wording
that implies a person checked a candidate; the code claim limited to "the product lists Janus holds"; the only
way from a label result to a request is `outboundOf` (the chosen ingredient's English name, a chosen NDC or the
chosen words; plus the region setting and `limit`); no logging and no storage of label text; the recogniser's
cache is off; the privacy page stays true; no candidate is selected for the user in the label panel, the scan
screen, `confirmView` or the confirm screen; the disclaimer and the emergency notice are untouched.

## Not checked by this pass
Rendered screens and axe (covered by `e2e/ocr-first.spec.ts`); whether the API accepts names typed in non-Latin
scripts; native-speaker quality of the texts.
