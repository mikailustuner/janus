"""Data-quality report: checks, classification, diff, outputs and routes (data-quality design §10).

Properties P1-P8 of the design; synthetic data only (no TİTCK string in the repository).
"""

from __future__ import annotations

import csv
import io
import json
import random
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from hypothesis import given
from hypothesis import strategies as st

from janus.http_policy.routes import RouteKind, route_kind
from janus.main import create_app
from janus.quality import checks as c
from janus.quality import report as r
from janus.quality.build import views
from janus.quality.router import DataQualityHolder
from janus.quality.router import router as quality_router
from janus.resolution.atc import AtcCode
from janus.resolution.prepare import PreparedDataset, PreparedIngredient, PreparedProduct

KEYS = ("Q1", "Q2", "Q3", "Q4")
# Codes in three level-4 groups, two of them in the same level-2 group (A01).
CODES = ("A01AA01", "A01AA02", "A01AB01", "B02BC03", "C09DA08")
SOURCES = (c.TITCK, c.CIMA)

observations_st = st.lists(
    st.builds(
        c.Observation,
        st.sampled_from(SOURCES),
        st.sampled_from(KEYS),
        st.sampled_from(CODES),
        st.integers(1, 5),
    ),
    max_size=12,
    unique_by=lambda o: (o.source, o.key, o.code),
)
items_st = st.dictionaries(
    st.sampled_from(KEYS),
    st.lists(st.sampled_from(CODES), max_size=3, unique=True),
)
exclusions_st = st.lists(
    st.tuples(
        st.sampled_from(KEYS), st.sampled_from(CODES), st.sampled_from(("titck", "wikidata"))
    ),
    max_size=3,
    unique=True,
)


@st.composite
def inputs_st(draw: st.DrawFn) -> c.Inputs:
    obs = tuple(draw(observations_st))
    items = {k: c.Item(k, f"label {k}", tuple(sorted(v))) for k, v in draw(items_st).items()}
    exclusions = tuple(
        c.Exclusion(k, code, src, "wrong_substance", "https://atcddd.fhi.no/x", "2026-11-08")
        for k, code, src in draw(exclusions_st)
    )
    comb = frozenset(draw(st.lists(st.sampled_from(CODES), max_size=2)))
    return c.Inputs(obs, items, exclusions, combination_codes=comb)


def _reference_item_group(inp: c.Inputs) -> set[tuple[str, str, str]]:
    excluded = {e.triple for e in inp.exclusions}
    out: set[tuple[str, str, str]] = set()
    for o in inp.observations:
        item = inp.items.get(o.key)
        if (o.key, o.code, o.source) in excluded or item is None or not item.codes:
            continue
        if all(o.code[:5] != x[:5] for x in item.codes):
            out.add((o.source, o.key, o.code))
    return out


@given(inputs_st())
def test_p1_confirmed_error_iff_reviewed_exclusion(inp: c.Inputs) -> None:
    found = c.run_checks(inp)
    triples = {e.triple for e in inp.exclusions}
    for f in found:
        is_confirmed = f.klass is c.Klass.confirmed_error
        assert is_confirmed == (f.check is c.Check.exclusion_status)
        if is_confirmed:
            assert (f.key, f.code, f.source) in triples
    assert len([f for f in found if f.klass is c.Klass.confirmed_error]) == len(triples)


@given(inputs_st())
def test_p2_item_group_is_exactly_the_level4_disagreements(inp: c.Inputs) -> None:
    got = {(f.source, f.key, f.code) for f in c.item_group_findings(inp)}
    assert got == _reference_item_group(inp)


@given(inputs_st())
def test_p3_benign_only_when_both_regulators_agree_and_nothing_else_explains_it(
    inp: c.Inputs,
) -> None:
    pairs = {(o.source, o.key, o.code) for o in inp.observations}
    for f in c.item_group_findings(inp):
        other = c.CIMA if f.source == c.TITCK else c.TITCK
        corroborated = (other, f.key, f.code) in pairs
        benign = f.klass is c.Klass.benign_difference
        assert benign == (
            corroborated
            and not f.other_keys
            and f.code not in inp.combination_codes
            and not any((f.key, f.code, s) in {e.triple for e in inp.exclusions} for s in SOURCES)
        )
        assert benign or f.klass is c.Klass.needs_pharmacist
        assert f.reasons


@given(inputs_st(), st.randoms(use_true_random=False))
def test_p4_order_of_inputs_does_not_change_the_findings(inp: c.Inputs, rnd: random.Random) -> None:
    obs = list(inp.observations)
    rnd.shuffle(obs)
    items = list(inp.items.items())
    rnd.shuffle(items)
    shuffled = c.Inputs(tuple(obs), dict(items), inp.exclusions[::-1], (), inp.combination_codes)
    assert c.run_checks(shuffled) == c.run_checks(inp)


