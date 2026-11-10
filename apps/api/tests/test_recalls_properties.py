"""Recall check: text reading, matching, answer and route (recall-check design §8).
Invented records only; no real recall text and no network."""

from __future__ import annotations

import datetime as dt
import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import duckdb
import pytest
from fastapi.testclient import TestClient
from hypothesis import given
from hypothesis import strategies as st

from janus.http_policy.routes import RouteKind, route_kind
from janus.main import create_app
from janus.recalls import router as recalls_router
from janus.recalls.codes import LOT_EXAMPLES, lot_codes, ndc_keys, normalise_lot
from janus.recalls.match import (
    Match,
    Query,
    Recall,
    build_index,
    find,
    query_from_input,
    recall_from_row,
)
from janus.recalls.router import CODE_INFO_MAX, MAX_MATCHES, check
from janus.recalls.store import COLUMNS, Loaded, RecallsHolder
from janus.resolution.ndc import LAYOUTS, NdcError, package11, product9

TODAY = dt.date(2026, 11, 10)
STATUSES = ("Ongoing", "Completed", "Terminated")

# --- strategies ------------------------------------------------------------------------------
# A small code space, so generated queries and records collide often.
labelers = st.sampled_from(["0071", "00071", "68462", "0591", "99999"])
products = st.sampled_from(["0155", "267", "3745", "012"])
packages = st.sampled_from(["30", "1", "23", "00"])


@st.composite
def package_ndcs(draw: st.DrawFn) -> str:
    """A hyphenated package NDC in one of the three published layouts."""
    a, b, c = draw(st.sampled_from(sorted(LAYOUTS.values())))
    digits = draw(st.text("0123456789", min_size=a + b + c, max_size=a + b + c))
    return f"{digits[:a]}-{digits[a : a + b]}-{digits[a + b :]}"


lot_alphabet = "ABCXYZ0123456789"
lots = st.text(lot_alphabet, min_size=3, max_size=10).filter(lambda s: any(c.isdigit() for c in s))


@st.composite
def recalls(draw: st.DrawFn, number: int = 0) -> Recall:
    pkgs = draw(st.frozensets(st.builds(package11, labelers, products, packages), max_size=3))
    prods = draw(st.frozensets(st.builds(product9, labelers, products)))
    status = draw(st.sampled_from(STATUSES))
    report = draw(st.none() | st.dates(dt.date(2012, 1, 1), dt.date(2026, 12, 31)))
    return Recall(
        recall_number=f"D-{number:04d}-2026",
        event_id=None,
        status=status,
        classification=draw(st.sampled_from(["Class I", "Class II", "Class III"])),
        product_description="Invented product",
        code_info=None,
        more_code_info=None,
        reason_for_recall="Invented reason",
        recalling_firm="Invented firm",
        recall_initiation_date=None,
        center_classification_date=None,
        report_date=report.isoformat() if report else None,
        termination_date="2026-01-01" if status == "Terminated" else None,
        package_keys=pkgs,
        product_keys=prods | {p[:9] for p in pkgs},
        lot_codes=draw(st.frozensets(lots, max_size=4)),
    )


@st.composite
def recall_lists(draw: st.DrawFn) -> list[Recall]:
    n = draw(st.integers(0, 12))
    return [draw(recalls(number=i)) for i in range(n)]


@st.composite
def query_st(draw: st.DrawFn) -> Query:
    labeler, product = draw(labelers), draw(products)
    package = draw(st.none() | packages)
    return Query(
        product=package11(labeler, product, "0")[:9],
        package=None if package is None else package11(labeler, product, package),
        lot=draw(st.none() | lots),
    )


queries = query_st()


def _numbers(matches: list[Match]) -> list[str]:
    return [m.recall.recall_number for m in matches]


# --- P1-P6: matching ---------------------------------------------------------------------------
@given(recall_lists(), queries)
def test_p1_a_record_is_reported_iff_it_names_the_code(rs: list[Recall], q: Query) -> None:
    """Validates: Req 3.1 — no match without a record that names the product or package code,
    and no such record is left out."""
    found = find(build_index(rs), q)
    expected = {
        r.recall_number
        for r in rs
        if q.product in r.product_keys or (q.package is not None and q.package in r.package_keys)
    }
    assert set(_numbers(found)) == expected
    assert len(found) == len(expected)  # each record once


