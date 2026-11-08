"""User layers: contributions, and the interface for outcomes (design §5.3, Req 4-5).

Counts only, never a rate: donations and outcomes have no comparison group. A cell is
(ingredient set, Janus event key, direction, region); its true contributor count is the number of
stored donations naming all the ingredients, the event and the direction in that region. A donation
is a donation, not a person (`privacy` DP13).

Release goes through the shared `release_table` (k >= 20 decided on the TRUE count, discrete
Laplace noise with scale 1/epsilon, totals from released cells only). Before it, the **sibling
rule** (Req 5.8, statistics review Q9) hides a cell when a nested cell of the same event, direction
and region could reveal, by subtraction, a group smaller than k. The noise of a cell is
deterministic per (cell, version of its contributors), so deleting or adding a donation of the
cell changes its version, and unrelated donations never redraw it.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from typing import Final, Protocol

import psycopg

from janus.memory import messages
from janus.memory.disclosure import Cell, NoiseSource, release_table
from janus.memory.model import USER_LAYER_REGIONS
from janus.memory.schemas import DisclosureOut, SharedCellOut, SharedIn, SharedOut

DATA_VERSION: Final = "memory-shared-1"

_COUNTS = (
    "SELECT region, count(*), "
    "encode(sha256(convert_to(string_agg(id::text, ',' ORDER BY id), 'UTF8')), 'hex') "
    "FROM contributions "
    "WHERE ingredients @> %s::text[] AND event = %s AND direction = %s GROUP BY region"
)
_SIBLINGS = (
    "SELECT c.region, x.x, count(*) FROM contributions c "
    "CROSS JOIN LATERAL unnest(c.ingredients) AS x(x) "
    "WHERE c.ingredients @> %s::text[] AND c.event = %s AND c.direction = %s "
    "AND NOT (x.x = ANY(%s::text[])) GROUP BY c.region, x.x"
)


@dataclass(frozen=True)
class ContributorCell:
    """True numbers behind one cell. Never leaves the server."""

    region: str
    n: int  # donations naming all the ingredients, the event and the direction
    version: str  # hash of the ids of those donations
    siblings: Mapping[str, int]  # other ingredient -> donations of the cell that also name it


class UserLayerSource(Protocol):
    def cells(
        self, conn: psycopg.Connection, ingredients: Sequence[str], event: str, direction: str
    ) -> list[ContributorCell]: ...


class ContributionsSource:
    """The `contributions` table (privacy spec), read inside the caller's read-only transaction."""

    def cells(
        self, conn: psycopg.Connection, ingredients: Sequence[str], event: str, direction: str
    ) -> list[ContributorCell]:
        wanted = sorted(set(ingredients))
        counts = conn.execute(_COUNTS, (wanted, event, direction)).fetchall()
        siblings: dict[str, dict[str, int]] = {}
        for region, other, m in conn.execute(
            _SIBLINGS, (wanted, event, direction, wanted)
        ).fetchall():
            siblings.setdefault(str(region), {})[str(other)] = int(m)
        return [
            ContributorCell(str(region), int(n), str(version), siblings.get(str(region), {}))
            for region, n, version in counts
        ]


# --- pure rules ------------------------------------------------------------------------------


def sibling_rule_count(cell: ContributorCell, k: int) -> int:
    """The count passed to `release_table`: the true count, or 0 when the cell is ineligible.

    Eligible iff n >= k and, for every other ingredient X, the donations of the cell that do not
    name X number 0 or at least k (so the nested cell S+X never differs from S by 1..k-1).
    """
    if cell.n < k:
        return 0
    for m in cell.siblings.values():
        if 0 < cell.n - m < k:
            return 0
    return cell.n


def release_cells(
    cells: Sequence[ContributorCell],
    *,
    layer: str,
    ingredients: Sequence[str],
    event: str,
    direction: str,
    k: int,
    epsilon: Fraction,
    noise_source: NoiseSource,
) -> tuple[list[SharedCellOut], int | None]:
    """Released and hidden cells for TR, EU and US, and the total of the released ones."""
    by_region = {c.region: c for c in cells}
    table: list[Cell] = []
    versions: dict[str, str] = {}
    key_ingredients = ",".join(sorted(set(ingredients)))
    for region in USER_LAYER_REGIONS:
        cell = by_region.get(region)
        count = 0 if cell is None else sibling_rule_count(cell, k)
        version = "" if cell is None else cell.version
        versions[region] = version
        table.append(Cell((layer, region, key_ingredients, event, direction, version), count))
    release = release_table(
        table, k=k, epsilon=epsilon, noise_source=noise_source, data_version=DATA_VERSION
    )
    released = {r.key[1]: r.value for r in release.cells}
    out = [
        SharedCellOut(region=region, status="released", value=released[region])  # pyright: ignore[reportArgumentType]
        if region in released
        else SharedCellOut(region=region, status="hidden")  # pyright: ignore[reportArgumentType]
        for region in USER_LAYER_REGIONS
    ]
    return out, release.total_of_released


def disclosure(k: int, epsilon: Fraction) -> DisclosureOut:
    return DisclosureOut(k=k, epsilon=str(epsilon))


def unavailable(req: SharedIn, status: str, k: int, epsilon: Fraction) -> SharedOut:
    return SharedOut(
        layer=req.layer,
        status=status,  # pyright: ignore[reportArgumentType]
        cells=[],
        total_of_released=None,
        disclosure=disclosure(k, epsilon),
        disclaimer=messages.DISCLAIMER,
        notices=[status],
    )


def shared(
    req: SharedIn,
    *,
    sources: Mapping[str, UserLayerSource],
    conn: psycopg.Connection | None,
    noise_source: NoiseSource | None,
    k: int,
    epsilon: Fraction,
) -> SharedOut:
    """Answer one user-layer request. No FAERS figure ever enters here.

    `sources` maps a layer to its store. `outcomes` has no store until doctor-loop provides one; the
    answer is then `not_available`, never an empty or zero count (Req 4.7).
    """
    source = sources.get(req.layer)
    if source is None and req.layer == "outcomes":
        return unavailable(req, "not_available", k, epsilon)
    if source is None or conn is None or noise_source is None:
        return unavailable(req, "layer_unavailable", k, epsilon)
    cells = source.cells(conn, req.ingredients, req.event, req.direction)
    out, total = release_cells(
        cells,
        layer=req.layer,
        ingredients=req.ingredients,
        event=req.event,
        direction=req.direction,
        k=k,
        epsilon=epsilon,
        noise_source=noise_source,
    )
    return SharedOut(
        layer=req.layer,
        status="ok",
        cells=out,
        total_of_released=total,
        disclosure=disclosure(k, epsilon),
        disclaimer=messages.DISCLAIMER,
        notices=["hidden_under_20_noise_added"],
    )
