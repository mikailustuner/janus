"""Fixtures the web tests read (medication-passport tasks 9 and 9.5).

- `schema-literals.json`: every closed set of `janus.passport.schemas` (statuses, results, reasons,
  sources, attributions, notices, form groups, regions, countries) and the request limits, so the
  TypeScript types and the `Passport` message keys are checked against the server (P16).
- `entry-cases.json`: 500 generated typed entries with the code `entry_code` gives (P21); the web
  test checks that `strengthFromEntry` gives the same code for each.

Both files are committed. This test fails when a file is out of date; run it with
`JANUS_WRITE_WEB_FIXTURES=1` to regenerate them. No health data: amounts and units only.
"""

from __future__ import annotations

import json
import os
import random
import types
import typing
from pathlib import Path
from typing import Any, Literal, get_args, get_origin

from janus.memory import messages
from janus.passport import schemas
from janus.passport.forms import COUNTABLE_GROUPS, GROUPS, NOT_COMPARED_GROUPS
from janus.passport.strength import ENTRY_BASES, ENTRY_UNITS, entry_code

FIXTURES = Path(__file__).resolve().parents[2] / "web" / "src" / "passport" / "fixtures"
WRITE = os.environ.get("JANUS_WRITE_WEB_FIXTURES") == "1"


def literals(annotation: Any) -> list[str]:
    """The string values of a `Literal[...]` annotation, `| None` and aliases included."""
    origin = get_origin(annotation)
    if origin is Literal:
        return [v for v in get_args(annotation) if isinstance(v, str)]
    if origin in (typing.Union, types.UnionType):
        return [v for arg in get_args(annotation) for v in literals(arg)]
    return []


def field(model: type[schemas.BaseModel], name: str) -> list[str]:
    return literals(model.model_fields[name].annotation)


def schema_literals() -> dict[str, Any]:
    return {
        "status": literals(schemas.Status),
        "result": literals(schemas.Result),
        "cmp_reason": literals(schemas.CmpReason),
        "notice": literals(schemas.Notice),
        "source_id": literals(schemas.SourceId),
        "form_group": literals(schemas.FormGroup),
        "countable_groups": sorted(COUNTABLE_GROUPS),
        "not_compared_groups": sorted(NOT_COMPARED_GROUPS),
        "region": field(schemas.SourceOut, "region"),
        "country": field(schemas.SourceOut, "country"),
        "source_status": field(schemas.SourceOut, "status"),
        "unavailable_reason": field(schemas.SourceOut, "reason"),
        "attribution": field(schemas.SourceOut, "attribution"),
        "unit": field(schemas.StrengthIn, "unit"),
        "basis": field(schemas.StrengthIn, "basis"),
        "key_pattern": schemas.KEY,
        "amount_pattern": schemas.AMOUNT,
        "max_items": schemas.MAX_ITEMS,
        "max_ingredients": schemas.MAX_INGREDIENTS,
        "max_keys": schemas.MAX_KEYS,
        "disclaimer": messages.DISCLAIMER,
    }


def entry_amount(rng: random.Random) -> str:
    shape = rng.randrange(10)
    whole = str(rng.choice([0, 1, 5, 40, 250, 1000, rng.randrange(10**9), 999_999_999]))
    if shape <= 3:
        return whole
    if shape <= 6:
        places = rng.randint(1, 7)  # 7 decimals is out of the grammar
        frac = "".join(rng.choice("0123456789") for _ in range(places))
        return f"{whole}{rng.choice('.,')}{frac}"
    return rng.choice(
        ["", " ", " 40 ", "0", "0.0", "0,000001", "1e3", "-5", "1.", ".5", "1 000", "10000000000",
         "0.0000001", "١٢", "40mg", "4,5,6", "1,000", "1.000", "0,125", "12,500", "2.25"]
    )  # fmt: skip


def entry_cases() -> list[dict[str, Any]]:
    rng = random.Random(20261108)  # noqa: S311 (fixed seed: the file is reproducible)
    units = [*ENTRY_UNITS, "mcg", "µg", "kg", ""]
    bases = [*ENTRY_BASES, "g", "tablet"]
    cases: list[dict[str, Any]] = []
    for _ in range(500):
        amount, unit, basis = entry_amount(rng), rng.choice(units), rng.choice(bases)
        if rng.random() < 0.8:  # mostly valid units and bases, so most cases give a code
            unit, basis = rng.choice(list(ENTRY_UNITS)), rng.choice(list(ENTRY_BASES))
        code = entry_code(amount, unit, basis)
        cases.append(
            {
                "amount": amount,
                "unit": unit,
                "basis": basis,
                "code": None
                if code is None
                else {"amount": code.amount, "unit": code.unit, "basis": code.basis},
            }
        )
    return cases


def check(name: str, value: Any) -> None:
    path = FIXTURES / name
    text = json.dumps(value, ensure_ascii=False, indent=1) + "\n"
    if WRITE:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    assert path.read_text(encoding="utf-8") == text, (
        f"{name} is out of date: run this test with JANUS_WRITE_WEB_FIXTURES=1"
    )


def test_schema_literals_fixture() -> None:
    """Feature: medication-passport, Property P16 (code lists) — Validates: Req 8.1, 8.3, 10.2."""
    value = schema_literals()
    assert value["form_group"] == list(GROUPS)
    assert all(value[k] for k in ("status", "result", "cmp_reason", "attribution", "country"))
    check("schema-literals.json", value)


def test_entry_cases_fixture() -> None:
    """Feature: medication-passport, Property P21 (Python side) — Validates: Req 6.7."""
    cases = entry_cases()
    coded = sum(c["code"] is not None for c in cases)
    assert 200 <= coded < 500  # both outcomes are well represented
    check("entry-cases.json", cases)


def test_entry_code_examples() -> None:
    """Typed strengths convert exactly as the published ones do (design §5.1)."""
    assert entry_code("40", "mg", "unit") == entry_code("0,04", "g", "unit")
    code = entry_code("0.5", "mg", "unit")
    assert code is not None and (code.amount, code.unit, code.basis) == ("500", "ug", "unit")
    code = entry_code("250", "mg", "mL")
    assert code is not None and code.amount == "250000" and code.basis == "mL"
    code = entry_code("1000", "IU", "unit")
    assert code is not None and (code.amount, code.unit) == ("1000", "IU")
    code = entry_code("0,125", "mg", "unit")
    assert code is not None and code.amount == "125"
    for amount in ("0", "0,0", "", "1e3", "-5", "1.", "0.0000001", "1 000", "1,000", "1.000"):
        assert entry_code(amount, "mg", "unit") is None, amount
    assert entry_code("100", "g", "unit") is not None
    assert entry_code("1000", "g", "unit") is None  # more than nine integer digits in ug
    assert entry_code("40", "mcg", "unit") is None
    assert entry_code("40", "mg", "g") is None
