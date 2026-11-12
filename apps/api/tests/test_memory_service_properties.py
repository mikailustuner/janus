"""Cells, regions, combinations and the ladder (collective-memory design §10: P7-P14, P24, P31).

Each example builds one counts file from generated report facts with the builder's own SQL, then
checks many queries against a plain-Python recount.
"""

from __future__ import annotations

import datetime as dt
import json
import tempfile
from pathlib import Path

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from janus.memory import service
from janus.memory.ladder import all_pairs, choose_level
from janus.memory.model import ALL_REGION, REGIONS, RESPONSE_REGIONS
from janus.memory.reader import CountsHolder
from janus.memory.schemas import CombinationIn, PairIn, RegionsIn
from janus.memory.vocabulary import parse_events
from tests.memory_counts import PTS, make_counts, matches_for, mk, ref_cells, ref_exposure, reports
from tests.test_faers_build_properties import ReportFact
from tests.test_memory_vocabulary_properties import (
    ADVERSE_PLACEHOLDERS,
    BENEFIT_PLACEHOLDERS,
    render,
)

KEYS = ["Q1", "Q2", "Q3"]  # the keys the builder test's name index maps to
SCOPES = ["suspect", "any"]
TODAY = dt.date(2026, 11, 8)


def vocab_text() -> str:
    """A small active vocabulary: key 'pain_group' = {Pain, Rash}, 'single' = {Nausea}."""
    rows: list[dict[str, str]] = []
    for i, key in enumerate(ADVERSE_PLACEHOLDERS):
        rows.append(
            {
                "key": key,
                "direction": "adverse",
                **{f"label_{c}": "x" for c in ("en", "tr", "de", "fr", "es", "pt")},
                "pts": {0: "Pain|Rash", 1: "Nausea"}.get(i, "Dizziness"),
                "pipc_positions": ";".join(
                    str(p) for p in range(1, 66) if p % len(ADVERSE_PLACEHOLDERS) == i
                ),
                "status": "active",
            }
        )
    for key in BENEFIT_PLACEHOLDERS:
        rows.append(
            {
                "key": key,
                "direction": "benefit",
                **{f"label_{c}": "x" for c in ("en", "tr", "de", "fr", "es", "pt")},
                "status": "active",
            }
        )
    return render(rows)


VOCAB = parse_events(vocab_text())
FIRST_KEY = ADVERSE_PLACEHOLDERS[0]  # Pain|Rash
SECOND_KEY = ADVERSE_PLACEHOLDERS[1]  # Nausea


def ctx(served: str | None = None) -> service.Context:
    return service.Context(VOCAB, TODAY, served)


@settings(max_examples=15, deadline=None)
@given(reports(min_size=1, max_size=14), st.data())
def test_cells_equal_a_recount_and_both_paths_agree(
    facts: list[ReportFact], data: st.DataObject
) -> None:
    """Feature: collective-memory, Properties P7, P11, P14 — Validates: Req 1.1, 2.1, 6.4.
    The raw cells from the count tables equal a recount from the report facts for every region and
    scope; the precomputed path and the report-level path give the same cells; a set's exposure
    count equals the recount and never rises when an ingredient is added.
    """
    with tempfile.TemporaryDirectory() as d:
        make_counts(Path(d), facts)
        reader = CountsHolder(Path(d)).current()
        matches = matches_for(facts)
        with reader.session() as s:
            for _ in range(6):
                key = data.draw(st.sampled_from(KEYS))
                pts = data.draw(st.lists(st.sampled_from(PTS), min_size=1, max_size=3, unique=True))
                scope = data.draw(st.sampled_from(SCOPES))
                got = s.cells([key], pts, scope, RESPONSE_REGIONS)
                forced = s.cells([key], pts, scope, RESPONSE_REGIONS, force_report_level=True)
                for region in RESPONSE_REGIONS:
                    want = ref_cells(facts, matches, [key], pts, scope, region)
                    assert got[region] == want, (region, scope)
                    assert forced[region] == want, (region, scope)
                    c = got[region]
                    # the 2x2 identities of data-pipelines Req 15.5
                    assert c.a <= min(c.exposure, c.event_mapped) and c.event_mapped <= c.event_all
                    assert c.exposure + c.event_mapped - c.a <= c.n_mapped
            subset = data.draw(st.lists(st.sampled_from(KEYS), min_size=2, max_size=3, unique=True))
            scope = data.draw(st.sampled_from(SCOPES))
            counts = s.exposure_by_region(subset, scope)
            for region in RESPONSE_REGIONS:
                assert counts[region] == ref_exposure(facts, matches, subset, scope, region)
                smaller = s.exposure_by_region(subset[:-1], scope) if len(subset) > 2 else None
                if smaller is not None:
                    assert counts[region] <= smaller[region]
            # order of the keys never matters
            assert s.exposure_by_region(list(reversed(subset)), scope) == counts