@given(recall_lists(), queries)
def test_p2_ndc_level_is_package_only_on_the_package_key(rs: list[Recall], q: Query) -> None:
    """Validates: Req 3.2."""
    for m in find(build_index(rs), q):
        named = q.package is not None and q.package in m.recall.package_keys
        assert m.ndc_match == ("package" if named else "product")


@given(recall_lists(), queries)
def test_p3_lot_match_is_equality_of_normalised_codes(rs: list[Recall], q: Query) -> None:
    """Validates: Req 3.3 — listed iff the normalised lot is one of the record's lot codes."""
    for m in find(build_index(rs), q):
        if q.lot is None:
            assert m.lot_match == "not_given"
        else:
            assert m.lot_match == ("listed" if q.lot in m.recall.lot_codes else "not_listed")


@given(recall_lists(), queries, st.none() | lots)
def test_p4_the_lot_never_adds_or_removes_a_record(
    rs: list[Recall], q: Query, other: str | None
) -> None:
    """Validates: Req 3.4 — a lot that is not listed keeps the product-level match."""
    index = build_index(rs)
    with_lot = find(index, q)
    without = find(index, Query(q.product, q.package, other))
    assert sorted(_numbers(with_lot)) == sorted(_numbers(without))


@given(recall_lists(), queries)
def test_p5_a_terminated_recall_is_labelled_terminated(rs: list[Recall], q: Query) -> None:
    """Validates: Req 3.5, 4.5 — terminated iff the published status says so; never dropped."""
    index = build_index(rs)
    loaded = Loaded(index, "run", TODAY, "CC0 1.0 (public domain)")
    out = check(loaded, q, TODAY)
    by_number = {r.recall_number: r for r in rs}
    assert len(out.matches) == min(len(find(index, q)), MAX_MATCHES)
    for m in out.matches:
        source = by_number[m.recall_number]
        assert m.status == source.status
        assert m.terminated == (source.status == "Terminated")
        if m.terminated:
            assert m.termination_date is not None


@given(recall_lists(), queries, st.randoms(use_true_random=False))
def test_p6_answer_does_not_depend_on_record_order(rs: list[Recall], q: Query, rnd: Any) -> None:
    """Validates: Req 3.6 — same answer for any order; lot listed first, package before product,
    newer report first."""
    shuffled = list(rs)
    rnd.shuffle(shuffled)
    found = find(build_index(rs), q)
    assert found == find(build_index(shuffled), q)
    keys = [
        (
            m.lot_match != "listed",
            m.ndc_match != "package",
            -int((m.recall.report_date or "0000-00-00").replace("-", "")),
            m.recall.recall_number,
        )
        for m in found
    ]
    assert keys == sorted(keys)


# --- P7: reading NDCs from the record's text --------------------------------------------------
noise = st.text("abcdefghij XYZ.,;()", max_size=12)


@given(package_ndcs(), noise, noise)
def test_p7_a_written_package_ndc_is_read_with_its_product(ndc: str, a: str, b: str) -> None:
    """Validates: Req 3.1, glossary — a hyphenated package NDC in the text gives its 11-digit key
    and the 9-digit product key."""
    pkgs, prods = ndc_keys(f"{a} {ndc} {b}")
    key = package11(*ndc.split("-"))
    assert key in pkgs and key[:9] in prods


@given(st.text("abcdefghijklmnopqrstuvwxyz NDC:#.,-", max_size=60))
def test_p7_text_without_digits_names_no_code(text: str) -> None:
    assert ndc_keys(text) == (frozenset(), frozenset())


@given(st.lists(package_ndcs(), max_size=3), st.text(max_size=40))
def test_p7_every_key_read_is_written_in_the_text(ndcs: list[str], other: str) -> None:
    """Validates: Req 3.1 — a key is never invented: its digits (without padding zeros) stand in
    the text in order."""
    text = " ; ".join([other, *ndcs])
    pkgs, prods = ndc_keys(text)
    digits = re.sub(r"[^0-9]", "", text)
    for key in pkgs:
        assert (
            any(
                key == package11(*m.group(0).split("-"))
                for m in re.finditer(r"[0-9]+-[0-9]+-[0-9]+", text)
            )
            or key in digits
        )
    for key in prods:
        assert key in {p[:9] for p in pkgs} or re.search(r"(?i)NDC", text)


