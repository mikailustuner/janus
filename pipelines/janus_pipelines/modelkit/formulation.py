"""Formulation and route of confirmed values from the study record (spec model-kit, milestone M3, design DP-M22).

Two resolvers read the study record independently (`formulation_a`, pattern based; `formulation_b`, token and
structure based). This module is the only place where they meet: where they agree the result is used; where they
disagree the formulation is `unspecified` and the route is kept as the readers had it (or unknown). A formulation
is never assumed: nothing stated stays `unspecified`. After resolution the confirmation of the pair is decided
again by code, because the context of both candidates now carries the same formulation. Research use only.
Not for clinical decisions.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import replace
from typing import Any

from janus_pipelines.modelkit import formulation_a, formulation_b
from janus_pipelines.modelkit.confirm import confirm
from janus_pipelines.modelkit.formref import BrandTable, Resolution
from janus_pipelines.modelkit.model import Candidate
from janus_pipelines.modelkit.pairing import Paired
from janus_pipelines.modelkit.resolver import IdentityTable


def combine(a: Resolution, b: Resolution) -> Resolution:
    """The agreed formulation and route; a disagreement is unresolved."""
    if a.formulation == b.formulation:
        form, why = a.formulation, a.why if a.why == b.why else f"{a.why}|{b.why}"
    else:
        form, why = "unspecified", "resolvers_disagree"
    route = a.route if a.route == b.route else "unknown"
    return Resolution(form, route, why)


def _apply(c: Candidate, res: Resolution, route: str) -> Candidate:
    note = "formulation:" + (res.why or "not stated")
    return replace(
        c,
        context=replace(c.context, formulation=res.formulation, route=route),
        notes=(*c.notes, note),
    )


def resolve_pairs(
    pairs: list[Paired],
    study: dict[str, Any],
    table: IdentityTable,
    brands: BrandTable,
    counts: Counter[str],
) -> list[Paired]:
    out: list[Paired] = []
    for p in pairs:
        if p.b is None:  # never confirmed: left as read
            out.append(p)
            continue
        ra = formulation_a.resolve(study, p.a.drug_key, p.a.locator, table, brands)
        rb = formulation_b.resolve(study, p.b.drug_key, p.b.locator, table, brands)
        res = combine(ra, rb)
        counts["pairs_resolved"] += 1
        if ra.formulation != rb.formulation:
            counts["formulation_resolvers_disagree"] += 1
        if ra.route != rb.route:
            counts["route_resolvers_disagree"] += 1
        route = res.route
        had_a, had_b = p.a.context.route, p.b.context.route
        if route == "unknown" and had_a == had_b and had_a != "unknown":
            route = had_a  # both readers found it independently of the resolvers
        if res.formulation == "other_route" and had_a == had_b == "other":
            route = "other"
        if route != "unknown" and had_a == had_b and had_a not in ("unknown", route):
            route = "unknown"  # the readers and the resolvers contradict each other
            counts["route_conflict"] += 1
        a2, b2 = _apply(p.a, res, route), _apply(p.b, res, route)
        out.append(Paired(a2, b2, confirm(a2.reading(), b2.reading())))
    return out
