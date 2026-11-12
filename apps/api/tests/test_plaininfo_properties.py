"""Plain medicine information (plain-medicine-info design §7): properties P1-P8, the route, the
spec's sentence table and the answers shared with the web app. Invented products only."""

from __future__ import annotations

import datetime as dt
import json
import re
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import duckdb
import pytest
from fastapi.testclient import TestClient
from hypothesis import given
from hypothesis import strategies as st

from janus.cascades.patterns import class_match
from janus.http_policy.routes import RouteKind, route_kind
from janus.main import create_app
from janus.notes.phrases import violations
from janus.plaininfo import router as info_router
from janus.plaininfo.groups import (
    GROUPS_FILE,
    HEADER,
    LANGUAGES,
    GroupsFileError,
    GroupTable,
    describe,
    load,
    parse,
)
from janus.plaininfo.official import (
    ES_URL,
    FR_URL,
    Holder,
    Labels,
    labels_holder,
    pages_holders,
    read_labels,
    unique_names,
)
from janus.plaininfo.router import (
    TEXT_MAX,
    Knowledge,
    MedicineInfoIn,
    answer,
    cut,
    ingredient_out,
    label_out,
    load_abrupt_stop,
    page_out,
)

TODAY = dt.date(2026, 11, 10)
TABLE = load()
KNOWLEDGE = Knowledge(TABLE, load_abrupt_stop())
PREFIXES = [p for g in TABLE.groups for p in g.prefixes]
EXCLUDED = [c for g in TABLE.groups for c in g.exclude]
REPO = Path(__file__).resolve().parents[3]
SPEC = REPO / ".kiro" / "specs" / "plain-medicine-info" / "design.md"

_UPPER = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_DIGITS = "0123456789"
_SHAPE = (_UPPER, _DIGITS, _DIGITS, _UPPER, _UPPER, _DIGITS, _DIGITS)


@st.composite
def atc_codes(draw: st.DrawFn) -> str:
    """An ingredient-level ATC code: under a covered prefix, an excluded code, or any code."""
    kind = draw(st.sampled_from(["covered", "excluded", "any"]))
    if kind == "excluded" and EXCLUDED:
        return draw(st.sampled_from(EXCLUDED))
    start = draw(st.sampled_from(PREFIXES)) if kind == "covered" else ""
    rest = [draw(st.sampled_from(chars)) for chars in _SHAPE[len(start) :]]
    return start + "".join(rest)


code_lists = st.lists(atc_codes(), max_size=8)


def oracle(code: str) -> str | None:
    """The group of a code by the table's rows, written without `Group.prefix_of`."""
    found = [
        g.id
        for g in TABLE.groups
        if any(code[: len(p)] == p for p in g.prefixes) and code not in g.exclude
    ]
    assert len(found) <= 1
    return found[0] if found else None


# --- P1-P4: groups ----------------------------------------------------------------------------
@given(code_lists)
def test_p1_a_group_is_returned_iff_a_code_is_in_it(codes: list[str]) -> None:
    """Validates: Req 2.2."""
    d = describe(TABLE, codes)
    expected: dict[str, set[str]] = {}
    for c in codes:
        gid = oracle(c)
        if gid is not None:
            expected.setdefault(gid, set()).add(c)
    assert {g.id: set(matched) for g, matched in d.groups} == expected
    matched = {c for _, cs in d.groups for c in cs}
    assert matched <= set(codes) and matched.isdisjoint(d.uncovered)
    assert matched | set(d.uncovered) == set(codes)


@given(atc_codes())
def test_p2_a_code_has_at_most_one_group(code: str) -> None:
    """Validates: Req 2.1."""
    assert sum(1 for g in TABLE.groups if g.prefix_of(code) is not None) <= 1
    group = TABLE.group_of(code)
    assert (group.id if group else None) == oracle(code)


@given(st.text(max_size=9))
def test_p2_only_ingredient_level_codes_have_a_group(text: str) -> None:
    if not re.fullmatch(r"[A-Z][0-9]{2}[A-Z]{2}[0-9]{2}", text):
        assert TABLE.group_of(text) is None
    assert TABLE.group_of("C10") is None and TABLE.group_of("C10AA") is None


@given(code_lists)
def test_p3_status_follows_the_groups(codes: list[str]) -> None:
    """Validates: Req 2.3."""
    d = describe(TABLE, codes)
    assert (d.status == "none") == (not d.groups)
    assert (d.status == "single") == (len(d.groups) == 1 and not d.uncovered)
    out = ingredient_out(KNOWLEDGE, codes, "en")
    assert out.other_uses == (bool(d.groups) and bool(d.uncovered))
    assert out.status == d.status


