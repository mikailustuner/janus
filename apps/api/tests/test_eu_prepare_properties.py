"""Properties of the French and Spanish ingredient lists (drug-resolution Phase 2)."""

from __future__ import annotations

from typing import Any

from hypothesis import given
from hypothesis import strategies as st

from janus.resolution.prepare_eu import (
    UNNAMED,
    bdpm_ingredients,
    cima_ingredients,
    is_homeopathic_name,
)

NAMES = st.text(alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ ÉÈÂ'()-", min_size=1, max_size=18).filter(
    lambda s: s.strip() != ""
)


@st.composite
def compositions(draw: st.DrawFn) -> list[dict[str, Any]]:
    """Lines of one presentation: links with 0-3 FT and 0-3 SA lines, lines in any order."""
    lines: list[dict[str, Any]] = []
    for link in range(1, draw(st.integers(1, 5)) + 1):
        for nature, hi in (("FT", 3), ("SA", 3)):
            for _ in range(draw(st.integers(0, hi))):
                lines.append(
                    {
                        "form": "comprimé",
                        "substance_code": "1",
                        "substance_name": draw(NAMES),
                        "dosage": draw(st.sampled_from(["1,00 mg", " 5 mg", "2CH à 30CH"])),
                        "reference": "un comprimé",
                        "nature": nature,
                        "link": str(link),
                    }
                )
    return draw(st.permutations(lines))


def _reference(lines: list[dict[str, Any]]) -> list[tuple[str, str]]:
    order: list[str] = []
    for line in lines:
        if line["link"] not in order:
            order.append(line["link"])
    out: list[tuple[str, str]] = []
    for link in order:
        mine = [ln for ln in lines if ln["link"] == link]
        chosen = [ln for ln in mine if ln["nature"] == "FT"] or mine
        out += [(ln["substance_name"], ln["dosage"]) for ln in chosen]
    return out


@given(lines=compositions())
def test_bdpm_ingredients_ft_before_sa(lines: list[dict[str, Any]]) -> None:
    """Feature: drug-resolution, Property P29. Validates Req 5.8.

    Per link in first-occurrence order the FT names stand for the ingredient, else the SA names;
    every line is either an ingredient or counted as superseded; links are never merged.
    """
    ings, stats = bdpm_ingredients(lines)
    assert [(i.name, i.strength) for i in ings] == _reference(lines)
    assert len(ings) + stats.superseded_sa_lines == len(lines)
    assert stats.links == len({ln["link"] for ln in lines})
    for ln in lines:  # names are the published text, unchanged
        if ln["nature"] == "FT":
            assert any(i.name == ln["substance_name"] for i in ings)


def test_bdpm_example_metformin_vildagliptin() -> None:
    """The FT + SA pair of the BDPM (link 1) and a second substance (link 2)."""
    lines = [
        {"nature": "FT", "link": "1", "substance_name": "METFORMINE", "dosage": "500 mg"},
        {
            "nature": "SA",
            "link": "1",
            "substance_name": "CHLORHYDRATE DE METFORMINE",
            "dosage": "1 g",
        },
        {"nature": "SA", "link": "2", "substance_name": "VILDAGLIPTINE", "dosage": "50 mg"},
    ]
    ings, stats = bdpm_ingredients(lines)
    assert [i.name for i in ings] == ["METFORMINE", "VILDAGLIPTINE"]
    assert stats.superseded_sa_lines == 1


def test_bdpm_line_without_link_is_its_own_ingredient() -> None:
    lines = [
        {"nature": "SA", "link": None, "substance_name": "A", "dosage": None},
        {"nature": "SA", "link": "", "substance_name": "B", "dosage": None},
    ]
    ings, _ = bdpm_ingredients(lines)
    assert [i.name for i in ings] == ["A", "B"]


@given(
    st.lists(
        st.tuples(st.one_of(st.none(), st.integers(0, 5)), NAMES),
        max_size=8,
    )
)
def test_cima_ingredients_follow_orden_colacion(items: list[tuple[int | None, str]]) -> None:
    """Ingredients in `orden_colacion` order, a missing order last, file order breaking ties."""
    raw = [{"order": o, "name": n, "dose": "5", "dose_unit": "mg"} for o, n in items]
    out = cima_ingredients(raw)
    expected = sorted(enumerate(items), key=lambda p: (p[1][0] is None, p[1][0] or 0, p[0]))
    assert [i.name for i in out] == [n for _, (_, n) in expected]
    assert all(i.strength == "5 mg" for i in out)


def test_cima_unnamed_ingredient_is_kept_visible() -> None:
    out = cima_ingredients([{"order": 1, "name": None, "dose": None, "dose_unit": None}])
    assert [(i.name, i.strength) for i in out] == [(UNNAMED, None)]


@given(
    base=NAMES,
    accents=st.booleans(),
    case=st.sampled_from(["upper", "lower", "title"]),
)
def test_homeopathic_marker_found_with_or_without_accents(
    base: str, accents: bool, case: str
) -> None:
    """Feature: drug-resolution, Property P41 (name part). Validates Req 12.10."""
    marker = "POUR PRÉPARATIONS HOMÉOPATHIQUES" if accents else "POUR PREPARATIONS HOMEOPATHIQUES"
    marker = {"upper": marker.upper(), "lower": marker.lower(), "title": marker.title()}[case]
    assert is_homeopathic_name(f"{base} {marker}")
    assert not is_homeopathic_name(base.replace("HOME", "").replace("PREPARATION", ""))
