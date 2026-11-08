"""Tests for the `eu_fr_bdpm` job (P19–P23, Req 11)."""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence

import pytest
from hypothesis import given
from hypothesis import strategies as st

from janus_pipelines.core.canonical import Json
from janus_pipelines.core.validation import SchemaMismatchError, check_accounting
from janus_pipelines.jobs.eu_fr_bdpm import (
    CIP,
    CIS,
    COMPO,
    DECODINGS,
    FILES,
    decode_file,
    parse_bdpm,
    parse_update_dates,
    valid_cip13,
)

# Characters that exist in Windows-1252 and in UTF-8, plus spaces, quotes and accents.
ALPHABET = (
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 ,.;:%()-/+'\"\u2019°²µ"
    "éèêëàâùûôîïçœÉÈÀÇ"
)
CELL = st.text(alphabet=ALPHABET, max_size=25)
DATES = {n: "2026-11-03" for n in FILES}


def check_digit13(first12: str) -> str:
    total = sum(int(d) * (3 if i % 2 else 1) for i, d in enumerate(first12))
    return str((10 - total % 10) % 10)


def make_cip13(body8: str) -> str:
    first12 = "3400" + body8
    return first12 + check_digit13(first12)


BODY8 = st.text(alphabet="0123456789", min_size=8, max_size=8)
VALID_CIP13 = BODY8.map(make_cip13)


def render(
    cis_rows: Sequence[Sequence[str]],
    cip_rows: Sequence[Sequence[str]],
    compo_rows: Sequence[Sequence[str]],
    *,
    crlf: bool = True,
) -> dict[str, bytes]:
    """The three BDPM files: CIS and COMPO use CRLF and Windows-1252, CIP uses LF and UTF-8."""
    eol = "\r\n" if crlf else "\n"

    def blob(name: str, rows: Sequence[Sequence[str]], line_end: str) -> bytes:
        return "".join("\t".join(r) + line_end for r in rows).encode(DECODINGS[name])

    return {
        CIS: blob(CIS, cis_rows, eol),
        CIP: blob(CIP, cip_rows, "\n"),
        COMPO: blob(COMPO, compo_rows, eol),
    }


def cis_row(cis: str, text: list[str]) -> list[str]:
    # 12 columns: CIS, denomination, form, routes, status, procedure, commercialisation,
    # date, bdm status, EU number, holder, enhanced monitoring.
    t = (text * 12)[:12]
    return [cis, t[1], t[2], t[3], t[4], t[5], t[6], t[7], t[8], t[9], t[10], t[11]]


def cip_row(cis: str, cip13: str, text: list[str]) -> list[str]:
    t = (text * 13)[:13]
    return [cis, t[1], t[2], t[3], t[4], t[5], cip13, t[7], t[8], t[9], t[10], t[11], t[12]]


def compo_row(cis: str, text: list[str], nature: str, link: str) -> list[str]:
    t = (text * 8)[:8]
    return [cis, t[1], t[2], t[3], t[4], t[5], nature, link]


CIS_IDS = st.lists(
    st.text(alphabet="0123456789", min_size=8, max_size=8), min_size=1, max_size=6, unique=True
)
TEXTS = st.lists(CELL, min_size=1, max_size=13)


@given(CIS_IDS, st.data())
def test_cells_are_not_altered(cis_ids: list[str], data: st.DataObject) -> None:
    """Feature: data-pipelines, Property P19 — Validates: Req 11.4.
    Every output cell equals the input cell exactly, including leading and trailing spaces,
    quotes and accents.
    """
    specs = {c: cis_row(c, data.draw(TEXTS)) for c in cis_ids}
    compo = [
        compo_row(c, data.draw(TEXTS), data.draw(st.sampled_from(["SA", "FT"])), str(i))
        for c in cis_ids
        for i in range(data.draw(st.integers(0, 3)))
    ]
    cip = [cip_row(c, data.draw(VALID_CIP13), data.draw(TEXTS)) for c in cis_ids]
    result = parse_bdpm(render(list(specs.values()), cip, compo), DATES)
    for row, source in zip(result.rows, cip, strict=True):
        spec = specs[source[0]]
        assert row["cip7"] == source[1] and row["presentation_label"] == source[2]
        assert row["presentation_status"] == source[3]
        assert row["presentation_commercialisation"] == source[4]
        assert row["presentation_declaration_date"] == source[5]
        assert row["denomination"] == spec[1] and row["pharmaceutical_form"] == spec[2]
        assert row["routes"] == spec[3] and row["authorisation_status"] == spec[4]
        assert row["procedure"] == spec[5] and row["commercialisation_status"] == spec[6]
        assert row["authorisation_date"] == spec[7] and row["holder"] == spec[10]
        lines = [c for c in compo if c[0] == source[0]]
        got = row["composition"]
        assert isinstance(got, list) and len(got) == len(lines)
        for line, cell in zip(lines, got, strict=True):
            assert isinstance(cell, dict)
            assert [cell[k] for k in cell] == line[1:]