@given(code_lists, st.randoms(use_true_random=False))
def test_p4_order_and_repetition_do_not_matter(codes: list[str], rnd: Any) -> None:
    """Validates: Req 2.4."""
    again = codes + codes
    rnd.shuffle(again)
    assert describe(TABLE, again) == describe(TABLE, codes)


def test_group_examples() -> None:
    def ids(*codes: str) -> tuple[str, list[str]]:
        d = describe(TABLE, codes)
        return d.status, [g.id for g, _ in d.groups]

    assert ids("C08CA01") == ("single", ["calcium_channel_blocker"])
    assert ids("C08CA06") == ("none", [])  # nimodipine is excluded
    assert ids("J01CR02") == ("single", ["antibiotic"])
    assert ids("B01AC06", "N02BA01") == ("mixed", ["antiplatelet"])  # acetylsalicylic acid
    assert ids("R06AE07") == ("single", ["antihistamine"])
    assert ids("R06AE05") == ("none", [])  # meclozine: single codes only
    assert ids("N06AB04") == ("none", [])  # not covered on purpose
    assert ids("R01AD05", "R03BA02", "H02AB16")[0] == "mixed"
    assert ids() == ("none", [])


# --- P5: the table ----------------------------------------------------------------------------
def test_p5_every_group_has_every_text_within_the_rules() -> None:
    """Validates: Req 2.5, 2.6, 6.1, 6.2."""
    assert len(TABLE.groups) == 31
    for g in TABLE.groups:
        assert set(g.names) == set(g.uses) == set(LANGUAGES)
        for lang in LANGUAGES:
            for text in (g.names[lang], g.uses[lang]):
                assert text and len(text) <= 400
                assert violations(text, lang) == ([], [])
                assert not re.search(r"\b(AI|KI|IA|YZ)\b", text)
            assert not any(ch.isdigit() for ch in g.uses[lang])
            assert g.uses[lang].endswith(".")
    starts = {
        "en": "Medicines in this group ",
        "tr": "Bu gruptaki ilaçlar ",
        "de": "Medikamente dieser Gruppe ",
        "fr": "Les médicaments de ce groupe ",
        "es": "Los medicamentos de este grupo ",
        "pt": "Os medicamentos deste grupo ",
    }
    assert all(g.uses[lang].startswith(starts[lang]) for g in TABLE.groups for lang in LANGUAGES)
    assert {g.status for g in TABLE.groups} == {"not_reviewed"}


def _rows() -> list[dict[str, str]]:
    import csv
    import io

    return list(csv.DictReader(io.StringIO(GROUPS_FILE.read_text(encoding="utf-8"))))


def _text(rows: list[dict[str, str]]) -> str:
    import csv
    import io

    buf = io.StringIO()
    writer = csv.DictWriter(buf, HEADER, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("use_en", "Medicines in this group cure infections."),
        ("use_en", "Medicines in this group are safe."),
        ("use_en", "Medicines in this group are used twice a day at 500 mg."),
        ("use_en", "Medicines in this group are used for pain"),
        ("use_tr", ""),
        ("use_de", "Medikamente dieser Gruppe sind sicher."),
        ("use_fr", "x" * 401 + "."),
        ("use_es", "Los medicamentos de este grupo son una cura."),
        ("name_en", "Chosen by AI"),
        ("name_tr", " Statinler"),
        ("id", "Statin"),
        ("prefixes", "C1"),
        ("prefixes", "C10AA C10AA"),
        ("prefixes", "A02BC"),  # the prefix of another group
        ("prefixes", "J01C"),  # inside another group's prefix
        ("exclude", "C09AA01"),  # not under the row's prefixes
        ("status", "reviewed"),
    ],
)
def test_p5_the_loader_refuses_a_defect(column: str, value: str) -> None:
    rows = _rows()
    assert parse(_text(rows)).version == TABLE.version
    target = next(r for r in rows if r["id"] == "statin")
    target[column] = value
    with pytest.raises(GroupsFileError) as err:
        parse(_text(rows))
    assert len(value) < 4 or value not in str(err.value)  # the message never quotes a text


def test_p5_header_and_empty_table_are_refused() -> None:
    with pytest.raises(GroupsFileError):
        parse("id,prefixes\n")
    with pytest.raises(GroupsFileError):
        parse(",".join(HEADER) + "\n")


