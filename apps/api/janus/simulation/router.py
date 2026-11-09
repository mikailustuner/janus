"""`/simulate` routes (simulation-service design §7). Medical routes: `no-store`, nothing logged
but the access line (route, status, latency), JSON bodies of at most 1 KiB.

- `GET /simulate/compounds`: the allow-list (compound and virtual-population ids, dose bounds,
  scenarios, validation), the limits and whether server runs are on.
- `POST /simulate`: validate, rate-limit, then reuse a cached or running identical job or queue
  a new one. 202 with the job while queued or running, 200 when the result is already there;
  429 `queue_full` or `rate_limited` with `Retry-After`; 422 naming fields only; 503
  `simulation_unavailable` when switched off or without a database.
- `GET /simulate/jobs/{job_id}`: state, queue position, the result when done. 404 `unknown_job`
  (also after expiry), 422 for an id that is not a UUID.

No individualised simulation (owner decision 2026-11-09): requests name a predefined virtual
population, results are distributions over it. Every answer of these routes, errors included,
carries the disclaimer ("Virtual population, for research. Not about any person and not a dose
recommendation."); job answers also carry the model's validation status.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import uuid
from dataclasses import dataclass, field
from typing import Any

import psycopg
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from janus.db.pool import Database
from janus.http_policy.routes import medical_router
from janus.settings import Settings
from janus.simulation import queue as q
from janus.simulation.allowlist import AllowList, Validation, allowlist
from janus.simulation.ratelimit import Limiter, Window, client_address
from janus.simulation.schemas import (
    DISCLAIMER,
    CompartmentalIn,
    InvalidRequestError,
    JobOut,
    canonical,
    input_hash,
    parse,
)

router = medical_router()

POLL_AFTER_S = 2
_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")


@dataclass
class SimulationLimits:
    """Per-client and global windows (design §7, DP-S7). Submissions: 3 per 30 s and 5 per
    10 min per client (half the queue: one client cannot fill it), 120 per 10 min in total.
    Polls: 120 per minute per client."""

    submit: Limiter = field(
        default_factory=lambda: Limiter(
            per_client=(Window(3, 30), Window(5, 600)), global_=(Window(120, 600),)
        )
    )
    poll: Limiter = field(default_factory=lambda: Limiter(per_client=(Window(120, 60),)))


def now() -> dt.datetime:  # replaced in tests
    return dt.datetime.now(dt.UTC)


def _error(
    status: int, error: str, fields: list[str] | None = None, retry: int | None = None
) -> JSONResponse:
    body: dict[str, Any] = {"error": error}
    if fields is not None:
        body["fields"] = fields
    body["disclaimer"] = DISCLAIMER  # every answer of these routes carries it (owner 2026-11-09)
    headers = {"retry-after": str(retry)} if retry is not None else None
    return JSONResponse(body, status_code=status, headers=headers)


def _limits(request: Request) -> SimulationLimits:
    lim = getattr(request.app.state, "simulation_limits", None)
    if not isinstance(lim, SimulationLimits):
        lim = SimulationLimits()
        request.app.state.simulation_limits = lim
    return lim


def _client(request: Request) -> str:
    headers = {k.decode().lower(): v.decode("latin-1") for k, v in request.scope.get("headers", [])}
    peer = request.client.host if request.client else None
    settings: Settings = request.app.state.settings
    return client_address(headers, peer, settings.trust_cf_connecting_ip)


def _db(request: Request) -> Database | None:
    settings: Settings = request.app.state.settings
    db = getattr(request.app.state, "database", None)
    return db if settings.simulation_enabled and isinstance(db, Database) else None


def validation_for(kind: str, compound: str, allow: AllowList) -> dict[str, Any]:
    model = "compartmental" if kind == "compartmental" else "httk"
    v: Validation = (
        allow.compartmental[compound].validation
        if model == "compartmental"
        else allow.httk[compound].validation
    )
    return {
        "model": model,
        "credibility": v.credibility,
        "cmax_fold": v.cmax_fold,
        "auc_fold": v.auc_fold,
        "auc_independent": v.auc_independent,
        "reference_key": v.reference_key,
        "cmax_direction": v.cmax_direction,
        "auc_direction": v.auc_direction,
        "validated_scope": allow.compartmental[compound].validated_scope
        if model == "compartmental"
        else "one oral dose per drug in healthy adults (time-machine validation table)",
    }


def job_out(job: q.Job, position: int | None, reused: bool, allow: AllowList) -> dict[str, Any]:
    out = JobOut(
        job_id=str(job.id),
        state=job.state,  # pyright: ignore[reportArgumentType]
        cached=reused and job.state == "done",
        queue_position=position,
        error=job.error,  # pyright: ignore[reportArgumentType]
        input=job.input,
        result=job.result,
        validation=validation_for(job.kind, str(job.input["compound"]), allow),  # pyright: ignore[reportArgumentType]
        disclaimer=DISCLAIMER,
        expires_at=job.expires_at.isoformat(),
    )
    return out.model_dump(mode="json") | {"poll_after_s": POLL_AFTER_S}


@router.get("/simulate/compounds")
def compounds(request: Request) -> Any:
    """The allow-list as the form needs it. Static data; no request is needed to run the
    in-browser explorer, which ships the same file."""
    allow = allowlist()
    settings: Settings = request.app.state.settings
    return JSONResponse(
        {
            "version": allow.version,
            "server_runs": settings.simulation_enabled,
            "compartmental": [
                {
                    "id": c.id,
                    "dose_mg": {"low": c.dose.low, "default": c.dose.default, "high": c.dose.high},
                    "intervals_h": list(c.intervals_h),
                    "scenarios": [
                        {"id": s.id, "dose_mg": s.dose_mg, "kind": s.kind, "note": s.note}
                        for s in c.scenarios
                    ],
                    "populations": [
                        {"id": p.id, "cl_factor": p.cl_factor, "reference_keys": p.reference_keys}
                        for p in c.populations.values()
                    ],
                    "validation": validation_for("compartmental", c.id, allow),
                }
                for c in allow.compartmental.values()
            ],
            "httk": [
                {"id": h.id, "validation": validation_for("httk_population", h.id, allow)}
                for h in allow.httk.values()
            ],
            "httk_populations": [
                {"id": p.id, "age_years": [p.age_low, p.age_high]}
                for p in allow.httk_populations.values()
            ],
            "limits": {
                "queue_max": q.QUEUE_MAX,
                "slots": q.SLOTS,
                "job_timeout_s": q.JOB_TIMEOUT_S,
                "result_ttl_h": int(q.RESULT_TTL.total_seconds() // 3600),
                "horizon_after_last_dose_h": allow.limits.horizon_after_last_dose_h,
                "horizon_max_h": allow.limits.horizon_max_h,
                "doses_max": allow.limits.doses_max,
                "population_samples": [
                    allow.limits.population_samples_min,
                    allow.limits.population_samples_max,
                ],
                "compartmental_samples": [
                    allow.limits.compartmental_samples_min,
                    allow.limits.compartmental_samples_max,
                ],
            },
            "disclaimer": DISCLAIMER,
        }
    )


@router.post("/simulate")
async def simulate(request: Request) -> Any:
    db = _db(request)
    if db is None:
        return _error(503, "simulation_unavailable")
    decision = _limits(request).submit.check(_client(request))
    if not decision.allowed:
        return _error(429, "rate_limited", retry=decision.retry_after)
    try:
        payload = json.loads(await request.body())
    except (ValueError, UnicodeDecodeError):
        return _error(422, "invalid_request", ["body"])
    allow = allowlist()
    try:
        req = parse(payload, allow)
    except InvalidRequestError as exc:
        return _error(422, "invalid_request", exc.fields)
    canon = canonical(req)
    key = input_hash(canon, allow.version)
    kind = "compartmental" if isinstance(req, CompartmentalIn) else req.kind
    at = now()

    def call() -> tuple[q.Job, bool, int | None]:
        with db.write_tx() as conn:
            job, reused = q.submit(conn, kind, canon, key, at)
            found = q.get(conn, job.id, at)
            return job, reused, found[1] if found else None

    try:
        job, reused, position = await run_in_threadpool(call)
    except q.QueueFullError as exc:
        return _error(429, "queue_full", retry=exc.retry_after)
    except psycopg.Error:
        return _error(503, "simulation_unavailable")
    body = job_out(job, position, reused, allow)
    return JSONResponse(body, status_code=200 if job.state == "done" else 202)


@router.get("/simulate/jobs/{job_id}")
async def job_status(request: Request, job_id: str) -> Any:
    if not _UUID.fullmatch(job_id):
        return _error(422, "invalid_request", ["job_id"])
    db = _db(request)
    if db is None:
        return _error(503, "simulation_unavailable")
    decision = _limits(request).poll.check(_client(request))
    if not decision.allowed:
        return _error(429, "rate_limited", retry=decision.retry_after)
    at = now()

    def call() -> tuple[q.Job, int | None] | None:
        with db.read_only_tx() as conn:
            return q.get(conn, uuid.UUID(job_id), at)

    try:
        found = await run_in_threadpool(call)
    except psycopg.Error:
        return _error(503, "simulation_unavailable")
    if found is None:
        return _error(404, "unknown_job")
    job, position = found
    return JSONResponse(job_out(job, position, False, allowlist()))
