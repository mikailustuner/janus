"""The open outcome dataset (open-data design §3, Req 1-3).

Released cells only, through the one release path of Collective Memory: for each candidate cell
(layer, ingredient set of one or two keys, Janus event key, direction) the stored contributors are
read by the layer's `UserLayerSource` and released by `memory.shared.release_cells` (k >= 20 on the
true count, the sibling rule, discrete Laplace noise deterministic per cell version). Hidden cells
are never listed, not even as "hidden": their existence would say that 1..k-1 contributors exist.

Candidates are enumerated in SQL and pre-filtered to sets with at least k stored contributors in
one region; the pre-filter only skips cells that `release_cells` would hide anyway. Nothing here
logs or returns a true count.
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import io
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from typing import Final

import psycopg

from janus.memory.disclosure import NoiseSource
from janus.memory.shared import UserLayerSource, release_cells

DATASET: Final = "janus-open-outcomes"
RULE_VERSION: Final = "open-outcomes-1"
LICENSE: Final = "CC BY 4.0"
LICENSE_URL: Final = "https://creativecommons.org/licenses/by/4.0/"
ATTRIBUTION: Final = (
    "Janus open outcome dataset (released cells of donated reports and doctor-confirmed "
    "outcomes), CC BY 4.0."
)
CSV_COLUMNS: Final = (
    "dataset_version",
    "snapshot_date",
    "layer",
    "ingredients",
    "event",
    "direction",
    "region",
    "value",
)
LAYERS: Final = ("contributions", "outcomes")
# Consent versions whose text names publication in this open dataset (safety-auditor review O1,
# open-data DP10). Empty until the owner issues such a consent text: a layer is released only
# when every stored row of it was given under one of these versions, so today's donations and
# outcome answers (consent 2026-11-v2: Collective Memory and research) are never published here.
OPEN_RELEASE_CONSENT_VERSIONS: Final[frozenset[str]] = frozenset()
_UNCONSENTED_CONTRIBUTIONS: Final = (
    "SELECT EXISTS (SELECT 1 FROM contributions WHERE NOT (consent_version = ANY(%s)))"
)
_UNCONSENTED_OUTCOMES: Final = (
    "SELECT EXISTS (SELECT 1 FROM outcomes WHERE assessment = 'confirmed' "
    "AND NOT (consent_version = ANY(%s)))"
)

# Ingredient sets of one and two keys per (event, direction, region) with at least k rows.
_SETS_CONTRIBUTIONS: Final = """
WITH t AS (SELECT ingredients, event, direction, region FROM contributions)
SELECT s, event, direction FROM (
  SELECT ARRAY[x] AS s, t.event, t.direction, t.region
    FROM t CROSS JOIN LATERAL unnest(t.ingredients) AS u(x)
  UNION ALL
  SELECT ARRAY[a, b] AS s, t.event, t.direction, t.region
    FROM t CROSS JOIN LATERAL unnest(t.ingredients) AS ua(a)
           CROSS JOIN LATERAL unnest(t.ingredients) AS ub(b)
   WHERE a < b
) q
GROUP BY s, event, direction, region
HAVING count(*) >= %s
"""
_SETS_OUTCOMES: Final = """
WITH t AS (
  SELECT ingredients, event, direction, region FROM outcomes WHERE assessment = 'confirmed'
)
SELECT s, event, direction FROM (
  SELECT ARRAY[x] AS s, t.event, t.direction, t.region
    FROM t CROSS JOIN LATERAL unnest(t.ingredients) AS u(x)
  UNION ALL
  SELECT ARRAY[a, b] AS s, t.event, t.direction, t.region
    FROM t CROSS JOIN LATERAL unnest(t.ingredients) AS ua(a)
           CROSS JOIN LATERAL unnest(t.ingredients) AS ub(b)
   WHERE a < b
) q
GROUP BY s, event, direction, region
HAVING count(*) >= %s
"""


@dataclass(frozen=True)
class Candidate:
    layer: str
    ingredients: tuple[str, ...]
    event: str
    direction: str


@dataclass(frozen=True)
class OpenCell:
    layer: str
    ingredients: tuple[str, ...]
    event: str
    direction: str
    region: str
    value: int


def candidates(conn: psycopg.Connection, layer: str, k: int) -> list[Candidate]:
    """Ingredient sets of one or two keys with at least k stored contributors in some region."""
    query = _SETS_OUTCOMES if layer == "outcomes" else _SETS_CONTRIBUTIONS
    seen: set[Candidate] = set()
    for s, event, direction in conn.execute(query, (k,)).fetchall():
        seen.add(Candidate(layer, tuple(sorted(str(x) for x in s)), str(event), str(direction)))
    return sorted(seen, key=lambda c: (c.layer, c.ingredients, c.event, c.direction))


def unconsented(conn: psycopg.Connection, layer: str, versions: frozenset[str]) -> bool:
    """True when a stored row of the layer was not given under an open-release consent."""
    query = _UNCONSENTED_OUTCOMES if layer == "outcomes" else _UNCONSENTED_CONTRIBUTIONS
    row = conn.execute(query, (sorted(versions),)).fetchone()
    return bool(row and row[0])


def release(
    conn: psycopg.Connection,
    sources: Mapping[str, UserLayerSource],
    *,
    k: int,
    epsilon: Fraction,
    noise_source: NoiseSource,
    consent_versions: frozenset[str] = OPEN_RELEASE_CONSENT_VERSIONS,
) -> tuple[list[OpenCell], list[str]]:
    """Every released cell of every layer that has a store, in a stable order, and the layers
    withheld because a stored row lacks an open-release consent (the whole layer, never a part
    of it: a partial layer would differ from `/memory/shared` and allow differencing)."""
    out: list[OpenCell] = []
    withheld: list[str] = []
    for layer in LAYERS:
        source = sources.get(layer)
        if source is None:
            continue
        if unconsented(conn, layer, consent_versions):
            withheld.append(layer)
            continue
        for c in candidates(conn, layer, k):
            rows = source.cells(conn, c.ingredients, c.event, c.direction)
            released, _ = release_cells(
                rows,
                layer=layer,
                ingredients=c.ingredients,
                event=c.event,
                direction=c.direction,
                k=k,
                epsilon=epsilon,
                noise_source=noise_source,
            )
            for cell in released:
                if cell.status == "released" and cell.value is not None:
                    out.append(
                        OpenCell(
                            layer, c.ingredients, c.event, c.direction, cell.region, cell.value
                        )
                    )
    return out, withheld


def version(cells: Sequence[OpenCell], k: int, epsilon: Fraction) -> str:
    """The rule version and a hash of the released cells (never of a true count)."""
    body = json.dumps(
        [RULE_VERSION, k, str(epsilon), [cell_row(c) for c in cells]],
        separators=(",", ":"),
    )
    return f"{RULE_VERSION}+{hashlib.sha256(body.encode()).hexdigest()[:12]}"


def cell_row(c: OpenCell) -> dict[str, object]:
    return {
        "layer": c.layer,
        "ingredients": list(c.ingredients),
        "event": c.event,
        "direction": c.direction,
        "region": c.region,
        "value": c.value,
    }


def to_csv(cells: Sequence[OpenCell], dataset_version: str, snapshot: dt.date) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(CSV_COLUMNS)
    for c in cells:
        w.writerow(
            [
                dataset_version,
                snapshot.isoformat(),
                c.layer,
                "|".join(c.ingredients),
                c.event,
                c.direction,
                c.region,
                c.value,
            ]
        )
    return buf.getvalue()
