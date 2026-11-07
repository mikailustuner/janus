"""Resolution service properties against PostgreSQL (drug-resolution design §8:
P8 request part, P13, P14, P15, P19, P20, P21)."""

from __future__ import annotations

import datetime as dt
import random
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, Literal

import psycopg
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from janus.db.pool import Database
from janus.regions.base import ProductKey, Region
from janus.resolution import repository, service
from janus.resolution.load import load
from janus.resolution.names import fold
from janus.resolution.ndc import canonical_package, layouts_of_ndc10
from tests.conftest import DB_EXAMPLES
from tests.resolution_db import inputs, reset
from tests.resolution_strategies import barcode13, titck_row, us_row, wikidata_row

TODAY = dt.date(2026, 11, 8)
WD = [
    wikidata_row("Q411347", ["C08CA01"], {"en": "amlodipine", "tr": "amlodipin"}),
    wikidata_row("Q412208", ["C09AA03"], {"en": "lisinopril"}),
]


@pytest.fixture(scope="module")
def database(db_url: str) -> Iterator[Database]:
    db = Database(db_url)
    db.open()
    yield db
    db.close()


# --- P21: adapter dispatch (pure) ------------------------------------------------------------


@dataclass
class StubAdapter:
    region: Region
    source_id: str
    accept: bool
    hint: bool
    matched_by: Literal["barcode", "ndc_gtin"] = "barcode"

    def accepts_gtin(self, gtin14: str) -> bool:
        return self.accept

    def keys_from_gtin(self, gtin14: str) -> list[ProductKey]:
        return []

    def structural_hint(self, gtin14: str) -> bool:
        return self.hint


@given(
    flags=st.lists(st.tuples(st.booleans(), st.booleans()), min_size=2, max_size=2),
    override=st.one_of(st.none(), st.sampled_from(["TR", "US"])),
    gtin=st.sampled_from(["08680199094206", "00300024462301", "03400930000001"]),
)
def test_adapter_dispatch(
    flags: list[tuple[bool, bool]], override: Region | None, gtin: str
) -> None:
    """Feature: drug-resolution, Property P21. Validates Req 1.5.

    With an override only that region's adapter is asked; without one, exactly the adapters
    whose `accepts_gtin` is true, hinted ones first.
    """
    tr = StubAdapter("TR", "titck", *flags[0])
    us = StubAdapter("US", "openfda_ndc", *flags[1])
    chosen = service.choose_adapters([tr, us], gtin, override)
    if override is not None:
        assert [a.region for a in chosen] == [override]
        return
    assert {a.region for a in chosen} == {a.region for a in (tr, us) if a.accept}
    hinted = [a.structural_hint(gtin) for a in chosen]
    assert hinted == sorted(hinted, reverse=True)


# --- P15 (pure part): ranking ---------------------------------------------------------------

HITS = st.lists(
    st.builds(
        repository.NameHit,
        st.sampled_from(["amlipin", "amlipin 10 mg", "amlodipin", "lisinopril", "ami"]),
        st.sampled_from(["product", "ingredient"]),
        st.sampled_from(["", "TR", "US"]),
        st.sampled_from(["TR:titck:1", "TR:titck:2", "US:openfda_ndc:3", "Q1", "Q2"]),
        st.floats(0, 1, allow_nan=False),
    ),
    max_size=12,
)


@given(
    hits=HITS,
    key=st.sampled_from(["amlipin", "ami", "lisinopril"]),
    limit=st.integers(1, 5),
    rnd=st.randoms(),
)
def test_rank_is_order_independent(
    hits: list[repository.NameHit], key: str, limit: int, rnd: random.Random
) -> None:
    """Feature: drug-resolution, Property P15 (rank). Validates Req 2.4, 3.3.

    `rank` does not depend on the order of candidate rows and never returns more than `limit`.
    """
    shuffled = list(hits)
    rnd.shuffle(shuffled)
    ranked = service.rank(key, hits, limit)
    assert ranked == service.rank(key, shuffled, limit)
    assert len(ranked) <= limit
    assert len({(r.kind, r.ref) for r in ranked}) == len(ranked)


