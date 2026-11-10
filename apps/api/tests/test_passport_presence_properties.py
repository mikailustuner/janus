"""Presence evaluation (medication-passport task 6, design §4.2, §5.3).

Feature: medication-passport, Properties P7 (presence equals a brute-force model over the raw rows,
database), P3 server part (no `matched` with an unknown side; `differs` only when all comparable),
P8 (homeopathic parity with `/resolve/products`; SQL and Python patterns agree), P9 (comparison
counts and result function), P10 (order, repetition and split invariance). Sentinel keys only.
"""

from __future__ import annotations

import datetime as dt
import random
import re
import unicodedata
from collections.abc import Sequence
from typing import Any

import psycopg
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from janus.passport import forms, repository, service
from janus.passport.forms import GROUPS, NOT_COMPARED_GROUPS
from janus.passport.presence import (
    SOURCE_ORDER,
    ItemQuery,
    Signature,
    cmp,
    compare,
    evaluate,
    is_homeopathic,
    signature,
)
from janus.passport.schemas import FormGroup, ItemIn, PresenceIn
from janus.passport.strength import StrengthCode, strength_code
from janus.resolution import service as resolution_service
from janus.resolution.model import HOMEOPATHIC_UNIT
from janus.resolution.prepare_eu import is_homeopathic_name
from tests.conftest import DB_EXAMPLES
from tests.passport_db import (
    KEYS,
    PRODUCT_SOURCES,
    REGION,
    UNKNOWN_KEY,
    Product,
    datasets,
    install,
    product_ids,
    products,
)
from tests.resolution_db import reset

TODAY = dt.date(2026, 11, 8)
TABLE = forms.load()
CODES = [
    StrengthCode("5000", "ug", "unit"),
    StrengthCode("10000", "ug", "unit"),
    StrengthCode("50000", "ug", "mL"),
]


# --- strategies ------------------------------------------------------------------------------
def strength_in(code: StrengthCode | None) -> dict[str, str] | None:
    return None if code is None else {"amount": code.amount, "unit": code.unit, "basis": code.basis}


@st.composite
def items_in(
    draw: st.DrawFn, keys: Sequence[str] = (*KEYS[:3], *KEYS[:3], KEYS[3], UNKNOWN_KEY)
) -> ItemIn:
    ks = list(dict.fromkeys(draw(st.lists(st.sampled_from(keys), min_size=1, max_size=2))))
    ings = [
        {
            "key": k,
            "strength": strength_in(draw(st.sampled_from([None, CODES[0], CODES[0], *CODES]))),
        }
        for k in ks
    ]
    form = draw(
        st.sampled_from(
            [
                None,
                "oral_solid",
                "oral_solid",
                "oral_solid",
                "oral_liquid",
                "ophthalmic",
                "other",
                "oral_solid_prolonged_release",
            ]
        )
    )
    return ItemIn.model_validate({"ingredients": ings, "dose_form": form})


@st.composite
def signatures(draw: st.DrawFn) -> Signature:
    keys = tuple(sorted(draw(st.lists(st.sampled_from(KEYS[:4]), min_size=1, max_size=3))))
    return Signature(
        source_id=draw(st.sampled_from(PRODUCT_SOURCES)),
        keys=keys,
        strengths=tuple(draw(st.sampled_from([None, *CODES])) for _ in keys),
        complete=draw(st.booleans()),
        homeopathic=draw(st.booleans()),
        form_group=draw(st.sampled_from([None, *GROUPS])),
        products=draw(st.integers(1, 5)),
    )


