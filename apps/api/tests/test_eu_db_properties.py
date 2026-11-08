"""EU resolution against PostgreSQL (drug-resolution tasks 23.1-23.9; P27, P28, P30-P33, P44, P47).

Synthetic BDPM- and Nomenclátor-shaped rows only; no source data.
"""

from __future__ import annotations

import datetime as dt
import socket
from collections.abc import Iterator
from dataclasses import replace
from typing import Any, NoReturn

import psycopg
import pytest
from fastapi.testclient import TestClient
from hypothesis import given, settings
from hypothesis import strategies as st

from janus.db.pool import Database
from janus.main import create_app
from janus.resolution import repository, service
from janus.resolution import router as resolution_router
from janus.resolution.load import load
from janus.resolution.model import ResolutionResult
from janus.settings import Settings
from tests.conftest import DB_EXAMPLES
from tests.harness import assert_stateless, capture_logs, isolated_tempdir
from tests.resolution_db import inputs, reset
from tests.resolution_strategies import (
    HOMEOPATHIC_SUFFIX,
    barcode13,
    bdpm_row,
    cima_row,
    cip13_of,
    titck_row,
    wikidata_row,
    with_check_digit,
)
from tests.sentinels import ascii_sentinels

pytestmark = pytest.mark.db

TODAY = dt.date(2026, 11, 8)
WD = [
    wikidata_row(
        "Q1",
        ["A02AA01"],
        {"en": "alfazin", "fr": "alfazine", "es": "alfazina", "de": "alfazind"},
    ),
    wikidata_row("Q2", ["N02BE01"], {"en": "paracetamol", "fr": "paracétamol"}),
    wikidata_row("Q3", ["C07AB02"], {"en": "betorol"}),
    # labels that are not similar to each other, so a search in one language cannot reach another
    wikidata_row(
        "Q4",
        ["R06AA01"],
        {"en": "pharmadex", "fr": "médicamentine", "es": "comprimidolina", "de": "arzneimittelin"},
    ),
]
NTIN1 = with_check_digit("0847000600001")  # CN 600001
GTIN1 = "04057598030861"
FR = [
    bdpm_row(1, " ALFAZINE 1 mg, comprimé ", ["alfazine "], routes="orale"),
    bdpm_row(2, "PARACETAMOL BIOGARAN 500 mg", ["PARACÉTAMOL"], routes="orale"),
    bdpm_row(3, "DOUBLON A", ["alfazine"]),
    bdpm_row(4, "DOUBLON B", ["betorol"], cip13=cip13_of(3)),  # the same CIP13 as DOUBLON A
    {**bdpm_row(5, "SANS CODE", ["alfazine"]), "cip13": None, "name_only": True},
    bdpm_row(6, "HOMEO", ["alfazine" + HOMEOPATHIC_SUFFIX]),
]
NTIN_SHARED = with_check_digit("0847000600005")
ES = [
    cima_row(1, "ALFAZINA 1 mg", ["alfazina"], "A02AA01", gtins=[GTIN1[1:]]),
    cima_row(2, "OTRA ALFAZINA", ["alfazina"], "A02AA01", ntins=[], gtins=[NTIN1]),
    cima_row(3, "TERCERA", ["paracetamol"], "N02BE01", ntins=[], gtins=[]),
    cima_row(4, "SIN INGREDIENTES", [], None),
    cima_row(5, "COMPARTIDA A", ["betorol"], "C07AB02", ntins=[NTIN_SHARED]),
    cima_row(6, "COMPARTIDA B", ["betorol"], "C07AB02", ntins=[NTIN_SHARED]),
]
TR = [titck_row(barcode13(1), "AMLIPIN", ["alfazin"], "A02AA01")]


@pytest.fixture(scope="module")
def database(db_url: str) -> Iterator[Database]:
    db = Database(db_url)
    db.open()
    yield db
    db.close()


