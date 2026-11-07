"""`POST /cascades/evaluate`: P6 (database part), P20, P21 and examples (cascade-engine task 11).

A synthetic, TİTCK-shaped dataset (no real TİTCK data) is loaded through the real resolution
loader with the real combination rules; the evidence and the real curated rule base are loaded
through their loaders.
"""

from __future__ import annotations

import json
import time
from collections.abc import Iterator
from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient
from hypothesis import given, settings
from hypothesis import strategies as st

from janus.cascades import router as cascades_router
from janus.cascades.load import load as load_rule_base
from janus.cascades.load import read_files
from janus.db.pool import Database
from janus.main import create_app
from janus.observability.logging import registered_route_templates
from janus.resolution.atc import CombinationRules, RouteMap
from janus.resolution.load import Inputs
from janus.resolution.load import load as load_resolution
from janus.settings import Settings
from tests.conftest import DB_EXAMPLES
from tests.harness import assert_stateless, capture_logs, isolated_tempdir
from tests.resolution_db import inputs
from tests.resolution_db import reset as reset_resolution
from tests.resolution_strategies import barcode13, titck_row, us_row, wikidata_row
from tests.sentinels import leaked
from tests.test_cascades_load_properties import TODAY, reset, seed_evidence

pytestmark = pytest.mark.db

# Synthetic ingredient keys; codes are the real ATC codes of the substances.
WD = [
    wikidata_row("Q411347", ["C08CA01"], {"en": "amlodipine", "tr": "amlodipin"}),
    wikidata_row("Q412208", ["C09AA03"], {"en": "lisinopril", "tr": "lisinopril"}),
    wikidata_row("Q900001", ["C03CA01"], {"en": "furosemide", "tr": "furosemid"}),
    wikidata_row("Q900002", ["A10BA02"], {"en": "metformin", "tr": "metformin"}),
    wikidata_row("Q900003", ["C10AA05"], {"en": "atorvastatin", "tr": "atorvastatin"}),
    wikidata_row("Q900004", ["N02BE01"], {"en": "paracetamol", "tr": "parasetamol"}),
    wikidata_row("Q900005", ["A02BC01"], {"en": "omeprazole", "tr": "omeprazol"}),
    wikidata_row("Q900006", ["N06AB06"], {"en": "sertraline", "tr": "sertralin"}),
    wikidata_row("Q900007", ["A06AD11"], {"en": "lactulose", "tr": "laktuloz"}),
    wikidata_row("Q900008", ["N05BA12"], {"en": "alprazolam", "tr": "alprazolam"}),
    wikidata_row("Q900010", ["N05AX08"], {"en": "twin one", "tr": "ikizmadde"}),
    wikidata_row("Q900011", ["N05AX12"], {"en": "twin two", "tr": "ikizmadde"}),
]
TR = [
    titck_row(
        barcode13(1), "AMLIPIN 10 / 10", ["amlodipin besilat", "lisinopril dihidrat"], "C09BB03"
    ),
    titck_row(barcode13(2), "FURO", ["furosemid"], "C03CA01"),
    titck_row(barcode13(3), "METFO", ["metformin hidroklorür"], "A10BA02"),
    titck_row(barcode13(4), "ATOR", ["atorvastatin kalsiyum"], "C10AA05"),
    titck_row(barcode13(5), "PARA", ["parasetamol"], "N02BE01"),
    titck_row(barcode13(6), "OMEP", ["omeprazol"], "A02BC01"),
    titck_row(barcode13(7), "SERT", ["sertralin hidroklorür"], "N06AB06"),
    titck_row(barcode13(8), "LAKT", ["laktuloz"], "A06AD11"),
    titck_row(barcode13(9), "ALPR", ["alprazolam"], "N05BA12"),
    titck_row(barcode13(10), "AMLO", ["amlodipin besilat"], "C08CA01"),
    titck_row(barcode13(11), "IKIZ", ["ikizmadde"], None),
]
US = [
    us_row("11111-111", ["11111-111-11"], ["amlodipine besylate"], ["ORAL"], brand="AMLO US"),
    us_row("22222-222", ["22222-222-22"], ["furosemide"], ["ORAL"], brand="FURO US"),
    {
        **us_row(
            "33333-333", ["33333-333-33"], ["furosemide"], ["ORAL"], "HUMAN OTC DRUG", "HOMEO US"
        ),
        "active_ingredients": [{"name": "FUROSEMIDE", "strength": "30 [hp_C]/1"}],
    },
]


