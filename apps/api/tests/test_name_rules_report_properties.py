"""The rule-impact report (drug-resolution task 19.1, Req 12.11, 13.3)."""

from __future__ import annotations

from collections import Counter

from hypothesis import given, settings
from hypothesis import strategies as st

from janus.resolution import name_lists
from janus.resolution.matching import IndexItem, NameIndex, map_name
from janus.resolution.name_lists import Lang
from janus.resolution.name_rules_report import (
    SourceNames,
    agreement,
    discover_words,
    evaluate_switch,
    evaluate_word,
    label_tokens_of,
    touched_names,
)
from janus.resolution.names import fold

CONS = "bcdfghjklmnpqrstvwxz"
STEM = st.text(alphabet=CONS, min_size=5, max_size=8)


def _items(stems: list[str]) -> list[IndexItem]:
    return [IndexItem(f"Q{i}", {"en": s}) for i, s in enumerate(stems, start=1)]


def _evaluate(src: SourceNames, items: list[IndexItem], word: str, **kw: object):  # type: ignore[no-untyped-def]
    wikidata = [{"label_en": i.labels["en"]} for i in items]
    return evaluate_word(
        word,
        src,
        build_index=lambda: NameIndex.build(items),
        label_tokens=label_tokens_of(wikidata),
        codes_of_key={},
        labels_of_key={i.qid: i.labels["en"] for i in items},
        **kw,  # type: ignore[arg-type]
    )


@settings(max_examples=60)
@given(
    stems=st.lists(STEM, min_size=2, max_size=4, unique=True),
    word=STEM,
    occ=st.lists(st.integers(1, 30), min_size=8, max_size=8),
    lang=st.sampled_from(["en", "fr", "es"]),
)
def test_counts_equal_an_independent_recount(
    stems: list[str], word: str, occ: list[int], lang: Lang
) -> None:
    """Feature: drug-resolution, task 19.1 (counts). Names touched, occurrences touched and
    the change counts equal a recount made with direct ladder calls."""
    if word in stems or any(word in s for s in stems):
        return
    names = [stems[0], f"{stems[0]} {word}", f"{stems[1]} {word}", f"x{stems[1]} {word}", word]
    counts = {n: occ[i] for i, n in enumerate(names)}
    src = SourceNames("synthetic", lang, counts)
    items = _items(stems)
    impact = _evaluate(src, items, word)
    touched = [n for n in counts if word in fold(n).split()]
    assert impact.names_touched == len(touched) == len(touched_names(counts, word))
    assert impact.occurrences_touched == sum(counts[n] for n in touched)
    index = NameIndex.build(items)
    expected: Counter[str] = Counter()
    expected_occ: Counter[str] = Counter()
    for n in touched:
        before = map_name(n, index, lang=lang)
        with name_lists.override(
            EXTRA_SALT_WORDS={**name_lists.EXTRA_SALT_WORDS, lang: frozenset({word})}
        ):
            after = map_name(n, index, lang=lang)
        b = before.status if before.status in ("mapped", "ambiguous") else "unmapped"
        a = after.status if after.status in ("mapped", "ambiguous") else "unmapped"
        kind = (
            f"{b}_to_{a}"
            if b != a
            else ("mapped_to_other_key" if before.keys != after.keys and b == "mapped" else None)
        )
        if kind:
            expected[kind] += 1
            expected_occ[kind] += counts[n]
    assert {k: v["names"] for k, v in impact.changes.items()} == dict(expected)
    assert {k: v["occurrences"] for k, v in impact.changes.items()} == dict(expected_occ)
    # the committed lists are restored after the evaluation
    assert word not in name_lists.EXTRA_SALT_WORDS[lang]


def test_a_word_that_changes_a_mapped_names_key_is_reported() -> None:
    """Feature: drug-resolution, task 19.1. `foo bar` maps to the label `foobar` by spelling key;
    as a salt word `bar` would send it to `foo` instead: a mapped name changes key."""
    items = [IndexItem("Q1", {"en": "foobar"}), IndexItem("Q2", {"en": "foo"})]
    src = SourceNames("synthetic", "en", {"foo bar": 40})
    impact = _evaluate(src, items, "bar")
    assert impact.changes == {"mapped_to_other_key": {"names": 1, "occurrences": 40}}
    assert impact.examples and impact.examples[0][:2] == ("foo bar", "mapped_to_other_key")


def test_a_clean_salt_word_only_adds_mappings_and_reports_the_atc_agreement() -> None:
    items = [IndexItem("Q1", {"en": "tramadol"})]
    src = SourceNames(
        "synthetic",
        "fr",
        {"xsalt de tramadol": 10, "tramadol": 5},
        single_products=[("xsalt de tramadol", "N02AX02"), ("tramadol", "N02AX02")],
    )
    wikidata = [{"label_en": "tramadol"}]
    impact = evaluate_word(
        "xsalt",
        src,
        build_index=lambda: NameIndex.build(items),
        label_tokens=label_tokens_of(wikidata),
        codes_of_key={"Q1": frozenset({"N02AX02"})},
        labels_of_key={"Q1": "tramadol"},
        env={"CONNECTORS": {**name_lists.CONNECTORS, "fr": frozenset({"de"})}},
    )
    assert impact.names_touched == 1
    assert impact.changes == {"unmapped_to_mapped": {"names": 1, "occurrences": 10}}
    assert impact.agreement == {
        "before": {"products": 1, "mapped": 0, "agree": 0},
        "after": {"products": 1, "mapped": 1, "agree": 1},
    }


def test_discover_words_finds_the_word_whose_removal_maps() -> None:
    index = NameIndex.build(_items(["tramadol", "bisoprolol"]))
    counts = {"tramadol": 9, "tramadol hcx": 7, "bisoprolol besilatx": 3, "unknown thing": 50}
    found = discover_words(counts, lambda n: map_name(n, index, lang="en"), "en")
    assert found == Counter({"hcx": 7, "besilatx": 3})


def test_agreement_counts_only_valid_codes() -> None:
    index = NameIndex.build(_items(["tramadol"]))
    out = agreement(
        [("tramadol", "N02AX02"), ("tramadol", "N02AX"), ("unknown", "N02AX02")],
        lambda n: map_name(n, index, lang="en"),
        {"Q1": frozenset({"N02AX02", "N02AX06"})},
    )
    assert out == {"products": 2, "mapped": 1, "agree": 1}


def test_switch_evaluation_restores_the_switch() -> None:
    items = _items(["infliximab"])
    src = SourceNames("synthetic", "en", {"INFLIXIMAB-DYYB": 100, "infliximab": 5})
    with name_lists.override(BIOLOGIC_SUFFIX_ENABLED=False):
        result = evaluate_switch(
            src, lambda: NameIndex.build(items), {"BIOLOGIC_SUFFIX_ENABLED": True}
        )
        assert name_lists.BIOLOGIC_SUFFIX_ENABLED is False
    assert result["names"] == {"unmapped_to_mapped": 1}
    assert result["occurrences"] == {"unmapped_to_mapped": 100}
    assert name_lists.BIOLOGIC_SUFFIX_ENABLED is True  # the committed state is back
