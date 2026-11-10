"""Canadian (Health Canada DPD) and Italian (AIFA) products (national-products design §8).

N1 strength codes of the two sources agree with the codes of the same quantity in the existing
sources and are never given without a stated or implied reference; N2 the DPD `A (B)` rule and N3
the national ATC bridge only map a name to a key both parts or one product code name, and never
choose between keys; N4 what is left out and what is kept; N5 a listed product has exactly the
item's keys and no unmapped ingredient; N6 Italian products are found by name with region EU and
Canadian products are never candidates; N7 migration 0015 is reversible. Synthetic data only.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator
from fractions import Fraction
from typing import Any

import psycopg
import pytest
from alembic import command
from fastapi.testclient import TestClient
from hypothesis import given, settings
from hypothesis import strategies as st

from janus.cascades.report import read_rows
from janus.db.pool import Database
from janus.main import create_app
from janus.passport import forms
from janus.passport import router as passport_router
from janus.passport.forms import COUNTABLE_GROUPS, GROUPS
from janus.passport.listing import marketed
from janus.passport.strength import StrengthCode, canonical, strength_code
from janus.resolution.load import load
from janus.resolution.matching import NO_MATCH, Match
from janus.resolution.prepare import PreparedDataset, prepare_dataset
from janus.resolution.prepare_national import (
    CA_DPD,
    IT_AIFA,
    UNNAMED,
    aifa_products,
    aifa_strength,
    dpd_products,
    dpd_strength,
    map_dpd_name,
)
from janus.settings import Settings
from tests.conftest import DB_EXAMPLES, alembic_config
from tests.resolution_db import inputs, reset
from tests.resolution_strategies import ROUTES, RULES, bdpm_row, cima_row, wikidata_row

TODAY = dt.date(2026, 11, 10)
JSON = {"content-type": "application/json"}

# --- synthetic rows in the shape of the two pipeline artifacts --------------------------------

WD = [
    wikidata_row("Q1", ["A02AA01"], {"en": "alfazin"}),
    wikidata_row("Q2", ["C08CA01"], {"en": "betorol"}),
    wikidata_row("Q3", ["N02BE01"], {"en": "kavidin"}),
    # Two items carry J01CA04: a code that cannot bridge a name.
    wikidata_row("Q4", ["J01CA04"], {"en": "dumapril"}),
    wikidata_row("Q5", ["J01CA04"], {"en": "eslotan"}),
]
CODE_OF = {"Q1": "A02AA01", "Q2": "C08CA01", "Q3": "N02BE01"}
ENGLISH = {"Q1": "alfazin", "Q2": "betorol", "Q3": "kavidin"}
ITALIAN = {"Q1": "ALFAZINA CLORIDRATO", "Q2": "BETOROLO", "Q3": "KAVIDINA SALE DI CALCIO"}


def dpd_row(
    i: int,
    brand: str,
    names: list[str],
    *,
    atc: list[str] | None = None,
    product_class: str = "Human",
    forms_: list[str] | None = None,
    strength: tuple[str, str, str, str] = ("5", "MG", "", ""),
) -> dict[str, Any]:
    return {
        "din": f"{i:08d}",
        "name_only": False,
        "drug_code": str(1000 + i),
        "product_class": product_class,
        "brand_name": brand,
        "descriptor": "",
        "number_of_ais": str(len(names)),
        "last_update_date": "02-NOV-2026",
        "ai_group_no": "0100000001",
        "forms": ["TABLET"] if forms_ is None else forms_,
        "routes": ["ORAL"],
        "atc": [{"code": c, "description": "X"} for c in (atc or [])],
        "status": "MARKETED",
        "status_date": "01-JAN-2020",
        "schedules": ["PRESCRIPTION"],
        "upcs": [],
        "ingredients": [
            {
                "code": str(k),
                "name": n,
                "strength": strength[0],
                "strength_unit": strength[1],
                "strength_type": "",
                "dosage_value": strength[2],
                "base": "N",
                "dosage_unit": strength[3],
            }
            for k, n in enumerate(names, start=1)
        ],
    }


def aifa_row(
    i: int,
    name: str,
    names: list[str],
    *,
    atc: str = "",
    procedure: str = "Procedura Nazionale",
    status: str = "Autorizzata",
    form: str = "Compressa",
    quantity: str = "5",
    unit: str = "milligrammi",
) -> dict[str, Any]:
    aic = f"{i:09d}"
    return {
        "aic": aic,
        "name_only": False,
        "medicine_code": aic[:6],
        "pack_code": aic[6:],
        "name": name,
        "description": f"5 MG COMPRESSE- {10 + i} COMPRESSE",
        "holder": "TESTHOLDER S.R.L.",
        "status": status,
        "procedure": procedure,
        "form": form,
        "atc_code": atc,
        "ingredients_text": "/".join(names),
        "ingredients": [{"name": n, "quantity": quantity, "unit": unit} for n in names],
    }


def prepared(ca: list[Any] | None, it: list[Any] | None) -> PreparedDataset:
    return prepare_dataset([], [], WD, RULES, ROUTES, ca_rows=ca, it_rows=it)


# --- N1: strength codes -----------------------------------------------------------------------

AMOUNTS = st.one_of(
    st.integers(1, 5000).map(str),
    st.tuples(st.integers(0, 500), st.integers(1, 99)).map(lambda p: f"{p[0]}.{p[1]:02d}"),
)
MASS = st.sampled_from([("MG", "mg", "milligrammi"), ("G", "g", "grammi"), ("MCG", "ug", None)])
GROUP = st.sampled_from([None, *GROUPS])


@given(a=AMOUNTS, unit=MASS, group=GROUP)
def test_n1_plain_strength_is_per_unit_only_for_countable_forms(
    a: str, unit: tuple[str, str, str | None], group: str | None
) -> None:
    """Feature: national-products, Property N1. Validates Req 5.2, 5.5.

    `A U` without a reference quantity is a code only for tablets and capsules, and then the same
    code as the BDPM gives the same amount and unit."""
    ca = strength_code(CA_DPD, f"{a} {unit[0]}", group)
    fr = strength_code("eu_fr_bdpm", f"{a.replace('.', ',')} {unit[1]}", group)
    assert ca == fr
    factor = {"mg": 10**3, "g": 10**6, "ug": 1}[unit[1]]
    fits = canonical(Fraction(a) * factor) is not None  # at most nine digits before the point
    assert (ca is not None) == (group in COUNTABLE_GROUPS and fits)
    if unit[2] is not None:
        assert strength_code(IT_AIFA, f"{a} {unit[2]}", group) == fr
    if ca is not None:
        assert ca.basis == "unit" and ca.unit == "ug"


@given(a=AMOUNTS, n=st.sampled_from(["", "1", "2", "5", "0.5", "100"]), group=GROUP)
def test_n1_stated_volume_gives_the_us_code(a: str, n: str, group: str | None) -> None:
    """Feature: national-products, Property N1. Validates Req 5.3, 5.5.

    `A MG / N ML` is A / N per mL whatever the form group, equal to the openFDA code of the same
    quantity; a litre is 1000 mL; AIFA's per-millilitre and per-litre unit names agree."""
    per = f"{n} ML" if n else "ML"
    ca = strength_code(CA_DPD, f"{a} MG / {per}", group)
    us = strength_code("openfda_ndc", f"{a} mg/{n}mL", group)
    assert ca == us
    if ca is not None:
        assert ca.basis == "mL"
    litres = f"{n} L" if n else "L"
    assert strength_code(CA_DPD, f"{a} G / {litres}", group) == ca
    if not n:
        assert strength_code(IT_AIFA, f"{a} milligram(s)/millilitre", group) == ca
        assert strength_code(IT_AIFA, f"{a} gram(s)/litre", group) == ca
        expected = canonical(Fraction(a) * 1000)
        assert ca == (None if expected is None else StrengthCode(expected, "ug", "mL"))


