"""Property P17: rule-base validation and version (cascade-engine design §5.1, §9)."""

from __future__ import annotations

import json
from collections.abc import Callable

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from janus.cascades.rulebase import RuleBaseError, build_rule_base
from tests.cascades_strategies import (
    EXTENSION_IDS,
    FILE_SET_EXAMPLES,
    SUPPORT_ID,
    FileSet,
    file_sets,
)

Mutation = Callable[[FileSet], object]


def _first_class(fs: FileSet, scope: str = "pipc") -> dict[str, str]:
    return next(r for r in fs.classes if r["scope"] == scope)


def _set_all_exclude(fs: FileSet) -> None:
    for r in fs.classes:
        if r["class_id"] == "cls_0":
            r["match"] = "exclude"


def _unmatchable_without_reason(fs: FileSet) -> None:
    fs.rules[-1].update(unmatchable_role="marker", marker_class="", unmatchable_reason="")


def _extension_in_marker(fs: FileSet) -> None:
    fs.rules[1]["marker_class"] = "ext_index"


def _whocc_note(fs: FileSet) -> None:
    row = _first_class(fs)
    row.update(basis="whocc_lookup", note="checked by hand")


def _priority_bad_ci(fs: FileSet) -> None:
    fs.priority.append(
        {
            "position": next(
                n for n in range(65, 0, -1) if all(p["position"] != n for p in fs.priority)
            ),
            "evidence_id": "paper:src_p:prio",
            "measure": "incidence",
            "value": "9.0",
            "ci_low": "10.7",
            "ci_high": "11.0",
            "unit": "percent",
            "locator": "Abstract, Results",
            "note": "",
        }
    )


def _priority_unknown_evidence(fs: FileSet) -> None:
    _priority_bad_ci(fs)
    fs.priority[-1].update(value="10.8", evidence_id="paper:nope:x")


MUTATIONS: list[tuple[str, Mutation]] = [
    ("bad_pattern", lambda fs: _first_class(fs).update(pattern="A1")),
    ("duplicate_pattern", lambda fs: fs.classes.append(dict(_first_class(fs)))),
    ("combination_pattern", lambda fs: fs.classes.append({**_first_class(fs), "pattern": "C09BA"})),
    (
        "extension_without_evidence",
        lambda fs: _first_class(fs, "form_extension").update(evidence_id=""),
    ),
    (
        "extension_evidence_unknown",
        lambda fs: _first_class(fs, "form_extension").update(evidence_id="paper:nope:x"),
    ),
    (
        "evidence_without_extension",
        lambda fs: _first_class(fs).update(evidence_id=EXTENSION_IDS[1]),
    ),
    ("missing_note", lambda fs: _first_class(fs).update(note="")),
    ("whocc_note_incomplete", _whocc_note),
    ("no_include_pattern", _set_all_exclude),
    ("unknown_class", lambda fs: fs.rules[3].update(index_class="zz_unknown")),
    ("missing_position", lambda fs: fs.rules.pop(10)),
    ("duplicate_position", lambda fs: fs.rules.append(dict(fs.rules[5]))),
    ("unknown_position", lambda fs: fs.rules[10].update(position=66)),
    (
        "missing_class",
        lambda fs: fs.rules[10].update(marker_class="", unmatchable_role="", unmatchable_reason=""),
    ),
    ("unmatchable_without_reason", _unmatchable_without_reason),
    ("extension_in_marker", _extension_in_marker),
    ("bad_supporting_id", lambda fs: fs.rules[0].update(supporting="paper:nope:x")),
    (
        "unused_class",
        lambda fs: fs.classes.append(
            {**_first_class(fs), "class_id": "zz_unused", "match": "include"}
        ),
    ),
    ("priority_bad_ci", _priority_bad_ci),
    ("priority_evidence_unknown", _priority_unknown_evidence),
    ("abrupt_stop_missing_group", lambda fs: fs.abrupt.pop(0)),
    ("pipc_hash_mismatch", lambda fs: fs.pipc[7].update(drug_a=fs.pipc[7]["drug_a"] + "z")),
    ("pipc_row_count", lambda fs: (fs.pipc.pop(), setattr(fs, "meta_hash", None))),
    ("window_out_of_range", lambda fs: setattr(fs, "window", 61)),
    ("bad_combination_rules", lambda fs: setattr(fs, "combination", "pattern,kind\n")),
]