# --- synthetic loaded datasets ----------------------------------------------------------------

NAME_WORDS = ["AMLIPIN", "İNDAPAMİD", "ŞURUP", "Ilık", "LİSİN"]  # noqa: RUF001 (Turkish)


@st.composite
def catalogues(draw: st.DrawFn) -> tuple[list[Any], list[Any]]:
    pool = [barcode13(i) for i in range(1, 5)]
    tr: list[Any] = []
    for i in range(draw(st.integers(1, 10))):
        barcode = draw(st.one_of(st.sampled_from(pool), st.none()))
        name = f"{draw(st.sampled_from(NAME_WORDS))} {i}"
        ings = draw(st.lists(st.sampled_from(["amlodipin besilat", "lisinopril", "x"]), max_size=2))
        tr.append(
            titck_row(barcode, name, ings, draw(st.sampled_from([None, "C09BB03", "C08CA01"])))
        )
    pkgs = ["1234-5678-90", "12345-678-90", "12345-6789-0", "54321-123-45"]
    us: list[Any] = []
    for i in range(draw(st.integers(0, 5))):
        chosen = draw(st.lists(st.sampled_from(pkgs), min_size=1, max_size=2, unique=True))
        product = "-".join(chosen[0].split("-")[:2])
        routes = draw(st.lists(st.sampled_from(["ORAL", "TOPICAL"]), max_size=1))
        us.append(us_row(product, chosen, ["amlodipine besylate"], routes, brand=f"BRAND{i}"))
    return tr, us


def _loaded(database: Database, conn: psycopg.Connection, tr: list[Any], us: list[Any]) -> str:
    reset(conn)
    return load(database, inputs(tr, us, WD)).dataset_version


def _call(database: Database, fn: Any, *args: Any) -> Any:
    with database.read_only_tx() as conn:
        return fn(conn, *args)


@pytest.mark.db
@settings(max_examples=DB_EXAMPLES)
@given(cat=catalogues())
def test_all_candidates_for_duplicate_keys(
    database: Database, db_conn: psycopg.Connection, cat: tuple[list[Any], list[Any]]
) -> None:
    """Feature: drug-resolution, Property P13. Validates Req 2.1, 3.1, 6.2.

    For every key occurring on n rows, every input form returns exactly those n rows, in
    product-id order; never fewer, never a choice.
    """
    tr, us = cat
    _loaded(database, db_conn, tr, us)
    counts = Counter(r["barcode"] for r in tr if r["barcode"])
    for barcode, n in counts.items():
        names = sorted(r["product_name"] for r in tr if r["barcode"] == barcode)
        for content in (barcode, "0" + barcode, f"(01)0{barcode}(17)300100", f"]d2010{barcode}"):
            res = _call(database, service.resolve_scan, content, None, TODAY)
            got = [c for c in res.candidates if c.region == "TR"]
            assert len(got) == n
            assert sorted(c.product_name for c in got) == names
            ids = [int(c.candidate_id.rsplit(":", 1)[1]) for c in got]
            assert ids == sorted(ids)
    for pkg in {p for r in us for p in r["package_ndcs"]}:
        canon = canonical_package(pkg)
        want = sorted(
            {
                r["brand_name"]
                for r in us
                if canon in {canonical_package(x) for x in r["package_ndcs"]}
            }
        )
        res = _call(database, service.resolve_ndc, pkg, TODAY)
        assert sorted({c.brand_name for c in res.candidates}) == want
        digits = pkg.replace("-", "")
        layouts = set(layouts_of_ndc10(digits).values()) if len(digits) == 10 else {canon}
        want10 = sorted(
            {
                r["brand_name"]
                for r in us
                if layouts & {canonical_package(x) for x in r["package_ndcs"]}
            }
        )
        res10 = _call(database, service.resolve_ndc, digits, TODAY)
        assert sorted({c.brand_name for c in res10.candidates}) == want10