def _load(database: Database, conn: psycopg.Connection, *, eu: bool = True) -> str:
    reset(conn)
    inp = inputs(TR, [], WD, fr=FR if eu else None, es=ES if eu else None)
    return load(database, replace(inp, route_map=inp.route_map)).dataset_version


def call(database: Database, fn: Any, *args: Any) -> Any:
    with database.read_only_tx() as conn:
        return fn(conn, *args)


def scan(database: Database, content: str, region: Any = None, today: dt.date = TODAY) -> Any:
    return call(database, service.resolve_scan, content, region, today)


def eu(res: Any) -> list[Any]:
    return [c for c in res.candidates if c.region == "EU"]


# --- P27, P28: France -------------------------------------------------------------------------


def test_p27_p28_french_codes_give_every_presentation(
    database: Database, db_conn: psycopg.Connection
) -> None:
    """Feature: drug-resolution, Properties P27 and P28. Validates Req 4.1, 2.3.

    "0" + CIP13 in every written form returns the presentation with its ingredients, status
    strings and BDPM date; a CIP13 on two rows returns both; a name-only row has no code.
    """
    _load(database, db_conn)
    gtin = "0" + cip13_of(2)
    forms = [gtin, cip13_of(2), f"(01){gtin}(17)300131", f"]d201{gtin}17300131"]
    results = [scan(database, f) for f in forms]
    for res in results:
        (c,) = eu(res)
        assert (c.country, c.matched_by, c.source.source_id) == ("FR", "cip13", "eu_fr_bdpm")
        assert c.product_name == "PARACETAMOL BIOGARAN 500 mg"
        assert [(i.published_name, i.status) for i in c.ingredients] == [("PARACÉTAMOL", "mapped")]
        assert c.ingredients[0].ingredient_key is not None
        assert c.ingredients[0].ingredient_key.qid == "Q2"
        assert [a.code for a in c.ingredients[0].atc_codes] == ["N02BE01"]
        assert c.routes == ["orale"] and c.dosage_form == "comprimé"
        assert c.source.snapshot_date == "2026-11-03"
        assert c.status_published[0] == "Autorisation active"
        assert not c.homeopathic
    # the same candidates whichever way the code was written (the expiry is the only difference)
    assert len({tuple(c.model_dump_json() for c in r.candidates) for r in results}) == 1
    both = eu(scan(database, "0" + cip13_of(3)))
    assert sorted(c.product_name for c in both) == ["DOUBLON A", "DOUBLON B"]
    assert [int(c.candidate_id.rsplit(":", 1)[1]) for c in both] == sorted(
        int(c.candidate_id.rsplit(":", 1)[1]) for c in both
    )
    # the name-only row is never returned by a scan, and a name search finds it
    assert not any(c.name_only for c in scan(database, "0" + cip13_of(1)).candidates)
    found = call(database, service.search, "SANS CODE", "EU", 10, TODAY)
    assert [c.name_only for c in found.candidates if c.kind == "product"] == [True]


def test_french_ingredient_routes_and_homeopathic_flag(
    database: Database, db_conn: psycopg.Connection
) -> None:
    _load(database, db_conn)
    res = call(database, service.search, "HOMEO", "EU", 10, TODAY)
    (h,) = [c for c in res.candidates if c.kind == "product"]
    assert h.homeopathic is True  # the marker in a substance name (Req 12.10, 11.1)
    plain = eu(scan(database, "0" + cip13_of(1)))[0]
    assert plain.homeopathic is False


# --- P30: Spain, order of trust --------------------------------------------------------------


