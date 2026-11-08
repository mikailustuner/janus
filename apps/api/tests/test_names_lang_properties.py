"""Language-aware name functions (drug-resolution Phase 2: P34, P35, P36, P39, P40)."""

from __future__ import annotations

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from janus.resolution import name_lists, names
from janus.resolution.matching import IndexItem, NameIndex, detect_unsplit, map_name
from janus.resolution.name_lists import LANGS, Lang
from janus.resolution.names import fold, spelling_key, strip_salts
from tests import frozen_matching as fm
from tests import frozen_names as fn
from tests.name_rule_data import (
    ALL_SWITCHES,
    ES_CONNECTORS,
    FR_CONNECTORS,
    TEST_LISTS,
    effective_salts,
    rule_data,
    with_everything,
)

LETTERS = "abcçdefgğhıijklmnoöprsştuüvyzABCÇDEFGĞHIİJKLMNOÖPRSŞTUÜVYZqwxQWXéèêàâîôûäëï"  # noqa: RUF001
TEXT = st.text(alphabet=LETTERS + " -'()0123456789", max_size=40)
LANG = st.sampled_from(LANGS)
CONSONANTS = "bcdfghjklmnpqrstvwxz"
WORD = st.text(alphabet=CONSONANTS, min_size=5, max_size=9)


def _all_lists() -> set[str]:
    out = set(name_lists.BASE_SALT_WORDS) | set(name_lists.BASE_NOT_ALONE)
    for d in (name_lists.EXTRA_SALT_WORDS, name_lists.EXTRA_NOT_ALONE, name_lists.CONNECTORS):
        for words in d.values():
            out |= set(words)
    return out


# --- P34 ------------------------------------------------------------------------------------


@given(text=TEXT, lang=LANG)
def test_p34_idempotent_and_non_empty_in_every_language(text: str, lang: Lang) -> None:
    """Feature: drug-resolution, Property P34. Validates Req 12.1, 12.2, 5.7.

    `strip_salts` and `spelling_key` are idempotent and `strip_salts` is never empty, for every
    language, with the Phase 1 lists and with the test lists and switches on.
    """
    for ctx in (rule_data(), with_everything()):
        with ctx:
            f = fold(text)
            s = strip_salts(f, lang)
            assert strip_salts(s, lang) == s
            if f:
                assert s
            k = spelling_key(f, lang)
            assert spelling_key(k, lang) == k


@given(text=TEXT, lang=st.sampled_from(["tr", "en"]))
def test_p34_phase1_equality_with_empty_lists(text: str, lang: Lang) -> None:
    """Feature: drug-resolution, Property P34. With the committed lists, `tr` and `en` equal the
    frozen Phase 1 functions for every name."""
    f = fold(text)
    assert f == fn.fold(text)
    assert strip_salts(f, lang) == fn.strip_salts(f)
    assert spelling_key(f, lang) == fn.spelling_key(f)


@given(
    tokens=st.lists(
        st.one_of(st.sampled_from(sorted(name_lists.BASE_SALT_WORDS)[:60]), WORD), max_size=5
    ),
    lang=st.sampled_from(["tr", "en"]),
)
def test_p34_phase1_equality_survives_other_languages_lists(tokens: list[str], lang: Lang) -> None:
    """Names without a Phase 2 word give the Phase 1 result in `tr`/`en` even with all test lists
    and switches set (they only add words of their own languages and `fr`/`es` rules)."""
    f = " ".join(tokens)
    with with_everything():
        banned = set(TEST_LISTS["EXTRA_SALT_WORDS"][lang]) | set(
            TEST_LISTS["EXTRA_NOT_ALONE"][lang]
        )
        assume(not banned & set(f.split()))
        assert strip_salts(f, lang) == fn.strip_salts(f)
        assert spelling_key(f, lang) == fn.spelling_key(f)


EMPTY_LISTS: dict[Lang, frozenset[str]] = {lg: frozenset[str]() for lg in LANGS}
PHASE1_STATE: dict[str, object] = {
    "EXTRA_SALT_WORDS": EMPTY_LISTS,
    "EXTRA_NOT_ALONE": EMPTY_LISTS,
    "CONNECTORS": EMPTY_LISTS,
    "BIOLOGIC_SUFFIX_ENABLED": False,
    "ES_FINAL_VOWEL_ENABLED": False,
    "ACID_WORD_ORDER_ENABLED": False,
}