@given(inputs_st())
def test_regulator_group_needs_both_regulators_and_no_shared_group(inp: c.Inputs) -> None:
    for f in c.regulator_group_findings(inp):
        assert f.klass is c.Klass.needs_pharmacist
        assert all(a[:5] != b[:5] for a in f.code.split("|") for b in f.compared_codes)


def test_substance_code_reaching_two_keys_is_a_finding() -> None:
    lines = [(c.BDPM, "123", "NAME A"), (c.BDPM, "123", "NAME B"), (c.CIMA, "9", "X")]
    keys = {(c.BDPM, "NAME A"): ["Q1"], (c.BDPM, "NAME B"): ["Q2"], (c.CIMA, "X"): ["Q3"]}
    subs = c.substance_codes(lines, keys)
    found = c.substance_code_findings(c.Inputs((), {}, substance_codes=subs))
    assert [(f.source, f.code, f.other_keys) for f in found] == [(c.BDPM, "123", ("Q1", "Q2"))]


def test_exclusion_upstream_status_follows_the_source() -> None:
    items = {"Q1": c.Item("Q1", "a", ("A01AA01",)), "Q2": c.Item("Q2", "b", ("B02BC03",))}
    exclusions = (
        c.Exclusion("Q1", "A01AA01", "wikidata", "wrong_substance", "u", "d"),
        c.Exclusion("Q2", "A01AA02", "wikidata", "old_code", "u", "d"),
        c.Exclusion("Q3", "C09DA08", "titck", "wrong_substance", "u", "d"),
        c.Exclusion("Q4", "B02BC03", "titck", "wrong_substance", "u", "d"),
    )
    obs = (c.Observation(c.TITCK, "Q3", "C09DA08", 2),)
    found = {f.key: f.upstream for f in c.exclusion_findings(c.Inputs(obs, items, exclusions))}
    assert found == {
        "Q1": c.Upstream.persisting,
        "Q2": c.Upstream.resolved_upstream,
        "Q3": c.Upstream.persisting,
        "Q4": c.Upstream.resolved_upstream,
    }


# --- diff, version, outputs ----------------------------------------------------------------

record_ids = st.lists(
    st.sampled_from([f"item_group:titck:Q{i}:A01AA01" for i in range(8)]), unique=True
)


def _record(i: str, klass: str = "needs_pharmacist") -> dict[str, Any]:
    return {"id": i, "class": klass, "check": "item_group", "upstream": None}


@given(record_ids, record_ids)
def test_p5_diff_partitions_current_and_previous(prev: list[str], cur: list[str]) -> None:
    d = r.diff([_record(i) for i in cur], [_record(i) for i in prev])
    new = {x["id"] for x in d.current if x["status"] == "new"}
    persisting = {x["id"] for x in d.current if x["status"] == "persisting"}
    assert new | persisting == set(cur)
    assert not new & persisting
    assert persisting == set(cur) & set(prev)
    assert {x["id"] for x in d.resolved} == set(prev) - set(cur)
    first = r.diff([_record(i) for i in cur], None)
    assert all(x["status"] == "new" for x in first.current) and not first.resolved
    again = r.diff([_record(i) for i in cur], [_record(i) for i in cur])
    assert all(x["status"] == "persisting" for x in again.current) and not again.resolved


def test_a_class_change_names_the_previous_class() -> None:
    d = r.diff([_record("x", "benign_difference")], [_record("x")])
    assert d.current[0]["class_changed_from"] == "needs_pharmacist"


@given(record_ids, record_ids)
def test_p6_version_changes_iff_the_findings_change(a: list[str], b: list[str]) -> None:
    va = r.version([_record(i) for i in a])
    vb = r.version([_record(i) for i in reversed(b)])
    assert (va == vb) == (set(a) == set(b))
    assert va.startswith(r.RULE_VERSION + "+")


META = r.RunMeta("20261109T000000Z-abc", "2026-11-09", None, "dataset-x", {"titck": {}})


@given(inputs_st())
def test_p7_csv_has_one_row_per_finding_with_the_version(inp: c.Inputs) -> None:
    rep = r.build_report(c.run_checks(inp), inp.items, META, None)
    rows = list(csv.DictReader(io.StringIO(r.to_csv(rep))))
    assert [x["finding_id"] for x in rows] == [f["id"] for f in rep["findings"]]
    assert all(x["dataset_version"] == rep["version"] for x in rows)
    assert rep["summary"]["findings"] == len(rep["findings"])
    assert sum(rep["summary"]["by_class"].values()) == len(rep["findings"])


SENTINELS = ("ZZPRODUCTNAME", "8699999999999", "ZZINGREDIENTSPELLING", "ZZBRAND")


