"""A worked example of presence evaluation (medication-passport design §5.3; Req 2.4, 2.6, 2.7,
6.2), next to the generated properties of `test_passport_presence_properties.py`."""

from __future__ import annotations

import datetime as dt

import psycopg
import pytest

from janus.passport import forms, service
from janus.passport.schemas import PresenceIn
from tests.passport_db import KEYS, UNKNOWN_KEY, Ing, Product, install
from tests.resolution_db import reset

pytestmark = pytest.mark.db
TODAY = dt.date(2026, 11, 8)
K1, K2 = KEYS[0], KEYS[1]


def us(form: str, routes: tuple[str, ...], *ings: Ing) -> Product:
    return Product("openfda_ndc", form, routes, ings)


DATA = [
    us("TABLET, FILM COATED", ("ORAL",), Ing("mapped", K1, "5 mg/1", "TESTNAME")),
    us("TABLET, FILM COATED", ("ORAL",), Ing("mapped", K1, "10 mg/1", "TESTNAME")),
    us("TABLET", (), Ing("mapped", K1, None, "TESTNAME")),  # no route: no group (DP23)
    us("TABLET", ("ORAL",), Ing("mapped", K1, "5 mg/1", "A"), Ing("mapped", K2, "1 mg/1", "B")),
    us("SOLUTION", ("ORAL",), Ing("mapped", K1, "6 [hp_X]/mL", "TESTNAME")),  # homeopathic
    us("TABLET", ("ORAL",), Ing("mapped", K1, "5 mg/1", "A"), Ing("unmapped", None, None, "C")),
]


def test_presence_example(db_conn: psycopg.Connection) -> None:
    install(db_conn, DATA, ["openfda_ndc", "titck"])
    body = PresenceIn.model_validate(
        {
            "items": [
                {
                    "ingredients": [
                        {"key": K1, "strength": {"amount": "5000", "unit": "ug", "basis": "unit"}}
                    ],
                    "dose_form": "oral_solid",
                },
                {"ingredients": [{"key": K2}]},
                {"ingredients": [{"key": UNKNOWN_KEY}]},
            ]
        }
    )
    with db_conn.transaction():
        out = service.presence(db_conn, body, forms.load(), TODAY)
    first = out.items[0].answers
    assert [a.status for a in first] == [
        "not_in_source",
        "source_unavailable",
        "source_unavailable",
        "source_unavailable",
        "present",
    ]
    a = first[4]
    assert (a.products, a.with_other_ingredients, a.homeopathic_left_out) == (3, 2, 1)
    assert a.comparison is not None
    s, f, b = a.comparison.strength, a.comparison.dose_form, a.comparison.strength_and_dose_form
    assert (s.result, s.comparable, s.equal) == ("matched", 2, 1)
    assert (f.result, f.comparable, f.equal) == ("matched", 2, 2)
    assert (b.result, b.comparable, b.equal) == ("matched", 2, 1)
    second = out.items[1].answers[4]
    assert (second.status, second.keys_found, second.with_other_ingredients) == (
        "not_present",
        [K2],
        1,
    )
    assert out.items[2].unknown_keys == [UNKNOWN_KEY]
    assert out.items[2].answers[4].status == "not_in_source"
    assert out.notices == ["presence_is_lower_bound", "unknown_ingredient_keys"]
    assert [x.reason for x in out.sources] == [
        None,
        "not_loaded",
        "not_loaded",
        "no_open_product_database",
        None,
    ]
    reset(db_conn)
