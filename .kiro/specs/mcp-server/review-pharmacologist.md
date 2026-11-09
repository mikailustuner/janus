# MCP server: pharmacologist review

**Date:** 2026-11-09 · **Reviewer:** pharmacologist (`.kiro/agents/pharmacologist.md`), the same read-only agent pass
as `.kiro/specs/cds-hooks/review-pharmacologist.md`, here for `apps/mcp/janus_mcp/safety.py`. The MCP server holds no
mapping or medical logic (it forwards to `/resolve/*` and `/cascades/evaluate`), so the review covered the wording
only.

| # | Finding | Severity | Action |
|---|---|---|---|
| P11 | The wording explained `status` but not `form_confirmed`, so an assistant could present an ingredient-level match (e.g. a name search for timolol) as if the eye-drop or oral form were known | advisory | **Fixed:** `janus_check_cascades` adds "form_confirmed false means the dose form was not confirmed (matched by ingredient only; the pattern may not apply to eye drops, creams or other local forms); say so." |

**What holds (reviewer):** the MCP safety texts meet `medical-safety.md` (possible prescribing cascade, pattern not
verdict, no advice to start, change or end a medicine, abrupt-stop line passed on, no reassurance from an empty list).