def test_p7_examples() -> None:
    """Published shapes (invented numbers): package NDCs anywhere, product NDCs and 11 digits
    only after the word NDC, ten plain digits and other number shapes never."""
    pkgs, prods = ndc_keys(
        "Tablets, NDC 99999-123-30; b) NDC# 0999-1234-05, NDC: 99999-0456, NDC 00999123405, "
        "NDC 9999912330, call 1-800-555-0100, made 2025-10-12, Lot 37-883948, UPC 3 99999 12330 1"
    )
    assert pkgs == {"99999012330", "00999123405"}
    assert prods == {"999990123", "009991234", "999990456"}
    assert ndc_keys(None, "") == (frozenset(), frozenset())


def test_p7_the_openfda_block_is_not_read() -> None:
    """Validates: design DP-R2 — openFDA's added product list never produces a match."""
    row = {
        "recall_number": "D-0001-2026",
        "product_description": "Invented tablets, no code written",
        "code_info": "Lot AB1234",
        "openfda": {"product_ndc": ["99999-123"], "package_ndc": ["99999-123-30"]},
    }
    recall = recall_from_row(row)
    assert recall.product_keys == frozenset() and recall.package_keys == frozenset()
    assert find(build_index([recall]), query_from_input("99999-123-30")) == []


# --- P8: lot codes ----------------------------------------------------------------------------
@pytest.mark.parametrize(("written", "normalised"), LOT_EXAMPLES)
def test_p8_lot_examples_shared_with_the_web_app(written: str, normalised: str) -> None:
    assert normalise_lot(written) == normalised


@given(st.text(max_size=30))
def test_p8_normalised_lot_is_ascii_upper_alphanumeric_and_stable(lot: str) -> None:
    """Validates: glossary — only ASCII letters and digits, upper-cased; idempotent."""
    out = normalise_lot(lot)
    assert re.fullmatch(r"[0-9A-Z]*", out)
    assert normalise_lot(out) == out


@given(lots, st.sampled_from(["-", " ", "/", "."]), st.integers(1, 9))
def test_p8_lot_written_differently_is_the_same_lot(lot: str, sep: str, at: int) -> None:
    """Validates: Req 3.3 — case and separators inside a lot do not matter."""
    cut = min(at, len(lot) - 1)
    assert normalise_lot(lot[:cut].lower() + sep + lot[cut:]) == lot


@given(st.lists(lots, min_size=1, max_size=5), lots)
def test_p8_a_lot_is_listed_iff_it_is_a_token_of_the_lot_text(codes: list[str], lot: str) -> None:
    """Validates: Req 3.3 — no prefix, substring or similarity: only a whole token."""
    text = "Lot #: " + ", ".join(codes) + "; Exp 06/2027"
    assert (lot in lot_codes(text)) == (lot in codes)


@given(lots, st.text(lot_alphabet, min_size=1, max_size=3))
def test_p8_a_longer_or_shorter_code_is_another_lot(lot: str, extra: str) -> None:
    text = f"Lot: {lot}"
    assert lot + extra not in lot_codes(text)
    assert extra + lot not in lot_codes(text)


def test_p8_lot_text_examples() -> None:
    """Dates next to a lot are not lot codes; a hyphen, a slash or an @ stays inside one code."""
    text = (
        "Lot Numbers: 19233792, Exp.: 8/2025; 19243163, 19243162, Exp.:7/2026;19243884. "
        "Lot# 396689, Use by 12-13-16; Lot # 37-883948, Exp 05/02/2023; a) CC/004/24-25; "
        "07282026@2, BUD: 9/11/2026; (B136HN) & M915602; All lots within expiry"
    )
    assert lot_codes(text) == {
        "19233792",
        "19243163",
        "19243162",
        "19243884",
        "396689",
        "37883948",
        "CC0042425",
        "072820262",
        "B136HN",
        "M915602",
    }
    assert lot_codes(None, "", "All lots") == frozenset()


# --- P9: the answer ----------------------------------------------------------------------------
def _row(number: str = "D-0001-2026", **over: Any) -> dict[str, Any]:
    base: dict[str, Any] = dict.fromkeys(COLUMNS)
    base |= {
        "recall_number": number,
        "event_id": "90001",
        "status": "Ongoing",
        "classification": "Class II",
        "product_description": "Exampletine Tablets 10 mg (invented), NDC 99999-123-30",
        "code_info": "Lot #: AB1234, Exp 06/2027",
        "reason_for_recall": "Failed Dissolution Specifications",
        "recalling_firm": "Example Labs (invented)",
        "recall_initiation_date": "2026-01-05",
        "report_date": "2026-01-28",
    }
    return base | over


