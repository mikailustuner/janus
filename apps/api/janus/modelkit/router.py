"""`/modelkit/*` routes (requirement 5): the drug model starter kit, read-only. Experimental.
Medical-policy routes (no-store, access line only). Everything is computed once per release when
the store loads; no request starts a simulation. 503 `modelkit_unavailable` when no release is
installed; 404 `unknown_drug` / `unknown_release`; 422 `invalid_request` names fields only.
Research use only. Not for clinical decisions.
"""

from __future__ import annotations

import re
from typing import Any, Literal

from fastapi import Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict
from starlette.concurrency import run_in_threadpool

from janus.http_policy.routes import medical_router
from janus.modelkit import export as ex
from janus.modelkit.builder import NoSet, ParameterSet
from janus.modelkit.evidence import Ev
from janus.modelkit.reasons import TEXT
from janus.modelkit.store import DrugEntry, ModelkitHolder, Release
from janus.modelkit.validate import MIN_STUDIES_FOR_INTERVAL, Metric, Validation

router = medical_router()
UNAVAILABLE = {"error": "modelkit_unavailable"}
KEY = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
RELEASE = re.compile(r"^[0-9]{8}T[0-9]{6}Z-[0-9a-f]{8}-[0-9a-f]{4}$")
Status = Literal["validated", "not_validated", "failed"]


