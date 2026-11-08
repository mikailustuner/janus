"""The `outcomes` user layer of Collective Memory (doctor-loop design §8, Req 11).

Implements `UserLayerSource` with the same statement shape as `ContributionsSource`: a cell
(ingredient set, Janus event key, direction, region) counts the stored outcomes with assessment
`confirmed` whose ingredient pair contains the set. Release (k = 20, noise, sibling rule, hidden
answers) is the shared code path in `memory/shared.py`; outcomes are never combined with donations.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

import psycopg

from janus.memory.shared import ContributorCell

_COUNTS: Final = (
    "SELECT region, count(*), "
    "encode(sha256(convert_to(string_agg(id::text, ',' ORDER BY id), 'UTF8')), 'hex') "
    "FROM outcomes "
    "WHERE assessment = 'confirmed' AND ingredients @> %s::text[] AND event = %s "
    "AND direction = %s GROUP BY region"
)
_SIBLINGS: Final = (
    "SELECT o.region, x.x, count(*) FROM outcomes o "
    "CROSS JOIN LATERAL unnest(o.ingredients) AS x(x) "
    "WHERE o.assessment = 'confirmed' AND o.ingredients @> %s::text[] AND o.event = %s "
    "AND o.direction = %s AND NOT (x.x = ANY(%s::text[])) GROUP BY o.region, x.x"
)


class OutcomesSource:
    """Doctor-confirmed outcomes, read inside the caller's read-only transaction."""

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