@settings(max_examples=12, deadline=None)
@given(reports(min_size=2, max_size=12), st.data())
def test_responses_do_not_depend_on_report_or_request_order(
    facts: list[ReportFact], data: st.DataObject
) -> None:
    """Feature: collective-memory, Property P8 — Validates: Req 7.4."""
    shuffled = data.draw(st.permutations(facts))
    ings = data.draw(st.lists(st.sampled_from(KEYS), min_size=2, max_size=3, unique=True))
    out: list[str] = []
    for order, rows in ((ings, facts), (list(reversed(ings)), shuffled)):
        with tempfile.TemporaryDirectory() as d:
            make_counts(Path(d), rows)
            reader = CountsHolder(Path(d)).current()
            with reader.session() as s:
                combo = service.combination(
                    s,
                    mk(CombinationIn, ingredients=order, region="ALL", scope="any", top_events=10),
                    ctx(),
                )
                pair = service.pair(
                    s,
                    mk(
                        PairIn,
                        ingredient=ings[0],
                        event={"pt": "Pain"},
                        region="ALL",
                        scope="suspect",
                    ),
                    ctx(),
                )
            # build ids differ; the statistics do not
            a = combo.model_dump(mode="json")
            b = pair.model_dump(mode="json")
            for x in (a, b):
                x["snapshot"].pop("build_id")
                x["snapshot"].pop("faers_run_id")
            out.append(json.dumps([a, b], sort_keys=True))
    assert out[0] == out[1]


@settings(max_examples=12, deadline=None)
@given(reports(min_size=1, max_size=14), st.data())
def test_pair_sensitivity_and_list_order(facts: list[ReportFact], data: st.DataObject) -> None:
    """Feature: collective-memory, P9 (service part), P10 — Validates: Req 1.7, 1.8, 2.1."""
    with tempfile.TemporaryDirectory() as d:
        make_counts(Path(d), facts)
        reader = CountsHolder(Path(d)).current()
        matches = matches_for(facts)
        key = data.draw(st.sampled_from(KEYS))
        pt = data.draw(st.sampled_from(PTS))
        scope = data.draw(st.sampled_from(SCOPES))
        region = data.draw(st.sampled_from(list(RESPONSE_REGIONS)))
        with reader.session() as s:
            out = service.pair(
                s, mk(PairIn, ingredient=key, event={"pt": pt}, region=region, scope=scope), ctx()
            )
            assert s.statements <= 6
            combo = service.combination(
                s,
                mk(CombinationIn, ingredients=KEYS, region=region, scope=scope, top_events=50),
                ctx(),
            )
            assert s.statements <= 6 + 12
    assert out.stats is not None
    raw = ref_cells(facts, matches, [key], [pt], scope, region)
    st_ = out.stats
    c = st_.cells
    assert (c.a, c.b, c.c, c.d, c.n) == (
        raw.a,
        raw.exposure - raw.a,
        raw.event_mapped - raw.a,
        raw.n_mapped - raw.exposure - raw.event_mapped + raw.a,
        raw.n_mapped,
    )
    sc = st_.sensitivity.cells
    assert (sc.a, sc.b) == (raw.a, raw.exposure - raw.a)
    assert (
        sc.c == raw.event_all - raw.a and sc.d == raw.n_all - raw.exposure - raw.event_all + raw.a
    )
    assert (
        st_.denominator_sensitive
        == st_.sensitivity.differs
        == (st_.sensitivity.assessment != st_.assessment)
    )
    if raw.n_all == raw.n_mapped and raw.event_all == raw.event_mapped:
        assert not st_.denominator_sensitive
    assert out.citation is not None and out.citation.evidence_id == "dataset:faers"
    # lists are ordered by reports, then PT, whatever the assessment
    for items in (
        combo.events,
        *[g.events for g in combo.pairs],
        *[g.events for g in combo.singles],
    ):
        order = [(-e.reports, e.pt) for e in items]
        assert order == sorted(order)


