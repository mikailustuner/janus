# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false, reportUnknownLambdaType=false
"""Tests for the `faers` job (P27–P32, Req 13). Archives are built in memory."""

from __future__ import annotations

import datetime as dt
import io
import tempfile
import zipfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import polars as pl
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from janus_pipelines.core.validation import SchemaMismatchError, check_accounting
from janus_pipelines.jobs.faers import (
    EU27,
    NOT_SPECIFIED,
    ROW_SCHEMA,
    Listing,
    Quarter,
    QuarterWindowError,
    choose_kept,
    derive_region,
    parse_archives,
    parse_listing,
    select_quarters,
    split_ai,
)

DEMO_HEADER = (
    "primaryid$caseid$caseversion$i_f_code$event_dt$mfr_dt$init_fda_dt$fda_dt$rept_cod$auth_num"
    "$mfr_num$mfr_sndr$lit_ref$age$age_cod$age_grp$sex$e_sub$wt$wt_cod$rept_dt$to_mfr$occp_cod"
    "$reporter_country$occr_country"
)
DRUG_HEADER = "primaryid$caseid$drug_seq$role_cod$drugname$prod_ai$val_vbm$route$dose_vbm"
REAC_HEADER = "primaryid$caseid$pt$drug_rec_act"


@dataclass(frozen=True)
class Report:
    caseid: str
    version: int
    quarter: int  # index into the window
    fda_dt: str = "20260101"
    occr: str = "US"
    reporter: str = "US"
    drugs: tuple[tuple[str, str, str], ...] = ()  # (drug_seq, role, prod_ai)
    events: tuple[str, ...] = ()

    @property
    def primaryid(self) -> str:
        return f"{self.caseid}{self.version:02d}"


QUARTERS = [Quarter(2025, 4), Quarter(2026, 1), Quarter(2026, 2), Quarter(2026, 3)]


def demo_line(r: Report, sentinel: str = "") -> str:
    cells = [r.primaryid, r.caseid, str(r.version), "I", "", "", "", r.fda_dt, "EXP", "", "", ""]
    cells += [
        "",
        sentinel,
        "YR",
        "A",
        sentinel,
        "Y",
        sentinel,
        "KG",
        "",
        "",
        "MD",
        r.reporter,
        r.occr,
    ]
    return "$".join(cells)


def build_archive(
    quarter: Quarter,
    reports: Sequence[Report],
    deleted: Sequence[str] = (),
    *,
    eol: str = "\n",
    sentinel: str = "",
    extra_demo: Sequence[str] = (),
    extra_drug: Sequence[str] = (),
    extra_reac: Sequence[str] = (),
) -> bytes:
    yy = f"{quarter.year % 100:02d}"
    demo = [DEMO_HEADER, *(demo_line(r, sentinel) for r in reports), *extra_demo]
    drug = [DRUG_HEADER]
    reac = [REAC_HEADER]
    for r in reports:
        for seq, role, ai in r.drugs:
            drug.append(f"{r.primaryid}${r.caseid}${seq}${role}$BRAND${ai}$1$ORAL$x")
        for pt in r.events:
            reac.append(f"{r.primaryid}${r.caseid}${pt}$")
    drug += list(extra_drug)
    reac += list(extra_reac)
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as zf:
        for kind, lines in (("DEMO", demo), ("DRUG", drug), ("REAC", reac)):
            zf.writestr(f"ASCII/{kind}{yy}Q{quarter.q}.txt", eol.join(lines) + eol)
        zf.writestr(f"Deleted/DELETE{yy}Q{quarter.q}.txt", "\n" + "\n".join(deleted) + "\n")
    return out.getvalue()


def archives_for(reports: Sequence[Report], deleted_in: dict[int, list[str]] | None = None, **kw):  # type: ignore[no-untyped-def]
    out: dict[str, bytes] = {}
    for i, q in enumerate(QUARTERS):
        mine = [r for r in reports if r.quarter == i]
        out[q.label] = build_archive(q, mine, (deleted_in or {}).get(i, []), **kw)
    return out


def run(archives: dict[str, bytes], quarters: Sequence[Quarter] = QUARTERS):  # type: ignore[no-untyped-def]
    scratch = Path(tempfile.mkdtemp(prefix="faers-test-"))
    result = parse_archives(archives, quarters, scratch)
    assert result.rows_file is not None
    return result, pl.read_parquet(result.rows_file).to_dicts()