@pytest.mark.parametrize(
    ("source", "published"),
    [
        (CA_DPD, "100 UNIT / ML"),  # units are not international units
        (CA_DPD, "100 UNIT"),
        (CA_DPD, "5 % / W/W"),
        (CA_DPD, "5 %"),
        (CA_DPD, "500 MG / VIAL"),
        (CA_DPD, "100 MCG / ACT"),
        (CA_DPD, "25 MCG / HOUR"),
        (CA_DPD, "5 MG / 0 ML"),
        (CA_DPD, "MG"),
        (CA_DPD, ""),
        (IT_AIFA, "5 percent"),
        (IT_AIFA, "5 international unit(s)/milli#"),  # truncated by the source
        (IT_AIFA, "25 microgram(s)/hour"),
        (IT_AIFA, "5 Unita"),
        (IT_AIFA, "5 N.D."),
        (IT_AIFA, "0.0 N.D."),
        (IT_AIFA, "milligrammi"),
    ],
)
def test_n1_everything_else_has_no_code(source: str, published: str) -> None:
    """Validates Req 5.4: no code where the source states no mass per unit, mL or g."""
    for group in (None, *GROUPS):
        assert strength_code(source, published, group) is None


def test_n1_examples() -> None:
    assert strength_code(CA_DPD, "10 MG", "oral_solid") == StrengthCode("10000", "ug", "unit")
    assert strength_code(CA_DPD, "250 MG / 5 ML", None) == StrengthCode("50000", "ug", "mL")
    assert strength_code(CA_DPD, "1 MG / G", "cutaneous") == StrengthCode("1000", "ug", "g")
    assert strength_code(IT_AIFA, "0.5 milligrammi", "oral_solid") == StrengthCode(
        "500", "ug", "unit"
    )
    assert strength_code(IT_AIFA, "400 international unit(s)", "oral_solid") == StrengthCode(
        "400", "IU", "unit"
    )
    assert strength_code(IT_AIFA, "1 milligram(s)/gram", None) == StrengthCode("1000", "ug", "g")