@settings(max_examples=12, deadline=None)
@given(reports(min_size=1, max_size=14), st.data())
def test_regions_add_up_and_filter_equals_the_row(
    facts: list[ReportFact], data: st.DataObject
) -> None:
    """Feature: collective-memory, Property P13 — Validates: Req 3.1, 3.3, 3.5."""
    key = data.draw(st.sampled_from(KEYS))
    pt = data.draw(st.sampled_from(PTS))
    with tempfile.TemporaryDirectory() as d:
        make_counts(Path(d), facts)
        reader = CountsHolder(Path(d)).current()
        with reader.session() as s:
            out = service.regions(s, mk(RegionsIn, ingredients=[key], event={"pt": pt}), ctx())
            assert s.statements <= 8
            rows = {r.region: r for r in out.rows}
            filtered = {
                r: service.pair(
                    s,
                    mk(PairIn, ingredient=key, event={"pt": pt}, region=r, scope="suspect"),
                    ctx(),
                )
                for r in RESPONSE_REGIONS
            }
            no_event = service.regions(s, mk(RegionsIn, ingredients=[key]), ctx())
    assert [r.region for r in out.rows] == list(RESPONSE_REGIONS)
    for field in ("n_primary", "n_all", "reports"):
        assert sum(getattr(rows[r], field) for r in REGIONS) == getattr(rows[ALL_REGION], field)
    all_stats = rows[ALL_REGION].stats
    assert all_stats is not None
    parts = [st_.cells.a for r in REGIONS if (st_ := rows[r].stats) is not None]
    assert sum(parts) == all_stats.cells.a
    for region in RESPONSE_REGIONS:
        assert filtered[region].stats == rows[region].stats  # filter uses only that region's counts
    assert sum(r.reports for r in no_event.rows if r.region != ALL_REGION) == next(
        r.reports for r in no_event.rows if r.region == ALL_REGION
    )
    # shares
    assert out.unknown.reports == rows["UNKNOWN"].n_all
    total = rows[ALL_REGION].n_all
    assert (out.unknown.share == out.unknown.reports / total) if total else out.unknown.share == 0.0
    basis = {b.region: b for b in out.basis}
    for r in RESPONSE_REGIONS:
        assert basis[r].occurrence + basis[r].reporter_fallback == rows[r].n_all
        assert basis[r].reporter_fallback <= rows[r].n_all


@settings(max_examples=12, deadline=None)
@given(reports(min_size=1, max_size=14), st.data())
def test_janus_key_union_and_unknown_event(facts: list[ReportFact], data: st.DataObject) -> None:
    """Feature: collective-memory, Property P14 — Validates: Req 6.4."""
    key = data.draw(st.sampled_from(KEYS))
    with tempfile.TemporaryDirectory() as d:
        make_counts(Path(d), facts)
        reader = CountsHolder(Path(d)).current()
        matches = matches_for(facts)
        with reader.session() as s:
            by_key = service.pair(
                s,
                mk(PairIn, ingredient=key, event={"key": FIRST_KEY}, region="ALL", scope="any"),
                ctx(),
            )
            one = service.pair(
                s,
                mk(PairIn, ingredient=key, event={"key": SECOND_KEY}, region="ALL", scope="any"),
                ctx(),
            )
            single_pt = service.pair(
                s,
                mk(PairIn, ingredient=key, event={"pt": "Nausea"}, region="ALL", scope="any"),
                ctx(),
            )
            ghost = service.pair(
                s,
                mk(
                    PairIn,
                    ingredient=key,
                    event={"pt": "Zzz Not A Term"},
                    region="ALL",
                    scope="any",
                ),
                ctx(),
            )
            benefit = service.pair(
                s,
                mk(
                    PairIn,
                    ingredient=key,
                    event={"key": BENEFIT_PLACEHOLDERS[0]},
                    region="ALL",
                    scope="any",
                ),
                ctx(),
            )
    want = ref_cells(facts, matches, [key], ["Pain", "Rash"], "any", ALL_REGION)
    assert by_key.stats is not None and by_key.stats.cells.a == want.a
    assert by_key.stats.cells.n == want.n_mapped
    assert by_key.event.pts == ["Pain", "Rash"]
    # a key with one PT equals the PT path (same cells, same statistics)
    assert one.stats == single_pt.stats
    assert (
        ghost.event.reported_in_window is False
        and ghost.stats is not None
        and ghost.stats.cells.a == 0
    )
    assert ghost.stats.assessment == "no_reports" and ghost.stats.estimates is None
    assert benefit.status == "not_available" and benefit.stats is None and benefit.citation is None