FRENCH = st.text(alphabet="éèêëàâùûôîïçœ\u2019°²µÉÈ" + "abc ", min_size=1, max_size=20)


@given(FRENCH, st.sampled_from(FILES))
def test_decoding_round_trips_with_the_declared_encoding(text: str, name: str) -> None:
    """Feature: data-pipelines, Property P20 (round trip) — Validates: Req 11.2."""
    assert decode_file(name, text.encode(DECODINGS[name])) == text


@given(st.sampled_from([0x81, 0x8D, 0x8F, 0x90, 0x9D]), st.sampled_from([CIS, COMPO]))
def test_undefined_windows_1252_bytes_fail_naming_the_file(byte: int, name: str) -> None:
    """Feature: data-pipelines, Property P20 (failure) — Validates: Req 11.2."""
    with pytest.raises(SchemaMismatchError, match=name):
        decode_file(name, b"abc" + bytes([byte]) + b"def")


def test_windows_1252_bytes_are_not_accepted_as_utf8() -> None:
    with pytest.raises(SchemaMismatchError, match=CIP):
        decode_file(CIP, "é".encode("cp1252") + b"x")
    with pytest.raises(SchemaMismatchError, match=CIP):
        decode_file(CIP, b"\xff")


@given(BODY8, st.integers(0, 12), st.integers(1, 9))
def test_cip13_validation(body: str, position: int, bump: int) -> None:
    """Feature: data-pipelines, Property P21 — Validates: Req 11.5.
    A CIP13 is valid exactly when it has 13 digits, the prefix 3400 and a correct check digit.
    """
    good = make_cip13(body)
    assert valid_cip13(good)
    changed = good[:position] + str((int(good[position]) + bump) % 10) + good[position + 1 :]
    assert not valid_cip13(changed)
    assert not valid_cip13(good[:-1]) and not valid_cip13(good + "0")
    other = "3401" + body
    other += check_digit13(other)
    assert not valid_cip13(other)
    assert not valid_cip13("3400" + "a" * 9) and not valid_cip13("")


@given(CIS_IDS, st.lists(CELL.filter(lambda s: not s.isdigit()), min_size=1, max_size=3))
def test_invalid_cip13_gives_name_only_row(cis_ids: list[str], junk: list[str]) -> None:
    """Feature: data-pipelines, Property P21 (rows) — Validates: Req 11.5."""
    cis = [cis_row(c, ["x"]) for c in cis_ids]
    bad = [j + "9" for j in junk]
    cip = [cip_row(cis_ids[0], b, ["x"]) for b in bad]
    result = parse_bdpm(render(cis, cip, []), DATES)
    assert all(r["cip13"] is None and r["name_only"] is True for r in result.rows)
    assert result.metrics["name_only_rows"] == len(bad)
    flat = repr(result.rows)
    assert all(f"'{b}'" not in flat for b in bad)


@given(CIS_IDS, st.data())
def test_join_orphans_composition_order_and_accounting(
    cis_ids: list[str], data: st.DataObject
) -> None:
    """Feature: data-pipelines, Property P22 — Validates: Req 11.3, 11.6, 1.5.
    One output row per well-formed presentation line; composition lists keep file order;
    presentations without a specialty are kept and flagged; malformed lines are excluded.
    """
    known = cis_ids[: max(1, len(cis_ids) - 1)]
    orphans = cis_ids[len(known) :]
    cis = [cis_row(c, ["x"]) for c in known]
    compo: list[list[str]] = []
    for n in range(data.draw(st.integers(0, 8))):
        compo.append(compo_row(data.draw(st.sampled_from(cis_ids)), ["c", str(n)], "SA", str(n)))
    cip: list[list[str]] = []
    cip13s = data.draw(st.lists(VALID_CIP13, min_size=len(cis_ids), max_size=len(cis_ids)))
    for c, p in zip(cis_ids, cip13s, strict=True):
        cip.append(cip_row(c, p, ["p"]))
    malformed = data.draw(st.integers(0, min(3, len(cip) - 1)))
    files = render(cis, cip, compo)
    files[CIP] += b"too\tfew\tcells\n" * malformed
    result = parse_bdpm(files, DATES)
    check_accounting(result.input_rows, len(result.rows), result.excluded)
    assert result.excluded == ({"malformed_row": malformed} if malformed else {})
    assert len(result.rows) == len(cip)
    for row, source in zip(result.rows, cip, strict=True):
        assert row["specialty_missing"] is (source[0] in orphans)
        lines = [c for c in compo if c[0] == source[0]]
        got = row["composition"]
        assert isinstance(got, list)
        assert [g["substance_name"] for g in got if isinstance(g, dict)] == [c[3] for c in lines]
    assert result.metrics["specialty_missing"] == len(orphans)