CASEID = st.text(alphabet="123456789", min_size=5, max_size=5)
FDA_DT = st.builds(
    lambda d: d.strftime("%Y%m%d"), st.dates(dt.date(2024, 1, 1), dt.date(2026, 12, 31))
)


@st.composite
def case_sets(draw: st.DrawFn) -> tuple[list[Report], dict[int, list[str]]]:
    caseids = draw(st.lists(CASEID, min_size=1, max_size=6, unique=True))
    reports: list[Report] = []
    seen: set[tuple[str, int, int]] = set()
    for c in caseids:
        for _ in range(draw(st.integers(1, 4))):
            ver = draw(st.integers(1, 4))
            quarter = draw(st.integers(0, 3))
            if (c, ver, quarter) in seen:
                continue
            seen.add((c, ver, quarter))
            reports.append(
                Report(
                    c,
                    ver,
                    quarter,
                    fda_dt=draw(FDA_DT),
                    occr=draw(st.sampled_from(["US", "TR", "EU", "", "JP"])),
                    drugs=draw(
                        st.lists(
                            st.tuples(
                                st.integers(1, 3).map(str),
                                st.sampled_from(["PS", "SS", "C", "I", "DN"]),
                                st.sampled_from(["ASPIRIN", "A\\B", "", "X\\\\Y"]),
                            ),
                            max_size=3,
                        ).map(tuple)
                    ),
                    events=draw(
                        st.lists(st.sampled_from(["Pain", "Rash", 'Q"uote']), max_size=3).map(tuple)
                    ),
                )
            )
    deleted: dict[int, list[str]] = {}
    for c in draw(st.lists(st.sampled_from(caseids), max_size=3)):
        deleted.setdefault(draw(st.integers(0, 3)), []).append(c)
    return reports, deleted


def reference(
    reports: Sequence[Report], deleted: dict[int, list[str]]
) -> tuple[dict[str, Report], dict[tuple[str, int], str]]:
    gone = {c for ids in deleted.values() for c in ids}
    best: dict[str, Report] = {}
    for r in reports:
        if r.caseid in gone:
            continue
        key = (r.version, r.fda_dt, int(r.primaryid), r.quarter)
        cur = best.get(r.caseid)
        if cur is None or key > (cur.version, cur.fda_dt, int(cur.primaryid), cur.quarter):
            best[r.caseid] = r
    reasons: dict[tuple[str, int], str] = {}
    for r in reports:
        if r.caseid in gone:
            reasons[(r.primaryid, r.quarter)] = "deleted_case"
        elif best[r.caseid] is not r:
            reasons[(r.primaryid, r.quarter)] = "superseded_version"
    return best, reasons


@settings(max_examples=25)
@given(case_sets(), st.data())
def test_case_deduplication(
    sets: tuple[list[Report], dict[int, list[str]]], data: st.DataObject
) -> None:
    """Feature: data-pipelines, Property P27 — Validates: Req 13.3, 1.5.
    One report per non-deleted case with the highest version (ties: fda_dt, primaryid,
    quarter); no deleted case is kept; `removed` explains every other report; the result
    is the same for any order of reports.
    """
    reports, deleted = sets
    shuffled = data.draw(st.permutations(reports))
    result, rows = run(archives_for(shuffled, deleted))
    best, reasons = reference(reports, deleted)
    quarter_label = {i: q.label for i, q in enumerate(QUARTERS)}
    got = {(r["primaryid"], r["quarter"]): r for r in rows}
    assert set(got) == {(r.primaryid, quarter_label[r.quarter]) for r in best.values()}
    assert {r["caseid"] for r in rows} == set(best)
    assert len(rows) == len(best)
    assert not {r["caseid"] for r in rows} & {c for ids in deleted.values() for c in ids}
    removed = pl.read_parquet(result.side_tables["removed"]).to_dicts()
    assert {(x["primaryid"], x["quarter"]): x["reason"] for x in removed} == {
        (pid, quarter_label[q]): why for (pid, q), why in reasons.items()
    }
    for x in removed:
        if x["reason"] == "superseded_version":
            assert x["kept_primaryid"] == best[x["caseid"]].primaryid
        else:
            assert x["kept_primaryid"] is None
    check_accounting(result.input_rows, result.output_rows, result.excluded)