def _loaded(rows: list[dict[str, Any]], snapshot: dt.date = TODAY) -> Loaded:
    index = build_index(recall_from_row(r) for r in rows)
    return Loaded(index, "run-1", snapshot, "CC0 1.0 (public domain)")


@given(st.integers(0, 40))
def test_p9_at_most_twenty_matches_with_the_total(n: int) -> None:
    """Validates: Req 4.4."""
    rows = [_row(f"D-{i:04d}-2026") for i in range(n)]
    out = check(_loaded(rows), query_from_input("99999-123-30"), TODAY)
    assert out.total_matches == n and len(out.matches) == min(n, MAX_MATCHES)
    assert out.truncated == (n > MAX_MATCHES)


@given(st.integers(0, 3 * CODE_INFO_MAX))
def test_p9_long_lot_text_is_cut_and_flagged_but_still_matched(length: int) -> None:
    """Validates: Req 4.5 — the quote is cut at 2,000 characters; the lot codes are not."""
    text = "Lot " + "X1 " * (length // 3) + "ZZ9999"
    out = check(_loaded([_row(code_info=text)]), query_from_input("99999-123-30", "zz-9999"), TODAY)
    m = out.matches[0]
    assert m.code_info is not None and len(m.code_info) <= CODE_INFO_MAX
    assert m.code_info_truncated == (len(text) > CODE_INFO_MAX)
    assert m.code_info == text[:CODE_INFO_MAX]
    assert m.lot_match == "listed" and "ZZ9999" in m.lot_codes


@given(st.integers(0, 60))
def test_p9_outdated_notice_after_twice_the_cadence(age: int) -> None:
    """Validates: Req 4.8 — more than 14 days after the data date."""
    out = check(
        _loaded([_row()], TODAY - dt.timedelta(days=age)), query_from_input("99999-123"), TODAY
    )
    assert ("snapshot_outdated" in out.notices) == (age > 14)
    assert {"us_records_only", "absence_is_not_clearance", "status_as_published"} <= set(
        out.notices
    )


def test_p9_answer_quotes_the_record_and_links_to_it() -> None:
    """Validates: Req 4.4, 4.5."""
    rows = [
        _row(),
        _row("D-0002-2025", status="Terminated", termination_date="2025-09-01", code_info="All"),
        _row("D-0003-2026", product_description="Other product, NDC 11111-222-33"),
    ]
    out = check(_loaded(rows), query_from_input("99999-123-30", "ab 1234"), TODAY)
    assert out.region == "US" and out.ndc_level == "package" and out.lot_given
    assert out.source.records == 3 and out.source.records_with_ndc == 3
    assert out.source.snapshot_date == TODAY and out.source.license.startswith("CC0")
    first, second = out.matches
    assert (first.recall_number, first.ndc_match, first.lot_match) == (
        "D-0001-2026",
        "package",
        "listed",
    )
    assert first.reason_for_recall == "Failed Dissolution Specifications"
    assert first.report_date == dt.date(2026, 1, 28) and not first.terminated
    assert first.record_url == (
        "https://api.fda.gov/drug/enforcement.json"
        "?search=recall_number.exact:%22D-0001-2026%22&limit=1"
    )
    assert (second.recall_number, second.lot_match) == ("D-0002-2025", "not_listed")
    assert second.terminated and second.termination_date == dt.date(2025, 9, 1)
    assert "medical advice" in out.disclaimer


@given(st.text(max_size=24))
def test_p9_query_accepts_only_unambiguous_ndcs(text: str) -> None:
    """Validates: Req 4.2 — whatever is accepted names exactly one product; ten plain digits
    are refused."""
    try:
        q = query_from_input(text)
    except NdcError:
        return
    assert re.fullmatch(r"[0-9]{9}", q.product)
    assert q.package is None or (
        re.fullmatch(r"[0-9]{11}", q.package) and q.package[:9] == q.product
    )
    assert len(re.sub(r"[^0-9]", "", text)) != 10 or "-" in text


def test_p9_ten_plain_digits_are_refused() -> None:
    with pytest.raises(NdcError):
        query_from_input("9999912330")
    assert query_from_input("NDC 99999-123-30") == Query("999990123", "99999012330", None)
    assert query_from_input("99999-0123") == Query("999990123", None, None)
    assert query_from_input("99999012330", " ab-1234 ").lot == "AB1234"


# --- store and route --------------------------------------------------------------------------
def _install(data_dir: Path, run: str, rows: list[dict[str, Any]], **manifest: Any) -> None:
    """Write a run in the pipeline's layout and point `current` at it."""
    root = data_dir / "artifacts" / "us_recalls"
    run_dir = root / "runs" / run
    run_dir.mkdir(parents=True)
    con = duckdb.connect()
    try:
        cols = ", ".join(f"{c} VARCHAR" for c in COLUMNS)
        con.execute(f"CREATE TABLE t ({cols})")
        marks = ", ".join("?" for _ in COLUMNS)
        for row in rows:
            con.execute(f"INSERT INTO t VALUES ({marks})", [row[c] for c in COLUMNS])  # noqa: S608
        con.execute(f"COPY t TO '{run_dir / 'rows.parquet'}' (FORMAT PARQUET)")
    finally:
        con.close()
    doc = {
        "run_id": run,
        "pipeline": "us_recalls",
        "source_id": "openfda_enforcement",
        "license": "CC0 1.0 (public domain)",
        "snapshot_date": "2026-11-03",
        "schema_version": "us_recalls-1",
        "outcome": "succeeded",
    } | manifest
    (run_dir / "manifest.json").write_text(json.dumps(doc), encoding="utf-8")
    link = root / "current"
    tmp = root / "current.tmp"
    tmp.symlink_to(Path("runs") / run)
    tmp.replace(link)


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    _install(tmp_path, "run-1", [_row()])
    monkeypatch.setattr(recalls_router, "today", lambda: TODAY)
    app = create_app(configure_logs=False)
    app.state.recalls = RecallsHolder(tmp_path)
    with TestClient(app) as cl:
        yield cl


def test_route_is_medical_post_only() -> None:
    """Validates: Req 4.1, 4.7 — codes in the body only."""
    (route,) = recalls_router.router.routes
    assert route_kind(route) is RouteKind.medical
    assert getattr(route, "methods", set[str]()) == {"POST"}
    assert getattr(route, "path", "") == "/recalls/check"


def test_route_answers_matches_and_the_checked_empty_state(client: TestClient) -> None:
    """Validates: Req 4.4, 4.5, 4.7."""
    res = client.post("/recalls/check", json={"ndc": "99999-123-30", "lot": "AB1234"})
    assert res.status_code == 200 and res.headers["cache-control"] == "no-store"
    body = res.json()
    assert body["source"]["snapshot_date"] == "2026-11-03" and body["region"] == "US"
    assert [m["recall_number"] for m in body["matches"]] == ["D-0001-2026"]
    assert body["matches"][0]["lot_match"] == "listed"
    none = client.post("/recalls/check", json={"ndc": "11111-222"}).json()
    assert none["matches"] == [] and none["total_matches"] == 0
    assert "absence_is_not_clearance" in none["notices"] and none["source"]["records"] == 1


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"ndc": "9999912330"}, {"error": "ndc_malformed"}),
        ({"ndc": "ZZSECRET"}, {"error": "ndc_malformed"}),
        ({"ndc": ""}, {"error": "invalid_request", "fields": ["ndc"]}),
        ({"lot": "AB1234"}, {"error": "invalid_request", "fields": ["ndc"]}),
        ({"ndc": "99999-123", "lot": "ZZ SECRET"}, {"error": "invalid_request", "fields": ["lot"]}),
        ({"ndc": "99999-123", "lot": "---"}, {"error": "invalid_request", "fields": ["lot"]}),
        ({"ndc": "99999-123", "lot": "Z" * 21}, {"error": "invalid_request", "fields": ["lot"]}),
        ({"ndc": "99999-123", "serial": "ZZ1"}, {"error": "invalid_request", "fields": ["body"]}),
        ({"ndc": "99999-123", "ZZKEY": 1}, {"error": "invalid_request", "fields": ["body"]}),
        ({"ndc": 99999123}, {"error": "invalid_request", "fields": ["ndc"]}),
    ],
)
def test_route_refuses_bad_input_without_echoing_it(
    client: TestClient, payload: dict[str, Any], expected: dict[str, Any]
) -> None:
    """Validates: Req 4.2, 4.3."""
    res = client.post("/recalls/check", json=payload)
    assert res.status_code == 422 and res.json() == expected
    assert "ZZ" not in res.text
    bad = client.post("/recalls/check", content=b"{", headers={"content-type": "application/json"})
    assert bad.status_code == 422 and bad.json() == {"error": "invalid_request", "fields": ["body"]}