# --- P6: the shown label text -----------------------------------------------------------------
@given(st.lists(st.text(min_size=1, max_size=60), max_size=8), st.integers(1, 120))
def test_p6_shown_text_is_a_prefix_of_the_published_text(paragraphs: list[str], limit: int) -> None:
    """Validates: Req 1.4."""
    shown, truncated = cut(paragraphs, limit)
    assert len(shown) <= len(paragraphs)
    for i, text in enumerate(shown):
        whole = paragraphs[i]
        assert text == whole or (i == 0 and len(shown) == 1 and whole.startswith(text))
    assert sum(len(p) for p in shown) <= limit
    assert truncated == (shown != paragraphs)
    if paragraphs:
        assert shown  # something of the first paragraph is always shown


def test_p6_default_limit() -> None:
    long = "x" * (TEXT_MAX + 5)
    assert cut(["a", long]) == (["a"], True)
    assert cut([long]) == ([long[:TEXT_MAX]], True)
    assert cut(["a", "b"]) == (["a", "b"], False)


# --- runs on disk -----------------------------------------------------------------------------
SET_A = "0a000000-0000-4000-8000-00000000000a"
SET_B = "0b000000-0000-4000-8000-00000000000b"
SET_C = "0c000000-0000-4000-8000-00000000000c"
LABEL_TEXT = [
    "1 INDICATIONS AND USAGE  Exampletine tablets (invented) are indicated for the  treatment of "
    "hypertension, to lower blood pressure. ",
    "Limitations of Use: not for a hypertensive crisis.",
]
LABEL_ROWS: list[tuple[Any, ...]] = [
    (SET_A, "7", "2026-01-29", "HUMAN PRESCRIPTION DRUG", ["99999-123", "99999-124"], LABEL_TEXT),
    (SET_B, "2", None, "HUMAN OTC DRUG", ["99999-555"], ["Uses relieves sneezing (invented)."]),
    (SET_C, None, "2025-05-01", "HUMAN OTC DRUG", ["99999-555"], ["Another label, same code."]),
]


def _install(
    data_dir: Path,
    pipeline: str,
    run: str,
    columns: str,
    rows: list[tuple[Any, ...]],
    **manifest: Any,
) -> None:
    """Write a run in the pipeline's layout and point `current` at it."""
    root = data_dir / "artifacts" / pipeline
    run_dir = root / "runs" / run
    run_dir.mkdir(parents=True)
    con = duckdb.connect()
    try:
        con.execute(f"CREATE TABLE t ({columns})")
        marks = ", ".join("?" for _ in rows[0])
        for row in rows:
            con.execute(f"INSERT INTO t VALUES ({marks})", list(row))  # noqa: S608
        con.execute(f"COPY t TO '{run_dir / 'rows.parquet'}' (FORMAT PARQUET)")
    finally:
        con.close()
    doc = {"run_id": run, "pipeline": pipeline, "outcome": "succeeded"} | manifest
    (run_dir / "manifest.json").write_text(json.dumps(doc), encoding="utf-8")
    tmp = root / "current.tmp"
    tmp.symlink_to(Path("runs") / run)
    tmp.replace(root / "current")


def install_labels(data_dir: Path, run: str = "run-1", **manifest: Any) -> None:
    _install(
        data_dir,
        "us_labels",
        run,
        "set_id VARCHAR, version VARCHAR, effective_date VARCHAR, product_type VARCHAR, "
        "product_ndcs VARCHAR[], indications VARCHAR[]",
        manifest.pop("rows", LABEL_ROWS),
        **{
            "source_id": "openfda_label_indications",
            "schema_version": "us_labels-1",
            "license": "CC0 1.0 (public domain)",
            "snapshot_date": "2026-11-09",
        }
        | manifest,
    )