@pytest.mark.db
@settings(max_examples=DB_EXAMPLES)
@given(cat=catalogues())
def test_name_only_rows(
    database: Database, db_conn: psycopg.Connection, cat: tuple[list[Any], list[Any]]
) -> None:
    """Feature: drug-resolution, Property P14. Validates Req 2.3.

    Name-only rows are never returned by a scan, and a search for their exact product name
    returns them.
    """
    tr, us = cat
    _loaded(database, db_conn, tr, us)
    for barcode in {r["barcode"] for r in tr if r["barcode"]}:
        res = _call(database, service.resolve_scan, barcode, None, TODAY)
        assert not any(getattr(c, "name_only", False) for c in res.candidates)
    for row in (r for r in tr if r["barcode"] is None):
        res = _call(database, service.search, row["product_name"], "TR", 20, TODAY)
        names = [getattr(c, "product_name", None) for c in res.candidates]
        assert row["product_name"] in names
        hit = next(
            c for c in res.candidates if getattr(c, "product_name", None) == row["product_name"]
        )
        assert hit.name_only is True


def _variants(text: str) -> list[str]:
    return [text, text.upper(), text.lower(), text.replace("I", "İ"), text.replace("i", "ı")]  # noqa: RUF001


@pytest.mark.db
@settings(max_examples=DB_EXAMPLES)
@given(
    cat=catalogues(), word=st.sampled_from(["amlipin", "indapamid", "surup", "ilik", "amlodipin"])
)
def test_search_variants(
    database: Database, db_conn: psycopg.Connection, cat: tuple[list[Any], list[Any]], word: str
) -> None:
    """Feature: drug-resolution, Property P15. Validates Req 2.4, 3.3.

    Case, Turkish dotted/dotless i and diacritic variants of a query give the same result, and
    the result does not depend on the order in which source rows were loaded.
    """
    tr, us = cat
    _loaded(database, db_conn, tr, us)
    results = {
        v: _call(database, service.search, v, None, 10, TODAY).model_dump_json()
        for v in _variants(word)
        if len(fold(v)) >= 2
    }
    assert len(set(results.values())) == 1
    _loaded(database, db_conn, list(reversed(tr)), list(reversed(us)))
    again = _call(database, service.search, word, None, 10, TODAY).model_dump_json()
    assert again == results[word]


@pytest.mark.db
def test_unavailable_vs_not_found(database: Database, db_conn: psycopg.Connection) -> None:
    """Feature: drug-resolution, Property P19 (examples over every route). Validates Req 6.2.

    With no dataset every route raises `ResolutionUnavailableError` (503); with sources loaded a
    miss is an empty candidate list naming the searched sources.
    """
    reset(db_conn)
    calls: list[tuple[Any, tuple[Any, ...]]] = [
        (service.resolve_scan, (barcode13(77), None, TODAY)),
        (service.resolve_ndc, ("99999-9999-99", TODAY)),
        (service.search, ("zzzz", None, 10, TODAY)),
        (service.resolve_products, (["TR:titck:999"], TODAY)),
    ]
    for fn, args in calls:
        with pytest.raises(service.ResolutionUnavailableError):
            _call(database, fn, *args)
    _loaded(database, db_conn, [titck_row(barcode13(1), "A", ["amlodipin"], None)], [])
    for fn, args in calls:
        res = _call(database, fn, *args)
        assert res.candidates == []
        assert {s.source_id for s in res.sources} >= {"wikidata"}
        assert res.regions_searched


@pytest.mark.db
@settings(max_examples=DB_EXAMPLES)
@given(cat=catalogues(), q=st.sampled_from(["amlipin", "amlodipine", "brand"]))
def test_provenance_and_determinism(
    database: Database, db_conn: psycopg.Connection, cat: tuple[list[Any], list[Any]], q: str
) -> None:
    """Feature: drug-resolution, Properties P20 and P8 (request part). Validates Req 7.2, 7.3.

    Every SourceRef in a result is one of the current dataset's source versions; repeating a
    request against the same dataset gives byte-identical JSON.
    """
    tr, us = cat
    version = _loaded(database, db_conn, tr, us)
    with database.read_only_tx() as conn:
        cur = repository.current(conn)
    assert cur is not None
    allowed = {(s.source_id, s.run_id, s.region, s.snapshot_date) for s in cur.sources.values()}
    requests: list[tuple[Any, tuple[Any, ...]]] = [
        (service.search, (q, None, 10, TODAY)),
        *[(service.resolve_scan, (r["barcode"], None, TODAY)) for r in tr if r["barcode"]],
        *[(service.resolve_ndc, (p, TODAY)) for r in us for p in r["package_ndcs"]],
    ]
    for fn, args in requests:
        first = _call(database, fn, *args)
        assert first.dataset_version == version
        assert first.model_dump_json() == _call(database, fn, *args).model_dump_json()
        refs = _source_refs(first.model_dump())
        assert refs and refs <= allowed


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


