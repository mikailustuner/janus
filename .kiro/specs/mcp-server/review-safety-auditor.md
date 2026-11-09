# MCP server: safety-auditor review

**Date:** 2026-11-09 · **Reviewer:** safety-auditor (`.kiro/agents/safety-auditor.md`), a separate read-only agent
pass over `apps/mcp/janus_mcp/` (safety block, instructions, tool descriptions, errors, logging, configuration),
`docs/mcp.md`, `.kiro/settings/mcp.json` and this spec, against `medical-safety.md`, `privacy.md`, `product.md`. No
files edited by the reviewer. The CDS part of the same pass is in `.kiro/specs/cds-hooks/review-safety-auditor.md`.
**0 blocking, 3 advisory (MCP).**

| # | Finding | Severity | Action |
|---|---|---|---|
| S7 | Rules 2 and 4 in five languages: the texts are English and model-facing, but assistants often answer in TR/DE/FR/ES; "word for word" would push an assistant to quote English to a Turkish user | advisory | **Fixed:** "pass it on next to that medicine, word for word or as a faithful translation in the person's language."; new wording line: "These rules apply in every language you answer in; never call a medicine unnecessary and never say that the medicines are safe or that there are no problems." |
| S8 | Rule 1: an assistant may repeat "probable cascade" as a clinical verdict | advisory | **Fixed:** "Report Janus's status field with its meaning: 'probable' means only that the start months fit the published time window, 'possible' that the timing is unknown or outside it; neither is a clinical judgement." |
| S9 | Privacy Req 3.3: `--host 0.0.0.0` exposed the unauthenticated endpoint, and `JANUS_API_URL` accepted plain `http://` to any host | advisory | **Fixed:** `--host` accepts only 127.0.0.1, localhost or ::1 (exit 2 otherwise); `JANUS_API_URL` must be https unless the host is loopback; tests `test_http_transport_is_loopback_only`, `test_config`; docs, requirement 3.3 and 4.2, design §6 and DP9 updated |

Also applied from the pharmacologist pass (P11, `.kiro/specs/cds-hooks/review-pharmacologist.md`): a
`janus_check_cascades` line says that `form_confirmed: false` means the dose form was not confirmed.

**Reviewer's judgements:** English-only texts are acceptable (instructions to the model; S7 covers the answer
language). The emergency line is relevant for MCP (assistants talk to patients and caregivers) and is present in the
instructions and every result's safety block.

**What holds (reviewer):** no forbidden phrase; the disclaimer in the instructions, every tool description and every
result; the API's no-pattern statement and abrupt-stop text pass through unchanged; time machine results say
"reports, not people" and that FAERS is spontaneous reporting; errors are fixed codes; the SDK's INFO lines (tool and
argument errors) are silenced at WARNING; Kiro auto-approve is limited to the three tools that carry no patient data;
the docs say that assistant providers see the medicine lists.

**Not checked by the reviewer:** the tests (read-only pass; P4 and P5 were run by the author and pass).
