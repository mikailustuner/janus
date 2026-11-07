"""Homeopathic products (P25) and curated Janus ingredient keys (P26), drug-resolution design §9.

Owner decisions of 2026-11-07 (cascade-engine review of the synonym proposals).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
from alembic import command
from hypothesis import given
from hypothesis import strategies as st

from janus.db.pool import Database
from janus.resolution import service
from janus.resolution.atc import CombinationRules, RouteMap
from janus.resolution.load import (
    CURATED_FILE,
    Inputs,
    LoadError,
    load,
    parse_curated,
    read_curated,
)
from janus.resolution.model import is_homeopathic_product, is_homeopathic_strength
from janus.resolution.prepare import prepare_dataset
from tests.conftest import alembic_config
from tests.resolution_db import inputs, reset
from tests.resolution_strategies import barcode13, titck_row, us_row, wikidata_row

HP_UNITS = ["[hp_X]", "[hp_C]", "[hp_M]", "[hp_Q]", "[kp_C]", "[HP_X]"]
OTHER_UNITS = ["mg", "g", "mL", "[iu]", "[pnu]", "[bau]", "[USP'U]", "%"]
NUMBER = st.decimals(min_value=0, max_value=10000, places=3).map(str)


@given(n=NUMBER, unit=st.sampled_from(HP_UNITS), per=st.sampled_from(["/1", "/mL", "/g", ""]))
def test_p25_homeopathic_units_are_detected(n: str, unit: str, per: str) -> None:
    """Feature: drug-resolution, Property 25. Homeopathic strength units are always detected."""
    assert is_homeopathic_strength(f"{n} {unit}{per}")


@given(n=NUMBER, unit=st.sampled_from(OTHER_UNITS), per=st.sampled_from(["/1", "/mL", "/g", ""]))
def test_p25_other_units_are_not_homeopathic(n: str, unit: str, per: str) -> None:
    """Feature: drug-resolution, Property 25. Ordinary units and missing strengths are not."""
    assert not is_homeopathic_strength(f"{n} {unit}{per}")
    assert not is_homeopathic_strength(None) and not is_homeopathic_strength("")


def _strength(n: str, unit: str) -> str:
    return f"{n} {unit}/1"


@given(
    strengths=st.lists(
        st.one_of(
            st.none(),
            st.builds(_strength, NUMBER, st.sampled_from(HP_UNITS + OTHER_UNITS)),
        ),
        max_size=6,
    )
)
def test_p25_product_flag(strengths: list[str | None]) -> None:
    """Feature: drug-resolution, Property 25. A product is homeopathic iff any ingredient is."""
    assert is_homeopathic_product(strengths) == any(is_homeopathic_strength(s) for s in strengths)


# --- P26: curated Janus keys -------------------------------------------------------------------

HEADER = "key,label_en,label_tr,label_de,label_fr,label_es,atc_codes,added_on,note\n"
DIMEN = (
    "J1,dimenhydrinate,dimenhidrinat,Dimenhydrinat,dimenhydrinate,dimenhidrinato,"
    "R06AA11,2026-11-07,n\n"
)


def test_p26_real_file_parses() -> None:
    """Feature: drug-resolution, Property 26. The committed file has dimenhydrinate as J1."""
    cur = read_curated(CURATED_FILE)
    (row,) = cur.rows
    assert (row["qid"], row["atc_codes"], row["label_en"]) == ("J1", ["R06AA11"], "dimenhydrinate")
    assert cur.added_on == "2026-11-07" and len(cur.sha256) == 64


@pytest.mark.parametrize(
    "bad",
    [
        "Q1,x,,,,,R06AA11,2026-11-07,n\n",  # a QID is not a Janus key
        "J1,x,,,,,R06AA,2026-11-07,n\n",  # not an ingredient-level code
        "J1,,,,,,R06AA11,2026-11-07,n\n",  # no label
        "J1,x,,,,,R06AA11,07.11.2026,n\n",  # bad date
        DIMEN + DIMEN,  # repeated key
    ],
)
def test_p26_bad_rows_are_refused(bad: str) -> None:
    """Feature: drug-resolution, Property 26. Bad keys, codes, labels and dates are refused."""
    with pytest.raises(LoadError) as err:
        parse_curated(HEADER + bad)
    assert "row" in str(err.value) and "dimen" not in str(err.value)


@given(synonym_to_parent=st.booleans())
def test_p26_curated_key_maps_its_names_with_its_own_code(synonym_to_parent: bool) -> None:
    """Feature: drug-resolution, Property 26. Names of a Janus key map to it (not to the parent
    substance's item) with its own code cited to `janus_curated`."""
    wd = [wikidata_row("Q413486", ["R06AA02"], {"en": "diphenhydramine", "tr": "difenhidramin"})]
    tr = [titck_row(barcode13(1), "DIMEN", ["dimenhidrinat"], "R06AA11")]
    us = [us_row("12345-001", ["12345-001-01"], ["dimenhydrinate"], ["ORAL"], "HUMAN OTC DRUG")]
    curated = parse_curated(HEADER + DIMEN).rows
    # A curated synonym (step 0) still wins over the key's labels, so the owner can override it.
    syn = (("unrelated name", "Q413486"),) if synonym_to_parent else ()
    ds = prepare_dataset(tr, us, wd, CombinationRules.load(), RouteMap.load(), syn, curated)
    for p in ds.products:
        (ing,) = p.ingredients
        assert ing.qid == "J1"
        assert [a.code for a in ing.atc] == ["R06AA11"]
    (code,) = ds.ingredients["J1"].ingredient_atc
    # A code observed on a TİTCK product is cited first (the regulator's list); without one,
    # the curated key itself is the source.
    assert (code.code, code.source_id) == ("R06AA11", "titck")
    us_only = prepare_dataset(
        [], us, wd, CombinationRules.load(), RouteMap.load(), syn, curated
    ).ingredients["J1"]
    assert [(a.code, a.source_id) for a in us_only.ingredient_atc] == [("R06AA11", "janus_curated")]


@pytest.fixture
def database(db_url: str) -> Iterator[Database]:
    db = Database(db_url)
    db.open()
    yield db
    db.close()


@pytest.mark.db
def test_p26_curated_key_through_the_database(
    database: Database, db_conn: psycopg.Connection
) -> None:
    """Feature: drug-resolution, Property 26. A J key is stored, searchable, and cites the
    curated source version; a US homeopathic product is flagged."""
    reset(db_conn)
    wd = [wikidata_row("Q413486", ["R06AA02"], {"en": "diphenhydramine"})]
    us = [
        us_row(
            "12345-001", ["12345-001-01"], ["dimenhydrinate"], ["ORAL"], "HUMAN OTC DRUG", "DRAMA"
        ),
        {
            **us_row(
                "12345-002",
                ["12345-002-02"],
                ["dimenhydrinate"],
                ["ORAL"],
                "HUMAN OTC DRUG",
                "HOMEO",
            ),
            "active_ingredients": [{"name": "DIMENHYDRINATE", "strength": "6 [hp_X]/1"}],
        },
    ]
    base = inputs([], us, wd)
    load(
        database,
        Inputs(
            base.artifacts,
            CombinationRules.load(),
            RouteMap.load(),
            (),
            "t",
            base.cadences,
            read_curated(),
        ),
    )
    today = dt.date(2026, 11, 7)
    with database.read_only_tx() as conn:
        res = service.search(conn, "dimenhydrinate", None, 10, today)
        prods = service.search(conn, "DRAMA", "US", 5, today)
        homeo = service.search(conn, "HOMEO", "US", 5, today)
    ing = next(c for c in res.candidates if c.kind == "ingredient")
    assert ing.ingredient_key.qid == "J1"  # pyright: ignore[reportAttributeAccessIssue]
    assert ing.source.source_id == "janus_curated"
    p = next(c for c in prods.candidates if c.kind == "product")
    assert not p.homeopathic and p.ingredients[0].ingredient_key is not None  # pyright: ignore[reportAttributeAccessIssue]
    h = next(c for c in homeo.candidates if c.kind == "product")
    assert h.homeopathic  # pyright: ignore[reportAttributeAccessIssue]


@pytest.mark.db
def test_migration_0006_is_reversible(db_url: str, db_conn: psycopg.Connection) -> None:
    """Upgrade → downgrade → upgrade; the widened check accepts J keys only after 0006."""

    def check() -> str:
        row = db_conn.execute(
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
            "WHERE conname = 'res_ingredient_qid'"
        ).fetchone()
        assert row is not None
        return str(row[0])

    reset(db_conn)
    cfg = alembic_config(db_url)
    after = check()
    assert "J[1-9]" in after
    command.downgrade(cfg, "0005")
    assert "J[1-9]" not in check()
    command.upgrade(cfg, "head")
    assert check() == after


def test_curated_file_is_in_data() -> None:
    assert Path(CURATED_FILE).name == "janus_ingredients.csv" and CURATED_FILE.is_file()