def test_published_strength_text() -> None:
    """Validates Req 5.1: the text shown is the published cells, trimmed and joined."""

    def dpd(strength: str, unit: str, value: str, per: str) -> str | None:
        return dpd_strength(
            {"strength": strength, "strength_unit": unit, "dosage_value": value, "dosage_unit": per}
        )

    assert dpd("10", "MG", "", "") == "10 MG"
    assert dpd("250", "MG", "5", "ML") == "250 MG / 5 ML"
    assert dpd("  100000", "UNIT", "", "ML") == "100000 UNIT / ML"
    assert dpd("", "MG", "", "") is None and dpd("5", "", "", "") is None

    def aifa(quantity: str, unit: str) -> str | None:
        return aifa_strength({"quantity": quantity, "unit": unit})

    assert aifa("10", "milligrammi") == "10 milligrammi"
    assert aifa(" 0.0", "N.D.") is None and aifa("", "") is None
    assert aifa("5", "N.D.") is None and aifa("0", "milligrammi") is None
    assert aifa("3", "MILIARDI                    ") == "3 MILIARDI"
    assert (
        aifa("1.000", "milligrammi") is None and aifa("0.500", "milligrammi") == "0.500 milligrammi"
    )
    base = {"strength": "10", "strength_unit": "MG", "dosage_value": "", "dosage_unit": ""}
    assert dpd_strength({**base, "base": "N"}) == "10 MG"
    assert dpd_strength({**base, "base": "Y"}) is None
    assert dpd_strength({**base, "strength_type": "EQUIVALENT TO"}) is None


def test_n4_a_source_count_that_the_lines_do_not_match_is_never_exact() -> None:
    """Safety audit: an ingredient the source counts or names but does not list stays unnamed."""
    short = {**dpd_row(1, "SHORT", ["ALFAZIN"]), "number_of_ais": "2"}
    full = dpd_row(2, "FULL", ["ALFAZIN"])
    ca, _ = dpd_products([short, full])
    assert sorted(len(p.names) for p in ca) == [1, 2]
    assert sum(1 for p in ca for n, _ in p.names if n == UNNAMED) == 1
    row = {**aifa_row(1, "PACK", ["BETOROLO"]), "ingredients_text": "BETOROLO/GAMMAZOLO"}
    ok = aifa_row(2, "OK", ["BETOROLO", "GAMMAZOLO"])
    it, _ = aifa_products([row, ok])
    assert sum(1 for p in it for n, _ in p.names if n == UNNAMED) == 1


# --- N2: the DPD `A (B)` rule -----------------------------------------------------------------

KEYS = st.sampled_from(["Q1", "Q2", "Q3"])
PART = st.one_of(
    KEYS.map(lambda q: Match("mapped", "any_label", (q,))),
    st.just(NO_MATCH),
    st.just(Match("ambiguous", "any_label", ("Q1", "Q2"))),
    st.just(Match("unsplit", None, ("Q2", "Q3"))),
)


@given(whole=PART, outer=PART, inner=PART)
def test_n2_parenthesis_rule_never_chooses(whole: Match, outer: Match, inner: Match) -> None:
    """Feature: national-products, Property N2. Validates Req 3.3.

    `A (B)` maps only when the whole name maps, or `A` maps to one key and `B` maps to the same
    key (or to none and starts like `A`, see below); two different keys are ambiguous with both
    kept; nothing else changes."""
    table = {"A (B)": whole, "A": outer, "B": inner}
    got = map_dpd_name("A (B)", table.__getitem__)
    if whole.status == "mapped":
        assert got == whole
    elif outer.status != "mapped":
        assert got == whole
    elif inner.status == "mapped" and inner.keys == outer.keys:
        assert got.status == "mapped" and got.keys == outer.keys
    elif inner.status == "none":
        assert got == whole  # "B" is not named as a form of "A": left to the ladder
    else:
        assert got.status == "ambiguous" and set(got.keys) == {*outer.keys, *inner.keys}
    if got.status == "mapped":
        assert got.keys in (whole.keys, outer.keys)


def test_n2_unmapped_parenthesis_must_name_a_form_of_the_outer_name() -> None:
    def mapper(text: str) -> Match:
        return Match("mapped", "any_label", ("Q1",)) if text == "ALFAZIN" else NO_MATCH

    assert map_dpd_name("ALFAZIN (ALFAZIN HYDROCHLORIDE)", mapper).keys == ("Q1",)
    assert map_dpd_name("ALFAZIN (BETOROL)", mapper) == NO_MATCH  # another substance: not dropped


def test_n2_names_without_the_shape_are_left_to_the_ladder() -> None:
    calls: list[str] = []

    def mapper(text: str) -> Match:
        calls.append(text)
        return NO_MATCH

    for name in ("ALFAZIN", "A (B) (C)", "(B)", "A (B) C", "A ()"):
        calls.clear()
        assert map_dpd_name(name, mapper) == NO_MATCH
        assert calls == [name]


