"""Safety check, part A: duplication (safety-check design §9, properties S1-S7).
Synthetic items and a synthetic, TİTCK-shaped dataset; no real product data and no network."""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient
from hypothesis import given
from hypothesis import strategies as st

from janus.cascades.model import EngineIngredient, EngineItem
from janus.db.pool import Database
from janus.http_policy.routes import RouteKind, route_kind
from janus.main import create_app
from janus.resolution.atc import CombinationRules, RouteMap
from janus.resolution.load import Inputs
from janus.resolution.load import load as load_resolution
from janus.safety import duplication
from janus.safety import router as safety_router
from janus.safety.duplication import Finding, find, group_of
from janus.safety.schemas import NO_DUPLICATION
from janus.settings import Settings
from tests.harness import assert_stateless, capture_logs, isolated_tempdir
from tests.resolution_db import inputs
from tests.resolution_db import reset as reset_resolution
from tests.resolution_strategies import barcode13, titck_row, us_row, wikidata_row
from tests.sentinels import leaked
from tests.test_cascades_load_properties import TODAY

# --- strategies ------------------------------------------------------------------------------
# Few keys and few codes, so generated lists collide often. N06AX is a residual subgroup.
KEYS = ["Q1", "Q2", "Q3", "Q4", "Q5", "J1"]
CODES = ["C09AA03", "C09AA05", "C09CA01", "N06AB06", "N06AX11", "N06AX16", "A02BC01", "A02BC02"]


@st.composite
def ingredients(draw: st.DrawFn) -> EngineIngredient:
    return EngineIngredient(
        key=draw(st.sampled_from(KEYS)),
        codes=draw(st.frozensets(st.sampled_from(CODES), max_size=3)),
        form_confirmed=draw(st.booleans()),
        label_en=draw(st.sampled_from([None, "a name"])),
    )


@st.composite
def lists(draw: st.DrawFn) -> list[EngineItem]:
    n = draw(st.integers(0, 6))
    return [EngineItem(i, None, tuple(draw(st.lists(ingredients(), max_size=3)))) for i in range(n)]


def occurrences(items: list[EngineItem]) -> set[tuple[int, str, str]]:
    """(item, key, code) of every ingredient code on the list."""
    return {(it.index, g.key, c) for it in items for g in it.ingredients for c in g.codes}


# --- S1-S6: the pure rules -------------------------------------------------------------------


@given(lists())
def test_s1_same_ingredient_iff_a_key_stands_in_two_items(items: list[EngineItem]) -> None:
    where: dict[str, set[int]] = {}
    for it in items:
        for g in it.ingredients:
            where.setdefault(g.key, set()).add(it.index)
    expected = {k: tuple(sorted(v)) for k, v in where.items() if len(v) >= 2}
    got = {f.members[0].key: f.members[0].items for f in find(items) if f.kind == "same_ingredient"}
    assert got == expected
    assert all(len(f.members) == 1 for f in find(items) if f.kind == "same_ingredient")


@given(lists())
def test_s2_same_group_iff_two_keys_of_one_subgroup_in_two_items(items: list[EngineItem]) -> None:
    occ = occurrences(items)
    expected: set[str] = set()
    for i, k, c in occ:
        for j, m, d in occ:
            if i != j and k != m and c[:5] == d[:5] and c[4] != "X":
                expected.add(c[:5])
    found = [f for f in find(items) if f.kind == "same_group"]
    assert {f.group for f in found} == expected
    assert len(found) == len(expected)  # once per subgroup
    for f in found:
        assert f.group is not None
        assert len({m.key for m in f.members}) == len(f.members) >= 2
        assert len(f.items) >= 2
        for m in f.members:
            # Every member really carries a code of the subgroup in each item it names.
            assert m.codes and all(c.startswith(f.group) for c in m.codes)
            for i in m.items:
                assert any((i, m.key, c) in occ for c in m.codes)
        # Nothing of the subgroup is left out.
        assert {(i, m.key) for m in f.members for i in m.items} == {
            (i, k) for i, k, c in occ if c.startswith(f.group)
        }


@given(st.lists(ingredients(), max_size=6))
def test_s3_one_item_alone_gives_no_finding(ings: list[EngineIngredient]) -> None:
    assert find([EngineItem(0, None, tuple(ings))]) == []


