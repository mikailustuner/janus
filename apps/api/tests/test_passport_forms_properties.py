"""Dose-form table (medication-passport design §5.2; task 3.1).

Feature: medication-passport, Property P6. Validates Req 6.5: the committed table loads; keys are
unique; every group is in the closed set; `group()` is total (unknown -> `None`); each single
injected defect is named at load; `COUNTABLE_GROUPS` is a subset of the groups; modified-release
forms never share a group with immediate-release ones. Generated tables use invented form names.
"""

from __future__ import annotations

import csv
import hashlib
import io

import pytest
from hypothesis import given
from hypothesis import strategies as st

from janus.passport import forms_draft
from janus.passport.forms import (
    ANY_ROUTE,
    COUNTABLE_GROUPS,
    FORMS_FILE,
    GROUPS,
    HEADER,
    NOT_COMPARED_GROUPS,
    SOURCES,
    FormTableError,
    load,
    parse,
    route_key,
)

forms = st.text(alphabet="ABCDEFGH ,", min_size=1, max_size=12).filter(lambda s: s.strip() != "")
routes = st.lists(st.sampled_from(["ORAL", "TOPICAL", "NASAL", "orale", "cutanée"]), max_size=3)
statuses = st.sampled_from(["proposed", "accepted"])


@st.composite
def tables(draw: st.DrawFn) -> list[list[str]]:
    keys = draw(
        st.lists(
            st.tuples(
                st.sampled_from(sorted(SOURCES)),
                forms,
                st.one_of(st.just(ANY_ROUTE), routes.map(route_key)),
            ),
            min_size=1,
            max_size=12,
            unique=True,
        )
    )
    return [
        [s, f, r, draw(st.sampled_from(["", *GROUPS])), f"{draw(statuses)}; test row"]
        for s, f, r in keys
    ]


