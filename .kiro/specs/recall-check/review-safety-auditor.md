# Safety-auditor review (agent `.kiro/agents/safety-auditor.md`, read-only), 2026-11-10

Automated review pass of the code, the texts in five languages and the spec. Expert review has not yet been done.

Checked clean: no forbidden phrase and no reassurance word in the 38 `Recall.*` texts of any language; the
nothing-found text ends with "does not mean … free of problems" in all five; a lot that is not found never reads as
"not concerned" and keeps the record; the pharmacist sentence is information; "automated" everywhere, no "AI"; the
review sentence equals `TimeMachine.review` in each language; the route is medical, nothing in `janus/recalls/`
logs or stores; the web request body is `{ndc}` only; the serial is still dropped; no `--risk` class; the answer
carries the disclaimer; the registry entry carries the licence, the credit line and FDA's two limits.

| # | Finding | Severity | Resolution |
|---|---|---|---|
| B1 | With records shown, the data date, "United States only", "not an alert service", the status note and the review status were only inside the folded "About this check" | blocking | The method line and the status note are visible under the list; only the coverage sentence is folded |
| B2 | tasks.md and design.md named the review files before they existed | blocking | Review files written; wording "automated read-only passes … Expert review has not yet been done" in requirements, design and tasks |
| A1 | "The lot is in the lot text" stated as a fact while "not found" was hedged | advisory | `Recall.lot.listed` now reads "The automated reading found the lot …" in five languages |
| A2 | The share of records without a product code was folded in the nothing-found state (Req 6.5) | advisory | Shown under the nothing-found line |
| A3 | Translated status labels made "Completed" and "Terminated" near-synonyms under "as published" | advisory | FDA's own word added in brackets in tr, de, fr, es |
| A4 | "Enforcement reports" rendered inconsistently | advisory | The English name kept in every language (see localization review) |
| A5 | No abrupt-stop line beside the notice on the confirm screen | advisory | Not changed: that line comes from the evaluation of the whole list, which does not exist before a medicine is added; on the medicine list the line stands directly above the notice. Open item |
| A6 | A 422 named an unknown key of the request (the client's own text) | advisory | Only `ndc`, `lot` or `body` are named; test added. The same pattern in other routers is not part of this change |
| A7 | The privacy page did not say the lot is kept in the browser | advisory | `Privacy.device.body` names the lot number of a scanned box in five languages |
| A8 | experience Req 10.2 and drug-resolution Req 1.4 not amended | advisory | Dated notes added to both |
| A9 | A private Docker subnet in `deploy/titck-refresh.sh` (existing line) | advisory | Not part of this change; left for the owner |

Not checked by the reviewer: nothing was run or rendered; proxy and service-worker behaviour for the route; real FDA
record text (quoted English text can contain any wording and is shown as a marked quotation).