@given(lists(), st.randoms(use_true_random=False))
def test_s4_item_order_does_not_change_the_result(items: list[EngineItem], rnd: Any) -> None:
    order = list(range(len(items)))
    rnd.shuffle(order)  # the item at old position `order[new]` moves to `new`
    new_of = {old: new for new, old in enumerate(order)}
    moved = [EngineItem(new, None, items[old].ingredients) for new, old in enumerate(order)]

    def renumbered(f: Finding) -> Any:
        return (
            f.kind,
            f.group,
            [
                (m.key, tuple(sorted(new_of[i] for i in m.items)), m.codes, m.form_confirmed)
                for m in f.members
            ],
        )

    def plain(f: Finding) -> Any:
        return (f.kind, f.group, [(m.key, m.items, m.codes, m.form_confirmed) for m in f.members])

    assert [renumbered(f) for f in find(items)] == [plain(f) for f in find(moved)]
    ids = [f.finding_id for f in find(items)]
    assert len(set(ids)) == len(ids)
    same = [f.members[0].key for f in find(items) if f.kind == "same_ingredient"]
    groups = [f.group for f in find(items) if f.kind == "same_group"]
    assert same == sorted(same) and groups == sorted(g for g in groups if g)
    assert [f.kind for f in find(items)] == ["same_ingredient"] * len(same) + ["same_group"] * len(
        groups
    )


@given(st.text("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", max_size=8))
def test_s5_only_ingredient_level_codes_of_a_named_subgroup_form_a_group(code: str) -> None:
    g = group_of(code)
    if g is not None:
        assert len(code) == 7 and code.startswith(g) and len(g) == 5 and g[4] != "X"
    two = [
        EngineItem(0, None, (EngineIngredient("Q1", frozenset({code}), True),)),
        EngineItem(1, None, (EngineIngredient("Q2", frozenset({code}), True),)),
    ]
    assert [f.group for f in find(two)] == ([g] if g else [])


def test_s5_examples() -> None:
    assert group_of("C09AA03") == "C09AA"
    assert group_of("N06AX11") is None  # "other antidepressants": not a chemical class
    assert group_of("C09BB03"[:5]) is None and group_of("C09") is None


@given(lists())
def test_s6_form_confirmed_iff_every_occurrence_is(items: list[EngineItem]) -> None:
    """Every occurrence of a member's key in the items the member names (the cautious reading
    when one item names a key twice)."""
    for f in find(items):
        expected = all(
            g.form_confirmed
            for it in items
            for g in it.ingredients
            for m in f.members
            if g.key == m.key and it.index in m.items
        )
        assert f.form_confirmed == expected


def test_examples_from_the_spec() -> None:
    """Design §4: the certain case, the group case, and a combination product."""
    amlo = EngineIngredient("Q411347", frozenset({"C08CA01"}), True, "amlodipine")
    lisi = EngineIngredient("Q412208", frozenset({"C09AA03"}), True, "lisinopril")
    rami = EngineIngredient("Q900020", frozenset({"C09AA05"}), False, "ramipril")
    combo = EngineItem(0, None, (amlo, lisi))
    assert find([combo]) == []
    out = find([combo, EngineItem(1, None, (amlo,)), EngineItem(2, None, (rami,))])
    assert [(f.kind, f.group, f.items, f.form_confirmed) for f in out] == [
        ("same_ingredient", None, (0, 1), True),
        ("same_group", "C09AA", (0, 2), False),
    ]
    assert out[0].finding_id == "same_ingredient:Q411347"
    assert out[1].finding_id == "same_group:C09AA"
    assert duplication.RULES_VERSION == "duplication-1"


# --- S7: the route ---------------------------------------------------------------------------

WD = [
    wikidata_row("Q411347", ["C08CA01"], {"en": "amlodipine", "tr": "amlodipin"}),
    wikidata_row("Q412208", ["C09AA03"], {"en": "lisinopril", "tr": "lisinopril"}),
    wikidata_row("Q900020", ["C09AA05"], {"en": "ramipril", "tr": "ramipril"}),
    wikidata_row("Q900005", ["A02BC01"], {"en": "omeprazole", "tr": "omeprazol"}),
    wikidata_row("Q900021", ["N06AX11"], {"en": "mirtazapine", "tr": "mirtazapin"}),
    wikidata_row("Q900022", ["N06AX16"], {"en": "venlafaxine", "tr": "venlafaksin"}),
    wikidata_row("Q900010", ["N05AX08"], {"en": "twin one", "tr": "ikizmadde"}),
    wikidata_row("Q900011", ["N05AX12"], {"en": "twin two", "tr": "ikizmadde"}),
]
TR = [
    titck_row(
        barcode13(1), "AMLIPIN 10 / 10", ["amlodipin besilat", "lisinopril dihidrat"], "C09BB03"
    ),
    titck_row(barcode13(2), "AMLO", ["amlodipin besilat"], "C08CA01"),
    titck_row(barcode13(3), "RAMI", ["ramipril"], "C09AA05"),
    titck_row(barcode13(4), "OMEP", ["omeprazol"], "A02BC01"),
    titck_row(barcode13(5), "MIRTA", ["mirtazapin"], "N06AX11"),
    titck_row(barcode13(6), "VENLA", ["venlafaksin hidroklorür"], "N06AX16"),
    titck_row(barcode13(7), "IKIZ", ["ikizmadde"], None),
]
US = [us_row("11111-111", ["11111-111-11"], ["amlodipine besylate"], ["ORAL"], brand="AMLO US")]


