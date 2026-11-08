"""Properties of the coverage snapshot and comparison (drug-resolution Req 13, P45)."""

from __future__ import annotations

import json
from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st

from janus.resolution import name_lists
from janus.resolution.atc import CombinationRules, RouteMap
from janus.resolution.coverage_snapshot import (
    NameResult,
    change_kind,
    check_output_path,
    compare_names,
    load_rule_file,
    summarise,
)
from janus.resolution.load import Inputs

STATUS = st.sampled_from(["mapped", "ambiguous", "unmapped"])
NAME = st.text(alphabet="abcdefg", min_size=1, max_size=4)


@st.composite
def name_results(draw: st.DrawFn) -> NameResult:
    status = draw(STATUS)
    keys = ()
    if status == "mapped":
        keys = (draw(st.sampled_from(["Q1", "Q2", "Q3"])),)
    elif status == "ambiguous":
        keys = ("Q1", "Q2")
    return NameResult(draw(st.integers(1, 50)), status, keys, "any_label" if keys else None)


results = st.dictionaries(NAME, name_results(), max_size=10)


@given(before=results, after=results)
def test_every_changed_name_is_in_exactly_one_kind(
    before: dict[str, NameResult], after: dict[str, NameResult]
) -> None:
    """Feature: drug-resolution, Property P45 (comparison). Validates Req 13.3."""
    counted = compare_names(before, after)
    expected_changed = 0
    for name in set(before) | set(after):
        b, a = before.get(name), after.get(name)
        if b is None or a is None or change_kind(b, a) is not None:
            expected_changed += 1
    assert sum(counted["names"].values()) == expected_changed
    assert set(counted["names"]) == set(counted["occurrences"])
    assert compare_names(before, before) == {"names": {}, "occurrences": {}}


@given(r=results)
def test_mapped_name_with_other_key_is_reported(r: dict[str, NameResult]) -> None:
    """A mapped name that changes key never goes unnoticed (Req 13.3)."""
    changed = {
        n: NameResult(x.occurrences, x.status, ("Q9",) if x.status == "mapped" else x.keys, x.step)
        for n, x in r.items()
    }
    out = compare_names(r, changed)["names"].get("mapped_to_other_key", 0)
    assert out == sum(1 for x in r.values() if x.status == "mapped")


@given(
    products=st.lists(st.lists(NAME, max_size=4), max_size=8),
    data=st.data(),
)
def test_summary_equals_an_independent_recount(
    products: list[list[str]], data: st.DataObject
) -> None:
    """Feature: drug-resolution, Property P45 (recount). Validates Req 13.2."""
    names = sorted({n for p in products for n in p})
    res = {n: data.draw(name_results()) for n in names}
    # occurrences come from the products, as in the real snapshot
    counts = {n: sum(p.count(n) for p in products) for n in names}
    res = {n: NameResult(counts[n], r.status, r.keys, r.step) for n, r in res.items()}
    s = summarise(products, res)
    assert s["occurrences"] == sum(len(p) for p in products)
    assert s["occurrences_mapped"] == sum(
        1 for p in products for n in p if res[n].status == "mapped"
    )
    nonempty = [p for p in products if p]
    assert s["products_with_ingredients"] == len(nonempty)
    assert s["products_fully_mapped"] == sum(
        1 for p in nonempty if all(res[n].status == "mapped" for n in p)
    )
    assert s["multi_ingredient_products"] == sum(1 for p in nonempty if len(p) >= 2)


def test_snapshot_refuses_a_tracked_repository_path(tmp_path: object) -> None:
    import pytest

    from janus.resolution.coverage_snapshot import REPO

    with pytest.raises(ValueError, match="tracked path"):
        check_output_path(REPO / "data" / "names-x.json")
    assert check_output_path(REPO / ".data" / "resolution" / "names-x.json").name == "names-x.json"


def test_rule_file_is_a_what_if_and_changes_nothing_committed(tmp_path: Path) -> None:
    """The `--rules` file gives name-list overrides and extra rows for one run (task 20)."""
    rules = tmp_path / "rules.json"
    rules.write_text(
        json.dumps(
            {
                "extra_salt_words": {"fr": ["zzword"]},
                "connectors": {"fr": ["de"]},
                "switches": ["es_final_vowel"],
                "anion_acid": [["any", "Mycophenolate", "mycophenolic acid", "candidate"]],
                "synonyms": [["foo", "Q1"]],
            }
        ),
        encoding="utf-8",
    )
    inputs = Inputs(
        {},
        CombinationRules.load(),
        RouteMap.load(),
        (("a", "Q9"),),
        "code",  # pyright: ignore[reportArgumentType]
    )
    changes, new = load_rule_file(rules, inputs)
    assert changes["EXTRA_SALT_WORDS"]["fr"] == name_lists.EXTRA_SALT_WORDS["fr"] | {"zzword"}
    assert changes["EXTRA_SALT_WORDS"]["en"] == name_lists.EXTRA_SALT_WORDS["en"]
    assert changes["CONNECTORS"]["fr"] == name_lists.CONNECTORS["fr"] | {"de"}
    assert changes["ES_FINAL_VOWEL_ENABLED"] is True
    assert [(r.lang, r.anion, r.acid) for r in new.acid.rows] == [
        ("any", "mycophenolate", "mycophenolic acid")
    ]
    assert new.synonyms == (("a", "Q9"), ("foo", "Q1"))
    assert "zzword" not in name_lists.EXTRA_SALT_WORDS["fr"]  # nothing was changed globally
    assert name_lists.ES_FINAL_VOWEL_ENABLED is False