def test_p30_spanish_order_of_trust_never_merges(
    database: Database, db_conn: psycopg.Connection
) -> None:
    """Feature: drug-resolution, Property P30. Validates Req 4.2.

    The NTIN list wins over the GTIN list, which wins over AI (712), which wins over the digits
    of an NTIN; the result is the first step that finds a presentation, never a merge.
    """
    _load(database, db_conn)

    def names(res: Any) -> tuple[list[str], list[str]]:
        c = eu(res)
        return sorted(x.product_name for x in c), sorted({x.matched_by for x in c})

    # 1. NTIN1 is in presentation 1's NTIN list (and in presentation 2's GTIN list): step 1 only
    assert names(scan(database, NTIN1, "EU")) == (["ALFAZINA 1 mg, 30 comprimidos"], ["ntin"])
    # 2. only the GTIN list has it
    assert names(scan(database, GTIN1, "EU")) == (["ALFAZINA 1 mg, 30 comprimidos"], ["gtin"])
    # 3. AI 712: the CN of presentation 3, the GTIN is on no list
    unknown = with_check_digit("0841123456789")
    res = scan(database, f"(01){unknown}(712)6000039", "EU")
    assert names(res) == (["TERCERA, 30 comprimidos"], ["ai_712"])
    # AI 712 is a product number: its value is not echoed anywhere in the result
    assert "6000039" not in res.model_dump_json()
    # the GTIN steps win over AI 712 when both find something
    res = scan(database, f"(01){NTIN1}(712)6000039", "EU")
    assert names(res)[1] == ["ntin"]
    # 4. an NTIN-shaped GTIN that is on no list: its digits 8-13 are the CN
    ntin3 = with_check_digit("0847000600003")
    assert names(scan(database, ntin3, "EU")) == (["TERCERA, 30 comprimidos"], ["ntin_digits"])
    # nothing found: no candidate, no guess
    assert eu(scan(database, with_check_digit("0841999999999"), "EU")) == []
    # a number on two presentations returns both
    shared = eu(scan(database, NTIN_SHARED, "EU"))
    assert sorted(c.brand_name for c in shared) == ["COMPARTIDA A", "COMPARTIDA B"]


def test_p30_spanish_presentation_shape(database: Database, db_conn: psycopg.Connection) -> None:
    _load(database, db_conn)
    (c,) = eu(scan(database, NTIN1, "EU"))
    assert (c.country, c.published_atc, c.routes) == ("ES", "A02AA01", [])
    assert [a.code for a in c.ingredients[0].atc_codes] == ["A02AA01"]
    assert c.ingredients[0].atc_selection == "single_ingredient_product"
    assert c.ingredients[0].atc_codes[0].product == c.candidate_id
    assert "commercialised:true" in c.status_published
    assert any(s.startswith("registration_status:1 2020-08-11") for s in c.status_published)
    assert c.source.snapshot_date == "2026-11-07"


# --- P32: no open database -------------------------------------------------------------------


def test_p32_german_codes_give_a_notice_and_no_german_candidate(
    database: Database, db_conn: psycopg.Connection
) -> None:
    """Feature: drug-resolution, Property P32. Validates Req 4.3, 6.2."""
    _load(database, db_conn)
    de = with_check_digit("0401234567890")
    for region in (None, "EU"):
        res = scan(database, de, region)
        notes = [n for n in res.notices if n.code == "no_open_product_database"]
        assert [(n.region, n.country) for n in notes] == [("EU", "DE")]
        assert res.scan is not None and res.scan.structural_hint == "DE"
        assert eu(res) == []
    assert "no_open_product_database" not in [n.code for n in scan(database, de, "TR").notices]
    # other countries never get the notice
    fr = scan(database, "0" + cip13_of(2))
    assert "no_open_product_database" not in [n.code for n in fr.notices]


# --- P33: EU name search ---------------------------------------------------------------------


