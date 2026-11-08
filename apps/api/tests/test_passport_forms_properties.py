"""Dose-form table (medication-passport design §5.2; tasks 3.1 and 4).

Feature: medication-passport, Property P6. Validates Req 6.5: the committed table loads; keys are
unique; every group is in the closed set; `group()` is total (unknown -> `None`); each single
injected defect is named at load; `COUNTABLE_GROUPS` is a subset of the groups; modified-release
forms never share a group with immediate-release ones; `*` rows only where the form fixes the
route or the group does not depend on it (owner decision 2026-11-08); the packaged copy equals
`data/dose_form_groups.csv`. Generated tables use invented form names.
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
    DATA_FILE,
    FORMS_FILE,
    GROUPS,
    HEADER,
    NOT_COMPARED_GROUPS,
    ROUTE_CLASSES,
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
    out: list[list[str]] = []
    for s, f, r in keys:
        from_form = draw(st.sampled_from(["", *sorted(ROUTE_CLASSES)])) if r == ANY_ROUTE else ""
        group = draw(st.sampled_from(["", *GROUPS]))
        out.append([s, f, r, group, from_form, f"{draw(statuses)}; test row"])
    return out


def render(header: list[str], rows: list[list[str]]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(header)
    w.writerows(rows)
    return buf.getvalue()


def committed_rows() -> list[dict[str, str]]:
    with FORMS_FILE.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def test_p6_committed_table_loads() -> None:
    """Feature: medication-passport, Property P6. Validates Req 6.5."""
    table = load()
    assert table.rows
    assert table.reviewed  # every row accepted by the owner (2026-11-08)
    assert table.version == hashlib.sha256(FORMS_FILE.read_bytes()).hexdigest()
    assert {g for g in table.rows.values() if g is not None} <= set(GROUPS)
    assert COUNTABLE_GROUPS <= set(GROUPS) and NOT_COMPARED_GROUPS <= set(GROUPS)
    assert not COUNTABLE_GROUPS & NOT_COMPARED_GROUPS
    keys = [(r["source_id"], r["published_form"], r["route"]) for r in committed_rows()]
    assert len(keys) == len(set(keys)) == len(table.rows)


def test_p6_packaged_copy_equals_data_copy() -> None:
    """Feature: medication-passport, Property P6. The API image is built from `apps/api` only, so
    the table ships inside the package; it must be byte-identical to the reviewed `data/` copy."""
    assert FORMS_FILE.read_bytes() == DATA_FILE.read_bytes()


def test_p6_committed_table_keeps_modified_release_apart() -> None:
    """Feature: medication-passport, Property P6. Validates Req 6.5: a published form with a
    modified-release word is never in an immediate-release group; delayed and prolonged release
    stay apart (owner decision R1)."""
    table = load()
    allowed = {
        "oral_solid_delayed_release",
        "oral_solid_prolonged_release",
        "transdermal",
        "other",
        None,
    }
    for (_, form, _), group in table.rows.items():
        f = form.lower()
        if any(w in f for w in forms_draft.MODIFIED):
            assert group in allowed, form
        if group == "oral_solid_delayed_release":
            assert any(w in f for w in forms_draft.DELAYED), form
        if group == "oral_solid_prolonged_release":
            assert any(w in f for w in forms_draft.PROLONGED), form


def test_p6_wildcards_only_where_the_form_fixes_the_route() -> None:
    """Feature: medication-passport, Property P6. Owner decision 2026-11-08: a `*` row exists only
    when the form string fixes the route (`route_from_form`) or the group does not depend on the
    route; no route is guessed."""
    for r in committed_rows():
        form = r["published_form"]
        if r["route"] == ANY_ROUTE:
            assert forms_draft.route_independent(form) or r["route_from_form"], form
            assert r["route_from_form"] == (forms_draft.route_from_form(form) or "")
        else:
            assert r["route_from_form"] == ""
    table = load()
    assert table.group("openfda_ndc", "TABLET", []) is None  # a plain tablet fixes no route
    assert table.group("openfda_ndc", "TABLET, FILM COATED", []) == "oral_solid"
    assert table.group("openfda_ndc", "CAPSULE", ["RESPIRATORY (INHALATION)"]) == "inhaled"  # R3
    assert table.group("openfda_ndc", "SOLUTION", []) is None
    assert table.group("openfda_ndc", "SOLUTION", ["OPHTHALMIC"]) == "ophthalmic"


def test_p6_draft_rules() -> None:
    """Feature: medication-passport, Property P6. Validates Req 6.5 on the draft rules."""
    for form in ("TABLET, EXTENDED RELEASE", "comprimé à libération prolongée"):
        assert forms_draft.propose(form, ["ORAL"])[0] == "oral_solid_prolonged_release"
    for form in ("gélule gastro-résistant(e)", "CAPSULE, DELAYED RELEASE"):
        assert forms_draft.propose(form, ["orale"])[0] == "oral_solid_delayed_release"
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
    assert forms_draft.route_from_form("TABLET") is None
    assert forms_draft.route_from_form("comprimé pelliculé") == "oral"
    assert forms_draft.route_from_form("PATCH") is None
    assert forms_draft.route_from_form("PATCH, TRANSDERMAL") == "transdermal"


@given(rows=tables())
def test_p6_generated_tables_load_and_look_up(rows: list[list[str]]) -> None:
    """Feature: medication-passport, Property P6. Validates Req 6.5: a valid table loads; an
    exact route-set row wins over the `*` row; `reviewed` iff every row is accepted."""
    table = parse(render(HEADER, rows))
    assert len(table.rows) == len(rows)
    assert table.reviewed == all(r[5].startswith("accepted") for r in rows)
    for source, form, route, group, _, _ in rows:
        if route == ANY_ROUTE:
            continue
        given_routes = route.split("|") if route else []
        assert table.group(source, form, given_routes) == (group or None)
    for source, form, route, group, _, _ in rows:
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
    "bad_route_from_form",
)
MESSAGES = {
    "duplicate": "repeated key",
    "unknown_group": "unknown group",
    "unknown_source": "unknown source",
    "bad_route": "route is not a sorted route set",
    "empty_form": "empty published form",
    "no_status": "note must start with a status",
    "short_row": "wrong number of fields",
    "bad_route_from_form": "route_from_form needs a * row",
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
        bad[i][5] = "looks fine"
    elif defect == "bad_route_from_form":
        bad[i][4] = "somewhere"
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
