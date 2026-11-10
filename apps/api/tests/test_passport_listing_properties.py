"""Products with the same active ingredients (medication-passport tasks 15-17, design §15).

Feature: medication-passport, Properties P22 (every listed product has exactly the item's
ingredient keys; the listing equals a brute-force model over the raw rows, database), P23 (`same`
only when both sides have a code and the codes are equal; `different` only when both are known),
P24 (counts, paging and order invariance), P25 (only licensed sources are listable; TİTCK never),
P26 (marketing statement), P27 (the route: stateless, silent logs, closed schema, 422 without echo,
503 with nothing partial, constant statement budget). Sentinel keys and invented names only.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
from collections.abc import Iterator, Sequence
from typing import Any, cast, get_args

import psycopg
import pytest
from fastapi.testclient import TestClient
from hypothesis import given, settings
from hypothesis import strategies as st

from janus.db.pool import Database
from janus.main import create_app
from janus.passport import forms, repository, service
from janus.passport import router as passport_router
from janus.passport.forms import NOT_COMPARED_GROUPS
from janus.passport.listing import (
    LISTABLE_SOURCES,
    NOT_FINISHED_TYPES,
    ListingRow,
    listing,
    marketed,
)
from janus.passport.presence import ItemQuery, PresenceRow, is_homeopathic
from janus.passport.schemas import ItemIn, ListableSourceId, ProductsIn, ProductsOut
from janus.passport.strength import StrengthCode, strength_code
from janus.settings import Settings
from tests.conftest import DB_EXAMPLES
from tests.harness import assert_stateless, capture_logs, isolated_tempdir
from tests.passport_db import (
    KEYS,
    REGION,
    SOURCE_DATES,
    UNKNOWN_KEY,
    Ing,
    Product,
    install,
    products,
)
from tests.resolution_db import reset
from tests.sentinels import leaked, sentinels

TODAY = dt.date(2026, 11, 10)
TABLE = forms.load()
URL = "/passport/products"
JSON = {"content-type": "application/json"}
CODES = [
    StrengthCode("5000", "ug", "unit"),
    StrengthCode("10000", "ug", "unit"),
    StrengthCode("50000", "ug", "mL"),
]
NAMES = ["TESTPRODUCT A 5", "Testproduct b", "TESTPRODUCT A 5 ", "ÉTESTPRODUCT"]
STATUS: dict[str, list[tuple[str, ...]]] = {
    "eu_fr_bdpm": [("Commercialisée",), ("Non commercialisée", "Autorisation active"), ()],
    "eu_es_cima": [("commercialised:true",), ("commercialised:false", "serialised:true"), ()],
    "openfda_ndc": [()],
    "titck": [()],
    "eu_it_aifa": [("Autorizzata", "Procedura Nazionale"), ()],
    "ca_dpd": [("MARKETED",), ()],
}
TYPES = ["HUMAN PRESCRIPTION DRUG", "HUMAN OTC DRUG", None, *sorted(NOT_FINISHED_TYPES)[:2]]
END_DATES = [None, None, "20261109", "20261110", "20491231", "x"]


# --- strategies ------------------------------------------------------------------------------
@st.composite
def listed_products(draw: st.DrawFn, source: str | None = None) -> Product:
    p = draw(products(source))
    us = p.source_id == "openfda_ndc"
    return dataclasses.replace(
        p,
        name=draw(st.sampled_from(NAMES)),
        product_type=draw(st.sampled_from(TYPES)) if us else None,
        status_published=draw(st.sampled_from(STATUS[p.source_id])),
        marketing_end_date=draw(st.sampled_from(END_DATES)) if us else None,
    )


def strength_in(code: StrengthCode | None) -> dict[str, str] | None:
    return None if code is None else {"amount": code.amount, "unit": code.unit, "basis": code.basis}


@st.composite
def queries(draw: st.DrawFn) -> dict[str, Any]:
    pool = (*KEYS[:3], *KEYS[:3], KEYS[3], UNKNOWN_KEY)
    ks = list(dict.fromkeys(draw(st.lists(st.sampled_from(pool), min_size=1, max_size=2))))
    return {
        "ingredients": [
            {
                "key": k,
                "strength": strength_in(draw(st.sampled_from([None, CODES[0], CODES[0], *CODES]))),
            }
            for k in ks
        ],
        "dose_form": draw(
            st.sampled_from(
                [None, "oral_solid", "oral_solid", "oral_liquid", "other", "ophthalmic"]
            )
        ),
        "target": draw(st.sampled_from(LISTABLE_SOURCES)),
    }


def row_of(p: Product) -> ListingRow:
    """The grouped row the statement gives for one product (count 1)."""
    mapped = sorted(
        ((i.qid or "", n, i.strength) for n, i in enumerate(p.ingredients) if i.status == "mapped"),
    )
    return ListingRow(
        row=PresenceRow(
            source_id=p.source_id,
            keys=[k for k, _, _ in mapped],
            strengths=[s for _, _, s in mapped],
            complete=all(i.status == "mapped" for i in p.ingredients),
            hp_strength=any(
                i.strength is not None and "[hp_" in i.strength.lower() for i in p.ingredients
            ),
            hp_names=[i.name for i in p.ingredients if "pathiques" in i.name.lower()],
            region=REGION[p.source_id],
            dosage_form=p.dosage_form,
            routes=list(p.routes),
            products=1,
        ),
        name=p.name,
        product_type=p.product_type,
        marketing_end_date=p.marketing_end_date,
        status_published=list(p.status_published),
    )


def item_of(query: dict[str, Any]) -> ItemQuery:
    return ItemQuery.of(
        ItemIn.model_validate({k: query[k] for k in ("ingredients", "dose_form")}, strict=False)
    )


# --- the model: straight from the raw product, no shared helper but the pure code functions ----
def model_levels(q: dict[str, Any], p: Product) -> tuple[str, str]:
    group = TABLE.group(p.source_id, p.dosage_form, p.routes)
    want = {
        i["key"]: None if i["strength"] is None else StrengthCode(**i["strength"])
        for i in q["ingredients"]
    }
    mapped = [i for i in p.ingredients if i.status == "mapped"]
    have: dict[str, list[StrengthCode | None]] = {}
    for i in mapped:
        have.setdefault(i.qid or "", []).append(strength_code(p.source_id, i.strength, group))
    if any(v is None for v in want.values()) or any(
        len(v) != 1 or v[0] is None for v in have.values()
    ):
        strength = "unknown"
    else:
        strength = "same" if all(have[k][0] == want[k] for k in want) else "different"
    form = q["dose_form"]
    if form is None or form in NOT_COMPARED_GROUPS or group is None or group in NOT_COMPARED_GROUPS:
        dose_form = "unknown"
    else:
        dose_form = "same" if group == form else "different"
    return strength, dose_form


def model_listed(q: dict[str, Any], data: Sequence[Product]) -> list[Product]:
    keys = {i["key"] for i in q["ingredients"]}
    return [
        p
        for p in data
        if p.source_id == q["target"]
        and all(i.status == "mapped" for i in p.ingredients)
        and {i.qid for i in p.ingredients} == keys
        and p.product_type not in NOT_FINISHED_TYPES
        and not is_homeopathic(
            (i.strength for i in p.ingredients),
            (i.name for i in p.ingredients),
            REGION[p.source_id],
        )
    ]


def check_against_model(out: ProductsOut, q: dict[str, Any], data: Sequence[Product]) -> None:
    keys = {i["key"] for i in q["ingredients"]}
    expected = model_listed(q, data)
    # P22: exact set equality for every listed product, and nothing that qualifies is missing.
    assert all({i.key for i in p.ingredients} == keys for p in out.products)
    assert out.listings == len(expected)
    assert (out.status == "present") == bool(expected)
    tally = {"strength": {"same": 0, "different": 0, "unknown": 0}}
    tally["dose_form"] = dict(tally["strength"])
    for p in expected:
        strength, dose_form = model_levels(q, p)
        tally["strength"][strength] += 1
        tally["dose_form"][dose_form] += 1
    assert out.counts.model_dump() == tally  # P23 over the whole listing
    names = sorted(p.name for p in expected)
    assert sorted(p.name for p in out.products for _ in range(p.listings)) == names
    for p in out.products:
        candidates = [
            e
            for e in expected
            if e.name == p.name
            and e.dosage_form == p.dose_form_published
            and model_levels(q, e) == (p.strength, p.dose_form)
        ]
        assert candidates, "a listed row has no product behind it"


# --- P22, P23, P24 (pure) ---------------------------------------------------------------------
@settings(max_examples=300)
@given(
    q=queries(),
    data=st.lists(listed_products(), max_size=30),
    order=st.data(),
    limit=st.integers(1, 7),
)
def test_p22_p23_p24_listing(
    q: dict[str, Any], data: list[Product], order: st.DataObject, limit: int
) -> None:
    """Feature: medication-passport, Properties P22, P23, P24. Validates Req 14.1-14.6, 16.3."""
    item = item_of(q)
    rows = [row_of(p) for p in data if p.source_id == q["target"]]
    out = listing(item, rows, TABLE, TODAY)
    for p in out.products:
        # P22: exact ingredient-set equality.
        assert {i.key for i in p.ingredients} == set(item.keys)
        # P23: `same` strength means every ingredient has a code on both sides, all equal.
        codes = [
            strength_code(q["target"], i.strength_published, p.dose_form_group)
            for i in p.ingredients
        ]
        if p.strength == "same":
            assert len(codes) == len(item.keys)
            assert all(
                c is not None and c == item.strengths[i.key]
                for c, i in zip(codes, p.ingredients, strict=True)
            )
        if p.strength == "different":
            assert all(c is not None for c in codes)
            assert all(item.strengths[k] is not None for k in item.keys)
        assert (p.strength == "unknown") == (p.strength_reason is not None)
        if p.dose_form == "same":
            assert p.dose_form_group == item.form_group and p.dose_form_group != "other"
        if p.dose_form == "different":
            assert None not in (p.dose_form_group, item.form_group)
            assert p.dose_form_group != item.form_group
        assert (p.dose_form == "unknown") == (p.dose_form_reason is not None)
        assert p.listings >= 1
    # P24: counts add up; the order does not depend on the row order; pages tile the list.
    total = sum(p.listings for p in out.products)
    assert out.answer.products == total
    for c in (out.counts.strength, out.counts.dose_form):
        assert c.same + c.different + c.unknown == total
    shuffled = order.draw(st.permutations(rows))
    assert listing(item, shuffled, TABLE, TODAY).products == out.products
    pages = [out.products[i : i + limit] for i in range(0, len(out.products), limit)]
    assert [p for page in pages for p in page] == out.products
    assert len({p.model_dump_json(exclude={"listings"}) for p in out.products}) == len(out.products)


def test_p23_examples() -> None:
    """Salts and unit spellings: equal quantities are `same`, a different amount is `different`,
    a liquid without a stated basis is `unknown`; nothing is converted (design §15.4)."""

    def one(strength: str | None, form: str | None, routes: tuple[str, ...]) -> tuple[str, str]:
        p = Product("eu_fr_bdpm", form, routes, (Ing("mapped", KEYS[0], strength, "TESTNAME"),))
        q = {
            "ingredients": [{"key": KEYS[0], "strength": strength_in(CODES[0])}],
            "dose_form": "oral_solid",
            "target": "eu_fr_bdpm",
        }
        out = listing(item_of(q), [row_of(p)], TABLE, TODAY).products[0]
        return out.strength, out.dose_form

    assert one("5 mg", "comprimé pelliculé", ("orale",)) == ("same", "same")
    assert one("5000 microgrammes", "gélule", ("orale",)) == ("same", "same")
    assert one("5,00 mg", "gélule", ("orale",)) == ("same", "same")
    assert one("10 mg", "gélule", ("orale",)) == ("different", "same")
    assert one("5 mg", "solution buvable", ("orale",)) == ("unknown", "different")
    assert one(None, None, ()) == ("unknown", "unknown")


# --- P25 ----------------------------------------------------------------------------------------
def test_p25_only_licensed_sources_are_listable() -> None:
    """Feature: medication-passport, Property P25. Validates Req 15.1, 15.2: the TİTCK list
    (redistribution terms unclear) is never a target; neither is Germany (no source)."""
    assert tuple(get_args(ListableSourceId)) == LISTABLE_SOURCES
    assert "titck" not in LISTABLE_SOURCES
    good = {"ingredients": [{"key": "Q1"}], "target": "eu_fr_bdpm"}
    assert ProductsIn.model_validate(good).limit == 50
    for target in ("titck", "eu_de", "", None, "EU_FR_BDPM", "wikidata"):
        with pytest.raises(ValueError):
            ProductsIn.model_validate({**good, "target": target})


# --- P26 ----------------------------------------------------------------------------------------
def test_p26_marketing_statement() -> None:
    """Feature: medication-passport, Property P26. Validates Req 14.7."""
    assert marketed("eu_fr_bdpm", ["Commercialisée"], None, TODAY) == "listed_as_marketed"
    assert marketed("eu_fr_bdpm", ["Non commercialisée"], None, TODAY) == "listed_as_not_marketed"
    assert marketed("eu_fr_bdpm", ["Autorisation active"], None, TODAY) == "not_stated"
    assert marketed("eu_es_cima", ["commercialised:true"], None, TODAY) == "listed_as_marketed"
    assert marketed("eu_es_cima", ["commercialised:false"], None, TODAY) == "listed_as_not_marketed"
    assert marketed("eu_es_cima", [], None, TODAY) == "not_stated"
    assert marketed("openfda_ndc", [], "20261109", TODAY) == "listed_as_not_marketed"
    assert marketed("openfda_ndc", [], "20261110", TODAY) == "not_stated"
    assert marketed("openfda_ndc", [], None, TODAY) == "not_stated"
    assert marketed("openfda_ndc", [], "soon", TODAY) == "not_stated"
    assert marketed("titck", ["Commercialisée"], "20000101", TODAY) == "not_stated"


# --- database and HTTP --------------------------------------------------------------------------
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


DATA = [
    Product(
        "openfda_ndc", "TABLET", ("ORAL",), (Ing("mapped", KEYS[0], "5 mg/1", "TESTNAME"),), "TP US"
    ),
    Product(
        "eu_fr_bdpm", "gélule", ("orale",), (Ing("mapped", KEYS[0], "5 mg", "TESTNAME"),), "TP FR"
    ),
    Product("titck", None, (), (Ing("mapped", KEYS[0], None, "TESTNAME"),), "TP TR"),
]


@pytest.mark.db
@settings(max_examples=DB_EXAMPLES)
@given(q=queries(), data=st.lists(listed_products(), max_size=25), limit=st.integers(1, 100))
def test_p22_database_equals_model(
    env: tuple[TestClient, Database],
    db_conn: psycopg.Connection,
    q: dict[str, Any],
    data: list[Product],
    limit: int,
) -> None:
    """Feature: medication-passport, Property P22 (statement and service). Validates Req 14.1-14.4,
    15.3."""
    dataset = install(db_conn, data)
    r = env[0].post(URL, json={**q, "limit": limit})
    assert r.status_code == 200, r.text
    page = ProductsOut.model_validate(r.json())
    assert page.dataset_version == dataset and page.source.source_id == q["target"]
    assert page.source.snapshot_date == SOURCE_DATES[q["target"]][1]
    assert len(page.products) == min(limit, page.total)
    rest: list[Any] = []
    for offset in range(limit, page.total, limit):
        more = env[0].post(URL, json={**q, "limit": limit, "offset": offset})
        rest += ProductsOut.model_validate(more.json()).products
    full = page.model_copy(update={"products": [*page.products, *rest]})
    assert len(full.products) == page.total
    check_against_model(full, q, data)
    assert page.unknown_keys == sorted(
        {i["key"] for i in q["ingredients"]}
        - {i.qid for p in data for i in p.ingredients if i.status == "mapped"}
    )
    # No TİTCK name ever leaves through this route (P25).
    assert "TP TR" not in r.text


@pytest.mark.db
@settings(max_examples=DB_EXAMPLES)
@given(
    secret=sentinels(),
    mode=st.sampled_from(
        ["valid", "extra_field", "bad_key", "bad_target", "titck", "name", "not_json", "limit"]
    ),
)
def test_p27_stateless_silent_closed(
    env: tuple[TestClient, Database], db_conn: psycopg.Connection, secret: str, mode: str
) -> None:
    """Feature: medication-passport, Property P27. Validates Req 15.3-15.6, 9.1, 9.2."""
    client, _ = env
    install(db_conn, DATA)
    body: Any = {"ingredients": [{"key": KEYS[0]}], "target": "eu_fr_bdpm"}
    if mode == "extra_field":
        body["demo"] = secret
    elif mode == "bad_key":
        body["ingredients"][0]["key"] = secret
    elif mode == "bad_target":
        body["target"] = secret
    elif mode == "titck":
        body["target"] = "titck"
    elif mode == "name":
        body["ingredients"][0]["name"] = secret
    elif mode == "limit":
        body["limit"] = 101
    with capture_logs() as logs, isolated_tempdir() as tmp:
        if mode == "not_json":
            r = assert_stateless(
                db_conn, tmp, lambda: client.post(URL, content=secret.encode(), headers=JSON)
            )
        else:
            r = assert_stateless(db_conn, tmp, lambda: client.post(URL, json=body))
    assert r.headers["cache-control"] == "no-store"
    assert leaked(logs.getvalue(), [secret, KEYS[0], "TP FR"]) == []
    if mode == "valid":
        assert r.status_code == 200, r.text
        out = r.json()
        assert [p["name"] for p in out["products"]] == ["TP FR"]
        assert out["products"][0]["strength"] == "unknown"  # the item gave no strength
        assert out["notices"] == ["listing_is_lower_bound"]
        assert "information, not medical advice" in out["disclaimer"]
    else:
        assert r.status_code == 422
        out = r.json()
        assert out["error"] == "invalid_request" and set(out) == {"error", "fields"}
        assert secret not in r.text and KEYS[0] not in r.text


def test_p27_closed_schema() -> None:
    """Every string field of the request has a pattern or a literal; unknown fields are refused."""
    schema = ProductsIn.model_json_schema()

    def walk(node: Any) -> Iterator[dict[str, Any]]:
        if isinstance(node, dict):
            d = cast(dict[str, Any], node)
            if d.get("type") == "string":
                yield d
            for v in d.values():
                yield from walk(v)
        elif isinstance(node, list):
            for v in cast(list[Any], node):
                yield from walk(v)

    strings = list(walk(schema))
    assert strings and all("pattern" in s or "enum" in s or "const" in s for s in strings)
    defs = cast(dict[str, Any], schema["$defs"])
    assert all(d.get("additionalProperties") is False for d in defs.values() if "properties" in d)
    assert schema.get("additionalProperties") is False


@pytest.mark.db
def test_p27_unavailable_and_budget(
    env: tuple[TestClient, Database], db_conn: psycopg.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Feature: medication-passport, Property P27. Validates Req 15.5, 15.6, 13.2."""
    client, database = env
    body = {"ingredients": [{"key": KEYS[0]}], "target": "openfda_ndc"}
    reset(db_conn)  # no current dataset
    r = client.post(URL, json=body)
    assert (r.status_code, r.json()) == (503, {"error": "passport_unavailable"})
    install(db_conn, DATA, ["eu_fr_bdpm", "titck"])  # the target source is not loaded
    out = client.post(URL, json=body).json()
    assert (out["status"], out["source"]["reason"], out["products"]) == (
        "source_unavailable",
        "not_loaded",
        [],
    )
    install(db_conn, DATA)
    counts: list[int] = []

    class Counting:
        def __init__(self, conn: psycopg.Connection) -> None:
            self.conn = conn
            self.statements = 0

        def execute(self, *args: Any, **kwargs: Any) -> Any:
            self.statements += 1
            return self.conn.execute(*args, **kwargs)

    for keys in ([KEYS[0]], list(KEYS)):
        query = ProductsIn.model_validate(
            {"ingredients": [{"key": k} for k in keys], "target": "openfda_ndc"}
        )
        with database.read_only_tx() as conn:
            counter = Counting(conn)
            service.products(cast(psycopg.Connection, counter), query, TABLE, TODAY)
            counts.append(counter.statements)
    assert counts == [5, 5]  # timeout, current (2), known keys, listing
    monkeypatch.setattr(repository, "STATEMENT_TIMEOUT", "50ms")
    monkeypatch.setattr(
        repository,
        "LISTING_SQL",
        "SELECT 1 FROM pg_sleep(1) WHERE %(d)s::text <> '' AND %(s)s::text <> '' "
        "AND %(keys)s::text[] IS NOT NULL",
    )
    r = client.post(URL, json=body)
    assert (r.status_code, r.json()) == (503, {"error": "passport_unavailable"})