def test_n2_dpd_examples() -> None:
    ds = prepared(
        [
            dpd_row(1, "ONE", ["ALFAZIN (ALFAZIN HYDROCHLORIDE)"]),
            dpd_row(2, "TWO", ["ALFAZIN (BETOROL)"]),
            dpd_row(3, "THREE", ["ALFAZIN (SOMETHING UNKNOWN)"]),
            dpd_row(4, "FOUR", ["UNKNOWN (ALFAZIN)"]),
        ],
        None,
    )
    by_name = {p.product_name: p.ingredients[0] for p in ds.products}
    assert (by_name["ONE"].status, by_name["ONE"].qid) == ("mapped", "Q1")
    assert by_name["ONE"].published_name == "ALFAZIN (ALFAZIN HYDROCHLORIDE)"
    assert by_name["TWO"].status == "ambiguous" and by_name["TWO"].qid is None
    assert set(by_name["TWO"].key_candidates) == {"Q1", "Q2"}
    assert by_name["THREE"].status == "unmapped" and by_name["THREE"].qid is None
    assert by_name["FOUR"].status == "unmapped" and by_name["FOUR"].qid is None


# --- N3: the national ATC bridge --------------------------------------------------------------


def test_n3_bridge_examples() -> None:
    """Validates Req 3.4-3.6."""
    it = [
        aifa_row(1, "UNO", [ITALIAN["Q1"]], atc="A02AA01"),
        # the bridged name maps inside a combination, which has a combination code of its own
        aifa_row(2, "DUE", [ITALIAN["Q1"], ITALIAN["Q2"]], atc="C09BB03"),
        aifa_row(3, "TRE", [ITALIAN["Q2"]], atc="C08CA01"),
        # a code that two items carry bridges nothing
        aifa_row(4, "QUATTRO", ["NOME SENZA CHIAVE"], atc="J01CA04"),
        # one name under two codes of different items is ambiguous
        aifa_row(5, "CINQUE", ["NOME DOPPIO"], atc="A02AA01"),
        aifa_row(6, "SEI", ["NOME DOPPIO"], atc="N02BE01"),
        # therapeutic-group and combination codes bridge nothing
        aifa_row(7, "SETTE", ["SOLO GRUPPO"], atc="A02AA"),
        aifa_row(8, "OTTO", ["SOLO COMBINAZIONE"], atc="C09BB03"),
        # a label wins over a product code
        aifa_row(9, "NOVE", ["BETOROL"], atc="A02AA01"),
    ]
    ds = prepared(None, it)
    ing = {p.brand_name: p.ingredients for p in ds.products}
    assert [(i.status, i.qid, i.match_step) for i in ing["UNO"]] == [
        ("mapped", "Q1", "national_atc_bridge")
    ]
    assert [(i.status, i.qid) for i in ing["DUE"]] == [("mapped", "Q1"), ("mapped", "Q2")]
    assert ing["QUATTRO"][0].status == "unmapped" and ing["QUATTRO"][0].qid is None
    for name in ("CINQUE", "SEI"):
        assert ing[name][0].status == "ambiguous" and ing[name][0].qid is None
        assert set(ing[name][0].key_candidates) == {"Q1", "Q3"}
    assert ing["SETTE"][0].status == "unmapped" and ing["OTTO"][0].status == "unmapped"
    assert (ing["NOVE"][0].qid, ing["NOVE"][0].match_step) == ("Q2", "any_label")


def test_n3_the_bridge_is_per_source_and_a_combination_never_feeds_it() -> None:
    it = [aifa_row(1, "UNO", [ITALIAN["Q1"]], atc="A02AA01")]
    ca = [
        dpd_row(1, "ONE", [ITALIAN["Q1"]]),  # the Italian name, no code of its own in the DPD
        dpd_row(2, "TWO", ["NEWNAME", "OTHERNAME"], atc=["A02AA01"]),  # two ingredients
        dpd_row(3, "THREE", ["THIRDNAME"], atc=["A02AA01", "C08CA01"]),  # two published codes
    ]
    ds = prepared(ca, it)
    canada = [p for p in ds.products if p.source_id == CA_DPD]
    assert all(i.status == "unmapped" for p in canada for i in p.ingredients)
    assert {p.product_name: p.published_atc for p in canada} == {
        "ONE": None,
        "TWO": "A02AA01",
        "THREE": None,
    }


@st.composite
def national_rows(draw: st.DrawFn) -> tuple[list[Any], list[Any]]:
    """Canadian and Italian rows whose names are a known English label, an Italian name that
    only a product code can bridge, an unknown name or the source's "not available"."""
    key = st.sampled_from(["Q1", "Q2", "Q3"])
    ca: list[Any] = []
    for i in range(1, draw(st.integers(0, 6)) + 1):
        names = draw(
            st.lists(
                st.one_of(
                    key.map(lambda q: ENGLISH[q].upper()),
                    key.map(lambda q: f"{ENGLISH[q].upper()} ({ENGLISH[q].upper()} SODIUM)"),
                    st.just("UNKNOWN SUBSTANCE"),
                ),
                min_size=1,
                max_size=3,
                unique=True,
            )
        )
        cls = draw(st.sampled_from(["Human"] * 4 + ["Veterinary", "Disinfectant"]))
        ca.append(dpd_row(i, f"CABRAND {i}", names, product_class=cls))
    it: list[Any] = []
    for i in range(1, draw(st.integers(0, 8)) + 1):
        keys = draw(st.lists(key, min_size=1, max_size=2, unique=True))
        names = [ITALIAN[q] for q in keys]
        if draw(st.integers(0, 5)) == 0:
            names.append(draw(st.sampled_from(["N.D.", "SOSTANZA SCONOSCIUTA"])))
        atc = CODE_OF[keys[0]] if len(names) == 1 and draw(st.booleans()) else ""
        procedure = draw(st.sampled_from(["Procedura Nazionale"] * 4 + ["Omeopatico"]))
        status = draw(st.sampled_from(["Autorizzata"] * 5 + ["Sospesa"]))
        it.append(aifa_row(i, f"ITBRAND {i}", names, atc=atc, procedure=procedure, status=status))
    return ca, it