def test_p34_rules_version_follows_every_list_and_switch() -> None:
    """The version changes with every list and every switch, and returns when they are restored.

    (The committed lists are the accepted Phase 2 data; the Phase 1 state is set by hand.)
    """
    committed = names.rules_version()
    with rule_data(**PHASE1_STATE):
        base = names.rules_version()
        assert base != committed  # the accepted lists are part of the version
        seen = {base}
        changes: list[dict[str, object]] = [
            {"EXTRA_SALT_WORDS": {**EMPTY_LISTS, "fr": frozenset({"x1"})}},
            {"EXTRA_NOT_ALONE": {**EMPTY_LISTS, "es": frozenset({"x2"})}},
            {"CONNECTORS": {**EMPTY_LISTS, "fr": frozenset({"de"})}},
            {"BIOLOGIC_SUFFIX_ENABLED": True},
            {"ES_FINAL_VOWEL_ENABLED": True},
            {"ACID_WORD_ORDER_ENABLED": True},
        ]
        for change in changes:
            with rule_data(**change):
                v = names.rules_version()
            assert v not in seen
            seen.add(v)
        assert names.rules_version() == base
    assert names.rules_version() == committed  # restored


def test_p34_accepted_switches_are_the_owners_decision() -> None:
    """Owner decision 2026-11-08: biologic_suffix and acid_word_order on, es_final_vowel off."""
    assert name_lists.BIOLOGIC_SUFFIX_ENABLED is True
    assert name_lists.ACID_WORD_ORDER_ENABLED is True
    assert name_lists.ES_FINAL_VOWEL_ENABLED is False
    assert name_lists.CONNECTORS["fr"] == frozenset({"de", "d"})
    assert name_lists.CONNECTORS["es"] == frozenset({"de"})
    assert "lauroxil" not in name_lists.EXTRA_SALT_WORDS["en"]  # prodrugs stay out


@given(
    words=st.lists(
        st.tuples(WORD, st.sampled_from(["tr", "en", "de", "fr", "es"]), st.booleans()),
        min_size=1,
        max_size=6,
        unique_by=lambda t: t[0],
    ),
    queries=st.lists(
        st.one_of(WORD, st.sampled_from(sorted(name_lists.BASE_SALT_WORDS)[:30])),
        min_size=1,
        max_size=4,
    ),
    lang=st.sampled_from(["tr", "en"]),
    salt=st.sampled_from(sorted(name_lists.BASE_SALT_WORDS)[:40]),
)
def test_p34_ladder_equals_frozen_ladder_for_tr_and_en(
    words: list[tuple[str, str, bool]], queries: list[str], lang: Lang, salt: str
) -> None:
    """Feature: drug-resolution, Property P34 (ladder). With the committed rule data the new
    ladder returns what the frozen Phase 1 ladder returns, for Turkish and English names."""
    items = [IndexItem(f"Q{i}", {lbl: w}) for i, (w, lbl, _) in enumerate(words, start=1)]
    new = NameIndex.build(items)
    old = fm.NameIndex.build([fm.IndexItem(i.qid, i.labels, i.aliases) for i in items])
    names_ = [*queries, *(w for w, _, _ in words), *(f"{w} {salt}" for w, _, _ in words)]
    for q in names_:
        a = map_name(q, new, lang=lang)
        b = fm.map_name(q, old, turkish=lang == "tr")
        assert (a.status, a.step, a.keys) == (b.status, b.step, b.keys)


# --- P35 / P36 / P39 / P40 ------------------------------------------------------------------


@given(
    base=st.lists(WORD, min_size=1, max_size=2),
    lang=st.sampled_from(["fr", "es"]),
    before=st.lists(st.integers(0, 3), max_size=3),
    after=st.lists(st.integers(0, 3), max_size=3),
)
def test_p35_salts_hydrates_and_connectors_around_a_base(
    base: list[str], lang: Lang, before: list[int], after: list[int]
) -> None:
    """Feature: drug-resolution, Property P35. Validates Req 12.2, 12.3.

    A base name with salt, hydrate and connector words of its language around it, in the
    language's word order (salt + connector before, or salt after), strips to the base.
    """
    with with_everything():
        salts = sorted(effective_salts(lang) - {"chlorure"})
        connectors = sorted(TEST_LISTS["CONNECTORS"][lang])
        assume(not set(base) & (set(salts) | set(connectors) | _all_lists()))
        pre: list[str] = []
        for i in before:
            pre += [salts[i % len(salts)], connectors[i % len(connectors)]]
        post = [salts[i % len(salts)] for i in after]
        name = " ".join([*pre, *base, *post])
        assert strip_salts(name, lang) == " ".join(base)
        # a name made only of such words is returned (hydrate-free) and never empty
        only = " ".join([*pre, *post]) or salts[0]
        assert strip_salts(only, lang)