def test_route_answers_503_without_a_usable_run(tmp_path: Path) -> None:
    """Validates: Req 4.6 — no run, a failed run, a run of another schema."""
    app = create_app(configure_logs=False)
    app.state.recalls = RecallsHolder(tmp_path)
    with TestClient(app) as cl:
        res = cl.post("/recalls/check", json={"ndc": "99999-123"})
        assert res.status_code == 503 and res.json() == {"error": "recalls_unavailable"}
        _install(tmp_path, "run-failed", [_row()], outcome="failed")
        assert cl.post("/recalls/check", json={"ndc": "99999-123"}).status_code == 503
        _install(tmp_path, "run-review", [_row()], outcome="needs_review")
        assert cl.post("/recalls/check", json={"ndc": "99999-123"}).status_code == 503
        _install(tmp_path, "run-other", [_row()], schema_version="us_recalls-0")
        assert cl.post("/recalls/check", json={"ndc": "99999-123"}).status_code == 503
        # A bad NDC is refused before the data is needed.
        assert cl.post("/recalls/check", json={"ndc": "x"}).status_code == 422
    assert RecallsHolder(None).value is None


def test_a_new_run_is_read_without_a_restart(client: TestClient, tmp_path: Path) -> None:
    """Validates: Req 4.9."""
    ask = {"ndc": "11111-222-33"}
    assert client.post("/recalls/check", json=ask).json()["total_matches"] == 0
    rows = [_row(), _row("D-0009-2026", product_description="New, NDC 11111-222-33")]
    _install(tmp_path, "run-2", rows, snapshot_date="2026-11-10")
    body = client.post("/recalls/check", json=ask).json()
    assert body["total_matches"] == 1 and body["source"]["run_id"] == "run-2"
    assert body["source"]["snapshot_date"] == "2026-11-10"