def install_pages(data_dir: Path) -> None:
    _install(
        data_dir,
        "eu_fr_bdpm",
        "run-fr",
        "denomination VARCHAR, cis VARCHAR, name_only BOOLEAN, specialty_missing BOOLEAN",
        [
            ("EXEMPLINE 10 mg, comprimé (inventé)", "69999991", False, False),
            ("EXEMPLINE 10 mg, comprimé (inventé)", "69999991", False, False),
            ("DEUX CODES 5 mg, gélule (inventé)", "69999992", False, False),
            ("DEUX CODES 5 mg, gélule (inventé)", "69999993", False, False),
            ("SANS FICHE (inventé)", "69999994", False, True),
        ],
        source_id="bdpm",
        schema_version="eu_fr_bdpm-1",
        license="Licence Ouverte (Etalab)",
        snapshot_date="2026-11-03",
    )
    _install(
        data_dir,
        "eu_es_cima",
        "run-es",
        "name VARCHAR, registration_number VARCHAR",
        [
            ("EJEMPLINA 10 mg COMPRIMIDOS (inventado)", "99991"),
            ("IMPORTACION PARALELA (inventado)", "99992IP"),
        ],
        source_id="cima",
        schema_version="eu_es_cima-1",
        license="Reuse with attribution (Ley 37/2007)",
        snapshot_date="2026-11-07",
    )


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    install_labels(tmp_path)
    install_pages(tmp_path)
    return tmp_path


# --- P7: official text and page ---------------------------------------------------------------
def test_p7_label_text_only_when_one_label_names_the_product(data_dir: Path) -> None:
    """Validates: Req 3.4, 3.6, 1.3 — and the text is the published paragraphs, unchanged."""
    labels = labels_holder(data_dir).value
    assert isinstance(labels, Labels) and labels.labels == 3
    out, status = label_out(labels, "999990123")
    assert status == "text" and out is not None
    assert out.paragraphs == LABEL_TEXT and not out.truncated
    assert (out.set_id, out.version, out.effective_date) == (SET_A, "7", dt.date(2026, 1, 29))
    assert out.url == f"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={SET_A}"
    assert out.source.snapshot_date == dt.date(2026, 11, 9) and out.source.run_id == "run-1"
    assert out.language == "en" and out.country == "US"
    assert label_out(labels, "999990124")[1] == "text"
    assert label_out(labels, "999990555") == (None, "several_labels")
    assert label_out(labels, "111110222") == (None, "not_found")
    assert label_out(None, "999990123") == (None, "source_unavailable")


@given(
    st.lists(
        st.tuples(st.sampled_from(["A", "B", "C", ""]), st.sampled_from(["11111111", "22222222"])),
        max_size=8,
    )
)
def test_p7_a_name_gives_a_code_iff_one_code_carries_it(pairs: list[tuple[str, str]]) -> None:
    """Validates: Req 3.5."""
    found = unique_names(list(pairs), re.compile(r"^[0-9]{8}$"))
    for name in ("A", "B", "C"):
        codes = {c for n, c in pairs if n == name}
        assert (name in found) == (len(codes) == 1)
        if name in found:
            assert found[name] in codes
    assert "" not in found


def test_p7_pages(data_dir: Path) -> None:
    pages = {c: h.value for c, h in pages_holders(data_dir).items()}
    fr, es = pages["FR"], pages["ES"]
    assert fr is not None and es is not None
    out, status = page_out(fr, "EXEMPLINE 10 mg, comprimé (inventé)")
    assert status == "page" and out is not None
    assert out.url == FR_URL.format("69999991") and out.language == "fr"
    assert out.source.source_id == "bdpm" and out.source.snapshot_date == dt.date(2026, 11, 3)
    assert page_out(fr, "DEUX CODES 5 mg, gélule (inventé)") == (None, "not_found")
    assert page_out(fr, "SANS FICHE (inventé)") == (None, "not_found")
    assert page_out(fr, "exempline 10 mg, comprimé (inventé)") == (None, "not_found")
    out, status = page_out(es, "EJEMPLINA 10 mg COMPRIMIDOS (inventado)")
    assert out is not None and out.url == ES_URL.format("99991") and out.language == "es"
    assert page_out(es, "IMPORTACION PARALELA (inventado)") == (None, "not_found")
    assert page_out(None, "x") == (None, "source_unavailable")


# --- P8: the answer ---------------------------------------------------------------------------
ALL_TEXTS = {t for g in TABLE.groups for d in (g.names, g.uses) for t in d.values()}