def test_p33_name_search_by_language_and_region(
    database: Database, db_conn: psycopg.Connection
) -> None:
    """Feature: drug-resolution, Property P33. Validates Req 4.4.

    French, Spanish and German ingredient names and the EU product names are found with region
    `EU` (or without a region when the EU sources are loaded) and not with `TR` or `US`; the
    English label is found everywhere; case and accents do not matter.
    """
    _load(database, db_conn)

    def keys(q: str, region: Any) -> set[str]:
        res = call(database, service.search, q, region, 10, TODAY)
        return {c.ingredient_key.qid for c in res.candidates if c.kind == "ingredient"}

    for q, region in (("médicamentine", "EU"), ("MEDICAMENTINE", "EU"), ("comprimidolína", "EU")):
        assert keys(q, region) == {"Q4"}, q
        assert keys(q, None) == {"Q4"}, q
        assert keys(q, "TR") == set() and keys(q, "US") == set(), q
    assert keys("arzneimittelin", "EU") == {"Q4"}  # the German label
    assert keys("pharmadex", "TR") == {"Q4"}  # the English label is searchable in every region
    for q in ("paracétamol", "PARACETAMOL", "Paracétamol"):
        assert keys(q, "EU") == {"Q2"}
    res = call(database, service.search, "paracetamol biogaran", "EU", 10, TODAY)
    prod = [c for c in res.candidates if c.kind == "product"]
    assert [p.product_name for p in prod] == ["PARACETAMOL BIOGARAN 500 mg"]
    assert res.regions_searched == ["EU"]
    assert {s.source_id for s in res.sources} == {"eu_fr_bdpm", "eu_es_cima", "wikidata"}
    both = call(database, service.search, "comprimidolina", None, 10, TODAY)
    assert both.regions_searched == ["TR", "US", "EU"]


# --- P47 (request part): optional sources ----------------------------------------------------


def test_p47_a_request_that_needs_a_missing_eu_source_is_unavailable(
    database: Database, db_conn: psycopg.Connection
) -> None:
    """Feature: drug-resolution, Property P47 (request part). Validates Req 6.2, 9.7.

    Without the EU sources: a request naming region EU, a French-prefix scan and an EU candidate
    id are "unavailable" (503), never "not found"; a Turkish scan and a default search work as
    in Phase 1 and give the same candidates as on a dataset with the EU sources.
    """
    with_eu = _load(database, db_conn)
    tr_eu = scan(database, barcode13(1))
    search_eu = call(database, service.search, "amlipin", None, 10, TODAY)
    _load(database, db_conn, eu=False)
    unavailable = service.ResolutionUnavailableError
    calls: list[tuple[Any, tuple[Any, ...]]] = [
        (service.resolve_scan, ("0" + cip13_of(2), None, TODAY)),
        (service.resolve_scan, (barcode13(1), "EU", TODAY)),
        (service.search, ("alfazine", "EU", 10, TODAY)),
        (service.resolve_products, (["EU:eu_fr_bdpm:1"], TODAY)),
        (service.rule_inputs, (["EU:eu_es_cima:1"], [])),
    ]
    for fn, args in calls:
        with pytest.raises(unavailable):
            call(database, fn, *args)
    tr_only = scan(database, barcode13(1))
    assert tr_only.candidates == tr_eu.candidates
    assert tr_only.dataset_version != with_eu
    assert tr_only.regions_searched == ["TR"]
    assert call(database, service.search, "amlipin", None, 10, TODAY).candidates == (
        search_eu.candidates
    )
    # a German-prefix scan still works: the notice, and the sources that are loaded
    res = scan(database, with_check_digit("0401234567890"))
    assert [n.code for n in res.notices if n.code == "no_open_product_database"]


def test_p47_rule_inputs_need_only_the_regions_present(
    database: Database, db_conn: psycopg.Connection
) -> None:
    _load(database, db_conn)
    got = call(database, service.rule_inputs, ["TR:titck:1", "EU:eu_es_cima:3"], ["Q1"])
    assert set(got.products) == {"TR:titck:1", "EU:eu_es_cima:3"} and set(got.ingredients) == {"Q1"}
    # without the openFDA source a list of Turkish and Spanish boxes still resolves
    db_conn.execute("DELETE FROM res_source_version WHERE source_id = 'openfda_ndc'")
    got = call(database, service.rule_inputs, ["TR:titck:1", "EU:eu_es_cima:3"], [])
    assert set(got.products) == {"TR:titck:1", "EU:eu_es_cima:3"}
    with pytest.raises(service.ResolutionUnavailableError):
        call(database, service.rule_inputs, ["US:openfda_ndc:1"], [])


