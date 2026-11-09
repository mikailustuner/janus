"""Request validation and normalisation of the simulation service (simulation-service design §4,
DP-S2, DP-S5, owner decision 2026-11-09). Pure.

No individualised simulation: a request names a compound and a predefined virtual population
from the allow-list; a compartmental run may also set a dose, a dosing interval and a number of
doses within hard bounds. There is no person-specific field (body weight, age, sex, kidney or
liver function, genotype, name, …) and no free text: unknown fields are rejected, numbers are
strict (no strings, no booleans, finite), ids follow a fixed pattern and must be on the
allow-list.

`canonical` gives the form used for the cache key: the parameters of the kind only, numbers
rounded to 6 significant digits. Equal canonical forms run the same model.
"""

from __future__ import annotations

import hashlib
import json
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from janus.simulation.allowlist import AllowList

Id = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,31}$")]
Num = Annotated[float, Field(allow_inf_nan=False)]


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class CompartmentalIn(_In):
    kind: Literal["compartmental"]
    compound: Id
    population: Id
    dose_mg: Num
    interval_h: Annotated[int, Field(ge=1, le=168)] | None
    doses: Annotated[int, Field(ge=1, le=100)]
    samples: Annotated[int, Field(ge=1, le=100_000)]


class HttkPopulationIn(_In):
    """Both HTTK-Pop age ranges in one run: the older-to-younger comparison is the result."""

    kind: Literal["httk_population"]
    compound: Id
    samples: Annotated[int, Field(ge=1, le=100_000)]


SimulationIn = Annotated[CompartmentalIn | HttkPopulationIn, Field(discriminator="kind")]
_adapter: TypeAdapter[CompartmentalIn | HttkPopulationIn] = TypeAdapter(SimulationIn)
REQUEST_MODELS = (CompartmentalIn, HttkPopulationIn)


class InvalidRequestError(ValueError):
    """Names failing field paths only; never a value or an unknown field's name."""

    def __init__(self, fields: list[str]) -> None:
        super().__init__("invalid request")
        self.fields = sorted(set(fields)) or ["body"]


_KINDS = {"compartmental", "httk_population"}


def _fields(exc: ValidationError) -> list[str]:
    out: list[str] = []
    for e in exc.errors():
        if e["type"] == "extra_forbidden":
            out.append("<unknown>")  # the name is the sender's text (cds-hooks rule)
            continue
        # The discriminator value and union branch names appear in `loc`; keep our field names.
        parts = [str(p) for p in e["loc"] if str(p) in _FIELD_NAMES]
        out.append(".".join(parts[:1]) or "body")
    return out


_FIELD_NAMES = {n for m in REQUEST_MODELS for n in m.model_fields}


def parse(payload: Any, allow: AllowList) -> CompartmentalIn | HttkPopulationIn:
    """Validate a decoded JSON body against the schema and the allow-list."""
    if not isinstance(payload, dict):
        raise InvalidRequestError(["body"])
    try:
        req = _adapter.validate_python(payload)
    except ValidationError as exc:
        raise InvalidRequestError(_fields(exc)) from None
    lim = allow.limits
    bad: list[str] = []
    if isinstance(req, CompartmentalIn):
        c = allow.compartmental.get(req.compound)
        if c is None:
            raise InvalidRequestError(["compound"])
        if req.population not in c.populations:
            bad.append("population")
        if not c.dose.contains(req.dose_mg):
            bad.append("dose_mg")
        if not (1 <= req.doses <= lim.doses_max):
            bad.append("doses")
        if req.doses == 1 and req.interval_h is not None:
            bad.append("interval_h")
        if req.doses > 1 and req.interval_h not in c.intervals_h:
            bad.append("interval_h")
        # Never cut a schedule short: the whole schedule and 48 h after it must fit.
        elif (req.doses - 1) * (req.interval_h or 0) + lim.horizon_after_last_dose_h > (
            lim.horizon_max_h
        ):
            bad.append("doses")
        if not (lim.compartmental_samples_min <= req.samples <= lim.compartmental_samples_max):
            bad.append("samples")
    else:
        if req.compound not in allow.httk:
            raise InvalidRequestError(["compound"])
        if not (lim.population_samples_min <= req.samples <= lim.population_samples_max):
            bad.append("samples")
    if bad:
        raise InvalidRequestError(bad)
    return req


def _round(x: float) -> float:
    return float(f"{x:.6g}")


def canonical(req: CompartmentalIn | HttkPopulationIn) -> dict[str, Any]:
    """The kind's parameters only, floats at 6 significant digits."""
    return {k: (_round(v) if isinstance(v, float) else v) for k, v in req.model_dump().items()}


def input_hash(canon: dict[str, Any], allow_version: str) -> str:
    """SHA-256 of the canonical form and the allow-list version (a new list, a new key)."""
    text = json.dumps({"v": allow_version, "in": canon}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode()).hexdigest()


# --- answers ---------------------------------------------------------------------------------

JobState = Literal["queued", "running", "done", "failed"]

# Owner decision 2026-11-09: every result carries this sentence; then the in-silico label and the
# standing disclaimer (medical-safety rule 9).
VIRTUAL_POPULATION = (
    "Virtual population, for research. Not about any person and not a dose recommendation."
)
DISCLAIMER = (
    f"{VIRTUAL_POPULATION} In silico and exploratory. "
    "Janus provides information, not medical advice. Research prototype — not a medical device."
)


class _Out(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ValidationOut(_Out):
    model: Literal["compartmental", "httk"]
    credibility: Literal["credible", "borderline", "failed"]
    cmax_fold: float
    auc_fold: float
    auc_independent: bool
    reference_key: str
    cmax_direction: Literal["model_lower", "model_higher"]
    auc_direction: Literal["model_lower", "model_higher"]
    validated_scope: str


class JobOut(_Out):
    job_id: str
    state: JobState
    cached: bool
    queue_position: int | None
    error: Literal["timeout", "model_failed", "expired", "worker_lost"] | None
    input: dict[str, Any]
    result: dict[str, Any] | None
    validation: ValidationOut
    disclaimer: str
    expires_at: str