def render(header: list[str], rows: list[list[str]]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(header)
    w.writerows(rows)
    return buf.getvalue()


def test_p6_committed_table_loads() -> None:
    """Feature: medication-passport, Property P6. Validates Req 6.5."""
    table = load()
    assert table.rows
    assert table.version == hashlib.sha256(FORMS_FILE.read_bytes()).hexdigest()
    assert {g for g in table.rows.values() if g is not None} <= set(GROUPS)
    assert COUNTABLE_GROUPS <= set(GROUPS) and NOT_COMPARED_GROUPS <= set(GROUPS)
    assert not COUNTABLE_GROUPS & NOT_COMPARED_GROUPS
    with FORMS_FILE.open(encoding="utf-8", newline="") as fh:
        keys = [(r["source_id"], r["published_form"], r["route"]) for r in csv.DictReader(fh)]
    assert len(keys) == len(set(keys)) == len(table.rows)


def test_p6_committed_table_keeps_modified_release_apart() -> None:
    """Feature: medication-passport, Property P6. Validates Req 6.5: a published form with a
    modified-release word is never in an immediate-release group."""
    table = load()
    immediate = set(GROUPS) - {"oral_solid_modified_release", "transdermal", "other"}
    for (_, form, _), group in table.rows.items():
        if any(w in form.lower() for w in forms_draft.MODIFIED):
            assert group not in immediate, form


def test_p6_draft_rules_keep_modified_release_apart() -> None:
    """Feature: medication-passport, Property P6. Validates Req 6.5 on the draft rules."""
    for form in (
        "TABLET, EXTENDED RELEASE",
        "comprimé à libération prolongée",
        "gélule gastro-résistant(e)",
        "CAPSULE, DELAYED RELEASE",
    ):
        assert forms_draft.propose(form, ["ORAL"])[0] == "oral_solid_modified_release"
        assert forms_draft.propose(form, ["orale"])[0] == "oral_solid_modified_release"
    for form in (
        "SUSPENSION, EXTENDED RELEASE",
        "INJECTION, SUSPENSION, EXTENDED RELEASE",
        "suspension injectable à libération prolongée",
        "collyre à libération prolongée",
    ):
        assert forms_draft.propose(form, ["ORAL"])[0] is None
    assert forms_draft.propose("TABLET", ["ORAL"])[0] == "oral_solid"
    assert forms_draft.propose("TABLET", ["SUBLINGUAL"])[0] == "other"
    assert forms_draft.propose("SOLUTION", ["OPHTHALMIC"])[0] == "ophthalmic"
    assert forms_draft.propose("SOLUTION", [])[0] is None


@given(rows=tables())
def test_p6_generated_tables_load_and_look_up(rows: list[list[str]]) -> None:
    """Feature: medication-passport, Property P6. Validates Req 6.5: a valid table loads; an
    exact route-set row wins over the `*` row; `reviewed` iff every row is accepted."""
    table = parse(render(HEADER, rows))
    assert len(table.rows) == len(rows)
    assert table.reviewed == all(r[4].startswith("accepted") for r in rows)
    for source, form, route, group, _ in rows:
        if route == ANY_ROUTE:
            continue
        given_routes = route.split("|") if route else []
        assert table.group(source, form, given_routes) == (group or None)
    for source, form, route, group, _ in rows:
        if route == ANY_ROUTE and (source, form, "UNSEEN") not in table.rows:
            assert table.group(source, form, ["UNSEEN"]) == (group or None)


@given(
    rows=tables(),
    source=st.text(max_size=12),
    form=st.one_of(st.none(), st.text(max_size=20)),
    given_routes=st.lists(st.text(max_size=8), max_size=3),
)
def test_p6_group_is_total(
    rows: list[list[str]], source: str, form: str | None, given_routes: list[str]
) -> None:
    """Feature: medication-passport, Property P6. Validates Req 6.5: unknown -> `None`."""
    table = parse(render(HEADER, rows))
    got = table.group(source, form, given_routes)
    assert got is None or got in GROUPS
    if source not in SOURCES or not form:
        assert got is None


DEFECTS = (
    "duplicate",
    "unknown_group",
    "unknown_source",
    "bad_route",
    "empty_form",
    "no_status",
    "short_row",
)
MESSAGES = {
    "duplicate": "repeated key",
    "unknown_group": "unknown group",
    "unknown_source": "unknown source",
    "bad_route": "route is not a sorted route set",
    "empty_form": "empty published form",
    "no_status": "note must start with a status",
    "short_row": "wrong number of fields",
}


@given(rows=tables(), defect=st.sampled_from(DEFECTS), at=st.integers(min_value=0))
def test_p6_each_defect_is_named(rows: list[list[str]], defect: str, at: int) -> None:
    """Feature: medication-passport, Property P6. Validates Req 6.5: one injected defect stops the
    load with a message naming the row and the defect."""
    i = at % len(rows)
    bad = [list(r) for r in rows]
    if defect == "duplicate":
        bad.insert(i + 1, list(bad[i]))
        i += 1
    elif defect == "unknown_group":
        bad[i][3] = "tablet_or_so"
    elif defect == "unknown_source":
        bad[i][0] = "de_pzn"
    elif defect == "bad_route":
        bad[i][2] = "TOPICAL|ORAL"
    elif defect == "empty_form":
        bad[i][1] = "  "
    elif defect == "no_status":
        bad[i][4] = "looks fine"
    else:
        bad[i] = bad[i][:3]
    with pytest.raises(FormTableError) as exc:
        parse(render(HEADER, bad))
    assert f"row {i + 2}:" in str(exc.value)
    assert MESSAGES[defect] in str(exc.value)


def test_p6_bad_header_is_named() -> None:
    """Feature: medication-passport, Property P6. Validates Req 6.5."""
    with pytest.raises(FormTableError, match="header"):
        parse(render(["source_id", "published_form", "group", "note"], []))