# --- P44 (database part): Phase 1 properties with EU sources ---------------------------------


def test_p44_not_found_is_empty_and_names_the_searched_sources(
    database: Database, db_conn: psycopg.Connection
) -> None:
    """Feature: drug-resolution, Properties P19, P20 with EU sources. Validates Req 6.2, 7.2."""
    _load(database, db_conn)
    miss = scan(database, "0" + cip13_of(99))
    assert miss.candidates == []
    assert {s.source_id for s in miss.sources} >= {"eu_fr_bdpm", "eu_es_cima", "wikidata", "titck"}
    assert "EU" in miss.regions_searched
    with database.read_only_tx() as conn:
        cur = repository.current(conn)
    assert cur is not None
    allowed = {(s.source_id, s.run_id, s.region, s.snapshot_date) for s in cur.sources.values()}
    for res in (
        scan(database, "0" + cip13_of(2)),
        scan(database, NTIN1, "EU"),
        call(database, service.search, "alfazina", None, 10, TODAY),
        call(database, service.resolve_products, ["EU:eu_fr_bdpm:2", "EU:eu_es_cima:1"], TODAY),
    ):
        refs = _source_refs(res.model_dump())
        assert refs and refs <= allowed
        again = res.model_dump_json()
        assert again == ResolutionResult.model_validate_json(again).model_dump_json()
    # determinism: the same request on the same dataset gives the same JSON
    first = scan(database, "0" + cip13_of(2)).model_dump_json()
    assert first == scan(database, "0" + cip13_of(2)).model_dump_json()


def _source_refs(value: Any) -> set[tuple[Any, ...]]:
    out: set[tuple[Any, ...]] = set()
    if isinstance(value, dict):
        d: dict[str, Any] = value  # pyright: ignore[reportUnknownVariableType]
        if set(d) == {"source_id", "run_id", "region", "snapshot_date"}:
            out.add((d["source_id"], d["run_id"], d["region"], d["snapshot_date"]))
        for v in d.values():
            out |= _source_refs(v)
    elif isinstance(value, list):
        for v in value:  # pyright: ignore[reportUnknownVariableType]
            out |= _source_refs(v)
    return out


# --- P31 (runtime part): no socket is opened by a request ------------------------------------