class _Out(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Statements(_Out):
    research_use: str = ex.RESEARCH_USE
    expert_review: str = ex.NO_REVIEW
    experimental: str = ex.EXPERIMENTAL


class MetricOut(_Out):
    name: Literal["auc", "cmax"]
    tested: bool
    n_points: int
    n_studies: int
    gm_ratio: float | None
    gmfe: float | None
    within_2_fold_points: int
    all_within_2_fold: bool | None


class PointOut(_Out):
    evidence_id: str
    metric: Literal["auc", "cmax"]
    study_id: str
    dose_mg: float
    observed: float
    predicted: float
    ratio: float
    within_2_fold: bool


class ReasonOut(_Out):
    evidence_id: str
    reason: str


class ValidationOut(_Out):
    status: Status
    reasons: list[str]
    metrics: list[MetricOut]
    points: list[PointOut]
    excluded: list[ReasonOut]
    suspect: list[str]
    failed_point_ids: list[str]
    interval_reason: str
    interval_min_studies: int
    interval_n_studies: int
    band: list[float]
    unit_note: str


class ParamOut(_Out):
    name: str
    label: str
    value: float
    unit: str
    confidence_class: Literal["A", "B", "C"]
    n_studies: int
    between_study_cv: float | None
    derivation: str | None
    notes: list[str]
    evidence_ids: list[str]


class SetOut(_Out):
    model: str
    model_reason: str
    basis: Literal["iv", "oral_apparent"]
    apparent: bool
    complete: bool
    missing: list[str]
    warnings: list[str]
    implied_half_life_h: float | None
    stated_half_life_h: float | None
    params: list[ParamOut]
    left_out: list[ReasonOut]
    held_out_studies: list[str]


class DrugSummary(_Out):
    key: str
    name: str
    status: Status
    status_reasons: list[str]
    has_set: bool
    set_complete: bool
    basis: str | None
    rows: int
    confirmed_rows: int
    studies: int
    auc: MetricOut
    cmax: MetricOut
    exportable: bool
    experimental: Literal[True] = True


class DrugsOut(_Out):
    release: dict[str, Any]
    statements: Statements
    drugs: list[DrugSummary]
    total: int  # drugs matching the filters
    offset: int
    limit: int
    counts: dict[str, int]  # whole release: by status, plus `all`, `with_set`


class DrugOut(_Out):
    release: dict[str, Any]
    statements: Statements
    summary: DrugSummary
    parameter_set: SetOut | None
    no_set_reasons: list[str]
    validation: ValidationOut
    targets: list[str]
    reason_text: dict[str, str]


class EvidenceRowOut(_Out):
    id: str
    analyte: str
    analyte_class: str
    parameter: str
    value: float
    value_low: float | None
    value_high: float | None
    statistic: str
    unit: str
    value_si: float
    dose: float | None
    route: str
    regimen: str
    interval_h: float | None
    population: str | None
    n_subjects: int | None
    formulation: str
    coadministered: bool
    study_id: str
    source_id: str
    source_locator: str
    source_version: str
    source_url: str | None
    quote: str
    reader_a: str
    reader_b: str
    confirmed: bool
    confirm_reason: str
    note: str | None
    extracted_at: str
    role: Literal["building", "validation", "excluded"]
    reason: str | None
    origin: str
    derivation: str | None
    arm_id: str | None
    food: str
    evidence_kind: str
    dispersion_type: str
    dispersion_low: float | None
    dispersion_high: float | None


class EvidenceOut(_Out):
    release: dict[str, Any]
    statements: Statements
    drug: str
    rows: list[EvidenceRowOut]
    attribution: list[str]
    reason_text: dict[str, str]


class SystemMetricOut(_Out):
    name: Literal["auc", "cmax"]
    n_drugs: int
    gmfe: float | None
    within_2_fold: int
    within_2_fold_share: float | None
    wilson_low: float | None
    wilson_high: float | None
    n_points: int
    points_within_2_fold: int
    points_gmfe: float | None


class SystemOut(_Out):
    release: dict[str, Any]
    statements: Statements
    n_drugs: int
    by_status: dict[str, int]
    metrics: list[SystemMetricOut]
    n_studies: int
    interpretable: bool
    min_drugs_for_interpretation: int
    n_drugs_both_tested: int
    conformal: str
    caveats: list[str]
    reason_text: dict[str, str]


def _holder(request: Request) -> ModelkitHolder | None:
    h = getattr(request.app.state, "modelkit", None)
    return h if isinstance(h, ModelkitHolder) else None


def _release(request: Request, release: str | None) -> Release | JSONResponse:
    h = _holder(request)
    rel = h.value if h else None
    if rel is None:
        return JSONResponse(UNAVAILABLE, status_code=503)
    if release is not None:
        if not RELEASE.match(release):
            return JSONResponse(
                {"error": "invalid_request", "fields": ["release"]}, status_code=422
            )
        if release != rel.run_id:
            return JSONResponse({"error": "unknown_release"}, status_code=404)
    return rel


def _drug(rel: Release, key: str) -> DrugEntry | JSONResponse:
    if not KEY.match(key):
        return JSONResponse({"error": "invalid_request", "fields": ["key"]}, status_code=422)
    d = rel.drugs.get(key)
    if d is None:
        return JSONResponse({"error": "unknown_drug"}, status_code=404)
    return d


def _metric(m: Metric) -> MetricOut:
    return MetricOut(**m.__dict__)


def summary(d: DrugEntry) -> DrugSummary:
    v = d.validation
    ps = d.built
    return DrugSummary(
        key=d.key,
        name=d.key.replace("_", " ").title(),
        status=v.status,
        status_reasons=list(v.reasons),
        has_set=isinstance(ps, ParameterSet),
        set_complete=isinstance(ps, ParameterSet) and ps.complete,
        basis=ps.basis if isinstance(ps, ParameterSet) else None,
        rows=len(d.rows),
        confirmed_rows=sum(1 for r in d.rows if r.confirmed),
        studies=len({r.study for r in d.rows}),
        auc=_metric(v.metrics[0]),
        cmax=_metric(v.metrics[1]),
        exportable=isinstance(ps, ParameterSet) and ps.complete,
    )


def validation_out(v: Validation) -> ValidationOut:
    return ValidationOut(
        status=v.status,
        reasons=list(v.reasons),
        metrics=[_metric(m) for m in v.metrics],
        points=[
            PointOut(
                evidence_id=p.eid, metric=p.metric, study_id=p.study_id, dose_mg=p.dose_mg,
                observed=p.observed, predicted=p.predicted, ratio=p.ratio, within_2_fold=p.within_2_fold,
            )
            for p in v.points
        ],
        excluded=[ReasonOut(evidence_id=e, reason=r) for e, r in v.excluded],
        suspect=list(v.suspect),
        failed_point_ids=list(v.failed_points),
        interval_reason=v.interval,
        interval_min_studies=MIN_STUDIES_FOR_INTERVAL,
        interval_n_studies=len({p.study_id for p in v.points}),
        band=[0.5, 2.0],
        unit_note="ratio = predicted / observed; AUC to infinity in ng*h/mL, Cmax in ng/mL",
    )  # fmt: skip


def set_out(ps: ParameterSet) -> SetOut:
    return SetOut(
        model=ps.model,
        model_reason=ps.model_reason,
        basis=ps.basis,
        apparent=ps.apparent,
        complete=ps.complete,
        missing=list(ps.missing),
        warnings=list(ps.warnings),
        implied_half_life_h=ps.implied_half_life_h,
        stated_half_life_h=ps.stated_half_life_h,
        params=[
            ParamOut(
                name=p.name, label=p.label, value=p.value, unit=p.unit, confidence_class=p.cls,
                n_studies=p.n_studies, between_study_cv=p.spread_cv, derivation=p.derivation,
                notes=[n for n in (p.note or "").split(";") if n], evidence_ids=list(p.evidence),
            )
            for p in ps.params
        ],
        left_out=[ReasonOut(evidence_id=e, reason=r) for e, r in ps.left_out],
        held_out_studies=[f"{s}:{t}" for s, t in ps.test_studies],
    )  # fmt: skip


def source_url(r: Ev) -> str | None:
    m = ex.source_info(r)
    return str(m["url"]) if m else None


def evidence_rows(d: DrugEntry) -> list[EvidenceRowOut]:
    ps = d.built
    used: set[str] = set(ps.used) if isinstance(ps, ParameterSet) else set()
    pts = {p.eid for p in d.validation.points}
    why = dict(ps.left_out) | dict(d.validation.excluded)
    out: list[EvidenceRowOut] = []
    for r in sorted(d.rows, key=lambda r: (r.parameter, r.study_id, r.source_locator, r.value)):
        role: Literal["building", "validation", "excluded"]
        if r.eid in used:
            role, reason = "building", None
        elif r.eid in pts:
            role, reason = "validation", None
        else:
            role, reason = "excluded", why.get(r.eid, "not used")
        out.append(
            EvidenceRowOut(
                id=r.eid, analyte=r.analyte, analyte_class=r.analyte_class, parameter=r.parameter,
                value=r.value, value_low=r.value_low, value_high=r.value_high, statistic=r.statistic,
                unit=r.unit, value_si=r.value_si, dose=r.dose, route=r.route, regimen=r.regimen,
                interval_h=r.interval_h, population=r.population, n_subjects=r.n_subjects,
                formulation=r.formulation, coadministered=r.coadministered, study_id=r.study_id,
                source_id=r.source_id, source_locator=r.source_locator,
                source_version=r.source_version, source_url=source_url(r), quote=r.quote,
                reader_a=r.reader_a, reader_b=r.reader_b, confirmed=r.confirmed,
                confirm_reason=r.confirm_reason, note=r.note, extracted_at=r.extracted_at,
                role=role, reason=reason, origin=r.origin, derivation=r.derivation,
                arm_id=r.arm_id, food=r.food, evidence_kind=r.evidence_kind,
                dispersion_type=r.dispersion_type, dispersion_low=r.dispersion_low,
                dispersion_high=r.dispersion_high,
            )
        )  # fmt: skip
    return out


ATTRIBUTION = [
    "ClinicalTrials.gov: source of the data is ClinicalTrials.gov; each row shows the record's last "
    "update and when it was retrieved; units were converted, values re-typed, rows filtered and short "
    "parts of the posted text quoted (modifications by Janus).",
    "DailyMed labels and Drugs@FDA reviews: public domain (U.S. government work). Not an FDA or NLM "
    "endorsement.",
    "PubMed Central articles: only CC BY or CC0 articles; credit the authors and the article, see the "
    "licence of each article; changes: values transcribed, units converted, short parts quoted.",
]


SEARCH = re.compile(r"^[a-z0-9 _.\-]{1,32}$")
MAX_LIMIT = 200
DEFAULT_LIMIT = 50


def _summaries(rel: Release) -> list[DrugSummary]:
    """The summaries of the release, computed once (the store never changes a release)."""
    cached = _SUMMARIES.get(rel.run_id)
    if cached is None:
        _SUMMARIES.clear()  # one release at a time
        cached = _SUMMARIES[rel.run_id] = [summary(d) for d in rel.drugs.values()]
    return cached


_SUMMARIES: dict[str, list[DrugSummary]] = {}


@router.get("/modelkit/drugs", response_model=DrugsOut)
def drugs(
    request: Request,
    release: str | None = None,
    q: str | None = None,
    status: str | None = None,
    has_set: bool | None = None,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
) -> Any:
    """The drugs of the experimental model kit with their validation status. `q` keeps the drugs
    whose name contains it, `status` and `has_set` filter; `limit` (at most 200) and `offset` page
    the answer. Sorted by name."""
    rel = _release(request, release)
    if isinstance(rel, JSONResponse):
        return rel
    bad: list[str] = []
    needle = (q or "").strip().lower()
    if q is not None and not SEARCH.match(needle):
        bad.append("q")
    if status is not None and status not in ("validated", "not_validated", "failed"):
        bad.append("status")
    if not 1 <= limit <= MAX_LIMIT:
        bad.append("limit")
    if offset < 0 or offset > 100_000:
        bad.append("offset")
    if bad:
        return JSONResponse({"error": "invalid_request", "fields": bad}, status_code=422)
    allrows = _summaries(rel)
    kept = [
        d
        for d in allrows
        if (not needle or needle.replace(" ", "_") in d.key or needle in d.name.lower())
        and (status is None or d.status == status)
        and (has_set is None or d.has_set == has_set)
    ]
    counts = {"all": len(allrows), "with_set": sum(d.has_set for d in allrows)}
    for st in ("validated", "not_validated", "failed"):
        counts[st] = sum(d.status == st for d in allrows)
    return DrugsOut(
        release=rel.info(),
        statements=Statements(),
        drugs=kept[offset : offset + limit],
        total=len(kept),
        offset=offset,
        limit=limit,
        counts=counts,
    )


@router.get("/modelkit/validation", response_model=SystemOut)
def system(request: Request, release: str | None = None) -> Any:
    """The system report over all drugs: counts by status, pooled fold errors with n."""
    rel = _release(request, release)
    if isinstance(rel, JSONResponse):
        return rel
    s = rel.system
    return SystemOut(
        release=rel.info(),
        statements=Statements(),
        n_drugs=s.n_drugs,
        by_status=s.by_status,
        metrics=[SystemMetricOut(**m.__dict__) for m in s.metrics],
        n_studies=s.n_studies,
        interpretable=s.interpretable,
        min_drugs_for_interpretation=s.min_drugs_for_interpretation,
        n_drugs_both_tested=s.n_drugs_both_tested,
        conformal=s.conformal,
        caveats=[
            "n_very_small",
            "two_automated_passes",
            "confirmed_precision_below_target",
            "expert_review_pending",
        ],
        reason_text=TEXT,
    )


@router.get("/modelkit/drugs/{key}", response_model=DrugOut)
def drug(request: Request, key: str, release: str | None = None) -> Any:
    """One drug: parameter set, validation report and what was left out."""
    rel = _release(request, release)
    if isinstance(rel, JSONResponse):
        return rel
    d = _drug(rel, key)
    if isinstance(d, JSONResponse):
        return d
    ps = d.built
    return DrugOut(
        release=rel.info(),
        statements=Statements(),
        summary=summary(d),
        parameter_set=set_out(ps) if isinstance(ps, ParameterSet) else None,
        no_set_reasons=list(ps.reasons) if isinstance(ps, NoSet) else [],
        validation=validation_out(d.validation),
        targets=list(ex.TARGETS) if isinstance(ps, ParameterSet) and ps.complete else [],
        reason_text=TEXT,
    )


@router.get("/modelkit/drugs/{key}/evidence", response_model=EvidenceOut)
def evidence(request: Request, key: str, release: str | None = None) -> Any:
    """Every evidence row of the drug with its quote, source and both reader verdicts."""
    rel = _release(request, release)
    if isinstance(rel, JSONResponse):
        return rel
    d = _drug(rel, key)
    if isinstance(d, JSONResponse):
        return d
    return EvidenceOut(
        release=rel.info(),
        statements=Statements(),
        drug=d.key,
        rows=evidence_rows(d),
        attribution=ATTRIBUTION,
        reason_text=TEXT,
    )


@router.get(
    "/modelkit/drugs/{key}/export/{target}",
    response_class=Response,
    responses={
        200: {"content": {"application/zip": {}}, "description": "Model files and provenance."}
    },
)
async def export(request: Request, key: str, target: str, release: str | None = None) -> Any:
    """A zip with the model file(s), provenance.json, references.bib and LICENSES.txt."""
    rel = _release(request, release)
    if isinstance(rel, JSONResponse):
        return rel
    d = _drug(rel, key)
    if isinstance(d, JSONResponse):
        return d
    if target not in ex.TARGETS:
        return JSONResponse({"error": "invalid_request", "fields": ["target"]}, status_code=422)
    ps = d.built
    if isinstance(ps, NoSet):
        return JSONResponse({"error": "no_parameter_set"}, status_code=409)
    if not ps.complete:
        return JSONResponse({"error": "incomplete_set"}, status_code=409)
    files = await run_in_threadpool(
        ex.export_files, target, ps, d.validation, list(d.rows), rel.info()
    )
    return Response(
        ex.build_zip(files),
        media_type="application/zip",
        headers={
            "content-disposition": f'attachment; filename="janus-modelkit-{key}-{target}.zip"',
            "x-janus-release": rel.run_id,
        },
    )