def _product(source: str, pid: int, code: str | None, keys: list[str | None]) -> PreparedProduct:
    ings = tuple(
        PreparedIngredient(
            i,
            f"{SENTINELS[2]} {i}",
            "5 mg",
            "mapped" if k else "unmapped",
            None if k else "no_ingredient_key",
            k,
            (),
            "tr_label" if k else None,
            (AtcCode(code, source),) if k and code else (),
            None,
            (),
            None,
        )
        for i, k in enumerate(keys)
    )
    return PreparedProduct(
        source,
        pid,
        "TR" if source == c.TITCK else "EU",
        f"{SENTINELS[0]} {pid}",
        SENTINELS[3],
        None,
        SENTINELS[2],
        code,
        None,
        (),
        None,
        None,
        None,
        False,
        (),
        (("tr_barcode", SENTINELS[1], SENTINELS[1]),),
        ings,
    )


@given(
    st.lists(
        st.tuples(
            st.sampled_from(SOURCES),
            st.sampled_from((*CODES, None)),
            st.lists(st.sampled_from((*KEYS, None)), min_size=1, max_size=2),
        ),
        max_size=10,
    ),
    items_st,
)
def test_p8_no_product_string_reaches_any_output(
    products: list[tuple[str, str | None, list[str | None]]], item_codes: dict[str, list[str]]
) -> None:
    ds = PreparedDataset(
        tuple(_product(s, i, code, keys) for i, (s, code, keys) in enumerate(products)),
        {},
        (),
        {},
        {},
    )
    obs, presence = c.reduce_products(views(ds))
    items = {k: c.Item(k, None, tuple(v)) for k, v in item_codes.items()}
    inp = c.Inputs(obs, items, presence=presence)
    rep = r.build_report(c.run_checks(inp), items, META, None)
    blob = json.dumps(rep) + r.to_csv(rep) + r.to_markdown(rep)
    for s in SENTINELS:
        assert s not in blob


def test_reduce_counts_single_ingredient_products_with_one_mapped_key() -> None:
    ds = PreparedDataset(
        (
            _product(c.TITCK, 1, "A01AA01", ["Q1"]),
            _product(c.TITCK, 2, "A01AA01", ["Q1"]),
            _product(c.TITCK, 3, "A01AA01", ["Q1", "Q2"]),  # two ingredients: presence only
            _product(c.TITCK, 4, "A01AA01", [None]),  # not mapped
            _product(c.CIMA, 5, None, ["Q1"]),  # no code
        ),
        {},
        (),
        {},
        {},
    )
    obs, presence = c.reduce_products(views(ds))
    assert obs == (c.Observation(c.TITCK, "Q1", "A01AA01", 2),)
    assert presence == {"Q1": {c.TITCK: 3, c.CIMA: 1}, "Q2": {c.TITCK: 1}}


# --- routes ------------------------------------------------------------------------------


def _report() -> dict[str, Any]:
    items = {"Q1": c.Item("Q1", "alpha", ("A01AA01",))}
    inp = c.Inputs((c.Observation(c.TITCK, "Q1", "B02BC03", 3),), items)
    return r.build_report(c.run_checks(inp), items, META, None, {"note": "x"})


@pytest.fixture
def app(tmp_path: Path) -> FastAPI:
    root = tmp_path / "quality" / "current"
    root.mkdir(parents=True)
    (root / "report.json").write_text(json.dumps(_report()), encoding="utf-8")
    application = create_app(configure_logs=False)
    application.state.data_quality = DataQualityHolder(tmp_path)
    return application


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as cl:
        yield cl


def test_routes_are_medical_get_only() -> None:
    for route in quality_router.routes:
        assert route_kind(route) is RouteKind.medical
        assert getattr(route, "methods", set[str]()) == {"GET"}


def test_routes_serve_json_csv_and_markdown(client: TestClient) -> None:
    body = client.get("/open/data-quality").json()
    assert body["dataset"] == "janus-data-quality"
    assert body["findings"][0]["class"] == "needs_pharmacist"
    assert body["findings"][0]["status"] == "new"
    res = client.get("/open/data-quality.csv")
    assert res.status_code == 200 and res.headers["x-janus-dataset-version"] == body["version"]
    assert res.text.splitlines()[0].startswith("dataset_version,run_date,finding_id")
    md = client.get("/open/data-quality.md")
    assert md.status_code == 200 and md.text.startswith("# Janus data-quality report")
    assert res.headers["cache-control"] == "no-store"


def test_routes_answer_503_without_a_report(tmp_path: Path) -> None:
    application = create_app(configure_logs=False)
    application.state.data_quality = DataQualityHolder(tmp_path)
    with TestClient(application) as cl:
        for path in ("/open/data-quality", "/open/data-quality.csv", "/open/data-quality.md"):
            res = cl.get(path)
            assert res.status_code == 503
            assert res.json() == {"error": "data_quality_unavailable"}


def test_a_malformed_report_is_not_served(tmp_path: Path) -> None:
    root = tmp_path / "quality" / "current"
    root.mkdir(parents=True)
    (root / "report.json").write_text(json.dumps({"dataset": "x"}), encoding="utf-8")
    assert DataQualityHolder(tmp_path).value is None