@given(rows=national_rows(), data=st.data())
def test_n4_prepared_products_keep_what_the_sources_publish(
    rows: tuple[list[Any], list[Any]], data: st.DataObject
) -> None:
    """Feature: national-products, Properties N3, N4. Validates Req 3.1-3.7, 4.1-4.4, 4.7.

    One product per human DPD row and per authorised, non-homeopathic AIFA pack, whatever the
    row order; every product keeps its identifier and one entry per published ingredient in
    order; an entry is mapped only with a key and a code of that key; an Italian name is mapped
    only if a single-ingredient pack bridges it; Canadian products get no name entry."""
    ca, it = rows
    ds = prepared(ca, it)
    again = prepared(data.draw(st.permutations(ca)), data.draw(st.permutations(it)))
    assert ds.products == again.products and ds.names == again.names
    human = [r for r in ca if r["product_class"] == "Human"]
    kept = [r for r in it if r["procedure"] != "Omeopatico" and r["status"] == "Autorizzata"]
    canada = [p for p in ds.products if p.source_id == CA_DPD]
    italy = [p for p in ds.products if p.source_id == IT_AIFA]
    assert len(canada) == len(human) and len(italy) == len(kept)
    assert {p.codes for p in canada} == {(("ca_din", r["din"], r["din"]),) for r in human}
    assert {p.codes for p in italy} == {(("it_aic", r["aic"], r["aic"]),) for r in kept}
    assert all(p.region == "CA" for p in canada) and all(p.region == "EU" for p in italy)
    bridged = {r["ingredients"][0]["name"] for r in kept if r["atc_code"]}
    for p in (*canada, *italy):
        assert [i.position for i in p.ingredients] == list(range(len(p.ingredients)))
        for i in p.ingredients:
            if i.status == "mapped":
                assert i.qid is not None and i.atc
                own = {a.code for a in ds.ingredients[i.qid].ingredient_atc}
                assert {a.code for a in i.atc} <= own
            else:
                assert i.qid is None and i.rule_input() == ()
            if p.source_id == IT_AIFA and i.published_name != UNNAMED:
                assert (i.status == "mapped") == (i.published_name in bridged)
            if i.published_name in (UNNAMED, "UNKNOWN SUBSTANCE", "SOSTANZA SCONOSCIUTA"):
                assert i.status == "unmapped"
    refs = {n.ref for n in ds.names if n.kind == "product"}
    assert not any(r.startswith("CA:") for r in refs) and all(n.region != "CA" for n in ds.names)
    assert {p.candidate_id for p in italy} <= refs
    for source, held, left in (
        (CA_DPD, canada, {"not_human_class": len(ca) - len(human)}),
        (
            IT_AIFA,
            italy,
            {
                "homeopathic_registration": sum(1 for r in it if r["procedure"] == "Omeopatico"),
                "not_authorised": len(it)
                - len(kept)
                - sum(1 for r in it if r["procedure"] == "Omeopatico"),
            },
        ),
    ):
        if held:
            cov = ds.coverage[source]
            assert cov["products"] == cov["with_identifier"] == len(held)
            assert cov["left_out"] == {k: v for k, v in left.items() if v}
        else:
            assert source not in ds.coverage


def test_n4_left_out_and_kept_examples() -> None:
    ca, left_ca = dpd_products(
        [
            dpd_row(1, "HUMAN", ["ALFAZIN"], forms_=["TABLET", "SOLUTION"]),
            dpd_row(2, "VET", ["ALFAZIN"], product_class="Veterinary"),
            {**dpd_row(3, "NO DIN", ["ALFAZIN"]), "din": None, "name_only": True},
        ]
    )
    assert left_ca.counts == {"not_human_class": 1}
    assert [p.product["product_name"] for p in ca] == ["HUMAN", "NO DIN"]
    assert ca[0].product["dosage_form"] == "TABLET; SOLUTION"
    assert ca[0].product["status_published"] == ("MARKETED",)
    assert ca[1].product["codes"] == () and ca[1].product["name_only"] is True
    it, left_it = aifa_products(
        [
            aifa_row(1, "TENUTA", ["N.D.", "BETOROLO"], form="Non nota"),
            aifa_row(2, "OMEO", ["ARNICA"], procedure="Omeopatico"),
            aifa_row(3, "SOSPESA", ["BETOROLO"], status="Sospesa"),
        ]
    )
    assert left_it.counts == {"homeopathic_registration": 1, "not_authorised": 1}
    (kept,) = it
    assert kept.product["product_name"] == "TENUTA 5 MG COMPRESSE- 11 COMPRESSE"
    assert kept.product["brand_name"] == "TENUTA" and kept.product["dosage_form"] is None
    assert kept.names == ((UNNAMED, None), ("BETOROLO", "5 milligrammi"))
    assert kept.product["status_published"] == ("Autorizzata", "Procedura Nazionale")