@given(st.lists(code_lists, max_size=4), st.sampled_from(LANGUAGES))
def test_p8_the_answer_holds_table_texts_and_the_abrupt_stop_flag(
    ingredients: list[list[str]], language: str
) -> None:
    """Validates: Req 1.2, 4.5, 4.6."""
    body = MedicineInfoIn.model_validate(
        {"language": language, "ingredients": [{"atc_codes": c} for c in ingredients]}
    )
    out = answer(KNOWLEDGE, body, None, "not_asked", TODAY)
    assert len(out.ingredients) == len(ingredients)
    for codes, ing in zip(ingredients, out.ingredients, strict=True):
        on_list = any(class_match(c, KNOWLEDGE.abrupt_stop) is not None for c in codes)
        assert ing.abrupt_stop == on_list
        for g in ing.groups:
            group = next(x for x in TABLE.groups if x.id == g.id)
            assert (g.name, g.text) == (group.names[body.language], group.uses[body.language])
            assert g.review_status == "not_reviewed" and set(g.codes) <= set(codes)
    shown = {t for i in out.ingredients for g in i.groups for t in (g.name, g.text)}
    assert shown <= ALL_TEXTS
    has_group = any(i.groups for i in out.ingredients)
    assert ("group_level_only" in out.notices) == has_group
    assert ("expert_review_not_done" in out.notices) == has_group
    assert "no_dose_information" in out.notices and out.official is None


def test_p8_abrupt_stop_examples() -> None:
    def flag(*codes: str) -> bool:
        return ingredient_out(KNOWLEDGE, codes, "en").abrupt_stop

    assert flag("C07AB02") and flag("H02AB06")  # covered groups on the list
    assert flag("N06AB04") and flag("N03AX09")  # not covered, still flagged
    assert not flag("C10AA05") and not flag("S01ED01") and not flag()


@given(st.integers(0, 60))
def test_p8_outdated_notice_after_twice_the_cadence(age: int) -> None:
    """Validates: Req 4.7."""
    labels = _fixture_labels()
    official, status = label_out(labels, "999990123")
    body = MedicineInfoIn.model_validate({"language": "en", "ingredients": []})
    out = answer(KNOWLEDGE, body, official, status, dt.date(2026, 11, 9) + dt.timedelta(days=age))
    assert ("snapshot_outdated" in out.notices) == (age > 14)
    assert {
        "official_text_not_translated",
        "label_not_verified_by_fda",
        "label_may_differ_from_box",
    } <= set(out.notices)


_LABELS: dict[str, Labels] = {}


def _fixture_labels() -> Labels:
    """The invented label run, built once in a temporary directory that lives with the process."""
    if "v" not in _LABELS:
        root = Path(tempfile.mkdtemp(prefix="janus-plaininfo-"))
        install_labels(root)
        _LABELS["v"] = read_labels(root / "artifacts" / "us_labels" / "runs" / "run-1")
    return _LABELS["v"]