# --- brute-force model over raw rows -------------------------------------------------------------
def model(items: Sequence[ItemIn], data: Sequence[Product], loaded: Sequence[str]) -> list[Any]:
    rows = product_ids(data, loaded)
    known = {i.qid for _, p in rows for i in p.ingredients if i.status == "mapped"}
    out: list[Any] = []
    for n, item in enumerate(items):
        q = ItemQuery.of(item)
        answers: list[dict[str, Any]] = []
        for idx, (sid, _, _) in enumerate(SOURCE_ORDER):
            if sid is None or sid not in loaded:
                answers.append(
                    {
                        "source": idx,
                        "status": "source_unavailable",
                        "products": 0,
                        "with_other_ingredients": 0,
                        "keys_found": [],
                        "homeopathic_left_out": 0,
                        "comparison": None,
                    }
                )
                continue
            exact: list[tuple[Product, str | None]] = []
            with_other = left_out = 0
            found: set[str] = set()
            for _, p in rows:
                if p.source_id != sid:
                    continue
                mapped = [i for i in p.ingredients if i.status == "mapped"]
                keys = {i.qid for i in mapped if i.qid}
                hom = is_homeopathic(
                    [i.strength for i in p.ingredients],
                    [i.name for i in p.ingredients],
                    REGION[sid],
                )
                if hom:
                    left_out += 1 if keys & q.keys else 0
                    continue
                found |= keys & q.keys
                complete = len(mapped) == len(p.ingredients)
                if complete and frozenset(keys) == q.keys:
                    exact.append((p, TABLE.group(sid, p.dosage_form, p.routes)))
                elif q.keys <= keys:
                    with_other += 1
            comparison = None
            if exact:
                total = len(exact)
                s_known = all(q.strengths[k] is not None for k in q.keys)
                f_known = q.form_group is not None and q.form_group not in NOT_COMPARED_GROUPS
                s_c = s_e = f_c = f_e = b_c = b_e = 0
                for p, g in exact:
                    mapped = sorted(
                        (i for i in p.ingredients if i.status == "mapped"),
                        key=lambda i: i.qid or "",
                    )
                    codes = [strength_code(sid, i.strength, g) for i in mapped]
                    keys_list = [i.qid for i in mapped]
                    sc = s_known and len(set(keys_list)) == len(keys_list) and None not in codes
                    se = sc and all(
                        q.strengths[k] == c for k, c in zip(keys_list, codes, strict=True) if k
                    )
                    fc = f_known and g is not None and g not in NOT_COMPARED_GROUPS
                    fe = fc and g == q.form_group
                    s_c, s_e, f_c, f_e = s_c + sc, s_e + se, f_c + fc, f_e + fe
                    b_c, b_e = b_c + (sc and fc), b_e + (se and fe)
                comparison = {
                    "strength": cmp(total, s_c, s_e, s_known).model_dump(),
                    "dose_form": cmp(total, f_c, f_e, f_known).model_dump(),
                    "strength_and_dose_form": cmp(
                        total, b_c, b_e, s_known and f_known
                    ).model_dump(),
                }
            status = "present" if exact else ("not_present" if found else "not_in_source")
            answers.append(
                {
                    "source": idx,
                    "status": status,
                    "products": len(exact),
                    "with_other_ingredients": with_other,
                    "keys_found": sorted(found),
                    "homeopathic_left_out": left_out,
                    "comparison": comparison,
                }
            )
        out.append(
            {
                "item": n,
                "keys": sorted(q.keys),
                "unknown_keys": sorted(q.keys - known),
                "answers": answers,
            }
        )
    return out


@pytest.mark.db
@settings(max_examples=DB_EXAMPLES)
@given(
    data=datasets(),
    items=st.lists(items_in(), min_size=1, max_size=6),
    loaded=st.lists(st.sampled_from(PRODUCT_SOURCES), min_size=0, max_size=4, unique=True),
)
def test_p7_presence_equals_a_brute_force_model(
    db_conn: psycopg.Connection, data: list[Product], items: list[ItemIn], loaded: list[str]
) -> None:
    """Feature: medication-passport, Property P7. Validates Req 2.4, 2.6, 2.7, 6.2."""
    install(db_conn, data, loaded)
    body = PresenceIn(items=items)
    with db_conn.transaction():
        out = service.presence(db_conn, body, TABLE, TODAY)
    assert [i.model_dump() for i in out.items] == model(items, data, loaded)
    reset(db_conn)


