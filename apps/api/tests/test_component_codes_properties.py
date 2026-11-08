"""Reviewed (key, combination code) pairs: imipenem (drug-resolution Req 14, DP43; tasks 27.1-27.2).

P48: the pair reaches `rule_input` only for its key; no other ingredient and no other combination
code gets the treatment; the loader refuses a bad file. Synthetic rows, plus the committed files.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any

import psycopg
import pytest
from hypothesis import given
from hypothesis import strategies as st

from janus.cascades.engine import EngineInputError, evaluate
from janus.cascades.model import EngineIngredient, EngineItem
from janus.db.pool import Database
from janus.resolution import service
from janus.resolution.atc import CombinationCheck, CombinationRules, RouteMap, RulesFileError
from janus.resolution.component_codes import (
    COMPONENT_HEADER,
    ComponentCode,
    parse_component_codes,
    validate_against_dataset,
)
from janus.resolution.load import (
    COMPONENT_FILE,
    CURATED_FILE,
    LoadError,
    load,
    parse_curated,
    read_component_codes,
    read_curated,
)
from janus.resolution.prepare import prepare_dataset
from tests.resolution_db import inputs, reset
from tests.resolution_strategies import (
    ROUTES,
    RULES,
    barcode13,
    sources,
    titck_row,
    us_row,
    wikidata_row,
)

TODAY = dt.date(2026, 11, 8)
URL = "https://atcddd.fhi.no/atc_ddd_index/?code=J01DH&showdescription=no"
GOOD = ComponentCode("J2", "J01DH51", "WHOCC index", URL, "2026-11-08", "owner decision")
CURATED_HEADER = "key,label_en,label_tr,label_de,label_fr,label_es,atc_codes,added_on,note\n"
J2_ROW = "J2,imipenem,imipenem,Imipenem,imipénème,imipenem,,2026-11-08,n\n"


def j2_curated(code: str = "") -> list[dict[str, Any]]:
    text = CURATED_HEADER + J2_ROW.replace(",,2026-11-08", f",{code},2026-11-08")
    return list(parse_curated(text, frozenset({"J2"})).rows)


def csv_text(*rows: dict[str, str]) -> str:
    out = io.StringIO()
    w = csv.DictWriter(out, fieldnames=COMPONENT_HEADER, lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return out.getvalue()


def good_row(**kw: str) -> dict[str, str]:
    row = {
        "key": "J2",
        "code": "J01DH51",
        "evidence": "WHOCC index",
        "whocc_url": URL,
        "whocc_date": "2026-11-08",
        "note": "owner decision",
    }
    return {**row, **kw}


# --- the file ----------------------------------------------------------------------------------


def test_the_committed_file_is_the_one_reviewed_pair() -> None:
    (c,) = read_component_codes()
    assert (c.key, c.code, c.whocc_date) == ("J2", "J01DH51", "2026-11-08")
    assert c.whocc_url == URL and "Refers to imipenem" in c.evidence
    assert "proxy" in c.note and "owner decision" in c.note.lower()
    assert COMPONENT_FILE.name == "component_codes.csv"
    cur = read_curated(CURATED_FILE, frozenset({"J2"}))
    assert [r["qid"] for r in cur.rows] == ["J1", "J2"]


@pytest.mark.parametrize(
    "bad",
    [
        good_row(key="Q42"),  # not a Janus key
        good_row(key="J02"),  # leading zero
        good_row(code="J01DH"),  # not seven characters
        good_row(code="j01dh51"),
        good_row(evidence=""),
        good_row(note="  "),
        good_row(whocc_url=""),
        good_row(whocc_url="https://example.org/atc"),  # not the WHOCC index
        good_row(whocc_date=""),
        good_row(whocc_date="08.11.2026"),
    ],
)
def test_p48_a_bad_row_is_refused_and_the_message_names_the_row_only(bad: dict[str, str]) -> None:
    """Feature: drug-resolution, Property P48 (file). Validates Req 14.2."""
    with pytest.raises(RulesFileError) as err:
        parse_component_codes(csv_text(bad))
    assert "row 2" in str(err.value) and "owner decision" not in str(err.value)


def test_p48_a_repeated_pair_and_a_bad_header_are_refused() -> None:
    with pytest.raises(RulesFileError, match="repeated pair"):
        parse_component_codes(csv_text(good_row(), good_row(note="again")))
    with pytest.raises(RulesFileError, match="header"):
        parse_component_codes(csv_text(good_row()).replace("whocc_date", "date"))
    assert len(parse_component_codes(csv_text(good_row(), good_row(key="J3")))) == 2
    assert parse_component_codes(",".join(COMPONENT_HEADER) + "\n") == ()


def test_p48_the_loader_refuses_a_code_that_is_no_combination_code_or_an_unknown_key() -> None:
    """The dataset decides what a combination code is: a pair for an ordinary code needs no
    exception, and a key outside the curated file is an error."""
    check = CombinationCheck(RULES)
    validate_against_dataset([GOOD], check, {"J2"})
    with pytest.raises(RulesFileError, match="not a combination code"):
        validate_against_dataset([replace(GOOD, code="C08CA01")], check, {"J2"})
    with pytest.raises(RulesFileError, match="not a curated Janus key"):
        validate_against_dataset([GOOD], check, {"J1"})
    with pytest.raises(LoadError):  # a curated key with no code and no pair is refused
        parse_curated(CURATED_HEADER + J2_ROW)


# --- P48: the pair reaches rule_input for its key only ---------------------------------------

CARBAPENEMS = [
    wikidata_row("Q500", ["J01DH02"], {"en": "meropenem", "tr": "meropenem"}),
    wikidata_row("Q501", ["J01DH51"], {"en": "imipenem and cilastatin"}),  # a combination item
]


def imipenem_dataset(extra_tr: list[Any] | None = None) -> Any:
    tr = [
        titck_row(
            barcode13(1),
            "TIENAM",
            ["imipenem monohidrat", "silastatin sodyum"],
            "J01DH51",
        ),
        titck_row(barcode13(2), "MERONEM", ["meropenem"], "J01DH02"),
        titck_row(barcode13(3), "IMIPENEM ALONE", ["imipenem"], None),
        *(extra_tr or []),
    ]
    return prepare_dataset(
        tr,
        [us_row("12345-001", ["12345-001-01"], ["imipenem", "cilastatin sodium"], ["INTRAVENOUS"])],
        CARBAPENEMS,
        CombinationRules.load(),
        RouteMap.load(),
        curated_rows=j2_curated(),
        component_codes=[GOOD],
    )


def test_row_58_example_imipenem_is_a_carbapenem_and_cilastatin_is_not() -> None:
    """Feature: drug-resolution, Property P48 (example). Validates Req 14.2, 14.3."""
    ds = imipenem_dataset()
    by_name = {p.product_name: p for p in ds.products}
    tienam, meronem, alone = by_name["TIENAM"], by_name["MERONEM"], by_name["IMIPENEM ALONE"]
    us = next(p for p in ds.products if p.region == "US")
    imipenem, cilastatin = tienam.ingredients
    assert (imipenem.status, imipenem.qid, imipenem.atc_selection) == (
        "mapped",
        "J2",
        "component_code",
    )
    assert imipenem.rule_input() == ("J01DH51",)
    assert [(a.code, a.source_id, a.product_ref) for a in imipenem.atc] == [
        ("J01DH51", "janus_curated", None)
    ]
    assert cilastatin.status == "unmapped" and cilastatin.rule_input() == ()
    assert cilastatin.reason == "no_ingredient_key"
    assert alone.ingredients[0].rule_input() == ("J01DH51",)
    assert [i.rule_input() for i in meronem.ingredients] == [("J01DH02",)]
    assert us.ingredients[0].qid == "J2" and us.ingredients[1].rule_input() == ()
    # J01DH51 stays a combination code everywhere else
    assert ds.combination_audit["J01DH51"] == "numbering"
    assert ds.ingredients["J2"].ingredient_atc[0].code == "J01DH51"
    assert ds.component_codes == (GOOD,)


@given(
    src=sources(),
    code=st.sampled_from(["J01DH51", "C09BB03", "A10BD05", "J01CA51", "N01AA20", "C08CA51"]),
    imipenem_rows=st.integers(0, 3),
)
def test_p48_no_other_ingredient_and_no_other_combination_code_gets_the_treatment(
    src: tuple[list[Any], list[Any], list[Any]], code: str, imipenem_rows: int
) -> None:
    """Feature: drug-resolution, Property P48. Validates Req 14.2, 14.3.

    With one reviewed pair (J2, code), a combination code reaches `rule_input` only as that pair:
    for key J2 and that code. Every other ingredient, and every other combination code, is held
    to the old rule (no combination code), on any generated sources.
    """
    tr, us, wd = src
    pair = ComponentCode("J2", code, "e", URL, "2026-11-08", "n")
    extra = [
        titck_row(barcode13(10 + i), f"IMI {i}", ["imipenem"], code) for i in range(imipenem_rows)
    ]
    ds = prepare_dataset(
        [*tr, *extra],
        us,
        wd,
        RULES,
        ROUTES,
        curated_rows=j2_curated(),
        component_codes=[pair],
    )
    combo = set(ds.combination_audit)
    check = CombinationCheck(RULES)
    for p in ds.products:
        for ing in p.ingredients:
            for c in ing.rule_input():
                if c in combo or check.is_combination(c):
                    assert (ing.qid, c) == ("J2", code), (ing.qid, c)
            if ing.atc_selection == "component_code":
                assert ing.qid == "J2" and [a.code for a in ing.atc] == [code]
    for p in ds.products[: len(tr) + imipenem_rows]:
        for ing in p.ingredients:
            if ing.qid == "J2":
                assert ing.status == "mapped"
    # the engine's input guard
    for qid in ("J2", "Q1"):
        items = [EngineItem(0, 2024 * 12, (EngineIngredient(qid, frozenset({code}), True),))]
        if qid == "J2":
            evaluate_guard(items, {code}, {("J2", code)})
        else:
            with pytest.raises(EngineInputError):
                evaluate_guard(items, {code}, {("J2", code)})
    with pytest.raises(EngineInputError):  # without the pair even J2 is refused
        evaluate_guard(
            [EngineItem(0, 2024 * 12, (EngineIngredient("J2", frozenset({code}), True),))],
            {code},
            set(),
        )


def evaluate_guard(
    items: list[EngineItem], combination: set[str], pairs: set[tuple[str, str]]
) -> None:
    """Run only the engine's input check (a rule base is not needed to see it refuse)."""
    from janus.cascades.engine import _validate  # pyright: ignore[reportPrivateUsage]

    _validate(items, combination, pairs)