def test_marketing_statement_of_the_new_sources() -> None:
    """Validates Req 6.5: only what the source states."""
    assert marketed(CA_DPD, ["MARKETED"], None, TODAY) == "listed_as_marketed"
    assert marketed(CA_DPD, [], None, TODAY) == "not_stated"
    assert marketed(IT_AIFA, ["Autorizzata", "Procedura Nazionale"], None, TODAY) == "not_stated"


# --- database and HTTP ------------------------------------------------------------------------

CA = [
    dpd_row(1, "CABRAND ALFA", ["ALFAZIN (ALFAZIN HYDROCHLORIDE)"], atc=["A02AA01"]),
    dpd_row(2, "CABRAND ALFA LIQUID", ["ALFAZIN"], strength=("250", "MG", "5", "ML")),
    dpd_row(3, "CABRAND COMBO", ["ALFAZIN", "UNKNOWN SUBSTANCE"]),
    dpd_row(4, "CABRAND VET", ["ALFAZIN"], product_class="Veterinary"),
]
IT = [
    aifa_row(1, "ITBRAND ALFA", [ITALIAN["Q1"]], atc="A02AA01"),
    aifa_row(2, "ITBRAND ALFA", [ITALIAN["Q1"]], atc="A02AA01", quantity="", unit=""),
    aifa_row(3, "ITBRAND IGNOTA", [ITALIAN["Q1"], "N.D."]),
    aifa_row(4, "ITBRAND OMEO", [ITALIAN["Q1"]], procedure="Omeopatico"),
]
FR = [bdpm_row(1, "ALFAZINE 1 mg, comprimé", ["alfazin"], routes="orale")]
ES = [cima_row(1, "ALFAZINA 1 mg", ["alfazin"], "A02AA01")]


@pytest.fixture(scope="module")
def env(db_url: str) -> Iterator[tuple[TestClient, Database]]:
    database = Database(db_url)
    database.open()
    app = create_app(Settings.from_env({}), database=database)
    old = passport_router.today
    passport_router.today = lambda: TODAY
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, database
    passport_router.today = old
    database.close()
    with psycopg.connect(db_url, autocommit=True) as conn:
        reset(conn)


def _products(client: TestClient, target: str, keys: list[str], **more: Any) -> dict[str, Any]:
    body = {"ingredients": [{"key": k} for k in keys], "target": target, **more}
    r = client.post("/passport/products", json=body, headers=JSON)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.db
def test_n5_listing_of_the_new_targets(
    env: tuple[TestClient, Database], db_conn: psycopg.Connection
) -> None:
    """Feature: national-products, Property N5 (example). Validates Req 4.4, 5.6, 6.1-6.5."""
    client, database = env
    reset(db_conn)
    ds = load(database, inputs([], [], WD, ca=CA, it=IT)).dataset_version
    rows = db_conn.execute(
        "SELECT source_id, region, count(*) FROM res_product WHERE dataset_id = %s GROUP BY 1, 2 "
        "ORDER BY 1",
        (ds,),
    ).fetchall()
    assert rows == [(CA_DPD, "CA", 3), (IT_AIFA, "EU", 3)]
    kinds = db_conn.execute(
        "SELECT kind, count(*), min(code) FROM res_product_code WHERE dataset_id = %s "
        "GROUP BY 1 ORDER BY 1",
        (ds,),
    ).fetchall()
    assert kinds == [("ca_din", 3, "00000001"), ("it_aic", 3, "000000001")]
    versions = db_conn.execute(
        "SELECT source_id, region, license, cadence_days FROM res_source_version "
        "WHERE dataset_id = %s AND source_id IN (%s, %s) ORDER BY 1",
        (ds, CA_DPD, IT_AIFA),
    ).fetchall()
    assert versions == [
        (CA_DPD, None, "Open Government Licence \u2013 Canada (version 2.0)", 30),
        (IT_AIFA, "EU", "CC BY 4.0", 7),
    ]

    ca = _products(client, CA_DPD, ["Q1"])
    assert (ca["status"], ca["total"], ca["with_other_ingredients"]) == ("present", 2, 1)
    src = ca["source"]
    assert (src["source"], src["source_id"], src["region"], src["country"]) == (
        6,
        CA_DPD,
        "CA",
        None,
    )
    assert (src["attribution"], src["snapshot_date"], src["as_published"]) == (
        "dpd",
        "2026-11-02",
        False,
    )
    assert src["can_compare"] == {"strength": True, "dose_form": False}
    by_name = {p["name"]: p for p in ca["products"]}
    assert set(by_name) == {"CABRAND ALFA", "CABRAND ALFA LIQUID"}  # never the unmapped combo
    assert by_name["CABRAND ALFA"]["ingredients"] == [{"key": "Q1", "strength_published": "5 MG"}]
    assert by_name["CABRAND ALFA"]["dose_form_published"] == "TABLET"
    assert all(p["marketed"] == "listed_as_marketed" for p in ca["products"])
    # The form group of a DPD form is not reviewed yet: unknown, and a tablet has no code.
    assert all(p["dose_form_group"] is None and p["dose_form"] == "unknown" for p in ca["products"])

    liquid = {"amount": "50000", "unit": "ug", "basis": "mL"}
    same = _products(client, CA_DPD, ["Q1"], ingredients=[{"key": "Q1", "strength": liquid}])
    levels = {p["name"]: (p["strength"], p["strength_reason"]) for p in same["products"]}
    assert levels == {
        "CABRAND ALFA LIQUID": ("same", None),
        "CABRAND ALFA": ("unknown", "not_known_in_source"),
    }

    italy = _products(client, IT_AIFA, ["Q1"])
    assert (italy["status"], italy["total"], italy["listings"]) == ("present", 2, 2)
    assert italy["with_other_ingredients"] == 1 and italy["homeopathic_left_out"] == 0
    src = italy["source"]
    assert (src["source"], src["region"], src["country"], src["attribution"]) == (
        5,
        "EU",
        "IT",
        "aifa",
    )
    names = sorted(p["name"] for p in italy["products"])
    assert names == [
        "ITBRAND ALFA 5 MG COMPRESSE- 11 COMPRESSE",
        "ITBRAND ALFA 5 MG COMPRESSE- 12 COMPRESSE",
    ]
    assert all(p["marketed"] == "not_stated" for p in italy["products"])
    assert sorted(p["ingredients"][0]["strength_published"] or "" for p in italy["products"]) == [
        "",
        "5 milligrammi",
    ]

    presence = client.post(
        "/passport/presence", json={"items": [{"ingredients": [{"key": "Q1"}]}]}, headers=JSON
    ).json()
    answers = presence["items"][0]["answers"]
    assert [(a["status"], a["products"]) for a in answers[5:]] == [("present", 2), ("present", 2)]
    reset(db_conn)