# --- P3 and P9 (pure) ------------------------------------------------------------------------
@given(item=items_in(KEYS[:4]), sigs=st.lists(signatures(), min_size=1, max_size=8))
def test_p3_p9_comparison(item: ItemIn, sigs: list[Signature]) -> None:
    """Feature: medication-passport, Properties P3 and P9. Validates Req 2.2, 6.1, 6.2."""
    q = ItemQuery.of(item)
    exact = [s for s in sigs if s.complete and frozenset(s.keys) == q.keys and not s.homeopathic]
    if not exact:
        return
    total = sum(s.products for s in exact)
    c = compare(q, exact)
    item_strength = all(q.strengths[k] is not None for k in q.keys)
    item_form = q.form_group is not None and q.form_group not in NOT_COMPARED_GROUPS
    for field, known in (
        (c.strength, item_strength),
        (c.dose_form, item_form),
        (c.strength_and_dose_form, item_strength and item_form),
    ):
        assert field.equal <= field.comparable <= total  # P9
        if not known:  # P3: an unknown item side never gives a result but could_not_compare
            assert (field.result, field.reason) == ("could_not_compare", "not_known_for_item")
        assert field == cmp(total, field.comparable, field.equal, known)
        if field.result == "matched":
            assert field.equal > 0
        if field.result == "differs":
            assert field.comparable == total and field.equal == 0
    # P3: matched only if at least one counted product has both values known and equal
    if c.strength.result == "matched":
        assert any(
            None not in s.strengths
            and len(set(s.keys)) == len(s.keys)
            and all(q.strengths[k] == v for k, v in zip(s.keys, s.strengths, strict=True))
            for s in exact
        )
    if c.dose_form.result == "matched":
        assert any(s.form_group == q.form_group for s in exact)
    if c.strength_and_dose_form.result == "matched":  # one product equal on both
        assert c.strength.result == "matched" and c.dose_form.result == "matched"


def test_p9_result_function_examples() -> None:
    """Feature: medication-passport, Property P9. Validates Req 6.2."""
    assert cmp(3, 3, 1, True).result == "matched"
    assert cmp(3, 3, 0, True).result == "differs"
    assert (cmp(3, 0, 0, True).result, cmp(3, 0, 0, True).reason) == (
        "could_not_compare",
        "not_known_in_source",
    )
    assert cmp(3, 2, 0, True).reason == "not_all_comparable"
    assert cmp(3, 2, 0, False).reason == "not_known_for_item"


# --- P10 (pure) --------------------------------------------------------------------------------
@given(
    items=st.lists(items_in(), min_size=1, max_size=6),
    sigs=st.lists(signatures(), max_size=10),
    seed=st.integers(0, 1000),
)
def test_p10_invariance(items: list[ItemIn], sigs: list[Signature], seed: int) -> None:
    """Feature: medication-passport, Property P10. Validates Req 4.4."""
    loaded, known = set(PRODUCT_SOURCES), set(KEYS)
    base = evaluate(items, sigs, loaded, known)
    rng = random.Random(seed)  # noqa: S311 (test order, not a secret)
    order = list(range(len(items)))
    rng.shuffle(order)
    shuffled = [
        ItemIn.model_validate(
            {
                **items[i].model_dump(),
                "ingredients": rng.sample(
                    items[i].model_dump()["ingredients"], len(items[i].ingredients)
                ),
            }
        )
        for i in order
    ]
    other = evaluate(shuffled, rng.sample(sigs, len(sigs)), loaded, known)
    for j, i in enumerate(order):
        assert other[j].model_dump(exclude={"item"}) == base[i].model_dump(exclude={"item"})
    twice = evaluate([*items, *items], sigs, loaded, known)
    assert [t.model_dump(exclude={"item"}) for t in twice[len(items) :]] == [
        b.model_dump(exclude={"item"}) for b in base
    ]
    cut = len(items) // 2
    split = evaluate(items[:cut], sigs, loaded, known) + evaluate(items[cut:], sigs, loaded, known)
    assert [s.model_dump(exclude={"item"}) for s in split] == [
        b.model_dump(exclude={"item"}) for b in base
    ]
    assert all(b.keys == sorted(b.keys) for b in base)