@pytest.fixture(scope="module")
def env(db_url: str) -> Iterator[tuple[TestClient, dict[str, str], str, Database, str]]:
    database = Database(db_url)
    database.open()
    with psycopg.connect(db_url, autocommit=True) as conn:
        reset_resolution(conn)
        reset(conn)
    base = inputs(TR, US, WD)
    load_resolution(
        database,
        Inputs(base.artifacts, CombinationRules.load(), RouteMap.load(), (), "test", base.cadences),
    )
    seed_evidence(database)
    load_rule_base(database, read_files(), TODAY)
    with database.read_only_tx() as conn:
        dataset = str(conn.execute("SELECT dataset_id FROM res_current").fetchone()[0])  # type: ignore[index]
        rows = conn.execute(
            "SELECT region, source_id, product_id, coalesce(product_name, brand_name) "
            "FROM res_product WHERE dataset_id = %s",
            (dataset,),
        ).fetchall()
    ids = {str(r[3]): f"{r[0]}:{r[1]}:{r[2]}" for r in rows}
    cascades_router.today = lambda: TODAY
    app = create_app(Settings.from_env({}), database=database)
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c, ids, dataset, database, db_url
    database.close()


def post(client: TestClient, body: Any) -> Any:
    return client.post("/cascades/evaluate", json=body)


def item(product: str, started: str | None) -> dict[str, Any]:
    return {"product": product, "started": started}


# --- Gate 1: the Istanbul synthetic patient -------------------------------------------------------


def istanbul(ids: dict[str, str]) -> list[dict[str, Any]]:
    return [
        item(ids["AMLIPIN 10 / 10"], "2024-01"),
        item(ids["FURO"], "2024-06"),
        item(ids["METFO"], "2022-05"),
        item(ids["ATOR"], "2023-01"),
        item(ids["PARA"], "2023-05"),
        item(ids["OMEP"], None),
        item(ids["SERT"], "2021-03"),
        item(ids["LAKT"], "2024-03"),
        item(ids["ALPR"], None),
    ]


def test_istanbul_patient_finds_the_cascade_inside_amlipin(env: Any) -> None:
    """Gate 1 (PLAN.md Phase 1): the CCB → diuretic cascade from the amlodipine in AMLIPIN
    (C09BB03) is found through the API. Req 9.8."""
    client, ids, dataset, _, _ = env
    r = post(client, {"dataset_version": dataset, "items": istanbul(ids)})
    assert r.status_code == 200, r.text
    body = r.json()
    by_rule = {f["rule_id"]: f for f in body["findings"]}
    f5 = by_rule["pipc:5"]
    assert f5["index"]["ingredient_key"] == "Q411347" and f5["index"]["matched_codes"] == [
        "C08CA01"
    ]
    assert f5["marker"]["ingredient_key"] == "Q900001"
    assert (f5["status"], f5["timing"], f5["months_between"]) == ("probable", "within_window", 5)
    assert "C09BB03" not in json.dumps(f5)
    # The seeded evidence has no Crossref check yet, so the PIPC paper is unknown, never ok.
    assert "integrity_unknown" in f5["integrity_codes"]
    assert set(f5["evidence_ids"]) >= {
        "rule:pipc:5",
        "dataset:pipc",
        "paper:hendrix_2024:s12874_023_02108_y",
    }
    assert by_rule["pipc:6"]["status"] == "probable"  # CCB → laxative (lactulose 2 months later)
    f9 = by_rule["pipc:9"]  # statin → pain reliever, named in the BMJ 2026 abstract
    assert f9["priority"]["value"] == "10.9" and f9["status"] == "probable"
    warned = {w["ingredient_key"] for w in body["item_warnings"]}
    assert {"Q900006", "Q900008"} <= warned  # sertraline, alprazolam: do not stop suddenly
    assert body["statement"] is None
    assert body["rules"]["checked"] == 63
    assert {n["rule_id"] for n in body["rules"]["not_matchable"]} == {"pipc:27", "pipc:57"}
    assert body["disclaimer"].startswith("Janus provides information, not medical advice.")
    assert all(f["codes"] == ["matches_published_pattern"] for f in body["findings"])


def test_no_pattern_statement(env: Any) -> None:
    """Req 4.3: no finding gives the no-false-reassurance statement."""
    client, ids, dataset, _, _ = env
    body = post(
        client, {"dataset_version": dataset, "items": [item(ids["OMEP"], "2024-01")]}
    ).json()
    assert body["findings"] == []
    assert body["statement"] == {
        "code": "no_pattern_found",
        "text": "Janus found no pattern from its rule list. "
        "This does not mean your medicines are free of problems.",
    }


# --- P6 (database part): region invariance --------------------------------------------------------


