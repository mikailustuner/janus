"""EU region adapters (drug-resolution tasks 23.1, 23.3, 23.4 import part, 23.5; pure).

P27 French key, P30 Spanish order of trust (key groups), P31 no external call (import graph),
P32 no open database. The database parts are in `test_eu_db_properties.py`.
"""

from __future__ import annotations

import ast
import datetime as dt
from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st

import janus
from janus.regions.base import (
    GS1_PREFIXES,
    KeyGroup,
    ProductKey,
    gs1_prefix_region,
    no_open_database_country,
)
from janus.regions.eu_es.adapter import EsNomenclatorAdapter
from janus.regions.eu_fr.adapter import FrCip13Adapter
from janus.regions.eu_name.adapter import EuNameAdapter
from janus.resolution import service
from janus.resolution.gs1 import Gs1Data, parse_element_string
from tests.resolution_strategies import cip13_of, gtin14s, with_check_digit

TODAY = dt.date(2026, 11, 8)
FR, ES, NAME = FrCip13Adapter(), EsNomenclatorAdapter(), EuNameAdapter()


def _data(gtin14: str, national: str | None = None) -> Gs1Data:
    return Gs1Data(gtin14, None, "absent", False, False, national)


def _cip13s() -> st.SearchStrategy[str]:
    return st.text(alphabet="0123456789", min_size=8, max_size=8).map(
        lambda d: with_check_digit("3400" + d)
    )


# --- P27: the French key ---------------------------------------------------------------------


@given(cip13=_cip13s(), form=st.sampled_from(["gtin14", "bare13", "paren", "fnc1"]))
def test_p27_the_french_key_is_the_last_thirteen_digits(cip13: str, form: str) -> None:
    """Feature: drug-resolution, Property P27. Validates Req 4.1.

    "0" + CIP13 is accepted and gives the key `fr_cip13` = the CIP13, whatever way the code was
    written; the same CIP13 gives the same key.
    """
    content = {
        "gtin14": "0" + cip13,
        "bare13": cip13,
        "paren": f"(01)0{cip13}(17)300131",
        "fnc1": f"]d201{'0' + cip13}17300131",
    }[form]
    data = parse_element_string(content, TODAY)
    assert data.gtin14 == "0" + cip13
    assert FR.accepts_gtin(data.gtin14)
    assert FR.key_groups(data) == [KeyGroup("cip13", (ProductKey("fr_cip13", cip13),))]
    assert FR.structural_hint(data.gtin14)  # CIP13 prefixes 340 are in the French GS1 range


@given(gtin=gtin14s())
def test_p27_no_other_layout_gives_a_french_key(gtin: str) -> None:
    """A GTIN-14 that is not "0" + `3400…` gives no French key and is not accepted."""
    if gtin.startswith("03400"):
        return
    assert not FR.accepts_gtin(gtin)
    assert FR.key_groups(_data(gtin)) == []


def test_p27_a_wrong_check_digit_is_not_a_cip13() -> None:
    good = cip13_of(7)
    bad = good[:-1] + str((int(good[-1]) + 1) % 10)
    assert not FR.accepts_gtin("0" + bad)
    assert FR.key_groups(_data("0" + bad)) == []


# --- P30 (pure part): Spanish key groups in the order of trust --------------------------------


@given(
    gtin=gtin14s(),
    national=st.one_of(
        st.none(), st.text(alphabet="0123456789", min_size=7, max_size=7), st.just("ABC")
    ),
)
def test_p30_spanish_key_groups_are_ordered_and_never_guessed(
    gtin: str, national: str | None
) -> None:
    """Feature: drug-resolution, Property P30 (key groups). Validates Req 4.2.

    Steps in order: `ntin`, `gtin`, `ai_712` (only with a 7-digit AI 712 value: its first six
    digits), `ntin_digits` (only for `0847000` + CN + check digit: digits 8 to 13).
    """
    groups = ES.key_groups(_data(gtin, national if national and national.isdigit() else None))
    steps = [g.matched_by for g in groups]
    assert steps[:2] == ["ntin", "gtin"]
    assert groups[0].keys == (ProductKey("es_ntin", gtin),)
    assert groups[1].keys == (ProductKey("es_gtin", gtin),)
    order = ["ntin", "gtin", "ai_712", "ntin_digits"]
    assert steps == sorted(steps, key=order.index)
    has_national = national is not None and national.isdigit()
    assert ("ai_712" in steps) == has_national
    if has_national:
        assert national is not None
        ai = next(g for g in groups if g.matched_by == "ai_712")
        assert ai.keys == (ProductKey("es_cn", national[:6]),)
    assert ("ntin_digits" in steps) == gtin.startswith("0847000")
    if gtin.startswith("0847000"):
        nd = next(g for g in groups if g.matched_by == "ntin_digits")
        assert nd.keys == (ProductKey("es_cn", gtin[7:13]),)


