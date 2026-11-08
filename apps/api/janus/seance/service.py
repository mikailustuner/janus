"""Séance orchestration (séance design §6): catalogue + counts session + integrity snapshot →
three witnesses → response. No I/O of its own: the router hands in the session and snapshot.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final, Literal

from janus.integrity.citability import Verdict, verdict_map
from janus.integrity.model import IntegritySnapshot
from janus.memory.reader import RawCells, Session
from janus.memory.stats import cells_from_counts, evaluate
from janus.seance.catalogue import Catalogue, Substance
from janus.seance.model import (
    CONDITIONS,
    PastItem,
    PresentItem,
    ScienceItem,
    Seance,
    Witness,
    synthesize,
)
from janus.seance.schemas import (
    CatalogueOut,
    GoldOut,
    HeadlineOut,
    IntervalOut,
    LocatorOut,
    PairSummaryOut,
    PastItemOut,
    PastOut,
    PresentItemOut,
    PresentObservedOut,
    PresentOut,
    ScienceItemOut,
    ScienceOut,
    SeanceOut,
    SourceOut,
    SubstanceOut,
    WitnessesOut,
)
from janus.seance.witnesses import past_witness, present_witness, science_witness

_NOT_CITABLE: Final = Verdict(False, "not_registered")
REGION: Final = "ALL"
SCOPE: Final = "suspect"
CI_LEVEL: Final = 0.95
PRESENT_CODES: Final = (
    "spontaneous_reports",
    "reports_not_people",
    "not_deduplicated_across_cases",
    "reporting_bias_notoriety_indication",
    "screening_pattern_not_effect",
)
GOLD_CITATION: Final = (
    "Aliasl J, Khoshzaban F. Jundishapur J Nat Pharm Prod 2013;8(4):192-196. "
    "doi:10.17795/jjnpp-11686. PMC3941892, CC BY 3.0."
)
SOURCES: Final = (
    SourceOut(
        id="openiti_canon",
        citation=(
            "Ibn Sina, al-Qanun fi al-Tibb, Book 2. OpenITI 0428IbnSina.QanunFiTibb."
            "Shamela0010706-ara1, commit 81d1d9e (2025-11-27); OpenITI release 2025.1.9, "
            "doi:10.5281/zenodo.17767721. OpenITI flags typos and missing parts in this version."
        ),
        license="CC BY-NC-SA 4.0",
    ),
    SourceOut(id="pmc3941892", citation=GOLD_CITATION, license="CC BY 3.0"),
    SourceOut(
        id="hamdard",
        citation=(
            "Al-Qanun fi'l-Tibb, Book II, English translation of the critical Arabic text. "
            "Jamia Hamdard, New Delhi, 1998. Cited only."
        ),
        license="© Jamia Hamdard",
    ),
    SourceOut(
        id="faers",
        citation="FDA Adverse Event Reporting System (FAERS) quarterly data (Collective Memory).",
        license="CC0",
    ),
)


def substance_out(s: Substance) -> SubstanceOut:
    gold = (
        GoldOut(gold_id=s.gold_id, scientific_name=s.gold_scientific_name, citation=GOLD_CITATION)
        if s.gold_id and s.gold_scientific_name
        else None
    )
    hazard: Literal["toxic", "caustic"] | None = (
        "toxic" if s.hazard == "toxic" else "caustic" if s.hazard == "caustic" else None
    )
    return SubstanceOut(
        id=s.substance_id,
        name_en=s.name_en,
        transliteration=s.transliteration,
        heading_ar=s.heading_ar,
        kind=s.kind,
        identification=s.identification,
        identification_status=s.identification_status,
        identification_label=(
            "identified" if s.identification_status == "matches_gold" else "uncertain"
        ),
        gold=gold,
        hamdard_ref=s.hamdard_ref,
        hazard=hazard,
        note=s.note,
    )


def present_cells(
    cat: Catalogue, session: Session | None, substance_id: str, condition: str
) -> tuple[RawCells | None, str | None]:
    """The suspect-scope counts for the pair, or (None, None) when they are not available."""
    link = cat.present.get(substance_id)
    if link is None or session is None:
        return None, None
    pts = cat.condition_pts[condition]
    cells = session.cells([link.ingredient_key], pts, SCOPE, [REGION])[REGION]
    return cells, session.meta.snapshot_date


def _observed(
    cat: Catalogue, substance_id: str, cells: RawCells | None, snapshot: str | None
) -> PresentObservedOut | None:
    link = cat.present.get(substance_id)
    if link is None or cells is None or snapshot is None:
        return None
    stats = evaluate(cells_from_counts(cells.a, cells.exposure, cells.event_mapped, cells.n_mapped))
    est = stats.estimates
    return PresentObservedOut(
        ingredient_key=link.ingredient_key,
        exposure_match=link.exposure_match,
        reports_with_both=cells.a,
        reports_with_ingredient=cells.exposure,
        ror=None if est is None else est.ror,
        ror_ci=None
        if est is None
        else IntervalOut(low=est.ror_ci.low, high=est.ror_ci.high, level=CI_LEVEL),
        snapshot_date=snapshot,
    )


def _past(w: Witness) -> PastOut:
    items = [
        PastItemOut(
            claim_id=i.claim_id,
            locator=LocatorOut(
                entry_id=i.locator.entry_id,
                span_id=i.locator.span_id,
                book=i.locator.book,
                page=i.locator.page,
                line_start=i.locator.line_start,
                line_end=i.locator.line_end,
            ),
            arabic_span=i.arabic_span,
            translation=i.machine_translation_en,
            translation_kind="machine_translation",
            use_en=i.use_en,
            ai_review="passed_both",
            expert_review="reviewed" if i.expert_review == "reviewed" else "pending",
            headline_eligible=i.headline_eligible,
        )
        for i in w.items
        if isinstance(i, PastItem)
    ]
    return PastOut(
        supports=w.supports, confidence=w.confidence, missing_reason=w.missing, items=items
    )


def _present(w: Witness, observed: PresentObservedOut | None, pts: Sequence[str]) -> PresentOut:
    items = [
        PresentItemOut(
            ingredient_key=i.ingredient_key,
            exposure_match=i.exposure_match,
            reports_with_both=i.a,
            reports_with_ingredient=i.exposure,
            ror=i.ror,
            ror_ci=IntervalOut(low=i.ror_ci.low, high=i.ror_ci.high, level=CI_LEVEL),
            region="ALL",
            scope="suspect",
            snapshot_date=i.snapshot_date,
        )
        for i in w.items
        if isinstance(i, PresentItem)
    ]
    return PresentOut(
        supports=w.supports,
        confidence=w.confidence,
        missing_reason=w.missing,
        items=items,
        observed=observed,
        pts=list(pts),
        codes=list(PRESENT_CODES),
    )


def _science(w: Witness, excluded: Sequence[str]) -> ScienceOut:
    items: list[ScienceItemOut] = []
    for i in w.items:
        if isinstance(i, ScienceItem):
            items.append(
                ScienceItemOut.model_validate(
                    {
                        "evidence_id": i.evidence_id,
                        "doi": i.doi,
                        "title": i.title,
                        "study_type": i.study_type,
                        "finding_en": i.finding_en,
                        "integrity_status": i.integrity_status,
                    }
                )
            )
    return ScienceOut(
        supports=w.supports,
        confidence=w.confidence,
        missing_reason=w.missing,
        items=items,
        excluded=list(excluded),
    )


def headline(seance: Seance, substance: Substance) -> HeadlineOut:
    """Headline demo claims: an ancient passage that passed both AI passes, from a substance
    that is not hazardous (Req 4.1; owner decision, design DP9). The screen shows "uncertain"
    next to any identification that does not match the gold table."""
    reasons: list[str] = []
    if not any(isinstance(i, PastItem) and i.headline_eligible for i in seance.past.items):
        reasons.append("no_eligible_passage")
    if substance.hazard:
        reasons.append("hazardous_substance")
    return HeadlineOut(eligible=not reasons, reasons=reasons)


def build(
    cat: Catalogue,
    substance_id: str,
    condition: str,
    *,
    cells: RawCells | None,
    snapshot_date: str | None,
    integrity: IntegritySnapshot | None,
) -> SeanceOut:
    sub = cat.substances[substance_id]
    studies = cat.science.get((substance_id, condition), ())
    verdicts = verdict_map(integrity) if integrity is not None and integrity.records else None
    statuses = (
        {s.evidence_id: integrity.state_of(s.evidence_id).status.value for s in studies}
        if integrity is not None
        else {}
    )
    excluded = (
        [s.evidence_id for s in studies if not verdicts.get(s.evidence_id, _NOT_CITABLE).citable]
        if verdicts is not None
        else []
    )
    seance = synthesize(
        substance_id,
        condition,
        past_witness(cat.claims, substance_id, condition),
        present_witness(cat.present.get(substance_id), cells, snapshot_date),
        science_witness(studies, verdicts, statuses),
    )
    return SeanceOut(
        substance=substance_out(sub),
        condition=condition,  # pyright: ignore[reportArgumentType]
        witnesses=WitnessesOut(
            past=_past(seance.past),
            present=_present(
                seance.present,
                _observed(cat, substance_id, cells, snapshot_date),
                cat.condition_pts[condition],
            ),
            science=_science(seance.science, excluded),
        ),
        supporting_witnesses=seance.supporting,
        missing_witnesses=list(seance.missing),
        headline=headline(seance, sub),
        sources=list(SOURCES),
    )


def catalogue(cat: Catalogue) -> CatalogueOut:
    pairs: list[PairSummaryOut] = []
    for sid in sorted(cat.substances):
        link = cat.present.get(sid)
        for c in CONDITIONS:
            past = sum(1 for cl in cat.claims if cl.substance_id == sid and cl.condition == c)
            science = len(cat.science.get((sid, c), ()))
            if past or science:
                pairs.append(
                    PairSummaryOut(
                        substance=sid,
                        condition=c,  # pyright: ignore[reportArgumentType]
                        past_passages=past,
                        science_studies=science,
                        present_link=link.exposure_match if link else "none",
                    )
                )
    return CatalogueOut(
        substances=[substance_out(cat.substances[s]) for s in sorted(cat.substances)],
        pairs=pairs,
        sources=list(SOURCES),
    )
