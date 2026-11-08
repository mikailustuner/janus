"""EU resolution on the real BDPM and Nomenclátor data (drug-resolution task 24). Local only.

`JANUS_REAL_DATABASE_URL` points to a database loaded with the real resolution dataset (all five
sources). Codes and names are picked from that database at run time, so no source data is in the
repository. Skipped in CI.
"""

from __future__ import annotations

import datetime as dt
import os
from collections.abc import Iterator
from typing import Any

import pytest

from janus.db.pool import Database
from janus.resolution import service
from tests.resolution_strategies import with_check_digit

URL = os.environ.get("JANUS_REAL_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    os.environ.get("CI") == "true" or not URL, reason="no local real database"
)

TODAY = dt.date(2026, 11, 8)


@pytest.fixture(scope="module")
def db() -> Iterator[Database]:
    assert URL is not None
    database = Database(URL)
    database.open()
    with database.read_only_tx() as conn:
        held = {
            r[0]
            for r in conn.execute(
                "SELECT s.source_id FROM res_source_version s JOIN res_current c "
                "ON c.dataset_id = s.dataset_id"
            ).fetchall()
        }
    if not {"eu_fr_bdpm", "eu_es_cima"} <= held:
        pytest.skip("the real dataset was loaded without the EU sources")
    yield database
    database.close()


def _one(db: Database, sql: str, *params: Any) -> Any:
    with db.read_only_tx() as conn:
        row = conn.execute(sql, params).fetchone()  # type: ignore[arg-type]
    assert row is not None, "the real dataset has no such row"
    return row


def _scan(db: Database, content: str, region: Any = None) -> Any:
    with db.read_only_tx() as conn:
        return service.resolve_scan(conn, content, region, TODAY)


def _eu(res: Any) -> list[Any]:
    return [c for c in res.candidates if c.region == "EU"]


def test_real_cip13_resolves_with_its_ingredients_and_the_bdpm_date(db: Database) -> None:
    # a presentation with a single code owner, all ingredients mapped, not homeopathic
    code, source, pid = _one(
        db,
        "SELECT c.code, c.source_id, c.product_id FROM res_current cur "
        "JOIN res_product_code c ON c.dataset_id = cur.dataset_id AND c.kind = 'fr_cip13' "
        "JOIN res_product p ON p.dataset_id = c.dataset_id AND p.source_id = c.source_id "
        "  AND p.product_id = c.product_id "
        "WHERE (SELECT count(*) FROM res_product_ingredient i WHERE i.dataset_id = c.dataset_id "
        "  AND i.source_id = c.source_id AND i.product_id = c.product_id AND i.status <> 'mapped')"
        "  = 0 "
        "AND (SELECT count(*) FROM res_product_ingredient i WHERE i.dataset_id = c.dataset_id "
        "  AND i.source_id = c.source_id AND i.product_id = c.product_id) >= 1 "
        "AND (SELECT count(*) FROM res_product_code d WHERE d.dataset_id = c.dataset_id "
        "  AND d.kind = 'fr_cip13' AND d.code = c.code) = 1 "
        "ORDER BY c.code LIMIT 1",
    )
    res = _scan(db, "0" + code)
    (c,) = _eu(res)
    assert (c.country, c.matched_by, c.source.source_id) == ("FR", "cip13", source)
    assert c.candidate_id == f"EU:{source}:{pid}"
    assert c.ingredients and all(i.status == "mapped" and i.atc_codes for i in c.ingredients)
    assert c.status_published and c.source.snapshot_date
    assert _scan(db, code).candidates == res.candidates  # the bare CIP13 gives the same answer


def test_real_spanish_codes_resolve_in_order_of_trust(db: Database) -> None:
    ntin = _one(
        db,
        "SELECT c.code FROM res_current cur JOIN res_product_code c "
        "ON c.dataset_id = cur.dataset_id AND c.kind = 'es_ntin' ORDER BY c.code LIMIT 1",
    )[0]
    res = _scan(db, ntin, "EU")
    found = _eu(res)
    assert found and {c.matched_by for c in found} == {"ntin"}
    assert all(c.country == "ES" and c.published_atc for c in found)
    # a GTIN of the Nomenclátor that is no NTIN
    gtin = _one(
        db,
        "SELECT c.code FROM res_current cur JOIN res_product_code c "
        "ON c.dataset_id = cur.dataset_id AND c.kind = 'es_gtin' "
        "WHERE NOT EXISTS (SELECT 1 FROM res_product_code n WHERE n.dataset_id = c.dataset_id "
        "AND n.kind = 'es_ntin' AND n.code = c.code) ORDER BY c.code LIMIT 1",
    )[0]
    assert {c.matched_by for c in _eu(_scan(db, gtin, "EU"))} == {"gtin"}
    # AI (712): the CN of a presentation, with a GTIN that no list holds
    cn = _one(
        db,
        "SELECT c.code FROM res_current cur JOIN res_product_code c "
        "ON c.dataset_id = cur.dataset_id AND c.kind = 'es_cn' ORDER BY c.code DESC LIMIT 1",
    )[0]
    unknown = with_check_digit("0841123456789")
    res = _scan(db, f"(01){unknown}(712){cn}1", "EU")
    got = _eu(res)
    assert got and {c.matched_by for c in got} == {"ai_712"}
    with db.read_only_tx() as conn:
        codes = {
            r[0]
            for r in conn.execute(
                "SELECT code FROM res_product_code c JOIN res_current cur "
                "ON cur.dataset_id = c.dataset_id WHERE c.kind = 'es_cn' AND c.source_id = %s "
                "AND c.product_id = ANY(%s)",
                ("eu_es_cima", [int(c.candidate_id.rsplit(":", 1)[1]) for c in got]),
            ).fetchall()
        }
    assert codes == {cn}
    assert f"{cn}1" not in res.model_dump_json()  # the AI (712) value is not echoed


def test_a_german_prefix_gives_the_notice_and_no_german_candidate(db: Database) -> None:
    res = _scan(db, with_check_digit("0401234567890"))
    assert [(n.region, n.country) for n in res.notices if n.code == "no_open_product_database"] == [
        ("EU", "DE")
    ]
    assert _eu(res) == []


@pytest.mark.parametrize("query", ["tramadol", "Tramadol", "ácido acetilsalicílico", "paracétamol"])
def test_real_eu_name_search(db: Database, query: str) -> None:
    with db.read_only_tx() as conn:
        res = service.search(conn, query, "EU", 10, TODAY)
    assert res.candidates, query
    assert res.regions_searched == ["EU"]
    assert {s.source_id for s in res.sources} >= {"eu_fr_bdpm", "eu_es_cima"}