PAGE = """<ul>{items}</ul><a href="/download/file/Contenu_et_format.pdf">PDF</a>"""
ITEM = (
    '<li><a class="x" href="/download/file/{name}.txt" role="link" download=\'{name}.txt\'>'
    "<span></span> {label}\n      (Date de mise à jour : {d}, 123 Ko)\n  </a></li>"
)
LABELS = {
    CIS: "Fichier des spécialités",
    CIP: "Fichier des présentations",
    COMPO: "Fichier des compositions",
}
DATE_VALUES = st.dates(dt.date(2020, 1, 1), dt.date(2030, 12, 31))


@given(st.permutations(FILES), st.lists(DATE_VALUES, min_size=3, max_size=3))
def test_update_dates_are_read_per_file(order: list[str], values: list[dt.date]) -> None:
    """Feature: data-pipelines, Property P23 — Validates: Req 11.1."""
    items = "".join(
        ITEM.format(name=n, label=LABELS[n], d=v.strftime("%d/%m/%Y"))
        for n, v in zip(order, values, strict=True)
    )
    got = parse_update_dates(PAGE.format(items=items))
    assert got == {n: v.isoformat() for n, v in zip(order, values, strict=True)}
    assert min(got.values()) == min(values).isoformat()


@pytest.mark.parametrize("missing", FILES)
def test_missing_or_impossible_date_fails(missing: str) -> None:
    items = "".join(
        ITEM.format(name=n, label=LABELS[n], d="31/02/2026" if n == missing else "03/11/2026")
        for n in FILES
    )
    with pytest.raises(SchemaMismatchError, match=missing):
        parse_update_dates(PAGE.format(items=items))
    without = "".join(
        ITEM.format(name=n, label=LABELS[n], d="03/11/2026") for n in FILES if n != missing
    )
    with pytest.raises(SchemaMismatchError, match=missing):
        parse_update_dates(PAGE.format(items=without))


def test_metformin_vildagliptin_composition_keeps_ft_and_sa_lines() -> None:
    """Validates: Req 11.3, 11.7 — FT and SA lines with link numbers, in file order."""
    cip13 = make_cip13("99999999")
    files = render(
        [cis_row("60004932", ["x"])],
        [cip_row("60004932", cip13, ["p"])],
        [
            ["60004932", "comprimé", "04442", "METFORMINE", "780 mg", "un comprimé", "FT", "1"],
            [
                "60004932",
                "comprimé",
                "24321",
                "CHLORHYDRATE DE METFORMINE",
                "1000 mg",
                "un comprimé",
                "SA",
                "1",
            ],
            ["60004932", "comprimé", "40035", "VILDAGLIPTINE", "50 mg", "un comprimé", "SA", "2"],
        ],
    )
    (row,) = parse_bdpm(files, DATES).rows
    comp = row["composition"]
    assert isinstance(comp, list)
    assert [(c["nature"], c["link"], c["substance_name"]) for c in comp if isinstance(c, dict)] == [
        ("FT", "1", "METFORMINE"),
        ("SA", "1", "CHLORHYDRATE DE METFORMINE"),
        ("SA", "2", "VILDAGLIPTINE"),
    ]
    assert row["composition"] is not None and row["cip13"] == cip13


def test_holder_keeps_its_leading_space_and_wrong_column_count_fails() -> None:
    cis = cis_row("1", ["x"])
    cis[10] = " PHARMA DEVELOPPEMENT"
    cip13 = make_cip13("12345678")
    (row,) = parse_bdpm(render([cis], [cip_row("1", cip13, ["p"])], []), DATES).rows
    assert row["holder"] == " PHARMA DEVELOPPEMENT"
    files = render([cis], [cip_row("1", cip13, ["p"])], [])
    files[CIS] = b"1\ttoo\tfew\r\n" * 3
    with pytest.raises(SchemaMismatchError, match=CIS):
        parse_bdpm(files, DATES)


def test_duplicate_cip13_is_kept_and_counted() -> None:
    cip13 = make_cip13("00000001")
    rows = [cip_row("1", cip13, ["a"]), cip_row("2", cip13, ["b"])]
    result = parse_bdpm(render([cis_row("1", ["x"]), cis_row("2", ["y"])], rows, []), DATES)
    assert len(result.rows) == 2 and result.metrics["duplicate_cip13"] == 1


def test_metrics_types_are_json() -> None:
    cip13 = make_cip13("00000002")
    result = parse_bdpm(render([cis_row("1", ["x"])], [cip_row("1", cip13, ["a"])], []), DATES)
    metrics: dict[str, Json] = result.metrics
    assert metrics["file_dates"] == DATES