@pytest.fixture(scope="module")
def env(db_url: str) -> Iterator[tuple[TestClient, dict[str, str], str, str]]:
    database = Database(db_url)
    database.open()
    with psycopg.connect(db_url, autocommit=True) as conn:
        reset_resolution(conn)
    base = inputs(TR, US, WD)
    load_resolution(
        database,
        Inputs(base.artifacts, CombinationRules.load(), RouteMap.load(), (), "test", base.cadences),
    )
    with database.read_only_tx() as conn:
        dataset = str(conn.execute("SELECT dataset_id FROM res_current").fetchone()[0])  # type: ignore[index]
        rows = conn.execute(
            "SELECT region, source_id, product_id, coalesce(product_name, brand_name) "
            "FROM res_product WHERE dataset_id = %s",
            (dataset,),
        ).fetchall()
    ids = {str(r[3]): f"{r[0]}:{r[1]}:{r[2]}" for r in rows}
    safety_router.today = lambda: TODAY
    app = create_app(Settings.from_env({}), database=database)
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c, ids, dataset, db_url
    database.close()


def post(client: TestClient, body: Any) -> Any:
    return client.post("/safety/check", json=body)


def test_route_is_medical_post_only() -> None:
    (route,) = safety_router.router.routes
    assert route_kind(route) is RouteKind.medical
    assert getattr(route, "methods", set[str]()) == {"POST"}
    assert getattr(route, "path", "") == "/safety/check"
    app = create_app(Settings.from_env({}))
    assert TestClient(app).post("/safety/check", json={}).status_code == 422
    body = {"dataset_version": "0" * 64, "items": [{"ingredient": "Q1"}]}
    r = TestClient(app).post("/safety/check", json=body)
    assert (r.status_code, r.json()) == (503, {"error": "safety_unavailable"})


@pytest.mark.db
def test_route_finds_the_ingredient_inside_a_combination_product(env: Any) -> None:
    client, ids, dataset, _ = env
    names = ["AMLIPIN 10 / 10", "AMLO", "RAMI", "OMEP", "AMLO US"]
    r = post(client, {"dataset_version": dataset, "items": [{"product": ids[n]} for n in names]})
    assert r.status_code == 200, r.text
    assert r.headers["cache-control"] == "no-store"
    body = r.json()
    dup = body["duplication"]
    assert [(f["kind"], f["atc_group"], f["items"]) for f in dup["findings"]] == [
        ("same_ingredient", None, [0, 1, 4]),
        ("same_group", "C09AA", [0, 2]),
    ]
    amlo = dup["findings"][0]["members"][0]
    assert (amlo["ingredient_key"], amlo["label_en"]) == ("Q411347", "amlodipine")
    assert [m["label_en"] for m in dup["findings"][1]["members"]] == ["lisinopril", "ramipril"]
    assert "C09BB03" not in r.text  # the combination product's own code is never compared
    assert dup["statement"] is None and dup["status"] == "checked" and dup["atc_level"] == 4
    assert {s["source_id"] for s in dup["sources"]} >= {"titck"}
    assert all(s["snapshot_date"] for s in dup["sources"])
    assert (body["items"], body["dataset_version"]) == (5, dataset)
    assert body["disclaimer"].startswith("Janus provides information, not medical advice.")


@pytest.mark.db
def test_route_nothing_found_is_not_a_clearance(env: Any) -> None:
    client, ids, dataset, _ = env
    # A combination product alone, two residual-subgroup ingredients, and an unmapped one.
    names = ["AMLIPIN 10 / 10", "MIRTA", "VENLA", "IKIZ"]
    body = post(
        client, {"dataset_version": dataset, "items": [{"product": ids[n]} for n in names]}
    ).json()
    dup = body["duplication"]
    assert dup["findings"] == []
    assert dup["statement"] == {"code": "no_duplication_found", "text": NO_DUPLICATION}
    assert NO_DUPLICATION.endswith("This does not mean your medicines are free of problems.")
    assert body["not_checked"] == [{"item": 3, "position": 0, "reason": "ambiguous"}]
    assert body["ingredients_checked"] == 4


