# CDS Hooks service: safety-auditor review

**Date:** 2026-11-09 · **Reviewer:** safety-auditor (`.kiro/agents/safety-auditor.md`), a separate read-only agent
pass over `apps/api/janus/cds/` (cards, discovery texts, errors, extraction), `docs/cds-hooks.md`,
`docs/cds-hooks-example.json`, the checklist section and this spec, against `medical-safety.md`, `privacy.md`,
`product.md`. No files edited by the reviewer. The MCP part of the same pass is in
`.kiro/specs/mcp-server/review-safety-auditor.md`. **0 blocking, 6 advisory (CDS).**

| # | Finding | Severity | Action |
|---|---|---|---|
| S1 | Rule 3: an empty `{"cards": []}` shows no text, but nothing said that silence is not an all-clear | advisory | **Fixed:** discovery `description` and `usageRequirements` and `docs/cds-hooks.md` say "Janus shows a card only when it finds a pattern from its rule list; no card does not mean the medicines are free of problems." |
| S2 | `not_provided` (prefetch key absent or an OperationOutcome) was computed but never shown, so a card could appear although the medication statements were never read | advisory | **Fixed:** "Not read: medication statements (not provided by the EHR)." (or current medication requests) on every card |
| S3 | `warning` fired only on `probable`, which cannot happen without start dates and would contradict the timing line | advisory | **Fixed:** `indicator` is always `info` (model `Literal["info"]`); requirement 4.3, design §6 and DP7, docs updated |
| S4 | Rule 6: `dataset:faers` appears among the evidence ids without the spontaneous-reporting caveat | advisory | **Fixed:** "FAERS (in the evidence ids): spontaneous reports, not incidence, not deduplicated across cases." when FAERS is listed |
| S5 | "Clinical decision support used in a clinic is regulated software" overstates the position (FDA enforcement discretion, non-device CDS) | advisory | **Fixed:** "Clinical decision support shown to clinicians can be regulated as a medical device (US FDA Clinical Decision Support guidance, revised 29 Jan 2026; EU MDR Annex VIII Rule 11, at least class IIa)." |
| S6 | The sandbox demo suggested "a tunnel of your choice", which would put an unauthenticated medical endpoint on the internet | advisory | **Fixed:** "put the API behind a local https proxy. Do not expose it through a public tunnel: the service has no client authentication." |

**Reviewer's judgements:** English-only cards are acceptable (CDS Hooks has no language field; readers are
clinicians; DP13). The emergency line is not needed on cards (clinicians, ordering; no symptom input). "This may be
worth considering in a medication review." is acceptable for a clinician audience (a clinician activity, no advice
to start, stop or change).

**What holds (reviewer):** no forbidden phrase in any CDS text or doc (five-language list; "safe" and "people" only
in negations); the framing line (a pattern, not an assessment); the PIPC row citation (locator, published text, CC
BY citation, DOI link) and evidence ids; the BMJ figure with its 95% CI; the abrupt-stop text from
`ABRUPT_STOP_TEXT`; the disclaimer and "Not for clinical use." in every detail and in the source label; no
suggestions or actions; labels from Janus, not from the EHR's display text; medical routes (`no-store`, access line
only, exception class only on a 500); 422 bodies with field paths and unknown keys as `<unknown>`; stateless; no
call to the FHIR server, `fhirAuthorization` never read; the checklist covers regulatory, JWT, Art. 28 and marketing
items.

**Not checked by the reviewer:** the tests (read-only pass: P5 and P8 were run by the author afterwards and pass);
whether a retracted PIPC or ThinkCascades source suppresses a card (the engine's integrity filter; `PIPC_CITATION` is
a fixed text naming the rule base's source); the API logging setup outside the middleware.
