# Report Assistant review: safety-auditor

**Date:** 2026-11-09
**Reviewer:** safety-auditor (`.kiro/agents/safety-auditor.md`), run as a separate read-only agent pass against
`medical-safety.md`, `privacy.md` and `product.md`. The reviewer edited no files and did not run tests.

## Scope

Spec (requirements, design), `data/report_channels.csv`, `apps/web/src/report/*.ts`,
`components/report/ReportAssistant.tsx`, the links added to `DoctorForm`, `FindingCard`, `FindingDetail` and
`Medicines`, and the `ReportAssistant` / `Doctor.report` texts in five languages.

## What holds

- The emergency notice is first (112 / 911 by region); the rule-10 safety line comes before the draft.
- No pressure and no advice: reporting is "your own choice", a report "passes on a suspicion; you do not need to
  prove…", same meaning in all five languages; no "should" or "must report"; "as far as you want to answer them".
- No forbidden phrase in any language (whole-word scan; "tanım…" is not "tanı").
- The disclaimer is in the Shell footer and inside the printed draft; print shows only the draft, the demo stamp, the
  not-sent sentence and the disclaimer.
- Nothing sent and nothing stored: React state only, no fetch, storage, analytics or usage tally (DP8).
- Fragments carry key-pattern codes and item positions only; the parser drops anything else and never throws. The
  doctor link is a plain `<a>` in a new tab; `/o` gains no state and sends nothing.
- Every mapped native label is in its CSV field list; UNVERIFIED rows yield no mapping, options or required list.
  Form 3500 and the TÜFAM professional form are named, not linked. FDA `/media/85598`, not `/media/76299`; the legacy
  French domain is not used. No MedDRA term.
- The death options of the TÜFAM forms (A9): the authority's own answers, not preselected, labelled as the form's
  answers, plain and consistent translations. Acceptable.

## Findings and what was done

| id | Severity | Finding | Done |
|----|----------|---------|------|
| A1 | advisory | "Address and questions checked on {date}" also showed for forms whose questions were not checked (French portal, German online form), contradicting the note under it. | **Fixed:** `channel.checkedAddress` ("Address checked on {date}…") when no field mapping applies; five languages. |
| A2 | advisory | NotificaRAM fields come from the official manual, not the live form, but the row was `verified` and the screen said nothing. | **Fixed:** row is `derived`; `derived` now means "an official description of the form (definition file or user manual)" in the meta file, DP4 and the on-screen note (`channel.derived`, five languages). |
| A3 | advisory | The NotificaRAM required item `one-of(… Cree que las reacciones que comunica…)` had one alternative and a truncated label, shown as "a question Janus does not fill". | **Fixed:** removed from `required_fields`; the notes say the requirement exists and that its full label is UNVERIFIED. |
| A4 | advisory | A real doctor link opened in a browser that is in demo mode was labelled "Demo · synthetic patient — do not submit". | **Fixed:** in the doctor view only the fragment's `demo=1` sets the demo label. |
| A5 | advisory | For "Another EU country" the button "Open the official form" opened the EMA guidance page, not a form. | **Fixed:** `draft.openGuidance` ("Open the EMA guidance") for guidance channels. |
| A6 | advisory | Suggests adding that the reviewed studies were "mostly about reporting by health professionals". | **Not applied:** the abstract checked does not say so; the statistician review (S2) forbids a claim either way until the full text is read. On the pre-launch checklist. |
| A7 | advisory | P2 says every URL shown is a CSV URL; the DOI citation link is not. | **Fixed in the spec:** P2 names the DOI link as the one exception. |
| A8 | advisory | The vocabulary chunk is a same-origin static request while the assistant is open; Req 6.1 said "no network request". | **Fixed in the spec:** Req 6.1 now says nothing is sent to `/api` or another origin; the app's own static files are excepted. The e2e asserts exactly that. |

## Not checked by the reviewer

Tests, axe, Playwright and a real print preview (all run by the implementer afterwards: see tasks.md); the live
official sites (the CSV was relied on).