# --- P8 ------------------------------------------------------------------------------------------
UNIT_TEXT = st.sampled_from(
    [
        "[hp_X]",
        "[HP_C]",
        "[hp_m]",
        "[kp_C]",
        "[hp_]",
        "[ hp_X]",
        "[iU]",
        "mg",
        "[hp_X",
        "hp_X]",
        "[hpX]",
    ]
)
NAMES = st.sampled_from(
    [
        "pour préparations homéopathiques",
        "POUR PRÉPARATIONS HOMÉOPATHIQUES",
        unicodedata.normalize("NFD", "pour préparations homéopathiques"),
        "pour preparations homeopathiques",
        "préparations homéopathique",
        "TESTNAME",
    ]
)


@pytest.mark.db
@settings(max_examples=DB_EXAMPLES)
@given(
    strength=st.tuples(st.integers(1, 30), UNIT_TEXT, st.sampled_from(["/mL", "/1", ""])),
    prefix=st.sampled_from(["", "TESTNAME "]),
    name=NAMES,
)
def test_p8_sql_and_python_patterns_agree(
    db_conn: psycopg.Connection, strength: tuple[int, str, str], prefix: str, name: str
) -> None:
    """Feature: medication-passport, Property P8. Validates Req 2.6: the SQL pattern equals
    `HOMEOPATHIC_UNIT`; the SQL name pre-filter keeps every name `is_homeopathic_name` accepts."""
    text = f"{strength[0]} {strength[1]}{strength[2]}"
    row = db_conn.execute(
        r"SELECT %s ~* '\[(hp|kp)_[a-z]+\]', %s ILIKE '%%pathiques%%'", (text, prefix + name)
    ).fetchone()
    assert row is not None
    assert bool(row[0]) == (HOMEOPATHIC_UNIT.search(text) is not None)
    assert re.escape(r"\[(hp|kp)_[a-z]+\]") in re.escape(repository.PRESENCE_SQL)
    if is_homeopathic_name(prefix + name):
        assert row[1]


@pytest.mark.db
@settings(max_examples=DB_EXAMPLES)
@given(p=products())
def test_p8_homeopathic_parity_with_resolution(db_conn: psycopg.Connection, p: Product) -> None:
    """Feature: medication-passport, Property P8. Validates Req 2.6, 1.5: the signature's
    `homeopathic` equals `ProductCandidate.homeopathic` of `/resolve/products`."""
    keys = sorted({i.qid for i in p.ingredients if i.status == "mapped" and i.qid})
    if not keys:
        return
    install(db_conn, [p])
    with db_conn.transaction():
        res = resolution_service.resolve_products(
            db_conn, [f"{REGION[p.source_id]}:{p.source_id}:1"], TODAY
        )
        dataset = res.dataset_version
        rows = repository.presence_rows(db_conn, dataset, keys)
    assert len(rows) == 1
    if p.source_id == "ca_dpd":
        assert res.candidates == []  # Canadian products are a target only, never a candidate
        reset(db_conn)
        return
    candidate = res.candidates[0]
    assert candidate.kind == "product"
    assert signature(rows[0], TABLE).homeopathic == candidate.homeopathic
    reset(db_conn)


def test_form_group_literal_matches_the_closed_set() -> None:
    """The request's `dose_form` literal is the table's closed group set (Req 5.1)."""
    assert tuple(FormGroup.__args__) == GROUPS  # type: ignore[attr-defined]
