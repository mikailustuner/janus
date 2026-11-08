"""Additive resolution fields (medication-passport task 5.1, design §2, Req 6.6).

Feature: medication-passport, Property P17: for any product, `strength_code` and
`dose_form_group` in the resolution response equal `strength_code()` and `group()` on the stored
values; every other field is unchanged (the answer without the table is the old answer).
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import psycopg
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from janus.passport import forms
from janus.passport.forms import FormTable
from janus.passport.strength import strength_code
from janus.resolution import service
from tests.conftest import DB_EXAMPLES
from tests.passport_db import REGION, Product, datasets, install, product_ids
from tests.resolution_db import reset

pytestmark = pytest.mark.db
TODAY = dt.date(2026, 11, 8)
TABLE = forms.load()


def _strip(dump: dict[str, Any]) -> dict[str, Any]:
    out = dict(dump)
    out["candidates"] = [
        {
            **{k: v for k, v in c.items() if k != "dose_form_group"},
            "ingredients": [
                {k: v for k, v in i.items() if k != "strength_code"} for i in c["ingredients"]
            ],
        }
        for c in dump["candidates"]
    ]
    return out


@settings(max_examples=DB_EXAMPLES)
@given(items=datasets().filter(bool), use_unreviewed=st.booleans())
def test_p17_resolution_fields(
    db_conn: psycopg.Connection, items: list[Product], use_unreviewed: bool
) -> None:
    """Feature: medication-passport, Property P17. Validates Req 6.6."""
    install(db_conn, items)
    ids = [f"{REGION[p.source_id]}:{p.source_id}:{pid}" for pid, p in product_ids(items, REGION)]
    with db_conn.transaction():
        old = service.resolve_products(db_conn, ids, TODAY)
        new = service.resolve_products(db_conn, ids, TODAY, forms=TABLE)
        unreviewed = FormTable(TABLE.rows, TABLE.version, reviewed=False)
        draft = service.resolve_products(db_conn, ids, TODAY, forms=unreviewed)
    assert _strip(new.model_dump()) == _strip(old.model_dump())
    by_id = dict(product_ids(items, REGION))
    for c in new.candidates:
        assert c.kind == "product"
        p = by_id[int(c.candidate_id.rsplit(":", 1)[1])]
        group = TABLE.group(p.source_id, p.dosage_form, p.routes)
        assert c.dose_form_group == group
        for i, ing in zip(c.ingredients, p.ingredients, strict=True):
            code = strength_code(p.source_id, ing.strength, group)
            assert (i.strength_code is None) == (code is None)
            if code is not None and i.strength_code is not None:
                assert (i.strength_code.amount, i.strength_code.unit, i.strength_code.basis) == (
                    code.amount,
                    code.unit,
                    code.basis,
                )
    if use_unreviewed:  # an unaccepted table names no group (task 4 review stop)
        assert all(c.dose_form_group is None for c in draft.candidates if c.kind == "product")
    for c in old.candidates:
        assert c.kind == "product" and c.dose_form_group is None
    reset(db_conn)
