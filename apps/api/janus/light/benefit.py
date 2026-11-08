"""Patient-reported layer: donated reports of an improvement (design §5.4, Req 3, DP7; P8).

One discovery statement lists the (ingredient, benefit key) cells whose true count reaches k; each
is then answered by the collective-memory user-layer release (`janus.memory.shared.shared`): TR,
EU and US cells, the sibling rule, k = 20 on the true count, discrete Laplace noise, and the total
of released cells only. A cell whose regions are all hidden yields nothing. True counts never leave
this module. A donation is a donation, not a person.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from fractions import Fraction
from typing import Final

import psycopg

from janus.light.schemas import PatientCellOut, PatientSignalOut
from janus.memory.disclosure import NoiseSource
from janus.memory.schemas import SharedIn, SharedOut
from janus.memory.shared import UserLayerSource, shared

MAX_CELLS: Final = 100
DISCOVER: Final = (
    "SELECT x.x, c.event FROM contributions c CROSS JOIN LATERAL unnest(c.ingredients) AS x(x) "
    "WHERE c.direction = 'benefit' AND c.event = ANY(%s) "
    "GROUP BY 1, 2 HAVING count(*) >= %s ORDER BY 1, 2 LIMIT %s"
)


def discover(
    conn: psycopg.Connection, events: Sequence[str], k: int, limit: int = MAX_CELLS
) -> list[tuple[str, str]]:
    """Cells worth asking; the count used here is never returned."""
    if not events:
        return []
    rows = conn.execute(DISCOVER, (sorted(set(events)), k, limit)).fetchall()
    return [(str(r[0]), str(r[1])) for r in rows]


def to_signal(out: SharedOut, event: str) -> PatientSignalOut | None:
    """A released cell as a card signal; None when nothing was released."""
    if out.status != "ok" or out.total_of_released is None:
        return None
    return PatientSignalOut(
        event=event,
        total_of_released=out.total_of_released,
        cells=[PatientCellOut(region=c.region, status=c.status, value=c.value) for c in out.cells],
        k=out.disclosure.k,
        epsilon=out.disclosure.epsilon,
    )


def released(
    conn: psycopg.Connection,
    events: Sequence[str],
    *,
    sources: Mapping[str, UserLayerSource],
    noise_source: NoiseSource,
    k: int,
    epsilon: Fraction,
) -> dict[tuple[str, str], PatientSignalOut]:
    """(ingredient, event) -> released signal, for the given benefit keys."""
    out: dict[tuple[str, str], PatientSignalOut] = {}
    for ingredient, event in discover(conn, events, k):
        answer = shared(
            SharedIn(
                layer="contributions", ingredients=[ingredient], event=event, direction="benefit"
            ),
            sources=sources,
            conn=conn,
            noise_source=noise_source,
            k=k,
            epsilon=epsilon,
        )
        signal = to_signal(answer, event)
        if signal is not None:
            out[(ingredient, event)] = signal
    return out
