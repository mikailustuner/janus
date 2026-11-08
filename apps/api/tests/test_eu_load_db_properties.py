"""Loader tests for the EU sources (drug-resolution task 22.7, P47 load part; P8 with EU rows)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import psycopg
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from janus.db.pool import Database
from janus.resolution.load import Artifact, LoadError, current_dataset, load
from janus.resolution.prepare import OPENFDA, TITCK, WIKIDATA
from janus.resolution.prepare_eu import ES_CIMA, FR_BDPM
from tests.conftest import DB_EXAMPLES
from tests.resolution_db import dump, inputs, reset
from tests.resolution_strategies import (
    HOMEOPATHIC_SUFFIX,
    bdpm_row,
    cima_row,
    eu_rows,
    sources,
    wikidata_row,
)

pytestmark = pytest.mark.db


@pytest.fixture(scope="module")
def database(db_url: str) -> Iterator[Database]:
    db = Database(db_url)
    db.open()
    yield db
    db.close()


WD = [
    wikidata_row(
        "Q1", ["A02AA01", "D07AA01"], {"en": "alfazin", "fr": "alfazine", "es": "alfazina"}
    )
]
FR = [
    bdpm_row(1, "ALFAZINE 1 mg, comprimé", ["alfazin"], routes="orale"),
    bdpm_row(2, "HOMEO", ["arnica" + HOMEOPATHIC_SUFFIX]),
]
ES = [
    cima_row(1, "ALFAZINA 1 mg", ["alfazin"], "A02AA01", gtins=["4057598030861", "4057598030"]),
    cima_row(2, "SIN INGREDIENTES", [], None),
]


@pytest.mark.parametrize("with_fr", [False, True])
@pytest.mark.parametrize("with_es", [False, True])
def test_any_subset_of_eu_sources_loads(
    database: Database, db_conn: psycopg.Connection, with_fr: bool, with_es: bool
) -> None:
    """Feature: drug-resolution, Property P47 (load part). Validates Req 9.7.

    The dataset loads with either, both or none of the EU sources; its source versions are
    exactly the sources present, with the registry's licence text and cadence.
    """
    reset(db_conn)
    result = load(
        database, inputs([], [], WD, fr=FR if with_fr else None, es=ES if with_es else None)
    )
    ds = result.dataset_version
    sources_loaded = {
        r[0]: r[1:]
        for r in db_conn.execute(
            "SELECT source_id, region, license, cadence_days FROM res_source_version "
            "WHERE dataset_id = %s",
            (ds,),
        ).fetchall()
    }
    expected = {TITCK, OPENFDA, WIKIDATA}
    expected |= {FR_BDPM} if with_fr else set()
    expected |= {ES_CIMA} if with_es else set()
    assert set(sources_loaded) == expected
    if with_fr:
        assert sources_loaded[FR_BDPM] == ("EU", "Licence Ouverte (Etalab)", 30)
    if with_es:
        assert sources_loaded[ES_CIMA] == ("EU", "Reuse with attribution (Ley 37/2007)", 7)
    counts = dict(
        db_conn.execute(
            "SELECT source_id, count(*) FROM res_product WHERE dataset_id = %s GROUP BY 1", (ds,)
        ).fetchall()
    )
    assert counts.get(FR_BDPM, 0) == (len(FR) if with_fr else 0)
    assert counts.get(ES_CIMA, 0) == (len(ES) if with_es else 0)
    assert current_dataset(db_conn) == ds


def test_eu_rows_are_stored_with_codes_statuses_and_names(
    database: Database, db_conn: psycopg.Connection
) -> None:
    reset(db_conn)
    ds = load(database, inputs([], [], WD, fr=FR, es=ES)).dataset_version
    kinds = sorted(
        r[0]
        for r in db_conn.execute(
            "SELECT DISTINCT kind FROM res_product_code WHERE dataset_id = %s", (ds,)
        ).fetchall()
    )
    assert kinds == ["es_cn", "es_gtin", "es_ntin", "fr_cip13"]
    # GTINs are stored padded to 14 digits and keep the published form
    gtins = db_conn.execute(
        "SELECT code, code_published FROM res_product_code WHERE dataset_id = %s AND kind = "
        "'es_gtin' ORDER BY 1",
        (ds,),
    ).fetchall()
    assert gtins == [("00004057598030", "4057598030"), ("04057598030861", "4057598030861")]
    status = db_conn.execute(
        "SELECT status_published, routes, marketing_end_date, region FROM res_product "
        "WHERE dataset_id = %s AND source_id = %s AND product_id = 1",
        (ds, FR_BDPM),
    ).fetchone()
    assert status is not None
    published, routes, end, region = status
    assert published[0] == "Autorisation active" and "Procédure nationale" in published
    assert published[-1] == "Déclaration de commercialisation 16/03/2011"
    assert routes == ["orale"] and end is None and region == "EU"
    # the presentation without ingredients is kept (visible, nothing to evaluate)
    n = db_conn.execute(
        "SELECT count(*) FROM res_product_ingredient WHERE dataset_id = %s AND source_id = %s "
        "AND product_id = 2",
        (ds, ES_CIMA),
    ).fetchone()
    assert n == (0,)
    eu_names = {
        r[0]
        for r in db_conn.execute(
            "SELECT name_key FROM res_name WHERE dataset_id = %s AND region = 'EU'", (ds,)
        ).fetchall()
    }
    assert {"alfazine", "alfazina", "homeo"} <= eu_names
    # the English label stays searchable in every region (""), and the mapped published name of
    # the EU sources is searchable with region EU
    other = db_conn.execute(
        "SELECT region FROM res_name WHERE dataset_id = %s AND name_key = 'alfazin' "
        "AND kind = 'ingredient'",
        (ds,),
    ).fetchall()
    assert sorted(other) == [("",), ("EU",)]


def test_invalid_eu_artifact_refuses_and_the_previous_dataset_keeps_serving(
    database: Database, db_conn: psycopg.Connection
) -> None:
    """Feature: drug-resolution, Property P47 (load part). A present EU artifact whose rows do
    not hash to its manifest refuses the load and changes nothing."""
    reset(db_conn)
    good = load(database, inputs([], [], WD, fr=FR, es=ES))
    before = dump(db_conn, good.dataset_version)
    for source in (FR_BDPM, ES_CIMA):
        inp = inputs([], [], WD, fr=FR[:1], es=ES[:1], run="other")
        bad = dict(inp.artifacts)
        a = bad[source]
        extra = (
            bdpm_row(9, "EXTRA", ["alfazin"]) if source == FR_BDPM else cima_row(9, "X", [], None)
        )
        bad[source] = Artifact(a.source_id, a.manifest, a.evidence, [*a.rows, extra])
        with pytest.raises(LoadError, match="content hash"):
            load(
                database,
                type(inp)(bad, inp.rules, inp.route_map, inp.synonyms, inp.code, inp.cadences),
            )
        assert current_dataset(db_conn) == good.dataset_version
        assert dump(db_conn, good.dataset_version) == before


def test_wrong_schema_version_of_an_eu_artifact_is_refused(
    database: Database, db_conn: psycopg.Connection
) -> None:
    reset(db_conn)
    inp = inputs([], [], WD, fr=FR)
    a = inp.artifacts[FR_BDPM]
    manifest: dict[str, Any] = {**a.manifest, "schema_version": "eu_fr_bdpm-9"}
    bad = {**inp.artifacts, FR_BDPM: Artifact(a.source_id, manifest, a.evidence, a.rows)}
    with pytest.raises(LoadError, match="schema"):
        load(
            database, type(inp)(bad, inp.rules, inp.route_map, inp.synonyms, inp.code, inp.cadences)
        )
    # a manifest that names another source is refused too
    manifest = {**a.manifest, "source_id": "titck"}
    bad = {**inp.artifacts, FR_BDPM: Artifact(a.source_id, manifest, a.evidence, a.rows)}
    with pytest.raises(LoadError, match="another source"):
        load(
            database, type(inp)(bad, inp.rules, inp.route_map, inp.synonyms, inp.code, inp.cadences)
        )
    assert current_dataset(db_conn) is None


@settings(max_examples=max(10, DB_EXAMPLES // 5))
@given(src=sources(), eu=eu_rows(), use=st.tuples(st.booleans(), st.booleans()))
def test_same_artifacts_same_dataset_with_eu_rows(
    database: Database,
    db_conn: psycopg.Connection,
    src: tuple[list[Any], list[Any], list[Any]],
    eu: tuple[list[Any], list[Any]],
    use: tuple[bool, bool],
) -> None:
    """Feature: drug-resolution, Property P8 (load part, EU). Validates Req 9.4, 7.3.

    The same artifacts, in any row order and under any run ids, give the same version and the
    same rows; the stored EU product counts equal the rows given.
    """
    tr, us, wd = src
    fr = eu[0] if use[0] else None
    es = eu[1] if use[1] else None
    reset(db_conn)
    first = load(database, inputs(tr, us, wd, "x", fr, es))
    rows = dump(db_conn, first.dataset_version)
    assert not load(database, inputs(tr, us, wd, "y", fr, es)).changed
    reset(db_conn)
    rev = [list(reversed(x)) if x is not None else None for x in (tr, us, wd, fr, es)]
    again = load(database, inputs(rev[0] or [], rev[1] or [], rev[2] or [], "x", rev[3], rev[4]))
    assert again.dataset_version == first.dataset_version
    assert dump(db_conn, again.dataset_version) == rows
    counts = dict(
        db_conn.execute(
            "SELECT source_id, count(*) FROM res_product WHERE dataset_id = %s GROUP BY 1",
            (again.dataset_version,),
        ).fetchall()
    )
    assert counts.get(FR_BDPM, 0) == (len(fr) if fr else 0)
    assert counts.get(ES_CIMA, 0) == (len(es) if es else 0)