@given(case_sets())
def test_choose_kept_matches_reference(sets: tuple[list[Report], dict[int, list[str]]]) -> None:
    """Feature: data-pipelines, Property P27 (pure part) — Validates: Req 13.3."""
    reports, deleted = sets
    demo = pl.DataFrame(
        [
            {
                "primaryid": r.primaryid,
                "caseid": r.caseid,
                "caseversion": str(r.version),
                "fda_dt": r.fda_dt,
                "quarter": QUARTERS[r.quarter].label,
            }
            for r in reports
        ],
        schema=dict.fromkeys(
            ["primaryid", "caseid", "caseversion", "fda_dt", "quarter"], pl.String
        ),
    )
    gone = {c for ids in deleted.values() for c in ids}
    kept, removed = choose_kept(demo, gone)
    best, _ = reference(reports, deleted)
    assert sorted(kept["caseid"].to_list()) == sorted(best)
    assert kept.height + removed.height == len(reports)


MALFORMED_LINES = st.lists(
    st.sampled_from(["only$two", "a$b$c$d$e$f$g$h$i$j$k$l$m$n$o$p$q$r$s$t$u$v$w$x$y$z"]), max_size=3
)


@settings(max_examples=25)
@given(case_sets(), MALFORMED_LINES, MALFORMED_LINES, st.integers(0, 2))
def test_line_accounting(
    sets: tuple[list[Report], dict[int, list[str]]],
    bad_drug: list[str],
    bad_demo: list[str],
    orphans: int,
) -> None:
    """Feature: data-pipelines, Property P28 — Validates: Req 13.2, 13.5, 1.5.
    Every line of DEMO, DRUG and REAC is in the output or excluded with a reason.
    """
    reports, deleted = sets
    orphan_drug = ["99999999$99999$1$PS$B$ASPIRIN$1$ORAL$x"] * orphans
    orphan_reac = ["99999999$99999$Pain$"] * orphans
    archives = {}
    for i, q in enumerate(QUARTERS):
        archives[q.label] = build_archive(
            q,
            [r for r in reports if r.quarter == i],
            deleted.get(i, []),
            extra_demo=bad_demo if i == 0 else (),
            extra_drug=[*bad_drug, *orphan_drug] if i == 0 else (),
            extra_reac=[*bad_drug, *orphan_reac] if i == 0 else (),
        )
    result, rows = run(archives)
    check_accounting(result.input_rows, result.output_rows, result.excluded)
    assert result.excluded.get("malformed_row", 0) == len(bad_demo)
    assert result.input_rows == len(reports) + len(bad_demo)
    acc = result.metrics["line_accounting"]
    assert isinstance(acc, dict)
    drug_lines = sum(len(r.drugs) for r in reports)
    reac_lines = sum(len(r.events) for r in reports)
    for kind, expected_lines, bad in (
        ("DRUG", drug_lines, len(bad_drug)),
        ("REAC", reac_lines, len(bad_drug)),
    ):
        entry: Any = acc[kind]
        assert entry["malformed"] == bad and entry["orphan"] == orphans
        assert entry["lines"] == expected_lines + bad + orphans
        assert (
            entry["kept"] + entry["of_removed_report"] + entry["orphan"] + entry["malformed"]
            == entry["lines"]
        )
    kept_drug = sum(len(r["drugs"]) for r in rows)
    assert kept_drug == acc["DRUG"]["kept"]  # type: ignore[index]


