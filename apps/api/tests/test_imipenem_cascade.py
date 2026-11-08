"""PIPC row 58 (carbapenem → seizures → anticonvulsant) with imipenem (drug-resolution task 27.2).

The synthetic dataset is loaded through the real resolution loader with the real curated key `J2`
and the reviewed pair (`J2`, `J01DH51`); the rule base and evidence are the real, curated ones.
No real TİTCK data.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient

from janus.cascades import router as cascades_router
from janus.cascades.load import load as load_rule_base
from janus.cascades.load import read_files
from janus.db.pool import Database
from janus.main import create_app
from janus.resolution.atc import CombinationRules, RouteMap
from janus.resolution.load import (
    Inputs,
    read_component_codes,
    read_curated,
)
from janus.resolution.load import load as load_resolution
from janus.settings import Settings
from tests.resolution_db import inputs
from tests.resolution_db import reset as reset_resolution
from tests.resolution_strategies import barcode13, titck_row, us_row, wikidata_row
from tests.test_cascades_load_properties import TODAY, reset, seed_evidence

pytestmark = pytest.mark.db

WD = [
    wikidata_row("Q600", ["J01DH02"], {"en": "meropenem", "tr": "meropenem"}),
    wikidata_row("Q601", ["J01DH51"], {"en": "imipenem and cilastatin"}),  # a combination item
    wikidata_row("Q602", ["N03AX14"], {"en": "levetiracetam", "tr": "levetirasetam"}),
]
TR = [
    titck_row(barcode13(1), "TIENAM", ["imipenem monohidrat", "silastatin sodyum"], "J01DH51"),
    titck_row(barcode13(2), "MERONEM", ["meropenem"], "J01DH02"),
    titck_row(barcode13(3), "KEPPRA", ["levetirasetam"], "N03AX14"),
]
US = [
    us_row(
        "44444-444", ["44444-444-44"], ["cilastatin sodium"], ["INTRAVENOUS"], brand="CILA ONLY"
    ),
    us_row(
        "55555-555",
        ["55555-555-55"],
        ["imipenem", "cilastatin sodium"],
        ["INTRAVENOUS"],
        brand="IMI US",
    ),
]


@pytest.fixture(scope="module")
def env(db_url: str) -> Iterator[tuple[TestClient, dict[str, str], str]]:
    database = Database(db_url)
    database.open()
    with psycopg.connect(db_url, autocommit=True) as conn:
        reset_resolution(conn)
        reset(conn)
    base = inputs(TR, US, WD)
    pairs = read_component_codes()
    load_resolution(
        database,
        Inputs(
            base.artifacts,
            CombinationRules.load(),
            RouteMap.load(),
            (),
            "test",
            base.cadences,
            read_curated(codeless=frozenset(c.key for c in pairs)),
            component_codes=pairs,
        ),
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
        yield c, ids, dataset
    database.close()


def evaluate(client: TestClient, dataset: str, items: list[tuple[str, str]]) -> dict[str, Any]:
    body = {
        "dataset_version": dataset,
        "items": [{"product": p, "started": s} for p, s in items],
    }
    r = client.post("/cascades/evaluate", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def row58(body: dict[str, Any]) -> list[dict[str, Any]]:
    return [f for f in body["findings"] if f["rule_id"] == "pipc:58"]


def test_row_58_fires_on_imipenem_with_the_reviewed_pair(env: Any) -> None:
    """Feature: drug-resolution, Property P48 (example). Validates Req 14.2.

    A carbapenem followed within the window by an anticonvulsant is a probable pattern. For
    imipenem the matched code is the reviewed pair's `J01DH51`, found through key `J2`."""
    client, ids, dataset = env
    body = evaluate(client, dataset, [(ids["TIENAM"], "2024-01"), (ids["KEPPRA"], "2024-03")])
    (finding,) = row58(body)
    assert finding["index"]["ingredient_key"] == "J2"
    assert finding["index"]["matched_codes"] == ["J01DH51"]
    assert finding["marker"]["ingredient_key"] == "Q602"
    assert (finding["status"], finding["timing"]) == ("probable", "within_window")
    assert body["rules"]["checked"] == 63


def test_row_58_still_fires_on_meropenem_and_the_us_imipenem_product(env: Any) -> None:
    client, ids, dataset = env
    mero = evaluate(client, dataset, [(ids["MERONEM"], "2024-01"), (ids["KEPPRA"], "2024-03")])
    (f,) = row58(mero)
    assert f["index"]["ingredient_key"] == "Q600" and f["index"]["matched_codes"] == ["J01DH02"]
    us = evaluate(client, dataset, [(ids["IMI US"], "2024-01"), (ids["KEPPRA"], "2024-03")])
    (g,) = row58(us)
    assert g["index"]["ingredient_key"] == "J2"  # the same key whichever region's box it is


def test_row_58_does_not_fire_on_cilastatin_alone(env: Any) -> None:
    """Cilastatin gets no carbapenem code (Req 14.3): the product is listed as not checked."""
    client, ids, dataset = env
    body = evaluate(client, dataset, [(ids["CILA ONLY"], "2024-01"), (ids["KEPPRA"], "2024-03")])
    assert row58(body) == []
    assert body["findings"] == []
    reasons = {n["reason"] for n in body["not_checked"]}
    assert "no_ingredient_key" in reasons


def test_the_combination_code_reaches_the_engine_as_a_pair_only(env: Any) -> None:
    """The engine's input guard knows the pair; the same code on any other key is refused."""
    from janus.cascades.engine import EngineInputError, _validate  # pyright: ignore[reportPrivateUsage]
    from janus.cascades.model import EngineIngredient, EngineItem

    def item(key: str) -> list[EngineItem]:
        return [EngineItem(0, 2024 * 12, (EngineIngredient(key, frozenset({"J01DH51"}), True),))]

    _validate(item("J2"), {"J01DH51"}, {("J2", "J01DH51")})
    with pytest.raises(EngineInputError):
        _validate(item("Q600"), {"J01DH51"}, {("J2", "J01DH51")})
    with pytest.raises(EngineInputError):
        _validate(item("J2"), {"J01DH51"}, set())