def test_the_engine_signature_carries_the_pairs() -> None:
    import inspect

    assert "component_pairs" in inspect.signature(evaluate).parameters


# --- through the database and the service ----------------------------------------------------


@pytest.fixture(scope="module")
def database(db_url: str) -> Iterator[Database]:
    db = Database(db_url)
    db.open()
    yield db
    db.close()


@pytest.mark.db
def test_p48_through_the_database(database: Database, db_conn: psycopg.Connection) -> None:
    """The pair is stored with its evidence, served as `component_code` cited to `janus_curated`,
    and handed to the engine as a (key, code) pair; other combination codes are not."""
    reset(db_conn)
    base = inputs(
        [
            titck_row(barcode13(1), "TIENAM", ["imipenem", "silastatin sodyum"], "J01DH51"),
            titck_row(barcode13(2), "KOMBI", ["meropenem", "betorol"], "J01DH51"),
        ],
        [],
        [*CARBAPENEMS, wikidata_row("Q3", ["C07AB02"], {"en": "betorol"})],
    )
    inp = replace(
        base,
        curated=parse_curated(CURATED_HEADER + J2_ROW, frozenset({"J2"})),
        component_codes=(GOOD,),
    )
    ds = load(database, inp).dataset_version
    row = db_conn.execute(
        "SELECT key, code, whocc_url, whocc_date FROM res_component_code WHERE dataset_id = %s",
        (ds,),
    ).fetchone()
    assert row == ("J2", "J01DH51", URL, "2026-11-08")
    res = service_scan(database, "0" + barcode13(1))
    (c,) = [x for x in res.candidates if x.region == "TR"]
    imipenem, cilastatin = c.ingredients
    assert (imipenem.atc_selection, [a.code for a in imipenem.atc_codes]) == (
        "component_code",
        ["J01DH51"],
    )
    assert imipenem.atc_codes[0].source.source_id == "janus_curated"
    assert cilastatin.atc_codes == [] and cilastatin.status == "unmapped"
    kombi = service_scan(database, "0" + barcode13(2)).candidates[0]
    assert all("J01DH51" not in [a.code for a in i.atc_codes] for i in kombi.ingredients)
    with database.read_only_tx() as conn:
        found = service.rule_inputs(conn, [c.candidate_id], ["J2"])
        by_name = service.search(conn, "imipenem", None, 5, TODAY)
    assert found.component_pairs == frozenset({("J2", "J01DH51")})
    assert "J01DH51" in found.combination_codes
    assert [a.code for a in found.ingredients["J2"].atc_codes] == ["J01DH51"]
    assert any(
        x.kind == "ingredient" and x.ingredient_key.qid == "J2"  # pyright: ignore[reportAttributeAccessIssue]
        for x in by_name.candidates
    )


def service_scan(database: Database, content: str) -> Any:
    with database.read_only_tx() as conn:
        return service.resolve_scan(conn, content, None, TODAY)


def test_the_loader_refuses_a_pair_for_an_unknown_key(tmp_path: Path) -> None:
    """`gather` checks that every key of the pair file is a curated Janus key."""
    from janus.resolution import load as load_module

    path = tmp_path / "component_codes.csv"
    path.write_text(csv_text(good_row(key="J9")), encoding="utf-8")
    pairs = load_module.read_component_codes(path)
    with pytest.raises(LoadError, match=r"ingredient-level"):
        load_module.read_curated(CURATED_FILE, frozenset({c.key for c in pairs}) - {"J2"})
    bad = tmp_path / "bad.csv"
    bad.write_text(csv_text(good_row(whocc_date="")), encoding="utf-8")
    with pytest.raises(LoadError, match="row 2"):
        load_module.read_component_codes(bad)
