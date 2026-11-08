"""Helpers for Collective Memory tests: counts files built from generated report facts, and a plain
Python reference of the 2x2 raw cells (independent of the SQL)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from janus.memory.faers_build import EXPOSURE_ROLES, SUSPECT_ROLES, BuildResult
from janus.memory.faers_build import ReportFact as ReportFact
from janus.memory.model import ALL_REGION, RESPONSE_REGIONS
from janus.memory.reader import RawCells
from janus.resolution.matching import Match
from tests.test_faers_build_properties import (
    INDEX,
    PTS,
    build,
    map_names,
    reports,
    write_artifact,
)

__all__ = [
    "INDEX",
    "PTS",
    "make_counts",
    "matches_for",
    "mk",
    "ref_cells",
    "ref_exposure",
    "reports",
]


def matches_for(facts: Sequence[ReportFact]) -> dict[str, Match]:
    return map_names({n for f in facts for _r, ing in f.lines for n in ing}, INDEX)


def make_counts(data_dir: Path, facts: Sequence[ReportFact], *, name: str = "run1") -> BuildResult:
    write_artifact(data_dir, facts, name=name)
    return build(data_dir)


def report_keys(f: ReportFact, matches: Mapping[str, Match]) -> dict[str, bool]:
    """Ingredient key -> suspect flag, for the exposure roles of one report."""
    keys: dict[str, bool] = {}
    for role, names in f.lines:
        if role not in EXPOSURE_ROLES:
            continue
        for n in names:
            m = matches[n]
            if m.status == "mapped":
                keys[m.keys[0]] = keys.get(m.keys[0], False) or role in SUSPECT_ROLES
    return keys


def in_exposure(ks: Mapping[str, bool], keys: Sequence[str], scope: str) -> bool:
    return all(k in ks and (scope == "any" or ks[k]) for k in keys)


def ref_cells(
    facts: Sequence[ReportFact],
    matches: Mapping[str, Match],
    keys: Sequence[str],
    pts: Sequence[str],
    scope: str,
    region: str,
) -> RawCells:
    n_m = n_a = exposure = ev_m = ev_a = a = 0
    for f in facts:
        if region != ALL_REGION and f.region != region:
            continue
        ks = report_keys(f, matches)
        mapped = bool(ks)
        n_a += 1
        n_m += mapped
        has_exposure = in_exposure(ks, keys, scope)
        has_event = any(pt in f.events for pt in pts)
        exposure += has_exposure
        ev_a += has_event
        ev_m += has_event and mapped
        a += has_exposure and has_event
    return RawCells(n_m, n_a, exposure, ev_m, ev_a, a)


def ref_exposure(
    facts: Sequence[ReportFact],
    matches: Mapping[str, Match],
    keys: Sequence[str],
    scope: str,
    region: str,
) -> int:
    return sum(
        in_exposure(report_keys(f, matches), keys, scope)
        for f in facts
        if region == ALL_REGION or f.region == region
    )


ALL_REGIONS = RESPONSE_REGIONS


def mk[T: BaseModel](model: type[T], **fields: Any) -> T:
    """Build a request model from plain values (validated, like the route does)."""
    return model.model_validate(fields)