@pytest.mark.db
def test_amlipin_end_to_end_service(database: Database, db_conn: psycopg.Connection) -> None:
    """Req 5.2 example through the database: AMLIPIN resolves to amlodipine and lisinopril."""
    from janus.resolution.atc import CombinationRules, RouteMap
    from janus.resolution.load import Inputs

    reset(db_conn)
    base = inputs(
        [
            titck_row(
                "8680199094206",
                "AMLIPIN 10 / 10 MG FILM TABLET, 30 ADET",
                ["amlodipin besilat", "lisinopril dihidrat"],
                "C09BB03",
            )
        ],
        [],
        WD,
    )
    real = Inputs(
        base.artifacts, CombinationRules.load(), RouteMap.load(), (), "test", base.cadences
    )
    load(database, real)
    res = _call(database, service.resolve_scan, "(01)08680199094206(17)280500", None, TODAY)
    (c,) = res.candidates
    assert c.published_atc == "C09BB03"
    assert [
        (i.ingredient_key.qid if i.ingredient_key else None, [a.code for a in i.atc_codes])
        for i in c.ingredients
    ] == [
        ("Q411347", ["C08CA01"]),
        ("Q412208", ["C09AA03"]),
    ]
    stale = _call(database, service.resolve_scan, "08680199094206", None, dt.date(2026, 12, 1))
    assert any(n.code == "source_may_be_outdated" for n in stale.notices)


@pytest.mark.db
def test_staleness_follows_the_shared_freshness_rule(
    database: Database, db_conn: psycopg.Connection
) -> None:
    """DP17: stale after twice the cadence (14 days for weekly sources), from the stored cadence."""
    from dataclasses import replace

    reset(db_conn)
    base = inputs([titck_row("8680199094206", "AMLIPIN", ["amlodipin besilat"], "C08CA01")], [], WD)
    load(database, base)
    # Snapshot of the synthetic TİTCK artifact is 2026-11-06; weekly cadence → limit 14 days.
    fresh = _call(database, service.resolve_scan, "08680199094206", None, dt.date(2026, 11, 20))
    assert not any(n.code == "source_may_be_outdated" for n in fresh.notices)
    stale = _call(database, service.resolve_scan, "08680199094206", None, dt.date(2026, 11, 21))
    assert [n.source_id for n in stale.notices if n.code == "source_may_be_outdated"] == ["titck"]
    # A longer cadence moves the limit; the cadence is part of the dataset version.
    slower = replace(base, cadences={**base.cadences, "titck": 30})
    assert slower.dataset_version() != base.dataset_version()
    load(database, slower)
    later = _call(database, service.resolve_scan, "08680199094206", None, dt.date(2026, 11, 21))
    assert not any(n.code == "source_may_be_outdated" for n in later.notices)
    # A dataset without a stored cadence cannot be judged: the notice is shown.
    unknown = replace(base, cadences={"titck": None, "openfda_ndc": 7, "wikidata": 30})
    load(database, unknown)
    res = _call(database, service.resolve_scan, "08680199094206", None, dt.date(2026, 11, 7))
    assert any(n.code == "source_may_be_outdated" for n in res.notices)


def test_no_hard_coded_staleness_constant_remains() -> None:
    from pathlib import Path

    root = Path(service.__file__).parent
    for path in root.glob("*.py"):
        assert "STALE_AFTER" not in path.read_text(encoding="utf-8"), path.name
