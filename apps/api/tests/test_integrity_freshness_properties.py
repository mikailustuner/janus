"""Freshness and registry cadence (evidence-integrity design §4.3): P7, P8."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st

from janus.integrity.freshness import (
    age_days,
    check_is_stale,
    freshness,
    parse_snapshot_date,
)
from janus.integrity.model import IntegritySnapshot
from janus.integrity.registry import parse_sources, read_sources
from janus.integrity.view import build_item
from tests.integrity_strategies import SOURCES, TODAY, snapshots

DAYS = st.dates(dt.date(2000, 1, 1), dt.date(2040, 12, 31))
CADENCE = st.integers(1, 400)


@given(DAYS, DAYS, CADENCE)
def test_p7_stale_iff_age_over_twice_cadence(snap: dt.date, today: dt.date, cadence: int) -> None:
    """Feature: evidence-integrity, Property P7 (Req 2.2)."""
    f = freshness(snap, today, cadence)
    days = today.toordinal() - snap.toordinal()
    assert f.age_days == max(0, days)
    assert f.limit_days == 2 * cadence
    assert (f.state == "stale") == (days > 2 * cadence)


@given(DAYS, CADENCE)
def test_p7_boundary(snap: dt.date, cadence: int) -> None:
    at_limit = dt.date.fromordinal(snap.toordinal() + 2 * cadence)
    over = dt.date.fromordinal(snap.toordinal() + 2 * cadence + 1)
    assert freshness(snap, at_limit, cadence).state == "current"
    assert freshness(snap, over, cadence).state == "stale"


@given(DAYS, DAYS, st.integers(0, 3000), CADENCE)
def test_p7_future_and_monotone(snap: dt.date, today: dt.date, step: int, cadence: int) -> None:
    assert age_days(snap, snap - dt.timedelta(days=5)) == 0
    later = today + dt.timedelta(days=step)
    if freshness(snap, today, cadence).state == "stale":
        assert freshness(snap, later, cadence).state == "stale"


@given(DAYS, DAYS)
def test_p7_no_cadence_is_not_applicable(snap: dt.date, today: dt.date) -> None:
    f = freshness(snap, today, None)
    assert f.state == "not_applicable"
    assert f.limit_days is None
    assert not check_is_stale(snap, today, None)


@given(
    st.datetimes(
        min_value=dt.datetime(2001, 1, 2),
        max_value=dt.datetime(2040, 1, 1),
        timezones=st.timezones(),
    )
)
def test_p7_date_parser(value: dt.datetime) -> None:
    assert parse_snapshot_date(value.isoformat()) == value.astimezone(dt.UTC).date()
    naive = value.replace(tzinfo=None)
    assert parse_snapshot_date(naive.isoformat()) == naive.date()
    assert parse_snapshot_date(value.date().isoformat()) == value.date()


@given(snapshots(), st.dates(dt.date(2025, 1, 1), dt.date(2030, 1, 1)))
def test_p7_freshness_never_changes_status_or_citability(
    snap: IntegritySnapshot, day: dt.date
) -> None:
    for rid in snap.records:
        a = build_item(snap, rid, TODAY)
        b = build_item(snap, rid, day)
        assert a.citable == b.citable
        assert a.exclusion_reason == b.exclusion_reason
        assert (a.integrity.status if a.integrity else None) == (
            b.integrity.status if b.integrity else None
        )


STORAGES = st.sampled_from(["runtime_only", "cache", "commit", "separate_package", "cited_only"])


@st.composite
def registries(draw: st.DrawFn) -> dict[str, int | None]:
    n = draw(st.integers(0, 8))
    out: dict[str, int | None] = {}
    for i in range(n):
        out[f"src_{i}"] = draw(st.one_of(st.none(), CADENCE))
    return out


@given(registries(), st.data())
def test_p8_cadence_comes_from_the_registry(
    spec: dict[str, int | None], data: st.DataObject
) -> None:
    """Feature: evidence-integrity, Property P8 (Req 2.1)."""
    parts = ['[notice]\nheader = "x"\n']
    for sid, cad in spec.items():
        storage = data.draw(STORAGES)
        extra = f"cadence_days = {cad}\n" if cad is not None else ""
        parts.append(
            f'[[sources]]\nid = "{sid}"\nname = "Name {sid}"\nstorage = "{storage}"\n'
            f'license = "L"\nunknown_key = true\n{extra}'
        )
    parsed = parse_sources("\n".join(parts))
    assert {k: v.cadence_days for k, v in parsed.items()} == spec


def test_p8_real_registry() -> None:
    reg = read_sources(Path(__file__).resolve().parents[3] / "pipelines" / "sources.toml")
    assert reg["titck"].cadence_days == 7
    assert reg["openfda_ndc"].cadence_days == 7
    assert reg["crossref"].cadence_days == 7
    assert reg["pipc"].cadence_days == 365
    assert reg["bmj_2026"].cadence_days is None
    assert reg["pipc"].license == "CC BY 4.0"
    assert SOURCES["crossref"].cadence_days == 7