@pytest.mark.db
@settings(max_examples=DB_EXAMPLES // 5)
@given(rows=national_rows())
def test_n5_no_product_is_listed_with_an_unmapped_ingredient(
    env: tuple[TestClient, Database],
    db_conn: psycopg.Connection,
    rows: tuple[list[Any], list[Any]],
) -> None:
    """Feature: national-products, Property N5. Validates Req 6.2, 6.3.

    For every key and both targets, the listed entries are exactly the loaded products whose
    ingredients are all mapped and whose keys are exactly the requested key."""
    client, database = env
    ca, it = rows
    reset(db_conn)
    load(database, inputs([], [], WD, ca=ca, it=it))
    ds = prepared(ca, it)
    for target in (CA_DPD, IT_AIFA):
        for key in ("Q1", "Q2", "Q3"):
            out = _products(client, target, [key])
            exact = [
                p
                for p in ds.products
                if p.source_id == target
                and all(i.status == "mapped" for i in p.ingredients)
                and {i.qid for i in p.ingredients} == {key}
            ]
            assert out["listings"] == len(exact)
            assert {p["name"] for p in out["products"]} == {p.product_name for p in exact}
            for listed in out["products"]:
                assert {i["key"] for i in listed["ingredients"]} == {key}
                assert listed["strength"] == "unknown"  # the item states no strength
    reset(db_conn)


@pytest.mark.db
def test_n6_italian_products_are_found_by_name_and_canadian_ones_are_not(
    env: tuple[TestClient, Database], db_conn: psycopg.Connection
) -> None:
    """Feature: national-products, Property N6 (example). Validates Req 7.1-7.4."""
    client, database = env
    reset(db_conn)
    load(database, inputs([], [], WD, fr=FR, es=ES, ca=CA, it=IT))

    def search(query: str, region: str | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {"query": query}
        if region:
            body["region"] = region
        r = client.post("/resolve/search", json=body, headers=JSON)
        assert r.status_code == 200, r.text
        return r.json()

    for region in ("EU", None):
        out = search("itbrand alfa", region)
        products = [c for c in out["candidates"] if c["kind"] == "product"]
        assert products and all(c["candidate_id"].startswith("EU:eu_it_aifa:") for c in products)
        first = products[0]
        assert (first["region"], first["country"]) == ("EU", "IT")
        assert first["source"]["source_id"] == IT_AIFA and first["packages"] == []
        assert first["ingredients"][0]["match_step"] == "national_atc_bridge"
        assert IT_AIFA in {s["source_id"] for s in out["sources"]}
    homeopathic = search("itbrand omeo", "EU")
    assert not any("OMEO" in (c.get("product_name") or "") for c in homeopathic["candidates"])
    # The Italian ingredient name is searchable with region EU, as French and Spanish ones are.
    named = search("alfazina cloridrato", "EU")
    assert any(
        c["kind"] == "ingredient" and c["ingredient_key"]["qid"] == "Q1"
        for c in named["candidates"]
    )
    for region in (None, "US", "TR", "EU"):
        out = search("cabrand", region)
        assert [c for c in out["candidates"] if c["kind"] == "product"] == []
        assert CA_DPD not in {s["source_id"] for s in out["sources"]}
    bad = client.post("/resolve/search", json={"query": "cabrand", "region": "CA"})
    assert bad.status_code == 422
    r = client.post("/resolve/products", json={"candidate_ids": ["CA:ca_dpd:1"]}, headers=JSON)
    assert r.status_code == 422

    # Without the Italian source a search that names the EU still answers (Req 7.3).
    reset(db_conn)
    load(database, inputs([], [], WD, fr=FR, es=ES))
    out = search("alfazine", "EU")
    assert out["regions_searched"] == ["EU"]
    assert {s["source_id"] for s in out["sources"]} >= {"eu_fr_bdpm", "eu_es_cima"}
    assert IT_AIFA not in {s["source_id"] for s in out["sources"]}
    reset(db_conn)


@pytest.mark.db
def test_cascade_coverage_report_reads_no_canadian_product(
    env: tuple[TestClient, Database], db_conn: psycopg.Connection
) -> None:
    """Validates Req 7.5: region CA is outside the three rule regions."""
    reset(db_conn)
    load(env[1], inputs([], [], WD, ca=CA, it=IT))
    with db_conn.transaction():
        _, products, _, _ = read_rows(db_conn)
    assert {p.source_id for p in products} == {IT_AIFA}
    assert {p.region for p in products} == {"EU"}
    reset(db_conn)


@pytest.mark.db
def test_n7_migration_0015_is_reversible(db_url: str, db_conn: psycopg.Connection) -> None:
    """Feature: national-products, Property N7. Validates Req 4.5."""
    cfg = alembic_config(db_url)
    reset(db_conn)
    new, old = "c" * 64, "d" * 64
    for dataset in (new, old):
        db_conn.execute(
            "INSERT INTO res_dataset (id, status, inputs) VALUES (%s, 'retired', '{}'::jsonb)",
            (dataset,),
        )
    for dataset, source in ((new, "ca_dpd"), (old, "titck")):
        db_conn.execute(
            "INSERT INTO res_source_version (dataset_id, source_id, run_id, region, "
            "snapshot_date, snapshot_is_retrieval_time, content_sha256, schema_version, license, "
            "source_url) VALUES (%s, %s, 'r1', NULL, '2026-11-02', false, 'h', 's-1', 'l', 'u')",
            (dataset, source),
        )
    db_conn.execute(
        "INSERT INTO res_product (dataset_id, source_id, product_id, region, routes, name_only, "
        "product_rxcuis) VALUES (%s, 'ca_dpd', 1, 'CA', '{}', false, '{}')",
        (new,),
    )
    db_conn.execute(
        "INSERT INTO res_product (dataset_id, source_id, product_id, region, routes, name_only, "
        "product_rxcuis) VALUES (%s, 'titck', 1, 'TR', '{}', false, '{}')",
        (old,),
    )
    for kind, code in (("ca_din", "00000001"), ("it_aic", "000000001")):
        db_conn.execute(
            "INSERT INTO res_product_code (dataset_id, kind, code, code_published, source_id, "
            "product_id) VALUES (%s, %s, %s, %s, 'ca_dpd', 1)",
            (new, kind, code, code),
        )
    with pytest.raises(psycopg.errors.CheckViolation):
        db_conn.execute(
            "INSERT INTO res_product (dataset_id, source_id, product_id, region, routes, "
            "name_only, product_rxcuis) VALUES (%s, 'x', 2, 'XX', '{}', false, '{}')",
            (new,),
        )
    command.downgrade(cfg, "0014")
    try:
        ids = {r[0] for r in db_conn.execute("SELECT id FROM res_dataset").fetchall()}
        assert ids == {old}  # the dataset with Canadian rows is gone, the other is kept
        for statement in (
            "INSERT INTO res_product (dataset_id, source_id, product_id, region, routes, "
            "name_only, product_rxcuis) VALUES (%s, 'ca_dpd', 3, 'CA', '{}', false, '{}')",
            "INSERT INTO res_product_code (dataset_id, kind, code, code_published, source_id, "
            "product_id) VALUES (%s, 'it_aic', '1', '1', 'titck', 1)",
        ):
            with pytest.raises(psycopg.errors.CheckViolation):
                db_conn.execute(statement, (old,))  # pyright: ignore[reportArgumentType]
    finally:
        command.upgrade(cfg, "head")
    db_conn.execute(
        "INSERT INTO res_product_code (dataset_id, kind, code, code_published, source_id, "
        "product_id) VALUES (%s, 'it_aic', '1', '1', 'titck', 1)",
        (old,),
    )
    reset(db_conn)


def test_form_table_accepts_rows_of_the_new_sources() -> None:
    """Validates Req 5.6: the table may name the two sources; today it has no row for them, so
    their group is unknown."""
    table = forms.load()
    assert {CA_DPD, IT_AIFA} <= forms.SOURCES
    assert table.group(CA_DPD, "TABLET", ("ORAL",)) is None
    assert table.group(IT_AIFA, "Compressa", ()) is None
    header = ",".join(forms.HEADER)
    extra = forms.parse(f"{header}\nca_dpd,TABLET,ORAL,oral_solid,,accepted; test\n")
    assert extra.group(CA_DPD, "TABLET", ("ORAL",)) == "oral_solid"
