"""The anion-acid step and the biologic-suffix step (drug-resolution P37, P38)."""

from __future__ import annotations

import pytest
from hypothesis import assume, example, given
from hypothesis import strategies as st

from janus.resolution.anion_acid import AnionAcidTable
from janus.resolution.atc import RulesFileError
from janus.resolution.matching import IndexItem, NameIndex, map_name
from janus.resolution.name_lists import LANGS, Lang
from janus.resolution.names import fold, strip_salts
from tests.name_rule_data import rule_data, with_everything

CONSONANTS = "bcdfghjklmnpqrstvwxz"
WORD = st.text(alphabet=CONSONANTS, min_size=5, max_size=9)
LANG = st.sampled_from(LANGS)
HEADER = "lang,anion,acid,note\n"


def _table(*rows: tuple[str, str, str]) -> AnionAcidTable:
    text = HEADER + "".join(f"{lang},{anion},{acid},evidence\n" for lang, anion, acid in rows)
    return AnionAcidTable.from_csv_text(text)


# --- P37: anion-acid ------------------------------------------------------------------------


@given(stem=WORD, lang=LANG, row_lang=st.sampled_from([*LANGS, "any"]))
def test_p37_step_lands_only_on_the_acid_label(stem: str, lang: Lang, row_lang: str) -> None:
    """Feature: drug-resolution, Property P37. Validates Req 12.6, 12.7.

    A name that is a reviewed anion maps through the label steps of its acid and nowhere else;
    a table row of another language does not apply; the step is `anion_acid`.
    """
    anion, acid = f"{stem}ate", f"{stem}ic acid"
    index = NameIndex.build([IndexItem("Q1", {"en": acid})], acid=_table((row_lang, anion, acid)))
    m = map_name(f"{anion} sodium", index, lang=lang)
    if row_lang in (lang, "any"):
        assert (m.status, m.step, m.keys) == ("mapped", "anion_acid", ("Q1",))
    else:
        assert m.status == "none"
    assert map_name(stem + "ate" + "q", index, lang=lang).status == "none"


@given(stem=WORD, lang=LANG)
def test_p37_an_earlier_step_always_wins(stem: str, lang: Lang) -> None:
    """The step never changes a name that steps 0-5 map: the anion is also a label of Q2."""
    anion, acid = f"{stem}ate", f"{stem}ic acid"
    index = NameIndex.build(
        [IndexItem("Q1", {"en": acid}), IndexItem("Q2", {"en": anion})],
        acid=_table(("any", anion, acid)),
    )
    m = map_name(anion, index, lang=lang)
    assert (m.status, m.step, m.keys) == ("mapped", "any_label", ("Q2",))


@given(stem=WORD)
def test_p37_two_acids_for_one_anion_are_ambiguous_never_chosen(stem: str) -> None:
    anion = f"{stem}ate"
    index = NameIndex.build(
        [IndexItem("Q1", {"en": f"{stem}ic acid"}), IndexItem("Q2", {"en": f"{stem}oic acid"})],
        acid=_table(("any", anion, f"{stem}ic acid"), ("en", anion, f"{stem}oic acid")),
    )
    m = map_name(anion, index, lang="en")
    assert (m.status, m.step, m.keys) == ("ambiguous", "anion_acid", ("Q1", "Q2"))


def test_p37_table_loader_refuses_bad_rows() -> None:
    bad = [
        "lang,anion\nen,x\n",  # header
        HEADER + "xx,a,b,note\n",  # unknown language
        HEADER + "en,,b,note\n",  # empty anion
        HEADER + "en,a,a,note\n",  # anion == acid
        HEADER + "en,a,b,\n",  # no evidence
        HEADER + "en,Mycophenolate,x,n\nen,mycophenolate,y,n\n",  # repeated after folding
    ]
    for text in bad:
        with pytest.raises(RulesFileError):
            AnionAcidTable.from_csv_text(text)
    ok = _table(("any", "mycophenolate", "mycophenolic acid"), ("en", "other", "x"))
    assert ok.lookup("fr", "mycophenolate") == ("mycophenolic acid",)
    assert ok.lookup("fr", "other") == ()
    assert AnionAcidTable.from_csv_text(HEADER).rows == ()


def test_p37_acid_must_resolve_to_exactly_one_key() -> None:
    table = _table(("any", "a", "b"))
    table.check_acids(lambda label: ["Q1"])
    for keys in ([], ["Q1", "Q2"]):
        with pytest.raises(RulesFileError):
            table.check_acids(lambda label, keys=keys: keys)


