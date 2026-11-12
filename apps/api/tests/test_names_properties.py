"""Property tests for name normalisation (drug-resolution design §8: P6)."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from janus.resolution.names import SALT_WORDS, fold, spelling_key, strip_salts

LETTERS = (
    "abcçdefgğhıijklmnoöprsştuüvyzABCÇDEFGĞHIİJKLMNOÖPRSŞTUÜVYZ"  # noqa: RUF001 (Turkish)
    "qwxQWXéèêàâîôûäëïæœøßÉÀÆαβγΑΒΓ"  # noqa: RUF001 (Latin-1 and Greek on purpose)
)
TEXT = st.text(alphabet=LETTERS + "0123456789%+-/.,() \t", max_size=40)
SALTY = st.lists(
    st.one_of(st.sampled_from(sorted(SALT_WORDS)), st.text(alphabet=LETTERS, min_size=1)),
    max_size=6,
).map(" ".join)


@given(text=st.one_of(TEXT, SALTY, st.text(max_size=30)))
def test_normalisation_is_idempotent(text: str) -> None:
    """Feature: drug-resolution, Property P6. Validates Req 5.3, 5.7.

    `fold`, `strip_salts∘fold` and `spelling_key∘fold` are idempotent, and `strip_salts` never
    returns an empty string for non-empty input.
    """
    f = fold(text)
    assert fold(f) == f
    s = strip_salts(f)
    assert strip_salts(s) == s
    assert fold(s) == s
    if f:
        assert s
    k = spelling_key(f)
    assert spelling_key(k) == k


@given(word=st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=12))
def test_turkish_i_and_case_variants_fold_together(word: str) -> None:
    """Feature: drug-resolution, Property P6 (fold). Case and Turkish i variants give one key."""
    variants = {
        word,
        word.upper(),
        word.replace("i", "ı"),  # noqa: RUF001
        word.upper().replace("I", "İ"),
        word.title(),
    }
    assert len({fold(v) for v in variants}) == 1


def test_examples() -> None:
    assert fold("İBUPROFEN") == fold("ibuprofen") == fold("Ibuprofen") == "ibuprofen"
    assert fold("Lidokain Hidroklorür") == "lidokain hidroklorur"
    assert strip_salts(fold("amlodipin besilat")) == "amlodipin"
    assert strip_salts(fold("METFORMIN HCL")) == "metformin"
    assert strip_salts(fold("sodyum klorür")) == "sodyum klorur"  # nothing left: unchanged
    assert strip_salts(fold("kalsiyum klorür.2H2O")) == "kalsiyum klorur"  # hydrate always goes
    assert strip_salts(fold("kalsiyum klorür dihidrat")) == "kalsiyum klorur"
    assert strip_salts(fold("isosorbid mononitrat")) == "isosorbid mononitrat"
    assert spelling_key(fold("siprofloksasin")) == spelling_key(fold("ciprofloxacin"))
    assert spelling_key(fold("dekzametazon")) == spelling_key(fold("dexamethasone"))
    assert spelling_key(fold("amlodipin")) == spelling_key(fold("amlodipine"))
    assert spelling_key(fold("parasetamol")) == spelling_key(fold("paracetamol"))
    # Pharmacologist review 2026-11-07.
    assert strip_salts(fold("sodyum bikarbonat")) != strip_salts(fold("potasyum bikarbonat"))
    assert strip_salts(fold("çinko asetat")) == "cinko asetat"
    assert strip_salts(fold("sodium calcium edetate")) != strip_salts(fold("edetate disodium"))
    assert strip_salts(fold("fluticasone furoate")) == "fluticasone furoate"
    assert strip_salts(fold("candesartan sileksetil")) == "candesartan"
    assert spelling_key(fold("iron ii")) != spelling_key(fold("iron iii"))
    assert spelling_key(fold("klorpromazin")) == spelling_key(fold("chlorpromazine"))
    assert spelling_key(fold("ketiapin")) == spelling_key(fold("quetiapine"))
    assert spelling_key(fold("folik asit")) == spelling_key(fold("folic acid"))
    assert strip_salts(fold("hiyosin butilbromür")) == "hiyosin butilbromur"


def test_spelling_key_is_idempotent_when_the_whole_key_is_a_numeral_token() -> None:
    """`yv` spells as `iv`, which is itself the numeral 4: the key reads the result again."""
    assert spelling_key("yv") == spelling_key("iv") == "4"
    assert spelling_key(spelling_key("yv")) == spelling_key("yv")