@given(base=WORD, lang=LANG)
def test_p35_ladder_result_equals_the_base_result(base: str, lang: Lang) -> None:
    """The ladder gives a salt-decorated name the result of its base."""
    with with_everything():
        assume(base not in _all_lists())
        index = NameIndex.build([IndexItem("Q1", {"en": base})])
        salts = sorted(effective_salts(lang) - {"chlorure"})
        decorated = f"{salts[0]} {sorted(TEST_LISTS['CONNECTORS'][lang] or {''})[0]} {base}"
        a, b = map_name(decorated, index, lang=lang), map_name(base, index, lang=lang)
        assert (a.status, a.keys) == (b.status, b.keys) == ("mapped", ("Q1",))


@given(lang=LANG, data=st.data())
def test_p36_counter_ion_substances_stay_apart(lang: Lang, data: st.DataObject) -> None:
    """Feature: drug-resolution, Property P36. Validates Req 12.4.

    Two names that differ only in a salt word next to a counter-ion that is a substance
    (zinc acetate / zinc gluconate, sodium / potassium bicarbonate) do not strip to the same
    name, and a prodrug ester word that is in no list is never removed.
    """
    with with_everything():
        alone = sorted(name_lists.BASE_NOT_ALONE | name_lists.EXTRA_NOT_ALONE[lang])
        salts = sorted(
            w
            for w in effective_salts(lang)
            if not names._is_hydrate(w, lang)  # pyright: ignore[reportPrivateUsage]
        )
        z = data.draw(st.sampled_from(alone))
        s1, s2 = data.draw(st.lists(st.sampled_from(salts), min_size=2, max_size=2, unique=True))
        assume(z not in salts)
        assert strip_salts(f"{z} {s1}", lang) != strip_salts(f"{z} {s2}", lang)
        for prodrug in ("lauroxil", "enacarbil"):
            assert prodrug not in effective_salts(lang)
            assert strip_salts(f"abcdefg {prodrug}", lang) == f"abcdefg {prodrug}"


def _index(*pairs: tuple[str, str]) -> NameIndex:
    return NameIndex.build([IndexItem(q, {"en": label}) for q, label in pairs])


@given(
    a=WORD,
    b=WORD,
    lang=st.sampled_from(["fr", "es"]),
    salt_i=st.integers(0, 3),
    conn_i=st.integers(0, 1),
    order=st.sampled_from(["salt_conn_a", "a_salt", "a_salt_conn", "conn_a"]),
)
def test_p39_salt_and_connector_words_are_never_an_ingredient(
    a: str, b: str, lang: Lang, salt_i: int, conn_i: int, order: str
) -> None:
    """Feature: drug-resolution, Property P39. Validates Req 12.12, 5.3.

    A name made of one known ingredient and salt or connector words is never `unsplit`, even when
    the salt or connector word is itself a label in the index (as `d` is in Wikidata); two known
    ingredients side by side still are.
    """
    with with_everything():
        salt = sorted(TEST_LISTS["EXTRA_SALT_WORDS"][lang])[salt_i % 4]
        conn = sorted(TEST_LISTS["CONNECTORS"][lang])[conn_i % 2]
        assume(len({a, b}) == 2 and not {a, b} & _all_lists())
        index = _index(("Q1", a), ("Q2", b), ("Q3", salt), ("Q4", conn))
        name = {
            "salt_conn_a": f"{salt} {conn} {a}",
            "a_salt": f"{a} {salt}",
            "a_salt_conn": f"{a} {salt} {conn}",
            "conn_a": f"{conn} {a}",
        }[order]
        assert detect_unsplit(name, index, lang) is None
        assert map_name(name, index, lang=lang).status != "unsplit"
        both = detect_unsplit(f"{a} {b}", index, lang)
        assert both == tuple(sorted(["Q1", "Q2"]))