@pytest.mark.db
def test_route_takes_ingredients_found_by_name(env: Any) -> None:
    client, ids, dataset, _ = env
    items = [{"ingredient": "Q412208"}, {"product": ids["RAMI"]}, {"ingredient": "Q412208"}]
    dup = post(client, {"dataset_version": dataset, "items": items}).json()["duplication"]
    assert [(f["kind"], f["items"], f["form_confirmed"]) for f in dup["findings"]] == [
        ("same_ingredient", [0, 2], False),
        ("same_group", [0, 1, 2], False),
    ]


@pytest.mark.db
@pytest.mark.parametrize(
    ("body", "status", "answer"),
    [
        ("not json", 422, {"error": "invalid_request", "fields": ["body"]}),
        ({}, 422, {"error": "invalid_request", "fields": ["dataset_version", "items"]}),
        (
            {"dataset_version": "x", "items": [{"ingredient": "SECRET-KEY"}], "SECRET": 1},
            422,
            {
                "error": "invalid_request",
                "fields": ["body", "dataset_version", "items.0.ingredient"],
            },
        ),
        (
            {"dataset_version": "0" * 64, "items": [{"ingredient": "Q412208"}]},
            409,
            {"error": "dataset_version_mismatch"},
        ),
    ],
)
def test_route_refuses_bad_input_without_echoing_it(
    env: Any, body: Any, status: int, answer: Any
) -> None:
    client, _, _, _ = env
    r = (
        client.post("/safety/check", content=body, headers={"content-type": "application/json"})
        if isinstance(body, str)
        else post(client, body)
    )
    assert (r.status_code, r.json()) == (status, answer)
    assert "SECRET" not in r.text


@pytest.mark.db
def test_route_names_unknown_items_by_position_only(env: Any) -> None:
    client, ids, dataset, _ = env
    items = [{"product": "TR:titck:999999999"}, {"ingredient": "Q999999"}, {"product": ids["OMEP"]}]
    r = post(client, {"dataset_version": dataset, "items": items})
    assert (r.status_code, r.json()) == (
        422,
        {"error": "invalid_request", "fields": ["items.0.product", "items.1.ingredient"]},
    )


@pytest.mark.db
def test_route_is_stateless_and_logs_nothing_of_the_request(env: Any) -> None:
    client, ids, dataset, db_url = env
    body = {
        "dataset_version": dataset,
        "items": [{"product": ids["AMLO"]}, {"product": ids["RAMI"]}],
    }
    secrets = [ids["AMLO"], ids["RAMI"], "Q411347", "amlodipine", dataset]
    with (
        psycopg.connect(db_url, autocommit=True) as conn,
        isolated_tempdir() as tmp,
        capture_logs() as logs,
    ):
        r = assert_stateless(conn, tmp, lambda: post(client, body))
    assert r.status_code == 200
    assert not leaked(logs.getvalue(), secrets)
    assert json.loads(logs.getvalue().splitlines()[-1])["route"] == "/safety/check"


# --- the contract fixture of the web app -----------------------------------------------------

WEB_FIXTURE = Path(__file__).parents[2] / "web" / "src" / "safety" / "fixtures" / "check.json"
FIXTURE_ITEMS = ["AMLIPIN 10 / 10", "AMLO", "RAMI", "OMEP", "AMLO US", "IKIZ"]


def fixture_answer(env: Any) -> dict[str, Any]:
    client, ids, dataset, _ = env
    items: list[dict[str, Any]] = [{"product": ids[n]} for n in FIXTURE_ITEMS]
    items.append({"ingredient": "Q412208"})
    r = post(client, {"dataset_version": dataset, "items": items})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.db
def test_web_fixture_is_the_api_answer(env: Any) -> None:
    """`apps/web/src/safety/fixtures/check.json` is this API's answer for an invented list; the
    web decoder and renderer are tested on it. Regenerate with JANUS_WRITE_FIXTURES=1."""
    answer = fixture_answer(env)
    if os.environ.get("JANUS_WRITE_FIXTURES") == "1":
        WEB_FIXTURE.write_text(json.dumps(answer, indent=2, ensure_ascii=False) + "\n", "utf-8")
    assert json.loads(WEB_FIXTURE.read_text(encoding="utf-8")) == answer