def test_p37_committed_table_is_the_reviewed_one() -> None:
    """The seven accepted rows (name-rules review, Appendix B), valid and each with a note."""
    table = AnionAcidTable.load()
    assert len(table.rows) == 7
    assert table.lookup("fr", "mycophenolate") == ("mycophenolic acid",)
    assert table.lookup("es", "micofenolato") == ("mycophenolic acid",)
    assert table.lookup("en", "micofenolato") == ()
    assert all(r.note and "salicylate" not in r.anion for r in table.rows)


def test_p37_salicylate_salts_do_not_become_salicylic_acid() -> None:
    """No generic rewrite: without a row, `magnesium salicylate` maps to nothing."""
    index = NameIndex.build([IndexItem("Q1", {"en": "salicylic acid"})], acid=_table())
    assert map_name("magnesium salicylate", index, lang="en").status == "none"
    assert strip_salts(fold("magnesium salicylate"), "en") == "salicylate"


# --- P38: biologic suffix -------------------------------------------------------------------


def _bio_index(*pairs: tuple[str, str]) -> NameIndex:
    return NameIndex.build([IndexItem(q, {"en": label}) for q, label in pairs])


SUFFIX = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ", min_size=4, max_size=4
)


@given(base=WORD, suffix=SUFFIX)
def test_p38_base_suffix_maps_to_the_base(base: str, suffix: str) -> None:
    """Feature: drug-resolution, Property P38. Validates Req 12.8.

    `BASE-XXXX` (any four ASCII letters, any case) maps to the key of BASE with step
    `biologic_suffix` when BASE maps by a label to exactly one key.
    """
    assume(fold(suffix) not in fold(base))
    index = _bio_index(("Q1", base))
    with rule_data(BIOLOGIC_SUFFIX_ENABLED=True):
        for name in (f"{base}-{suffix}", f"{base.upper()}-{suffix.upper()}"):
            m = map_name(name, index, lang="en")
            assert (m.status, m.step, m.keys) == ("mapped", "biologic_suffix", ("Q1",))


def _not_by_suffix(name: str, index: NameIndex, lang: Lang = "en") -> bool:
    """The suffix rule does not map `name`. Another step may: the spelling key folds variant
    letters and repeated letters, so a generated `bbbbb-bae` can equal the label `bbbbb`."""
    m = map_name(name, index, lang=lang)
    return m.status == "none" or m.step != "biologic_suffix"


# Counterexamples found by the nightly profile (random seeds), pinned (docs/testing.md).
@example(base="bbbbb", suffix="BAEA", other="tr")
@given(base=WORD, suffix=SUFFIX, other=st.sampled_from(["tr", "fr", "es"]))
def test_p38_near_misses_and_switch_change_nothing(base: str, suffix: str, other: Lang) -> None:
    index = _bio_index(("Q1", base))
    with rule_data(BIOLOGIC_SUFFIX_ENABLED=False):
        assert _not_by_suffix(f"{base}-{suffix}", index)  # switch off
    with rule_data(BIOLOGIC_SUFFIX_ENABLED=True):
        near = [
            f"{base}-{suffix[:3]}",  # three letters
            f"{base}-{suffix}x",  # five letters
            f"{base}-{suffix[:3]}1",  # a digit
            f"{base} {suffix}",  # no hyphen
            f"{base}{suffix}",
            f"-{suffix}",  # no base
        ]
        for name in near:
            assert _not_by_suffix(name, index), name
        # not English: no effect
        assert _not_by_suffix(f"{base}-{suffix}", index, lang=other)
        # an unmapped base stays unmapped
        assert _not_by_suffix(f"zq{base}-{suffix}", index)


@example(base="bbbbc", suffix="CCCH")
@given(base=WORD, suffix=SUFFIX)
def test_p38_ambiguous_base_and_earlier_steps(base: str, suffix: str) -> None:
    with rule_data(BIOLOGIC_SUFFIX_ENABLED=True):
        two = _bio_index(("Q1", base), ("Q2", base))  # the base is ambiguous: not mapped
        assert map_name(f"{base}-{suffix}", two, lang="en").status != "mapped"
        # the whole name is itself a label: step any_label wins, the suffix rule is not used
        whole = _bio_index(("Q1", base), ("Q2", f"{base}-{suffix}"))
        m = map_name(f"{base}-{suffix}", whole, lang="en")
        assert (m.step, m.keys) == ("any_label", ("Q2",))


def test_p38_examples() -> None:
    index = _bio_index(
        ("Q1", "infliximab"), ("Q2", "insulin glargine"), ("Q3", "interferon alfa-2b")
    )
    with with_everything():
        assert map_name("INFLIXIMAB-DYYB", index, lang="en").keys == ("Q1",)
        assert map_name("INSULIN GLARGINE-YFGN", index, lang="en").keys == ("Q2",)
        assert map_name("INTERFERON ALFA-2B-NJFT", index, lang="en").keys == ("Q3",)
        assert map_name("RISANKIZUMAB-RZAA", index, lang="en").status == "none"
