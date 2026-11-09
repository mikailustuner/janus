# Cascade map: safety-auditor pass (2026-11-09)

Scope: `/cascades` (`apps/web/src/components/cascade-map/*`, `src/cascade-map/model.ts`), the
`CascadeMap` namespace in five languages, the entry links (results scope card, Research, footer) and
the e2e network checks. One labelled AI pass in the role of `.kiro/agents/safety-auditor.md`,
against `medical-safety.md` and `privacy.md`, done separately from the localization pass. Status:
**AI-reviewed, pending expert review**.

## Checked
- **Rule 1 (patterns, not verdicts; no advice)**: the screen describes literature patterns. The
  framing line in all five languages: "Patterns described in the literature (PIPC list, Rochon et
  al., Eur Geriatr Med 2025). A pattern is something to discuss with your doctor, not a verdict
  about your medicines." No text tells the person to start, stop or change a medicine. Matched lines
  say "Matches a finding for your list", never "you have".
- **Rule 2 (forbidden phrases)**: none in any language (vitest guard over `apps/`, and the e2e text
  check on the rendered page in all five locales and both themes).
- **Rule 3 (no false reassurance)**: with no finding the screen shows `Findings.noPattern`
  ("… does not mean your medicines are free of problems"). See S2 for the per-pattern line.
- **Rule 4 (abrupt stop)**: the panel shows "Do not stop this medicine suddenly." next to the
  person's medicines when the API warned that item (`item_warnings`), as the finding card does.
- **Rule 5 (every claim cites evidence)**: every pattern shows its PIPC row and the source line, and
  the evidence ids `rule:pipc:N`, `dataset:pipc` and the supporting paper; the integrity verdicts
  stay on the finding page, linked from the panel. Rules disabled by the API (e.g. all sources
  retracted) are labelled "cannot be checked" from the result's own list.
- **Rule 9 (disclaimer)**: the footer disclaimer is on the screen (e2e checks its text in every
  locale).
- **Rule 10 / safety lines**: see S4.
- **Experience DP3**: matches come only from `findings[].rule_id`; the client evaluates no rule.
- **Privacy**: no new request; the screen reuses `useEvaluation` (no list → no request; demo → the
  recorded fixture, e2e asserts zero `/api/` and zero cross-origin requests); box names are shown in
  the browser only; nothing is logged or stored.
- **Colour**: `--risk` is not used on the map; matched lines differ by width, dash and a text legend.

## Findings

| # | Where | Rule | Finding | Severity | Outcome |
|---|---|---|---|---|---|
| S1 | framing line | 1, 2 | Draft idea "A pattern is not a diagnosis" would trip the EN list ("diagnosis") and reads as a verdict word. | blocking (draft) | **Applied** before writing: "something to discuss with your doctor, not a verdict about your medicines" in all five. |
| S2 | panel, "Your list" on rows 27/57 or a disabled rule | 3 | "None of the findings for your list uses this pattern." is true but misleading when Janus cannot check the pattern at all. | blocking | **Applied**: for a pattern that cannot be checked the section repeats "Janus cannot check this pattern: {reason}." instead. |
| S3 | panel, "Your list" | 3 | For checkable patterns the "none" line could be read as reassurance about the person's medicines. | advisory | Kept: it is about findings, not medicines; the screen-level line is the rule-3 sentence when there is no finding at all. |
| S4 | panel of a matched pattern whose event has a safety line (e.g. Cologne row 51, GI bleeding → `urgent_care_gi`) | 10 + experience Req 7 | The first draft showed the person's finding without the urgent-care line that the Results screen shows. | blocking | **Applied**: the panel then starts with the emergency notice and shows the safety line next to the finding (e2e "Cologne, row 51"). Literature patterns without a finding for the list show neither (DP10). |
| S5 | map labels of events | 10 | Events such as "Seizures" or "Arrhythmia" appear as literature labels for every visitor; an emergency notice on every visit would alarm without cause. | advisory | Kept (DP10): no urgent-care line for literature patterns; the footer keeps the emergency number on every screen. For the experts. |
| S6 | `matches.count` | 1 | "N patterns match findings for your list" — wording keeps "finding" (an API result), not a judgement. | — | Passed |

Verdict: **pass** after S2 and S4. Not checkable by this pass: clinical adequacy of the PIPC
wording itself (expert review of the rule base, already on the pre-launch checklist).