@settings(max_examples=200, deadline=None)
@given(
    st.integers(2, 20),
    st.integers(0, 10),
    st.dictionaries(
        st.tuples(st.sampled_from("ABCD"), st.sampled_from("EFGH")), st.integers(0, 10), max_size=6
    ),
)
def test_ladder(n: int, combo: int, pairs: dict[tuple[str, str], int]) -> None:
    """Feature: collective-memory, Property P12 (pure part) — Validates: Req 2.2."""
    ch = choose_level(n, combo, pairs, 3)
    reaching = sorted(p for p, c in pairs.items() if c >= 3)
    if combo >= 3:
        assert ch.level == "combination" and ch.skipped == ()
    elif n >= 3 and reaching:
        assert ch.level == "pairwise" and list(ch.pairs) == reaching
        assert ch.skipped == (("combination", "below_display_threshold"),)
    else:
        assert ch.level == "single" and ch.pairs == ()
        expect = [("combination", "below_display_threshold")]
        if n >= 3:
            expect.append(("pairwise", "below_display_threshold"))
        assert list(ch.skipped) == expect
    assert all(pairs[p] >= 3 for p in ch.pairs)
    assert len(all_pairs(list("ABCDE"))) == 10


@settings(max_examples=12, deadline=None)
@given(reports(min_size=1, max_size=16), st.data())
def test_ladder_on_the_database(facts: list[ReportFact], data: st.DataObject) -> None:
    """Feature: collective-memory, Properties P12, P31 — Validates: Req 2.1-2.4."""
    ings = data.draw(st.lists(st.sampled_from([*KEYS, "Q99"]), min_size=2, max_size=4, unique=True))
    scope = data.draw(st.sampled_from(SCOPES))
    with tempfile.TemporaryDirectory() as d:
        make_counts(Path(d), facts)
        reader = CountsHolder(Path(d)).current()
        matches = matches_for(facts)
        with reader.session() as s:
            out = service.combination(
                s,
                mk(CombinationIn, ingredients=ings, region="ALL", scope=scope, top_events=50),
                ctx(),
            )
            used = s.statements
    assert used <= 12
    combo = ref_exposure(facts, matches, ings, scope, ALL_REGION)
    assert out.combination.reports == combo
    pair_ref = {
        p: ref_exposure(facts, matches, list(p), scope, ALL_REGION) for p in all_pairs(ings)
    }
    ch = choose_level(len(ings), combo, pair_ref, 3)
    assert out.level == ch.level
    assert [(x.level, x.reason) for x in out.skipped] == list(ch.skipped)
    by_key = {r.key: r for r in out.ingredients}
    for k in ings:
        n = ref_exposure(facts, matches, [k], scope, ALL_REGION)
        assert by_key[k].reports == n and (by_key[k].assessment == "no_reports") == (n == 0)
    assert out.exposure == "all_of_set" and out.comparison == "all_other_mapped_reports"
    if out.level == "combination":
        assert out.pairs == [] and out.singles == []
        for e in out.events:
            assert len(e.members_alone) == len(ings)
            assert all(m.reports >= e.reports for m in e.members_alone)  # P31
            assert e.reports <= combo
        want = {pt: ref_cells(facts, matches, ings, [pt], scope, ALL_REGION).a for pt in PTS}
        assert {e.pt: e.reports for e in out.events} == {pt: n for pt, n in want.items() if n > 0}
    elif out.level == "pairwise":
        assert [tuple(g.keys) for g in out.pairs] == list(ch.pairs)
        assert all(g.reports >= 3 for g in out.pairs) and out.events == [] and out.singles == []
    else:
        assert [g.key for g in out.singles] == sorted(ings) and out.events == [] and out.pairs == []
    assume(True)