@given(
    label=st.text(alphabet=CONSONANTS, min_size=8, max_size=12),
    cut=st.integers(3, 6),
    lang=LANG,
)
def test_p40_a_part_of_a_name_is_not_guessed(label: str, cut: int, lang: Lang) -> None:
    """Feature: drug-resolution, Property P40. Validates Req 12.9.

    A name that is only part of a label or of a combination string maps to nothing: there is no
    substring, prefix or fuzzy matching. A curated synonym maps its exact folded name only.
    """
    with with_everything():
        assume(label not in _all_lists())
        part = label[:cut]
        assume(part not in _all_lists() and spelling_key(part, lang) != spelling_key(label, lang))
        index = NameIndex.build([IndexItem("Q1", {"en": label})], [(label + "x", "Q1")])
        assert map_name(part, index, lang=lang).status == "none"
        assert map_name(f"{part}\\{part}", index, lang=lang).status != "mapped"
        assert map_name(label + "x", index, lang=lang).step == "curated_synonym"
        assert map_name(label + "xy", index, lang=lang).status != "mapped"


@pytest.mark.parametrize(
    ("name", "lang", "expected"),
    [
        ("chlorhydrate de tramadol", "fr", "tramadol"),
        ("amlodipino besilato", "es", "amlodipino"),
        ("sodium (chlorure de)", "fr", "sodium chlorure de"),
    ],
)
def test_examples_of_the_reviewed_shapes(name: str, lang: Lang, expected: str) -> None:
    with rule_data(**TEST_LISTS):
        assert strip_salts(fold(name), lang) == expected


def test_french_acid_word_order_and_spanish_final_vowel_are_switchable() -> None:
    ref = spelling_key(fold("ascorbic acid"))
    off = {k: False for k in ALL_SWITCHES}
    with rule_data(**off):
        assert spelling_key(fold("acide ascorbique"), "fr") != ref
        assert spelling_key(fold("duloxetina"), "es") != spelling_key(fold("duloxetine"))
    with rule_data(**ALL_SWITCHES):
        assert spelling_key(fold("acide ascorbique"), "fr") == ref
        assert spelling_key(fold("ascorbico acido"), "es") == ref
        assert spelling_key(fold("duloxetina"), "es") == spelling_key(fold("duloxetine"))
        assert spelling_key(fold("sildenafilo"), "es") == spelling_key(fold("sildenafil"))
        # English names are not touched by the Spanish rule
        assert spelling_key(fold("duloxetina"), "en") == fn.spelling_key(fold("duloxetina"))
    # the committed state: acid order on, Spanish vowel rule off
    assert spelling_key(fold("acide ascorbique"), "fr") == ref
    assert spelling_key(fold("duloxetina"), "es") != spelling_key(fold("duloxetine"))


def test_connector_sets_are_what_the_test_lists_say() -> None:
    assert FR_CONNECTORS >= {"de", "d"} and ES_CONNECTORS >= {"de", "del"}


@given(
    stems=st.lists(WORD, min_size=1, max_size=4, unique=True),
    ending=st.sampled_from(["a", "o", "ina", "ato"]),
    label_lang=st.sampled_from(["es", "fr", "en"]),
    lang=st.sampled_from(["tr", "en"]),
)
def test_p34_french_and_spanish_rule_data_never_unmaps_a_turkish_or_english_name(
    stems: list[str], ending: str, label_lang: str, lang: Lang
) -> None:
    """Feature: drug-resolution, Property P34 (monotonic). Validates Req 12.1, 13.3.

    Turning on the French and Spanish lists and switches only adds keys for French and Spanish
    labels, so a Turkish or English name that mapped before still maps (or becomes ambiguous if
    a new key collides); it never becomes unmapped. (The first version of the Spanish vowel rule
    replaced the keys of Spanish labels and unmapped 5 TİTCK names on the real data.)
    """
    items = [IndexItem(f"Q{i}", {label_lang: s + ending}) for i, s in enumerate(stems, start=1)]
    items += [IndexItem(f"Q9{i}", {"en": s + "e"}) for i, s in enumerate(stems, start=1)]
    queries = [*stems, *(s + ending for s in stems), *(s + "e" for s in stems)]
    off_index = NameIndex.build(items)
    off = {q: map_name(q, off_index, lang=lang) for q in queries}
    with with_everything():
        on_index = NameIndex.build(items)
        on = {q: map_name(q, on_index, lang=lang) for q in queries}
    for q in queries:
        if off[q].status == "mapped":
            assert on[q].status in ("mapped", "ambiguous"), q
