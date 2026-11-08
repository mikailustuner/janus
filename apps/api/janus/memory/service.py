"""Orchestration of the FAERS routes: reader integers -> pure statistics -> response models
(collective-memory design §4, §5). No I/O of its own; the reader does the reading.

Counts are reports, never people.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from janus.memory import messages
from janus.memory.evidence import FAERS_EVIDENCE_ID, EventRef, faers_locator
from janus.memory.ladder import choose_level
from janus.memory.model import ALL_REGION, REGIONS, RESPONSE_REGIONS
from janus.memory.reader import (
    RawCells,
    Session,
    SnapshotMeta,
    counts_match_served,
    snapshot_freshness,
)
from janus.memory.schemas import (
    BasisOut,
    CellsOut,
    CitationOut,
    CombinationCountOut,
    CombinationIn,
    CombinationOut,
    EstimatesOut,
    EventOut,
    EventRefIn,
    EventStatsOut,
    IngredientCountOut,
    IntervalOut,
    MemberAloneOut,
    PairGroupOut,
    PairIn,
    PairOut,
    RegionRowOut,
    RegionsIn,
    RegionsOut,
    SensitivityOut,
    SingleGroupOut,
    SkippedOut,
    SnapshotOut,
    SnapshotPart,
    StatsOut,
    TotalsOut,
    UnknownShareOut,
)
from janus.memory.stats import (
    PARAMS,
    Stats,
    Table,
    cells_from_counts,
    evaluate,
    sensitivity,
)
from janus.memory.vocabulary import EventVocabulary

ADRREPORTS_URL = "https://www.adrreports.eu/"  # fixed public address; form verified before launch
PER_PAIR_EVENTS = 10
PAIRS_WITH_EVENTS = 5
SINGLE_EVENTS = 10


class UnknownEventError(ValueError):
    """The Janus event key is not an active key of the vocabulary (route: 422 on `event.key`)."""


class InconsistentCountsError(RuntimeError):
    """The count tables are inconsistent (a negative cell). Fails loudly; names nothing."""


@dataclass(frozen=True)
class Context:
    vocab: EventVocabulary
    today: dt.date
    served_version: str | None


@dataclass(frozen=True)
class ResolvedEvent:
    pt: str | None
    key: str | None
    pts: tuple[str, ...]
    safety_line: str | None
    benefit: bool

    @property
    def ref(self) -> EventRef:
        return EventRef(key=self.key, pt=self.pt)


def resolve_event(ref: EventRefIn, vocab: EventVocabulary) -> ResolvedEvent:
    if ref.pt is not None:
        return ResolvedEvent(ref.pt, None, (ref.pt,), vocab.line_for_pts((ref.pt,)), False)
    assert ref.key is not None  # noqa: S101  (exactly-one validator)
    k = vocab.usable(ref.key)
    if k is None:
        raise UnknownEventError("unknown event key")
    return ResolvedEvent(
        None,
        k.key,
        k.pts,
        vocab.line_for_pts(k.pts) or (k.safety_line or None),
        k.direction == "benefit",
    )


# --- envelope -------------------------------------------------------------------------------


def snapshot_part(meta: SnapshotMeta, ctx: Context) -> SnapshotPart:
    fresh = snapshot_freshness(meta.snapshot_date, ctx.today)
    return SnapshotPart(
        build_id=meta.build_id,
        snapshot_date=meta.snapshot_date,
        window=list(meta.window),
        faers_run_id=meta.faers_run_id,
        resolution_dataset_version=meta.resolution_dataset_version,
        served_resolution_dataset_version=ctx.served_version,
        counts_match_served=counts_match_served(
            meta.resolution_dataset_version, ctx.served_version
        ),
        stale=fresh.state == "stale",
        age_days=fresh.age_days,
    )


def common_fields(
    meta: SnapshotMeta, ctx: Context, *, has_pt: bool, extra: Sequence[str] = ()
) -> dict[str, object]:
    part = snapshot_part(meta, ctx)
    notices = list(messages.BASE_NOTICES)
    if part.counts_match_served is False:
        notices.append("counts_built_against_other_dataset")
    if part.stale:
        notices.append("source_may_be_outdated")
    notices.extend(n for n in extra if n not in notices)
    return {
        "snapshot": part,
        "notices": notices,
        "disclaimer": messages.DISCLAIMER,
        "attribution": messages.ATTRIBUTION.format(date=meta.snapshot_date),
        "meddra_notice": meta.meddra_notice if has_pt else None,
    }


# --- statistics -----------------------------------------------------------------------------


def _cells_out(t: Table) -> CellsOut:
    return CellsOut(a=t.a, b=t.b, c=t.c, d=t.d, n=t.n)


def _estimates_out(s: Stats) -> EstimatesOut | None:
    """PRR, ROR, interval and chi-squared; withheld below the display threshold (Req 1.3, 10.3).

    With fewer than 3 reports no sentence may state a number derived from the cell, so the API does
    not return one; the raw cells (and so the report count) are still returned.
    """
    e = s.estimates
    if e is None or s.assessment in ("no_reports", "insufficient_data"):
        return None
    return EstimatesOut(
        prr=e.prr,
        ror=e.ror,
        ror_ci=IntervalOut(
            low=e.ror_ci.low, high=e.ror_ci.high, level=e.ror_ci.level, method=e.ror_ci.method
        ),
        chi2=e.chi2,
        chi2_form=e.chi2_form,
    )


def stats_out(raw: RawCells, region: str, scope: str, *, event_reported: bool = True) -> StatsOut:
    from janus.memory.stats import StatsError

    try:
        primary_table = cells_from_counts(raw.a, raw.exposure, raw.event_mapped, raw.n_mapped)
        primary = evaluate(primary_table)
        sens = sensitivity(
            primary,
            a=raw.a,
            ingredient=raw.exposure,
            event_all=raw.event_all,
            n_all=raw.n_all,
        )
    except StatsError as exc:
        raise InconsistentCountsError("inconsistent counts") from exc
    codes: list[str] = []
    if primary.haldane_applied and _estimates_out(primary) is not None:
        codes.append("estimate_uses_continuity_correction")
    if _estimates_out(primary) is not None and (
        primary.haldane_applied or raw.a < PARAMS.weak_below
    ):
        codes.append("interval_approximate")
    if primary.assessment == "weak":
        codes.append("weak_pattern")
    if sens.differs:
        codes.append("denominator_sensitive")
    if not event_reported:
        codes.append("event_not_reported_in_window")
    return StatsOut(
        region=region,  # pyright: ignore[reportArgumentType]
        scope=scope,  # pyright: ignore[reportArgumentType]
        cells=_cells_out(primary_table),
        haldane_applied=primary.haldane_applied,
        estimates=_estimates_out(primary),
        evans_met=primary.evans_met,
        ror_signal=primary.ror_signal,
        assessment=primary.assessment,
        sensitivity=SensitivityOut(
            cells=_cells_out(sens.stats.cells),
            haldane_applied=sens.stats.haldane_applied,
            estimates=_estimates_out(sens.stats),
            assessment=sens.stats.assessment,
            differs=sens.differs,
        ),
        denominator_sensitive=sens.differs,
        codes=codes,
    )


def _citation(keys: Sequence[str], event: EventRef, region: str, scope: str) -> CitationOut:
    return CitationOut(
        evidence_id=FAERS_EVIDENCE_ID,
        locator=faers_locator(tuple(keys), event, region, scope),
    )


def _tr_notice(region: str) -> list[str]:
    return ["tr_reports_small_self_selected"] if region == "TR" else []


def _absence_notice(assessments: Sequence[str]) -> list[str]:
    weak_or_none = {"no_reports", "insufficient_data", "not_disproportionate"}
    return ["absence_is_not_reassurance"] if any(a in weak_or_none for a in assessments) else []


# --- pair -----------------------------------------------------------------------------------


def pair(session: Session, req: PairIn, ctx: Context) -> PairOut:
    ev = resolve_event(req.event, ctx.vocab)
    meta = session.meta
    event_out = EventOut(
        pt=ev.pt, key=ev.key, pts=list(ev.pts), reported_in_window=False, safety_line=ev.safety_line
    )
    if ev.benefit:
        return PairOut(
            **common_fields(meta, ctx, has_pt=False, extra=["benefit_not_in_faers"]),  # type: ignore[arg-type]
            status="not_available",
            ingredient=req.ingredient,
            event=event_out,
            stats=None,
            citation=None,
        )
    raw = session.cells([req.ingredient], ev.pts, req.scope, [req.region])[req.region]
    reported = raw.event_all > 0
    stats = stats_out(raw, req.region, req.scope, event_reported=reported)
    return PairOut(
        **common_fields(  # type: ignore[arg-type]
            meta,
            ctx,
            has_pt=True,
            extra=[*_absence_notice([stats.assessment]), *_tr_notice(req.region)],
        ),
        status="ok",
        ingredient=req.ingredient,
        event=event_out.model_copy(update={"reported_in_window": reported}),
        stats=stats,
        citation=_citation([req.ingredient], ev.ref, req.region, req.scope),
    )


# --- regions --------------------------------------------------------------------------------


def regions(session: Session, req: RegionsIn, ctx: Context) -> RegionsOut:
    meta = session.meta
    keys = sorted(req.ingredients)
    scope = req.scope or ("suspect" if len(keys) == 1 else "any")
    totals = session.totals()
    rows: list[RegionRowOut] = []
    event_out: EventOut | None = None
    ev: ResolvedEvent | None = None
    if req.event is not None:
        ev = resolve_event(req.event, ctx.vocab)
        if ev.benefit:
            raise UnknownEventError("benefit keys have no FAERS counts")
        event_out = EventOut(
            pt=ev.pt,
            key=ev.key,
            pts=list(ev.pts),
            reported_in_window=False,
            safety_line=ev.safety_line,
        )
        cells = session.cells(keys, ev.pts, scope, RESPONSE_REGIONS)
        event_out = event_out.model_copy(
            update={"reported_in_window": cells[ALL_REGION].event_all > 0}
        )
        for region in RESPONSE_REGIONS:
            raw = cells[region]
            rows.append(
                RegionRowOut(
                    region=region,  # pyright: ignore[reportArgumentType]
                    n_primary=raw.n_mapped,
                    n_all=raw.n_all,
                    reports=raw.a,
                    stats=stats_out(raw, region, scope, event_reported=raw.event_all > 0),
                    citation=_citation(keys, ev.ref, region, scope),
                )
            )
    else:
        if len(keys) == 1:
            counts = session.ingredient_counts(keys, scope, RESPONSE_REGIONS)
            exposure = {r: counts.get((keys[0], r), 0) for r in RESPONSE_REGIONS}
        else:
            exposure = session.exposure_by_region(keys, scope)
        for region in RESPONSE_REGIONS:
            n_m, n_a = totals.get(region, (0, 0))
            rows.append(
                RegionRowOut(
                    region=region,  # pyright: ignore[reportArgumentType]
                    n_primary=n_m,
                    n_all=n_a,
                    reports=exposure[region],
                    stats=None,
                    citation=_citation(keys, EventRef(), region, scope),
                )
            )
    unknown_reports = totals.get("UNKNOWN", (0, 0))[1]
    all_reports = totals.get(ALL_REGION, (0, 0))[1]
    basis_raw = session.region_basis()
    basis = [
        BasisOut(
            region=r,  # pyright: ignore[reportArgumentType]
            occurrence=basis_raw.get(r, {}).get("occr_country", 0),
            reporter_fallback=basis_raw.get(r, {}).get("reporter_country", 0),
        )
        for r in RESPONSE_REGIONS
    ]
    assessments = [r.stats.assessment for r in rows if r.stats is not None]
    extra = [
        "region_is_report_origin",
        "eu_member_states_not_separable",
        "regions_not_comparable",
        "tr_reports_small_self_selected",
        *_absence_notice(assessments),
    ]
    if event_out is None and any(r.reports == 0 for r in rows):
        extra.append("absence_is_not_reassurance")  # a 0 for a region is not reassurance
    if len(keys) > 1:
        extra += ["combination_caveat", "set_counts_are_lower_bounds"]
    return RegionsOut(
        **common_fields(meta, ctx, has_pt=event_out is not None, extra=extra),  # type: ignore[arg-type]
        scope=scope,  # pyright: ignore[reportArgumentType]
        event=event_out,
        rows=rows,
        unknown=UnknownShareOut(
            reports=unknown_reports, share=(unknown_reports / all_reports) if all_reports else 0.0
        ),
        basis=basis,
        adrreports_url=ADRREPORTS_URL,
    )


# --- combination ----------------------------------------------------------------------------


def _event_rows(
    vocab: EventVocabulary,
    keys: Sequence[str],
    exposure: int,
    events: Sequence[tuple[str, int]],
    totals_by_pt: Mapping[str, tuple[int, int]],
    n: tuple[int, int],
    region: str,
    scope: str,
    members_alone: Mapping[tuple[str, str], int] | None,
) -> list[EventStatsOut]:
    out: list[EventStatsOut] = []
    for pt, a in events:
        ev_m, ev_a = totals_by_pt.get(pt, (a, a))
        raw = RawCells(n[0], n[1], exposure, ev_m, ev_a, a)
        alone = (
            [MemberAloneOut(key=k, reports=members_alone.get((k, pt), 0)) for k in sorted(keys)]
            if members_alone is not None
            else []
        )
        out.append(
            EventStatsOut(
                pt=pt,
                reports=a,
                stats=stats_out(raw, region, scope),
                safety_line=vocab.line_for_pts((pt,)),
                members_alone=alone,
                citation=_citation(keys, EventRef(pt=pt), region, scope),
            )
        )
    return out


def combination(session: Session, req: CombinationIn, ctx: Context) -> CombinationOut:
    meta = session.meta
    keys = sorted(req.ingredients)
    region, scope = req.region, req.scope
    totals = session.totals()
    n = totals.get(region, (0, 0))
    singles_counts = session.ingredient_counts(keys, scope, [region])
    ingredient_rows = [
        IngredientCountOut(
            key=k,
            reports=singles_counts.get((k, region), 0),
            citation=_citation([k], EventRef(), region, scope),
            assessment="no_reports" if singles_counts.get((k, region), 0) == 0 else "ok",
        )
        for k in keys
    ]
    combo = session.exposure_by_region(keys, scope)[region]
    pair_counts: dict[tuple[str, str], int] = {}
    pair_events: dict[tuple[str, str], list[tuple[str, int]]] = {}
    choice = choose_level(len(keys), combo, {}, PARAMS.min_reports)
    if choice.level != "combination" and len(keys) >= 3:
        pair_counts, pair_events = session.pairwise(
            keys, scope, region, PARAMS.min_reports, PER_PAIR_EVENTS, PAIRS_WITH_EVENTS
        )
        choice = choose_level(len(keys), combo, pair_counts, PARAMS.min_reports)

    events_out: list[EventStatsOut] = []
    pairs_out: list[PairGroupOut] = []
    singles_out: list[SingleGroupOut] = []
    extra = ["reported_together_only", "combination_caveat", "set_counts_are_lower_bounds"]
    if choice.level == "combination":
        top = session.top_events_for_set(keys, scope, region, req.top_events)
        pts = [pt for pt, _ in top]
        events_out = _event_rows(
            ctx.vocab,
            keys,
            combo,
            top,
            session.event_totals(pts, region) if pts else {},
            n,
            region,
            scope,
            session.pair_report_counts(keys, pts, scope, region) if pts else {},
        )
    elif choice.level == "pairwise":
        extra.append("pairwise_shown")
        all_pts = sorted({pt for p in choice.pairs for pt, _ in pair_events.get(p, [])})
        totals_by_pt = session.event_totals(all_pts, region) if all_pts else {}
        for p in choice.pairs:
            pairs_out.append(
                PairGroupOut(
                    keys=list(p),
                    reports=pair_counts[p],
                    citation=_citation(list(p), EventRef(), region, scope),
                    events_omitted=p not in pair_events,
                    events=_event_rows(
                        ctx.vocab,
                        list(p),
                        pair_counts[p],
                        pair_events.get(p, []),
                        totals_by_pt,
                        n,
                        region,
                        scope,
                        None,
                    ),
                )
            )
    else:
        extra.append("single_shown")
        by_key = session.top_events_single(keys, scope, region, SINGLE_EVENTS)
        all_pts = sorted({pt for lst in by_key.values() for pt, _ in lst})
        totals_by_pt = session.event_totals(all_pts, region) if all_pts else {}
        for k in keys:
            singles_out.append(
                SingleGroupOut(
                    key=k,
                    reports=singles_counts.get((k, region), 0),
                    citation=_citation([k], EventRef(), region, scope),
                    events=_event_rows(
                        ctx.vocab,
                        [k],
                        singles_counts.get((k, region), 0),
                        by_key.get(k, []),
                        totals_by_pt,
                        n,
                        region,
                        scope,
                        None,
                    ),
                )
            )
    shown = [e.stats.assessment for e in events_out]
    shown += [e.stats.assessment for g in pairs_out for e in g.events]
    shown += [e.stats.assessment for g in singles_out for e in g.events]
    if choice.level != "combination" or not shown:
        shown.append("insufficient_data" if choice.level != "combination" else "no_reports")
    extra += _absence_notice(shown) + _tr_notice(region)
    if any(r.assessment == "no_reports" for r in ingredient_rows):
        extra.append("absence_is_not_reassurance")
    return CombinationOut(
        **common_fields(meta, ctx, has_pt=True, extra=list(dict.fromkeys(extra))),  # type: ignore[arg-type]
        region=region,
        scope=scope,
        level=choice.level,
        skipped=[SkippedOut(level=lv, reason=reason) for lv, reason in choice.skipped],
        ingredients=ingredient_rows,
        combination=CombinationCountOut(reports=combo, n=n[0]),
        citation=_citation(keys, EventRef(), region, scope),
        events=events_out,
        pairs=pairs_out,
        singles=singles_out,
    )


# --- snapshot -------------------------------------------------------------------------------


def snapshot(session: Session, ctx: Context, layers: Mapping[str, str]) -> SnapshotOut:
    meta = session.meta
    totals = session.totals()
    fresh = snapshot_freshness(meta.snapshot_date, ctx.today)
    all_reports = totals.get(ALL_REGION, (0, 0))[1]
    unknown = totals.get("UNKNOWN", (0, 0))[1]
    return SnapshotOut(
        build_id=meta.build_id,
        snapshot_date=meta.snapshot_date,
        window=list(meta.window),
        faers_run_id=meta.faers_run_id,
        resolution_dataset_version=meta.resolution_dataset_version,
        stale=fresh.state == "stale",
        age_days=fresh.age_days,
        totals=[
            TotalsOut(
                region=r,  # pyright: ignore[reportArgumentType]
                reports_mapped=totals.get(r, (0, 0))[0],
                reports_all=totals.get(r, (0, 0))[1],
            )
            for r in (*REGIONS, ALL_REGION)
        ],
        unknown_share=(unknown / all_reports) if all_reports else 0.0,
        layers=dict(layers),
        notices=list(messages.BASE_NOTICES),
        meddra_notice=meta.meddra_notice,
        attribution=messages.ATTRIBUTION.format(date=meta.snapshot_date),
    )
