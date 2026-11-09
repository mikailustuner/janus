"""`/timemachine` routes (design §10). Medical routes: read-only, stateless, `no-store`,
nothing logged but the access line. Everything served is precomputed by
`python -m janus.timemachine.build`; no model runs on a request.

503 when the artifact is not installed; 404 for an unknown id (the id is a curated key, not
user data, so it may be named back).
"""

from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from janus.http_policy.routes import medical_router
from janus.timemachine.schemas import CascadeOut, CatalogueOut, Meta, SubstanceOut
from janus.timemachine.store import Holder, TimeMachine

router = medical_router()

MAX_ID = 64


def _holder(request: Request) -> Holder | None:
    value = getattr(request.app.state, "timemachine", None)
    return value if isinstance(value, Holder) else None


def _loaded(request: Request) -> TimeMachine | JSONResponse:
    holder = _holder(request)
    value = holder.value if holder is not None else None
    if value is None:
        return JSONResponse({"error": "time_machine_not_installed"}, status_code=503)
    return value


def _meta(tm: TimeMachine) -> Meta:
    return Meta(
        built_at=tm.built_at,
        review_status="Expert review has not yet been done",
        disclaimer=tm.payload["disclaimer"],
        seed=int(tm.payload["seed"]),
        simulations=int(tm.payload["simulations"]),
    )


def _valid(identifier: str) -> bool:
    return 0 < len(identifier) <= MAX_ID and identifier.replace("_", "").isalnum()


@router.get("/timemachine/catalogue", response_model=CatalogueOut)
def catalogue(request: Request) -> Any:
    tm = _loaded(request)
    if isinstance(tm, JSONResponse):
        return tm
    return CatalogueOut(
        meta=_meta(tm),
        substance_ids=tm.substance_ids,
        cascade_ids=tm.cascade_ids,
        validation=tm.payload["validation"],
        sources=tm.payload["sources"],
        onset_subset_caveat=tm.payload["onset_subset_caveat"],
    )


@router.get("/timemachine/substance/{substance_id}", response_model=SubstanceOut)
def substance(request: Request, substance_id: str) -> Any:
    tm = _loaded(request)
    if isinstance(tm, JSONResponse):
        return tm
    if not _valid(substance_id):
        return JSONResponse(
            {"error": "invalid_request", "fields": ["substance_id"]}, status_code=422
        )
    found = tm.substance(substance_id)
    if found is None:
        return JSONResponse({"error": "unknown_substance"}, status_code=404)
    return SubstanceOut(
        meta=_meta(tm),
        substance=found,
        exposure=tm.exposure_for(substance_id),
        references=tm.payload["references"],
    )


@router.get("/timemachine/cascade/{cascade_id}", response_model=CascadeOut)
def cascade(request: Request, cascade_id: str) -> Any:
    tm = _loaded(request)
    if isinstance(tm, JSONResponse):
        return tm
    if not _valid(cascade_id):
        return JSONResponse({"error": "invalid_request", "fields": ["cascade_id"]}, status_code=422)
    found = tm.cascade(cascade_id)
    if found is None:
        return JSONResponse({"error": "unknown_cascade"}, status_code=404)
    return CascadeOut(
        meta=_meta(tm),
        cascade=found,
        faers_quality=tm.payload["faers_quality"],
        onset_subset_caveat=tm.payload["onset_subset_caveat"],
        references=tm.payload["references"],
    )
