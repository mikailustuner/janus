# Report Assistant review: statistician

**Date:** 2026-11-09
**Reviewer:** statistician (`.kiro/agents/statistician.md`), run as a separate labelled pass by the implementing
agent, in that role only, against `medical-safety.md` rule 6 ("statistics are honest") and design DP12.

## Scope

The one number the feature shows: the under-reporting sentence (`ReportAssistant.intro.fact`, `intro.caveat`,
`intro.cite`, `intro.doi`) in five languages, and its source. Source checked in the research notes of 2026-11-09:
Hazell L, Shakir SAW, Drug Saf 2006;29(5):385–396, DOI 10.2165/00002018-200629050-00003 (Crossref record; doi.org
resolves to Springer), PubMed abstract PMID 16689555: "The median under-reporting rate across the 37 studies was 94%
(interquartile range 82-98%)."

## What holds

- The figure is a **median across studies**, and the sentence says so; it is not presented as a rate for the
  reader, their country or their medicine. The caveat says the studies differ in country, setting and method and that
  the figure holds for no single country today.
- The spread is shown: the interquartile range 82–98 % with a plain explanation ("the middle half of the studies
  found between 82 % and 98 %"), the correct reading of an IQR of study-level estimates.
- No big-number tile and no headline "94 % are never reported" (DP12). The sentence is shown once, in the muted
  footer of the intro card.
- The citation (authors, journal, year, volume, pages, DOI) is next to the number on screen; `hazell_2006` is in
  `pipelines/sources.toml` (cited only) and in NOTICE.
- The number of studies (37) is stated. Percent formatting follows each language (EN 94%, TR %94, DE/FR/ES 94 %).

## Findings

| id | Severity | Finding | Done |
|----|----------|---------|------|
| S1 | advisory | The studies estimate under-reporting against reactions found by other means, so the verb "estimated" must stay in the sentence. | Kept: "estimated what share … were not reported" in all five languages. |
| S2 | advisory | The abstract does not say which reporters the 37 studies covered (many under-reporting studies are about health-professional reporting). The sentence must not claim either way. | No claim made; a full-text check is on the pre-launch checklist. |
| S3 | advisory | A median of study estimates must never become "9 in 10 of your side effects" in README, video or Devpost copy. | Pre-launch checklist line. |
| S4 | advisory | The review is from 2006; a newer systematic review may report a different median. | The year is in the sentence; re-check for a newer review is on the checklist. |

## Verdict

Pass. The sentence is honest about what the number is (a median of 37 study estimates with its IQR), where it comes
from and what it is not. No blocking finding.