def test_real_run_when_present() -> None:
    """The current `us_recalls` run of this machine, when there is one (skipped in CI)."""
    data_dir = Path(__file__).resolve().parents[3] / ".data"
    loaded = RecallsHolder(data_dir).value
    if loaded is None:
        pytest.skip("no us_recalls run in .data")
    assert loaded.index.records > 10_000
    assert 0 < loaded.index.records_with_ndc < loaded.index.records
    for group in loaded.index.by_product.values():
        for recall in group:
            assert all(re.fullmatch(r"[0-9]{11}", k) for k in recall.package_keys)
            assert all(re.fullmatch(r"[0-9]{9}", k) for k in recall.product_keys)
            assert all(re.fullmatch(r"[0-9A-Z]{3,20}", c) for c in recall.lot_codes)


# --- contract shared with the web app ---------------------------------------------------------
WEB_FIXTURE = (
    Path(__file__).resolve().parents[2] / "web" / "src" / "recall" / "fixtures" / "check.json"
)


def web_fixture() -> dict[str, Any]:
    """Three invented records for one product: the lot listed, a terminated recall of another
    lot, and a record of another package size with a long lot text."""
    rows = [
        _row(),
        _row(
            "D-0002-2025",
            status="Terminated",
            termination_date="2025-09-01",
            report_date="2025-03-12",
            classification="Class III",
            code_info="Lot: ZX9001, Exp 01/2026",
            reason_for_recall="Labeling: Incorrect or Missing Lot and/or Exp Date",
        ),
        _row(
            "D-0003-2026",
            report_date="2026-02-04",
            classification="Class I",
            product_description="Exampletine Tablets 10 mg (invented), 90-count, NDC 99999-123-90",
            code_info="All lots within expiry; " + ", ".join(f"QQ{i:04d}" for i in range(300)),
            reason_for_recall="Presence of Foreign Tablets/Capsules",
        ),
    ]
    out = check(_loaded(rows, dt.date(2026, 11, 3)), query_from_input("99999012330"), TODAY)
    return out.model_dump(mode="json")


def test_web_fixture_is_the_api_answer() -> None:
    """The answer the web tests decode and render is what this API returns (design §7).
    Rewrite it with `python -m tests.test_recalls_properties` after a contract change."""
    assert json.loads(WEB_FIXTURE.read_text(encoding="utf-8")) == web_fixture()


if __name__ == "__main__":
    WEB_FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    WEB_FIXTURE.write_text(
        json.dumps(web_fixture(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
