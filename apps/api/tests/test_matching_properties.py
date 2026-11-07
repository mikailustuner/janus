"""Property tests for the name ladder (drug-resolution design §8: P16)."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from janus.resolution.matching import IndexItem, NameIndex, _tier, map_name  # pyright: ignore[reportPrivateUsage]
from janus.resolution.names import fold, spelling_key, strip_salts
from tests.resolution_strategies import SALTS, WORDS

QIDS = [f"Q{i}" for i in range(1, 7)]
NAME = st.one_of(
    st.sampled_from(WORDS),
    st.tuples(st.sampled_from(WORDS), st.sampled_from(SALTS)).map(" ".join),
    st.sampled_from(WORDS).map(lambda w: w.replace("k", "c").replace("s", "z")),
    st.sampled_from(WORDS).map(str.upper),
)


@st.composite
def items(draw: st.DrawFn) -> list[IndexItem]:
    out: list[IndexItem] = []
    for qid in draw(st.lists(st.sampled_from(QIDS), unique=True, min_size=1, max_size=5)):
        labels = draw(st.dictionaries(st.sampled_from(["en", "tr", "de"]), NAME, max_size=2))
        aliases = draw(
            st.dictionaries(
                st.sampled_from(["en", "tr"]),
                st.lists(NAME, max_size=2).map(tuple),
                max_size=2,
            )
        )
        out.append(IndexItem(qid, labels, aliases))
    return out


def _steps(index: NameIndex, name: str, turkish: bool) -> list[tuple[str, frozenset[str] | None]]:
    f = fold(name)
    s = strip_salts(f)
    return [
        ("curated_synonym", index.synonyms.get(f)),
        ("tr_label", _tier(index.tr_label, f) if turkish else None),
        ("any_label", _tier(index.any_label, f)),
        ("salt_normalised", _tier(index.salt, s)),
        ("spelling_key", _tier(index.spell, spelling_key(f))),
        ("spelling_key_salt", _tier(index.spell_salt, spelling_key(s))),
    ]


@given(
    its=items(),
    name=NAME,
    turkish=st.booleans(),
    order=st.randoms(use_true_random=False),
    synonyms=st.lists(st.tuples(NAME, st.sampled_from(QIDS)), max_size=2),
)
def test_ladder(
    its: list[IndexItem],
    name: str,
    turkish: bool,
    order: object,
    synonyms: list[tuple[str, str]],
) -> None:
    """Feature: drug-resolution, Property P16. Validates Req 5.3.

    `map_name` returns the first step with a hit (label hits before alias hits inside a step);
    several keys at that step give `ambiguous` with exactly those keys; the result does not
    depend on the order of index entries.
    """
    index = NameIndex.build(its, synonyms)
    shuffled = list(its)
    order.shuffle(shuffled)  # type: ignore[attr-defined]
    reversed_items = [
        IndexItem(
            i.qid,
            dict(reversed(list(i.labels.items()))),
            {k: tuple(reversed(v)) for k, v in i.aliases.items()},
        )
        for i in shuffled
    ]
    other = NameIndex.build(reversed_items, list(reversed(synonyms)))
    match = map_name(name, index, turkish=turkish)
    assert match == map_name(name, other, turkish=turkish)

    steps = _steps(index, name, turkish)
    first = next(((step, keys) for step, keys in steps if keys), None)
    if first is None:
        assert match.status in ("none", "unsplit")
        return
    step, keys = first
    assert match.step == step
    assert set(match.keys) == keys
    assert match.status == ("mapped" if len(keys) == 1 else "ambiguous")


@given(
    a=st.sampled_from(WORDS), b=st.sampled_from(WORDS), salt=st.sampled_from(["", " hidroklorur"])
)
def test_unsplit_names_are_flagged(a: str, b: str, salt: str) -> None:
    """Feature: drug-resolution, Property P16 (unsplit). Two known names without a separator."""
    if a == b:
        return
    index = NameIndex.build([IndexItem("Q1", {"en": a}), IndexItem("Q2", {"tr": b})])
    match = map_name(f"{a}{salt} {b}", index, turkish=True)
    assert (match.status, set(match.keys)) == ("unsplit", {"Q1", "Q2"})


def test_label_beats_alias() -> None:
    """Wikidata example: esomeprazole lists "omeprazole" as an alias."""
    index = NameIndex.build(
        [
            IndexItem("Q422210", {"en": "omeprazole"}),
            IndexItem("Q553223", {"en": "esomeprazole"}, {"en": ("omeprazole",)}),
        ]
    )
    match = map_name("OMEPRAZOLE", index, turkish=False)
    assert (match.status, match.keys) == ("mapped", ("Q422210",))


def test_bridge_only_after_unsplit_check() -> None:
    index = NameIndex.build(
        [IndexItem("Q1", {"en": "alfazin"}), IndexItem("Q2", {"en": "betorol"})],
        bridge={"alfazin betorol": {"Q1"}, "gorvacin": {"Q1", "Q2"}},
    )
    assert map_name("alfazin betorol", index, turkish=True).status == "unsplit"
    assert map_name("gorvacin", index, turkish=True).status == "ambiguous"
    assert map_name("gorvacin", index, turkish=False).status == "none"