# --- route ------------------------------------------------------------------------------------
@pytest.fixture
def client(data_dir: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setattr(info_router, "today", lambda: TODAY)
    app = create_app(configure_logs=False)
    app.state.medicine_labels = labels_holder(data_dir)
    app.state.medicine_pages = pages_holders(data_dir)
    with TestClient(app) as cl:
        yield cl


def test_route_is_medical_post_only() -> None:
    """Validates: Req 4.1 — codes and names in the body only."""
    (route,) = info_router.router.routes
    assert route_kind(route) is RouteKind.medical
    assert getattr(route, "methods", set[str]()) == {"POST"}
    assert getattr(route, "path", "") == "/medicine-info"


def test_route_answers_groups_and_the_official_text(client: TestClient) -> None:
    """Validates: Req 4.5, 3.4, 3.6."""
    res = client.post(
        "/medicine-info",
        json={
            "language": "tr",
            "ingredients": [{"atc_codes": ["C07AB02"]}, {"atc_codes": ["N06AB04"]}],
            "product": {"country": "US", "ndc": "99999-123"},
        },
    )
    assert res.status_code == 200 and res.headers["cache-control"] == "no-store"
    body = res.json()
    first, second = body["ingredients"]
    assert first["status"] == "single" and first["abrupt_stop"] is True
    assert first["groups"][0]["id"] == "beta_blocker"
    assert first["groups"][0]["text"].startswith("Bu gruptaki ilaçlar ")
    assert first["groups"][0]["review_status"] == "not_reviewed"
    assert second == {"status": "none", "groups": [], "other_uses": False, "abrupt_stop": True}
    assert body["official_status"] == "text" and body["official"]["paragraphs"] == LABEL_TEXT
    assert body["official"]["language"] == "en" and body["language"] == "tr"
    assert body["disclaimer"].startswith("Janus provides information, not medical advice.")
    # The same product by its package code; a French product by its published name.
    again = client.post(
        "/medicine-info",
        json={
            "language": "en",
            "ingredients": [],
            "product": {"country": "US", "ndc": "99999-123-30"},
        },
    ).json()
    assert again["official"]["set_id"] == SET_A and again["ingredients"] == []
    page = client.post(
        "/medicine-info",
        json={
            "language": "de",
            "ingredients": [{"atc_codes": ["A02BC01"]}],
            "product": {"country": "FR", "name": "EXEMPLINE 10 mg, comprimé (inventé)"},
        },
    ).json()
    assert page["official_status"] == "page" and page["official"]["kind"] == "product_page"
    assert page["ingredients"][0]["groups"][0]["text"].startswith("Medikamente dieser Gruppe ")
    none = client.post(
        "/medicine-info", json={"language": "es", "ingredients": [{"atc_codes": ["N06AB04"]}]}
    ).json()
    assert none["official"] is None and none["official_status"] == "not_asked"
    assert none["notices"] == ["no_dose_information"]


_OK_ING: list[dict[str, Any]] = [{"atc_codes": ["C10AA05"]}]
_Case = tuple[dict[str, Any], dict[str, Any]]


_REFUSED: list[_Case] = [
    ({"ingredients": _OK_ING}, {"error": "invalid_request", "fields": ["language"]}),
    (
        {"language": "ZZ", "ingredients": _OK_ING},
        {"error": "invalid_request", "fields": ["language"]},
    ),
    ({"language": "en"}, {"error": "invalid_request", "fields": ["ingredients"]}),
    (
        {"language": "en", "ingredients": []},
        {"error": "invalid_request", "fields": ["ingredients"]},
    ),
    (
        {"language": "en", "ingredients": [{"atc_codes": ["ZZSECRET"]}]},
        {"error": "invalid_request", "fields": ["ingredients"]},
    ),
    (
        {"language": "en", "ingredients": [{"atc_codes": ["C10"]}]},
        {"error": "invalid_request", "fields": ["ingredients"]},
    ),
    (
        {"language": "en", "ingredients": [{"atc_codes": ["C10AA05"] * 21}]},
        {"error": "invalid_request", "fields": ["ingredients"]},
    ),
    (
        {"language": "en", "ingredients": _OK_ING * 13},
        {"error": "invalid_request", "fields": ["ingredients"]},
    ),
    (
        {"language": "en", "ingredients": [{"atc_codes": [], "name": "ZZ"}]},
        {"error": "invalid_request", "fields": ["ingredients"]},
    ),
    (
        {"language": "en", "ingredients": _OK_ING, "ZZKEY": 1},
        {"error": "invalid_request", "fields": ["body"]},
    ),
    (
        {"language": "en", "ingredients": _OK_ING, "product": {"country": "TR", "name": "ZZ"}},
        {"error": "invalid_request", "fields": ["product"]},
    ),
    (
        {"language": "en", "ingredients": _OK_ING, "product": {"country": "US", "name": "ZZ"}},
        {"error": "invalid_request", "fields": ["product"]},
    ),
    (
        {
            "language": "en",
            "ingredients": _OK_ING,
            "product": {"country": "FR", "ndc": "99999-123"},
        },
        {"error": "invalid_request", "fields": ["product"]},
    ),
    (
        {"language": "en", "ingredients": _OK_ING, "product": {"country": "US"}},
        {"error": "invalid_request", "fields": ["product"]},
    ),
    (
        {
            "language": "en",
            "ingredients": _OK_ING,
            "product": {"country": "US", "ndc": "99999-123", "name": "ZZ"},
        },
        {"error": "invalid_request", "fields": ["product"]},
    ),
    (
        {
            "language": "en",
            "ingredients": _OK_ING,
            "product": {"country": "FR", "name": "Z" * 301},
        },
        {"error": "invalid_request", "fields": ["product"]},
    ),
    (
        {
            "language": "en",
            "ingredients": _OK_ING,
            "product": {"country": "US", "ndc": "9999912330"},
        },
        {"error": "ndc_malformed"},
    ),
    (
        {
            "language": "en",
            "ingredients": _OK_ING,
            "product": {"country": "US", "ndc": "ZZSECRET"},
        },
        {"error": "ndc_malformed"},
    ),
]


@pytest.mark.parametrize(("payload", "expected"), _REFUSED)
def test_route_refuses_bad_input_without_echoing_it(
    client: TestClient, payload: dict[str, Any], expected: dict[str, Any]
) -> None:
    """Validates: Req 4.2, 4.3."""
    res = client.post("/medicine-info", json=payload)
    assert res.status_code == 422 and res.json() == expected
    assert "ZZ" not in res.text
    bad = client.post("/medicine-info", content=b"{", headers={"content-type": "application/json"})
    assert bad.status_code == 422 and bad.json() == {"error": "invalid_request", "fields": ["body"]}


def test_route_without_runs_still_answers_the_groups(tmp_path: Path) -> None:
    """Validates: Req 3.7, 4.4 — no run, a failed run, a run of another schema."""
    app = create_app(configure_logs=False)
    app.state.medicine_labels = labels_holder(tmp_path)
    app.state.medicine_pages = pages_holders(tmp_path)
    ask: dict[str, Any] = {
        "language": "en",
        "ingredients": [{"atc_codes": ["C10AA05"]}],
        "product": {"country": "US", "ndc": "99999-123"},
    }
    with TestClient(app) as cl:
        body = cl.post("/medicine-info", json=ask).json()
        assert body["official"] is None and body["official_status"] == "source_unavailable"
        assert body["ingredients"][0]["groups"][0]["id"] == "statin"
        install_labels(tmp_path, "run-failed", outcome="failed")
        assert cl.post("/medicine-info", json=ask).json()["official_status"] == "source_unavailable"
        install_labels(tmp_path, "run-other", schema_version="us_labels-0")
        assert cl.post("/medicine-info", json=ask).json()["official_status"] == "source_unavailable"
        fr: dict[str, Any] = {
            "language": "en",
            "ingredients": [],
            "product": {"country": "FR", "name": "x"},
        }
        assert cl.post("/medicine-info", json=fr).json()["official_status"] == "source_unavailable"
        # Without the group table or the abrupt-stop list nothing is served.
        app.state.medicine_info = None
        res = cl.post("/medicine-info", json=ask)
        assert res.status_code == 503 and res.json() == {"error": "medicine_info_unavailable"}
    assert Holder(None, "us_labels", read_labels).value is None


def test_a_new_run_is_read_without_a_restart(client: TestClient, data_dir: Path) -> None:
    ask: dict[str, Any] = {
        "language": "en",
        "ingredients": [],
        "product": {"country": "US", "ndc": "11111-222"},
    }
    assert client.post("/medicine-info", json=ask).json()["official_status"] == "not_found"
    rows = [
        *LABEL_ROWS,
        (
            "0d000000-0000-4000-8000-00000000000d",
            "1",
            None,
            "HUMAN OTC DRUG",
            ["11111-222"],
            ["New."],
        ),
    ]
    install_labels(data_dir, "run-2", rows=rows, snapshot_date="2026-11-10")
    body = client.post("/medicine-info", json=ask).json()
    assert body["official"]["paragraphs"] == ["New."]
    assert body["official"]["source"]["run_id"] == "run-2"


def test_real_runs_when_present() -> None:
    """The current runs of this machine, when there are any (skipped in CI)."""
    labels = labels_holder(REPO / ".data").value
    if labels is None:
        pytest.skip("no us_labels run in .data")
    assert labels.labels > 10_000 and len(labels.by_product) > labels.labels
    key = next(k for k, v in labels.by_product.items() if len(v) == 1)
    out, status = label_out(labels, key)
    assert status == "text" and out is not None and out.paragraphs
    assert sum(len(p) for p in out.paragraphs) <= TEXT_MAX


# --- the spec's table and the contract shared with the web app --------------------------------
def spec_table(table: GroupTable = TABLE) -> str:
    """The groups and their exact sentences as design.md §3 lists them."""
    lines = [
        f"{len(table.groups)} groups, {len(table.groups) * 2 * len(LANGUAGES)} texts. "
        "Status of every row: `not_reviewed`.",
        "",
        "| Group id | ATC prefixes (excluded codes) | Lang. | Name | Sentence |",
        "|---|---|---|---|---|",
    ]
    for g in table.groups:
        codes = " ".join(g.prefixes)
        if g.exclude:
            codes += f" (not {' '.join(sorted(g.exclude))})"
        for i, lang in enumerate(LANGUAGES):
            lines.append(
                f"| {f'`{g.id}`' if i == 0 else ''} | {codes if i == 0 else ''} | {lang} "
                f"| {g.names[lang]} | {g.uses[lang]} |"
            )
    return "\n".join(lines) + "\n"


_START = "<!-- groups-table:start"
_END = "<!-- groups-table:end -->"


def test_the_spec_lists_the_exact_sentences() -> None:
    """design.md §3 is generated from groups.csv; rewrite it with
    `python -m tests.test_plaininfo_properties` after a change of the table."""
    text = SPEC.read_text(encoding="utf-8")
    start = text.index("\n", text.index(_START)) + 1
    assert text[start : text.index(_END)] == spec_table()


WEB_FIXTURE = (
    Path(__file__).resolve().parents[2] / "web" / "src" / "plaininfo" / "fixtures" / "info.json"
)


def web_fixture() -> dict[str, Any]:
    """Answers for invented products: a US product with a label text (Turkish interface), a
    French product with a page and a mixed ingredient (German), a long label that is cut
    (English), and a medicine Janus has nothing for (Spanish)."""
    root = Path(tempfile.mkdtemp(prefix="janus-plaininfo-fixture-"))
    long_text = [
        "1 INDICATIONS AND USAGE " + "Exampletine (invented) is indicated. " * 200,
        "Next.",
    ]
    install_labels(
        root,
        rows=[
            *LABEL_ROWS,
            (
                "0e000000-0000-4000-8000-00000000000e",
                "3",
                "2026-02-02",
                "HUMAN PRESCRIPTION DRUG",
                ["99999-777"],
                long_text,
            ),
        ],
    )
    install_pages(root)
    labels = labels_holder(root).value
    fr = pages_holders(root)["FR"].value

    def ask(payload: dict[str, Any], official: Any, status: Any) -> dict[str, Any]:
        body = MedicineInfoIn.model_validate(payload)
        return answer(KNOWLEDGE, body, official, status, TODAY).model_dump(mode="json")

    return {
        "us": ask(
            {
                "language": "tr",
                "ingredients": [{"atc_codes": ["C07AB02"]}, {"atc_codes": ["C03AA03"]}],
            },
            *label_out(labels, "999990123"),
        ),
        "fr": ask(
            {"language": "de", "ingredients": [{"atc_codes": ["B01AC06", "N02BA01"]}]},
            *page_out(fr, "EXEMPLINE 10 mg, comprimé (inventé)"),
        ),
        "long": ask(
            {"language": "en", "ingredients": [{"atc_codes": ["R01AD05", "R03BA02"]}]},
            *label_out(labels, "999990777"),
        ),
        "none": ask(
            {"language": "es", "ingredients": [{"atc_codes": ["N06AB04"]}]}, None, "not_asked"
        ),
    }


def test_web_fixture_is_the_api_answer() -> None:
    """The answers the web tests decode and render are what this API returns (design §6)."""
    assert json.loads(WEB_FIXTURE.read_text(encoding="utf-8")) == web_fixture()


DEMO_DIR = Path(__file__).resolve().parents[2] / "web" / "src" / "demo"
DEMO_RECORDED = DEMO_DIR / "plain-info.recorded.json"


def demo_recorded() -> dict[str, Any]:
    """The group answers for every ingredient code set of the demo lists, in five languages.
    The web app answers from this file in demo mode, where nothing reaches the API."""
    code_sets: set[tuple[str, ...]] = {()}  # an ingredient without a code is asked too
    for patient in ("istanbul", "ohio", "cologne"):
        fixture = json.loads((DEMO_DIR / "fixtures" / f"{patient}.json").read_text("utf-8"))
        for item in fixture["items"]:
            for candidate in item["resolution"]["candidates"]:
                parts = candidate["ingredients"] if candidate["kind"] == "product" else [candidate]
                for part in parts:
                    codes = {a["code"] for a in part["atc_codes"]}
                    kept = sorted(
                        c for c in codes if re.fullmatch(r"[A-Z][0-9]{2}[A-Z]{2}[0-9]{2}", c)
                    )
                    code_sets.add(tuple(kept[:20]))
    return {
        "groups_version": TABLE.version,
        "ingredients": {
            lang: {
                " ".join(codes): ingredient_out(KNOWLEDGE, codes, lang).model_dump(mode="json")
                for codes in sorted(code_sets)
            }
            for lang in LANGUAGES
        },
    }


def test_demo_recorded_file_is_the_api_answer() -> None:
    """Demo mode shows exactly what the API answers for the demo lists' codes (design DP-M12)."""
    assert json.loads(DEMO_RECORDED.read_text(encoding="utf-8")) == demo_recorded()


if __name__ == "__main__":
    DEMO_RECORDED.write_text(
        json.dumps(demo_recorded(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    doc = SPEC.read_text(encoding="utf-8")
    a = doc.index("\n", doc.index(_START)) + 1
    SPEC.write_text(doc[:a] + spec_table() + doc[doc.index(_END) :], encoding="utf-8")
    WEB_FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    WEB_FIXTURE.write_text(
        json.dumps(web_fixture(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