def test_p30_example_ntin_of_a_spanish_pack() -> None:
    gtin = with_check_digit("0847000605712")
    groups = ES.key_groups(_data(gtin, "6057122"))
    assert [(g.matched_by, g.keys[0].kind, g.keys[0].code) for g in groups] == [
        ("ntin", "es_ntin", gtin),
        ("gtin", "es_gtin", gtin),
        ("ai_712", "es_cn", "605712"),
        ("ntin_digits", "es_cn", "605712"),
    ]


# --- P32: no open database ------------------------------------------------------------------


@given(prefix=st.integers(0, 999), indicator=st.integers(0, 8))
def test_p32_only_the_reviewed_prefixes_have_no_open_database(prefix: int, indicator: int) -> None:
    """Feature: drug-resolution, Property P32. Validates Req 4.3, 6.2.

    Exactly the prefix ranges of the country table with `no_open_database` (Germany 400-440
    today) are recognised; every other prefix is not, and the table is the single source.
    """
    gtin = with_check_digit(f"{indicator}{prefix:03d}123456789")
    expected = any(r.low <= prefix <= r.high and r.no_open_database for r in GS1_PREFIXES)
    assert (no_open_database_country(gtin) == "DE") == expected
    assert NAME.accepts_gtin(gtin) == expected
    assert NAME.structural_hint(gtin) == expected
    assert NAME.key_groups(_data(gtin)) == []
    if expected:
        assert gs1_prefix_region(gtin) == "DE"


def test_p32_the_table_names_its_sources() -> None:
    for row in GS1_PREFIXES:
        assert row.source and row.checked and row.low <= row.high
    assert {(r.country, r.no_open_database) for r in GS1_PREFIXES} == {
        ("FR", False),
        ("DE", True),
        ("ES", False),
    }


# --- dispatch with the registered adapters (P21, pure part) ----------------------------------


def test_dispatch_french_and_german_and_spanish_packs() -> None:
    fr = "0" + cip13_of(3)
    de = with_check_digit("0401123456789")  # GS1 prefix 401
    es = with_check_digit("0841123456789")  # GS1 prefix 841

    def sources_of(gtin: str) -> list[tuple[str, str | None]]:
        return [
            (a.region, a.source_id) for a in service.choose_adapters(service.ADAPTERS, gtin, None)
        ]

    # A French pack: the French adapter first (hinted), then the Spanish one and Türkiye's
    assert sources_of(fr)[0] == ("EU", "eu_fr_bdpm")
    assert ("TR", "titck") in sources_of(fr)
    # A German pack: the no-database adapter is hinted and comes first; no German source exists
    first = sources_of(de)[0]
    assert first == ("EU", None)
    # A Spanish pack: the Spanish adapter is hinted
    assert sources_of(es)[0] == ("EU", "eu_es_cima")
    # With an override only that region's adapters are asked, all three for the EU
    eu = service.choose_adapters(service.ADAPTERS, fr, "EU")
    assert [a.country for a in eu] == ["FR", "ES", None]


# --- P31 (import part): the request path cannot call out ------------------------------------

NETWORK_MODULES = frozenset(
    {"socket", "ssl", "http", "urllib", "urllib3", "requests", "httpx", "httpx2", "aiohttp",
     "websockets", "ftplib", "smtplib", "xmlrpc"}
)  # fmt: skip


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            out.add(node.module.split(".")[0])
    return out


def test_p31_no_module_of_the_request_path_imports_a_network_library() -> None:
    """Feature: drug-resolution, Property P31 (import graph). Validates Req 4.2, 7.1.

    Spanish codes resolve from the Nomenclátor in PostgreSQL (DP27): nothing under `resolution`
    or `regions` imports an HTTP or socket library, so no request can call the CIMA API.
    """
    root = Path(janus.__file__).parent
    offenders: dict[str, set[str]] = {}
    for package in ("resolution", "regions"):
        for path in (root / package).rglob("*.py"):
            bad = _imports(path) & NETWORK_MODULES
            if bad:
                offenders[str(path.relative_to(root))] = bad
    assert offenders == {}