def test_p31_a_scan_opens_no_socket(
    database: Database, db_conn: psycopg.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Feature: drug-resolution, Property P31. Validates Req 4.2, 7.1.

    With every Python-level socket connection and name lookup refused, Spanish and French scans
    and EU searches still resolve: nothing on the request path calls out.
    """
    _load(database, db_conn)

    def refuse(*args: object, **kwargs: object) -> NoReturn:
        raise AssertionError("a request tried to open a network connection")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)
    assert len(eu(scan(database, NTIN1, "EU"))) == 1
    assert len(eu(scan(database, "0" + cip13_of(2)))) == 1
    assert eu(scan(database, f"(01){with_check_digit('0841123456789')}(712)6000039", "EU"))
    assert call(database, service.search, "paracétamol", "EU", 10, TODAY).candidates


# --- 23.9: staleness, empty ingredient lists, text exactly as published -----------------------


def test_stale_notices_for_the_bdpm_and_the_nomenclator(
    database: Database, db_conn: psycopg.Connection
) -> None:
    """Twice the cadence from the registry: BDPM 30 days (snapshot 2026-11-03), Nomenclátor
    7 days (snapshot 2026-11-07). Validates Req 4.1, 4.2, 2.2 rule."""
    _load(database, db_conn)

    def stale(today: dt.date) -> list[str]:
        res = scan(database, "0" + cip13_of(2), None, today)
        return sorted(n.source_id or "" for n in res.notices if n.code == "source_may_be_outdated")

    assert stale(dt.date(2026, 11, 21)) == ["titck"]  # Nomenclátor fresh until 2026-11-21
    assert stale(dt.date(2026, 11, 22)) == ["eu_es_cima", "titck"]
    assert stale(dt.date(2027, 1, 2)) == ["eu_es_cima", "titck"]  # BDPM limit: 60 days
    assert stale(dt.date(2027, 1, 3)) == ["eu_es_cima", "eu_fr_bdpm", "titck"]


def test_empty_ingredient_list_and_exact_published_text(
    database: Database, db_conn: psycopg.Connection
) -> None:
    _load(database, db_conn)
    (empty,) = eu(scan(database, with_check_digit("0847000600004"), "EU"))
    assert empty.ingredients == [] and empty.brand_name == "SIN INGREDIENTES"
    (c,) = eu(scan(database, "0" + cip13_of(1)))
    # leading and trailing spaces and accents are returned as published (licence ouverte)
    assert c.product_name == " ALFAZINE 1 mg, comprimé "
    assert c.ingredients[0].published_name == "alfazine "
    assert c.ingredients[0].strength == "1,00 mg"


# --- P22/P10 with EU codes over HTTP ---------------------------------------------------------


@pytest.fixture(scope="module")
def client(db_url: str) -> Iterator[TestClient]:
    database = Database(db_url)
    database.open()
    with psycopg.connect(db_url, autocommit=True) as conn:
        _load(database, conn)
    app = create_app(Settings.from_env({}), database=database)
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    database.close()


def test_eu_routes_work_over_http(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(resolution_router, "today", lambda: TODAY)
    r = client.post("/resolve/scan", json={"content": "0" + cip13_of(2), "region": "EU"})
    assert r.status_code == 200
    body = r.json()
    assert body["regions_searched"] == ["EU"]
    assert [c["country"] for c in body["candidates"]] == ["FR"]
    r = client.post("/resolve/search", json={"query": "paracétamol", "region": "EU"})
    assert r.status_code == 200 and r.json()["candidates"]
    r = client.post("/resolve/products", json={"candidate_ids": ["EU:eu_es_cima:1"]})
    assert r.status_code == 200 and r.json()["candidates"][0]["country"] == "ES"
    r = client.post("/resolve/scan", json={"content": NTIN1, "region": "XX"})
    assert r.status_code == 422


@settings(max_examples=DB_EXAMPLES)
@given(national=st.integers(1_000_000, 9_999_999).map(str), value=ascii_sentinels())
def test_ai_712_values_and_eu_inputs_are_never_logged_or_echoed(
    client: TestClient, db_conn: psycopg.Connection, national: str, value: str
) -> None:
    """Feature: drug-resolution, Properties P10 and P22 with EU inputs. Validates Req 8.1-8.4.

    An AI (712) value, an EU search text and an EU candidate id leave the database and the temp
    directory unchanged, are not echoed in the response and appear in no log line.
    """
    gtin = with_check_digit("0841123456789")
    requests: list[tuple[str, dict[str, Any], str]] = [
        ("/resolve/scan", {"content": f"(01){gtin}(712){national}", "region": "EU"}, national),
        ("/resolve/search", {"query": value, "region": "EU"}, value),
        ("/resolve/products", {"candidate_ids": [value]}, value),
    ]
    for path, body, secret in requests:
        with isolated_tempdir() as tmp, capture_logs() as logs:
            response = assert_stateless(db_conn, tmp, lambda p=path, b=body: client.post(p, json=b))
        assert response.headers["cache-control"] == "no-store"
        assert response.status_code in (200, 422)
        assert secret not in logs.getvalue()
        if path == "/resolve/scan":
            assert secret not in response.text