COUNTRY = st.one_of(
    st.sampled_from(
        [
            "",
            " ",
            NOT_SPECIFIED,
            "country not specified",
            "EU",
            "eu",
            "TR",
            "tr",
            "US",
            "GB",
            "CH",
            "NO",
            "IS",
            "LI",
            "PR",
            "GU",
            "VI",
            "AS",
            "MP",
            "UM",
            "JP",
            *sorted(EU27),
            "XU",
            "ZZ",
        ]
    ),
    st.text(alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ ", max_size=3),
    st.none(),
)


def reference_region(code: str | None) -> str | None:
    if code is None:
        return None
    c = code.strip().upper()
    if c in ("", NOT_SPECIFIED):
        return None
    if c == "TR":
        return "TR"
    if c in {"US", "PR", "GU", "VI", "AS", "MP", "UM"}:
        return "US"
    if c == "EU" or c in EU27:
        return "EU"
    return "OTHER"


@given(COUNTRY, COUNTRY)
def test_region_rule(occr: str | None, reporter: str | None) -> None:
    """Feature: data-pipelines, Property P29 — Validates: Req 13.6."""
    region, basis = derive_region(occr, reporter)
    assert region in {"TR", "EU", "US", "OTHER", "UNKNOWN"}
    first, second = reference_region(occr), reference_region(reporter)
    if first is not None:
        assert (region, basis) == (first, "occr_country")
    elif second is not None:
        assert (region, basis) == (second, "reporter_country")
    else:
        assert (region, basis) == ("UNKNOWN", "none")


def test_region_examples() -> None:
    assert derive_region("GB", "US") == ("OTHER", "occr_country")
    assert derive_region("", "PR") == ("US", "reporter_country")
    assert derive_region(None, NOT_SPECIFIED) == ("UNKNOWN", "none")
    assert derive_region("EU", "DE") == ("EU", "occr_country")
    assert derive_region("LI", "") == ("OTHER", "occr_country")


# --- quarter window ------------------------------------------------------------------------

QUARTER = st.builds(Quarter, st.integers(2012, 2030), st.integers(1, 4))


def listing(quarters: list[Quarter]) -> list[Listing]:
    return [Listing(q, f"https://example.org/faers_ascii_{q.label}.zip", None) for q in quarters]


@given(st.integers(2012, 2029), st.integers(1, 4), st.integers(0, 12), st.data())
def test_quarter_window(year: int, q: int, extra_old: int, data: st.DataObject) -> None:
    """Feature: data-pipelines, Property P30 — Validates: Req 13.1.
    The window is the four latest consecutive quarters, oldest first, in any listing order.
    """
    newest = Quarter(year, q)
    quarters = [
        Quarter((newest.ordinal - i) // 4, (newest.ordinal - i) % 4 + 1)
        for i in range(4 + extra_old)
    ]
    shuffled = data.draw(st.permutations(quarters))
    got = select_quarters(listing(list(shuffled)))
    assert [x.quarter for x in got] == sorted(quarters)[-4:]
    assert [x.quarter.ordinal for x in got] == list(range(newest.ordinal - 3, newest.ordinal + 1))


@given(st.lists(QUARTER, min_size=1, max_size=3, unique=True))
def test_quarter_window_needs_four(quarters: list[Quarter]) -> None:
    with pytest.raises(QuarterWindowError):
        select_quarters(listing(quarters))


def test_quarter_window_gap_fails() -> None:
    gap = [Quarter(2026, 3), Quarter(2026, 1), Quarter(2025, 4), Quarter(2025, 3)]
    with pytest.raises(QuarterWindowError, match="consecutive"):
        select_quarters(listing(gap))


def test_listing_parses_case_comments_and_typos() -> None:
    html = """
    <table><tbody>
    <!--
    <tr><td><p>October - December 2025</p></td><td><a href="https://x/faers_ascii_2025Q4.zip">A</a></td></tr>
    -->
    <tr><td><p>July - September 2026<br><span>posted on 28-Oct-2026</span></p></td>
      <td><a href="https://fis.fda.gov/content/Exports/faers_ascii_2026q3.zip">ASCII</a>
      <a href="https://fis.fda.gov/content/Exports/faers_xml_2026q3.zip">XML</a></td></tr>
    <tr><td><p>October - December 2025<br><span>posted on 27-Jan-2025</span></p></td>
      <td><a href="https://fis.fda.gov/content/Exports/faers_ascii_2025Q4.zip">ASCII</a></td></tr>
    <tr><td><p>XML only</p></td><td><a href="https://x/faers_xml_2025q3.zip">XML</a></td></tr>
    </tbody></table>"""
    items = parse_listing(html)
    assert [(i.quarter.label, i.posted) for i in items] == [
        ("2025Q4", None),  # impossible posting date (typo on the page) is dropped
        ("2026Q3", "2026-10-28"),
    ]


# --- format and minimisation --------------------------------------------------------------


@settings(max_examples=25)
@given(case_sets(), st.sampled_from(["\n", "\r\n"]))
def test_line_ends_and_quotes(sets: tuple[list[Report], dict[int, list[str]]], eol: str) -> None:
    """Feature: data-pipelines, Property P31 — Validates: Req 13.2.
    LF and CRLF files give the same rows; quote characters in values are kept.
    """
    reports, deleted = sets
    _, lf = run(archives_for(reports, deleted, eol="\n"))
    _, other = run(archives_for(reports, deleted, eol=eol))
    key = lambda r: (r["quarter"], r["primaryid"])  # noqa: E731
    assert sorted(lf, key=key) == sorted(other, key=key)
    assert all("\r" not in e for row in lf for e in row["events"])


@settings(max_examples=25)
@given(case_sets(), st.text(alphabet="QWXZ", min_size=6, max_size=8))
def test_only_allowed_fields_leave_the_parser(
    sets: tuple[list[Report], dict[int, list[str]]], sentinel: str
) -> None:
    """Feature: data-pipelines, Property P32 — Validates: Req 13.4.
    Output rows have exactly the keys of schema faers-1 and carry no value from an unused column.
    """
    reports, deleted = sets
    result, rows = run(archives_for(reports, deleted, sentinel=f"SENTINEL{sentinel}"))
    assert all(set(r) == set(ROW_SCHEMA) for r in rows)
    assert "SENTINEL" not in repr(rows)
    removed = pl.read_parquet(result.side_tables["removed"])
    assert "SENTINEL" not in repr(removed.to_dicts())


# --- examples ------------------------------------------------------------------------------


def test_combination_string_is_split_and_dn_role_is_kept() -> None:
    """Validates: Req 13.4 — the builder, not the pipeline, excludes role DN."""
    r = Report(
        "11111",
        1,
        3,
        drugs=(
            ("1", "PS", "SULFAMETHOXAZOLE\\TRIMETHOPRIM"),
            ("2", "DN", "ASPIRIN"),
            ("3", "C", ""),
        ),
        events=("Rash",),
        occr="",
        reporter=NOT_SPECIFIED,
    )
    _, rows = run(archives_for([r]))
    (row,) = rows
    assert row["drugs"] == [
        {"drug_seq": "1", "role": "PS", "ingredients": ["SULFAMETHOXAZOLE", "TRIMETHOPRIM"]},
        {"drug_seq": "2", "role": "DN", "ingredients": ["ASPIRIN"]},
        {"drug_seq": "3", "role": "C", "ingredients": []},
    ]
    assert (row["region"], row["region_basis"]) == ("UNKNOWN", "none")
    assert row["occr_country"] == "" and row["reporter_country"] == NOT_SPECIFIED


def test_follow_up_replaces_initial_version_from_an_earlier_quarter() -> None:
    first = Report("22222", 1, 0, drugs=(("1", "PS", "A"),), events=("Pain",))
    follow = Report("22222", 2, 2, drugs=(("1", "PS", "B"),), events=("Rash",))
    result, rows = run(archives_for([first, follow]))
    (row,) = rows
    assert row["primaryid"] == follow.primaryid and row["quarter"] == "2026Q2"
    assert result.excluded == {"superseded_version": 1}


def test_quote_characters_are_kept() -> None:
    r = Report("33333", 1, 0, events=('Q"uote', "O'Neil"), drugs=(("1", "PS", 'A"B'),))
    _, rows = run(archives_for([r], eol="\r\n"))
    assert rows[0]["events"] == ['Q"uote', "O'Neil"]
    assert rows[0]["drugs"][0]["ingredients"] == ['A"B']


@given(st.text(alphabet="AB\\ C", max_size=12))
def test_split_ai_keeps_parts_as_published(text: str) -> None:
    parts = split_ai(text)
    assert all(p != "" for p in parts)
    assert [p for p in text.split("\\") if p != ""] == parts


def test_missing_column_and_bad_encoding_fail_loudly() -> None:
    q = QUARTERS[0]
    archives = archives_for([])
    bad = io.BytesIO()
    with zipfile.ZipFile(bad, "w") as zf:
        zf.writestr("ASCII/DEMO25Q4.txt", "primaryid$caseid\n1$2\n")
        zf.writestr("ASCII/DRUG25Q4.txt", DRUG_HEADER + "\n")
        zf.writestr("ASCII/REAC25Q4.txt", REAC_HEADER + "\n")
    archives[q.label] = bad.getvalue()
    with pytest.raises(SchemaMismatchError, match="caseversion"):
        parse_archives(archives, QUARTERS, Path(tempfile.mkdtemp()))
    latin = io.BytesIO()
    with zipfile.ZipFile(latin, "w") as zf:
        zf.writestr("ASCII/DEMO25Q4.txt", DEMO_HEADER.encode() + b"\n\xe9\n")
        zf.writestr("ASCII/DRUG25Q4.txt", DRUG_HEADER + "\n")
        zf.writestr("ASCII/REAC25Q4.txt", REAC_HEADER + "\n")
    archives[q.label] = latin.getvalue()
    with pytest.raises(SchemaMismatchError, match="UTF-8"):
        parse_archives(archives, QUARTERS, Path(tempfile.mkdtemp()))