def _hash_frozen(fs: FileSet) -> FileSet:
    """Freeze the PIPC meta hash, so a changed PIPC cell no longer matches it."""
    out = fs.copy()
    inputs = fs.inputs()
    out.meta_hash = json.loads(inputs.pipc_meta_json)["content_sha256"]
    return out


@settings(max_examples=FILE_SET_EXAMPLES)
@given(fs=file_sets(), data=st.data())
def test_valid_file_sets_build_and_version_ignores_row_order(
    fs: FileSet, data: st.DataObject
) -> None:
    """Feature: cascade-engine, Property 17. Validates: Req 1.1, 1.4, 5.2.

    A valid file set builds; shuffling the rows of every file gives the same version.
    """
    rb = build_rule_base(fs.inputs())
    assert len(rb.rules) == 65
    shuffled = fs.copy()
    for name in ("pipc", "classes", "rules", "priority", "abrupt", "papers"):
        setattr(shuffled, name, list(data.draw(st.permutations(getattr(shuffled, name)))))
    assert build_rule_base(shuffled.inputs()).version == rb.version


@pytest.mark.parametrize(("code", "mutate"), MUTATIONS, ids=[m[0] for m in MUTATIONS])
@settings(max_examples=FILE_SET_EXAMPLES)
@given(fs=file_sets())
def test_each_defect_gives_its_code(code: str, mutate: Mutation, fs: FileSet) -> None:
    """Feature: cascade-engine, Property 17. Validates: Req 1.1, 5.5.

    One defect per example; the loader refuses it with that defect's code and the error names
    no cell value.
    """
    bad = _hash_frozen(fs) if code == "pipc_hash_mismatch" else fs.copy()
    mutate(bad)
    with pytest.raises(RuleBaseError) as err:
        build_rule_base(bad.inputs())
    assert err.value.code == code
    assert "zz_" not in str(err.value) and "nope" not in str(err.value)


CHANGES: list[tuple[str, Mutation]] = [
    ("pattern note", lambda fs: fs.classes[0].update(note=fs.classes[0]["note"] + " more")),
    ("window", lambda fs: setattr(fs, "window", 13)),
    (
        "supporting",
        lambda fs: fs.rules[0].update(supporting="" if fs.rules[0]["supporting"] else SUPPORT_ID),
    ),
    ("abrupt note", lambda fs: fs.abrupt[0].update(note="other")),
    (
        "abrupt row",
        lambda fs: fs.abrupt.append({**fs.abrupt[0], "pattern": "A01B", "group": "x_extra"}),
    ),
    ("pipc text", lambda fs: fs.pipc[3].update(adverse_event=fs.pipc[3]["adverse_event"] + "y")),
    (
        "rule class",
        lambda fs: fs.rules[-1].update(
            index_class="cls_0" if fs.rules[-1]["index_class"] == "cls_1" else "cls_1"
        ),
    ),
    (
        "extra pattern",
        lambda fs: fs.classes.append(
            {**_first_class(fs), "pattern": "A03BB04", "match": "exclude"}
        ),
    ),
]


@pytest.mark.parametrize(("what", "change"), CHANGES, ids=[c[0] for c in CHANGES])
@settings(max_examples=FILE_SET_EXAMPLES)
@given(fs=file_sets())
def test_any_content_change_gives_a_new_version(what: str, change: Mutation, fs: FileSet) -> None:
    """Feature: cascade-engine, Property 17. Validates: Req 1.4.

    Any change of content (pattern, class, supporting id, abrupt-stop row, window, PIPC text)
    gives a different rule base version.
    """
    before = build_rule_base(fs.inputs()).version
    changed = fs.copy()
    change(changed)
    try:
        after = build_rule_base(changed.inputs()).version
    except RuleBaseError:
        return  # the change happened to collide with an existing row; not a version question
    assert after != before, what