@settings(max_examples=max(10, DB_EXAMPLES // 5), deadline=None)
@given(
    a=st.sampled_from(["2024-01", "2024-02", None]), b=st.sampled_from(["2024-06", "2023-01", None])
)
def test_p6_region_invariance_through_the_api(env: Any, a: str | None, b: str | None) -> None:
    """Feature: cascade-engine, Property 6 (database part). Validates: Req 7.1."""
    client, ids, dataset, _, _ = env

    def findings(amlo: str, furo: str) -> list[Any]:
        body = post(
            client, {"dataset_version": dataset, "items": [item(amlo, a), item(furo, b)]}
        ).json()
        return [
            (f["finding_id"], f["status"], f["timing"], f["form_confirmed"])
            for f in body["findings"]
        ]

    tr = findings(ids["AMLO"], ids["FURO"])
    us = findings(ids["AMLO US"], ids["FURO US"])
    mixed = findings(ids["AMLO"], ids["FURO US"])
    assert tr == us == mixed


# --- P20: stateless, silent route ---------------------------------------------------------------


def _month(y: int, m: int) -> str:
    return f"{y}-{m:02d}"


NAMES = [
    "AMLIPIN 10 / 10",
    "FURO",
    "METFO",
    "ATOR",
    "PARA",
    "OMEP",
    "SERT",
    "LAKT",
    "ALPR",
    "AMLO US",
]
MONTHS = st.one_of(st.none(), st.builds(_month, st.integers(2019, 2026), st.integers(1, 10)))


@st.composite
def requests(draw: st.DrawFn, ids: dict[str, str], dataset: str) -> tuple[dict[str, Any], int]:
    names = draw(st.lists(st.sampled_from(NAMES), min_size=1, max_size=6))
    body: dict[str, Any] = {
        "dataset_version": dataset,
        "items": [item(ids[n], draw(MONTHS)) for n in names],
    }
    kind = draw(
        st.sampled_from(
            ["ok", "ok", "unknown_product", "future", "bad_month", "extra", "version", "ingredient"]
        )
    )
    expect = 200
    if kind == "unknown_product":
        body["items"].append(item("TR:titck:999999", None))
        expect = 422
    elif kind == "future":
        body["items"][0]["started"] = "2027-01"
        expect = 422
    elif kind == "bad_month":
        body["items"][0]["started"] = "2024-13"
        expect = 422
    elif kind == "extra":
        body["items"][0]["atc"] = "C08CA01"
        expect = 422
    elif kind == "version":
        body["dataset_version"] = "0" * 64
        expect = 409
    elif kind == "ingredient":
        body["items"].append(
            {"ingredient": draw(st.sampled_from(["Q900004", "Q900007"])), "started": draw(MONTHS)}
        )
    return body, expect


@settings(max_examples=DB_EXAMPLES, deadline=None)
@given(data=st.data())
def test_p20_stateless_silent_route(env: Any, data: st.DataObject) -> None:
    """Feature: cascade-engine, Property 20. Validates: Req 9.1-9.5.

    For any request the database and temp directory are unchanged, the response has `no-store`,
    nothing of the request (candidate ids, keys, months, codes, rule ids) is logged, and error
    bodies name fields only.
    """
    client, ids, dataset, _, url = env
    body, expect = data.draw(requests(ids, dataset))
    with (
        isolated_tempdir() as tmp,
        capture_logs() as logs,
        psycopg.connect(url, autocommit=True) as conn,
    ):
        r = assert_stateless(conn, tmp, lambda: post(client, body))
    assert r.status_code == expect, r.text
    assert r.headers["cache-control"] == "no-store"
    secrets = [
        *(it.get("product") or it.get("ingredient") for it in body["items"]),
        *(it.get("started") for it in body["items"] if it.get("started")),
    ]
    out = r.json()
    if r.status_code == 200:
        secrets += [f["rule_id"] for f in out["findings"]]
        secrets += [c for f in out["findings"] for c in f["index"]["matched_codes"]]
    else:
        assert set(out) <= {"error", "fields"}
        assert not leaked(r.text, [s for s in secrets if s])
    assert not leaked(logs.getvalue(), [s for s in secrets if s])


def test_p20_unavailable_without_rule_base(env: Any) -> None:
    """Feature: cascade-engine, Property 20. Validates: Req 9.4 (nothing loaded: 503)."""
    client, ids, dataset, database, url = env
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute("DELETE FROM cascade_rule_base_current")
    try:
        r = post(client, {"dataset_version": dataset, "items": [item(ids["OMEP"], None)]})
        assert r.status_code == 503 and r.json() == {"error": "cascades_unavailable"}
    finally:
        load_rule_base(database, read_files(), TODAY)


# --- P21: deterministic route --------------------------------------------------------------------


@settings(max_examples=max(10, DB_EXAMPLES // 5), deadline=None)
@given(data=st.data())
def test_p21_deterministic_route(env: Any, data: st.DataObject) -> None:
    """Feature: cascade-engine, Property 21. Validates: Req 9.6."""
    client, ids, dataset, _, _ = env
    items = istanbul(ids)
    body = {"dataset_version": dataset, "items": items}
    first = post(client, body).content
    assert post(client, body).content == first
    perm: list[int] = list(data.draw(st.permutations(list(range(len(items))))))
    shuffled = {"dataset_version": dataset, "items": [items[i] for i in perm]}
    a = json.loads(first)
    b = post(client, shuffled).json()
    assert [f["finding_id"] for f in b["findings"]] == [f["finding_id"] for f in a["findings"]]
    for fa, fb in zip(a["findings"], b["findings"], strict=True):
        moved: list[int] = [perm[int(i)] for i in fb["index"]["items"]]
        assert sorted(moved) == fa["index"]["items"]


# --- Examples -------------------------------------------------------------------------------------


def test_route_is_registered_and_codes_never_travel_in_urls(env: Any) -> None:
    """`classify(app)` accepted the route (create_app fails otherwise). Req 9.1."""
    client, _, _, _, _ = env
    assert "/cascades/evaluate" in registered_route_templates()
    assert client.get("/cascades/evaluate").status_code == 405
    assert client.post("/cascades/evaluate/Q411347", json={}).status_code == 404


def test_ambiguous_ingredient_choices(env: Any) -> None:
    """An ambiguous ingredient is not checked without a choice; a choice outside its key
    candidates is 422; a valid choice is evaluated as form-unconfirmed. Req 7.2, 7.3."""
    client, ids, dataset, _, _ = env
    ikiz = ids["IKIZ"]
    plain = post(client, {"dataset_version": dataset, "items": [item(ikiz, "2024-01")]}).json()
    assert plain["not_checked"] == [{"item": 0, "position": 0, "reason": "ambiguous"}]
    bad = post(
        client,
        {
            "dataset_version": dataset,
            "items": [{"product": ikiz, "choices": [{"position": 0, "ingredient": "Q900004"}]}],
        },
    )
    assert bad.status_code == 422 and bad.json() == {
        "error": "invalid_request",
        "fields": ["items.0.choices"],
    }
    good = {
        "dataset_version": dataset,
        "items": [
            {
                "product": ikiz,
                "choices": [{"position": 0, "ingredient": "Q900010"}],
                "started": "2024-01",
            },
            {"ingredient": "Q900001", "started": "2024-02"},
        ],
    }
    body = post(client, good).json()
    assert body["not_checked"] == []
    assert all(f["form_confirmed"] is False for f in body["findings"])


def test_fifteen_items_under_one_second(env: Any) -> None:
    """Req 9.7: a 15-item list evaluates in under one second on the server."""
    client, ids, dataset, _, _ = env
    items = [item(ids[n], "2024-01") for n in NAMES] + [
        {"ingredient": q, "started": "2024-05"}
        for q in ["Q900001", "Q900002", "Q900003", "Q900004", "Q900005"]
    ]
    assert len(items) == 15
    post(client, {"dataset_version": dataset, "items": items})  # warm the rule-base cache
    t0 = time.perf_counter()
    r = post(client, {"dataset_version": dataset, "items": items})
    assert r.status_code == 200 and time.perf_counter() - t0 < 1.0


def test_homeopathic_product_is_not_checked(env: Any) -> None:
    """A product with homeopathic strengths is never evaluated as the substance (owner decision
    2026-11-07): no finding, listed as `homeopathic_product`; the same substance as a real
    product gives the finding."""
    client, ids, dataset, _, _ = env
    homeo = post(
        client,
        {
            "dataset_version": dataset,
            "items": [item(ids["AMLO"], "2024-01"), item(ids["HOMEO US"], "2024-04")],
        },
    ).json()
    assert homeo["findings"] == []
    assert homeo["not_checked"] == [{"item": 1, "position": 0, "reason": "homeopathic_product"}]
    real = post(
        client,
        {
            "dataset_version": dataset,
            "items": [item(ids["AMLO"], "2024-01"), item(ids["FURO US"], "2024-04")],
        },
    ).json()
    assert "pipc:5" in {f["rule_id"] for f in real["findings"]}
    flagged = client.post("/resolve/ndc", json={"ndc": "33333-333-33"}).json()
    assert flagged["candidates"][0]["homeopathic"] is True
