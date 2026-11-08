"""The three witnesses (séance design §4.2-4.4). Pure: data in, `Witness` out.

- Past: Canon claims for the pair that passed both AI review passes, each with its locator.
- Present: FAERS report counts for (ingredient key, the condition's PT group). Support means a
  possible protective association (upper bound of the ROR interval below 1, light-face Req 1.1)
  on at least `MIN_REPORTS` reports, for an exposure that matches the ancient substance. It is a
  screening pattern in spontaneous reports, not evidence of an effect.
- Science: listed studies that support the pair and are citable under Evidence Integrity
  (retracted papers are removed, never shown as support).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Final

from janus.integrity.citability import Verdict
from janus.memory.reader import RawCells
from janus.memory.stats import PARAMS, cells_from_counts, evaluate
from janus.seance.catalogue import Claim, PresentLink, Study
from janus.seance.model import (
    Confidence,
    Interval,
    PastItem,
    PresentItem,
    ScienceItem,
    Witness,
    silent,
)

MIN_REPORTS: Final = PARAMS.min_reports
STRONG_STUDIES: Final = frozenset({"systematic_review"})


def past_witness(claims: Sequence[Claim], substance_id: str, condition: str) -> Witness:
    mine = [c for c in claims if c.substance_id == substance_id and c.condition == condition]
    if not mine:
        return silent("past", "no_canon_passage")
    usable = [c for c in mine if c.ai_review == "passed_both"]
    if not usable:
        return silent("past", "passages_rejected_by_review")
    items = tuple(
        PastItem(
            claim_id=c.claim_id,
            locator=c.locator,
            arabic_span=c.arabic_span,
            machine_translation_en=c.machine_translation_en,
            use_en=c.use_en,
            ai_review=c.ai_review,
            expert_review=c.expert_review,
            headline_eligible=c.headline_eligible,
        )
        for c in usable
    )
    # The experts have not reviewed the passages yet: the text is a witness of low confidence
    # until they have (Req 1.5); "moderate" needs expert review of at least one passage.
    reviewed = any(c.expert_review == "reviewed" for c in usable)
    return Witness("past", items, "moderate" if reviewed else "low", None)


def present_witness(
    link: PresentLink | None, cells: RawCells | None, snapshot_date: str | None
) -> Witness:
    """`cells` are the suspect-scope 2x2 counts for the link's key and the condition's PTs."""
    if link is None:
        return silent("present", "no_faers_mapping")
    if link.exposure_match == "different":
        return silent("present", "exposure_differs", ("faers_exposure_differs",))
    if cells is None or snapshot_date is None:
        return silent("present", "counts_unavailable")
    table = cells_from_counts(cells.a, cells.exposure, cells.event_mapped, cells.n_mapped)
    stats = evaluate(table)
    if stats.estimates is None or cells.a < MIN_REPORTS:
        return silent("present", "too_few_reports", ("faers_counted",))
    ci = stats.estimates.ror_ci
    if not ci.high < 1.0:
        return silent("present", "no_protective_association", ("faers_counted",))
    item = PresentItem(
        ingredient_key=link.ingredient_key,
        exposure_match=link.exposure_match,
        a=cells.a,
        exposure=cells.exposure,
        ror=stats.estimates.ror,
        ror_ci=Interval(float(ci.low), float(ci.high)),
        snapshot_date=snapshot_date,
    )
    # Spontaneous reports are weak evidence on their own (light-face introduction).
    return Witness("present", (item,), "low", None)


def science_witness(
    studies: Sequence[Study],
    verdicts: Mapping[str, Verdict] | None,
    statuses: Mapping[str, str],
) -> Witness:
    """`verdicts` from `integrity.citability.verdict_map`; None when integrity is unavailable."""
    if not studies:
        return silent("science", "no_study_listed")
    if verdicts is None:
        return silent("science", "integrity_unavailable")
    citable = [s for s in studies if verdicts.get(s.evidence_id, Verdict(False, None)).citable]
    if not citable:
        return silent("science", "no_citable_study")
    supporting = [s for s in citable if s.direction == "supports"]
    if not supporting:
        return silent("science", "studies_do_not_support")
    items = tuple(
        ScienceItem(
            evidence_id=s.evidence_id,
            doi=s.doi,
            title=s.title,
            study_type=s.study_type,
            finding_en=s.finding_en,
            integrity_status=statuses.get(s.evidence_id, "unknown"),
        )
        for s in supporting
    )
    confidence: Confidence = (
        "moderate" if any(s.study_type in STRONG_STUDIES for s in supporting) else "low"
    )
    return Witness("science", items, confidence, None)
