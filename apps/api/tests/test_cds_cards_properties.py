"""Cards of the CDS Hooks service: P2-P5 (cds-hooks task 3). Pure."""

from __future__ import annotations

from typing import Any

from hypothesis import given
from hypothesis import strategies as st

from janus.cascades.model import ABRUPT_STOP_TEXT
from janus.cascades.schemas import (
    DISCLAIMER,
    CascadeResult,
    FindingOut,
    IndexSideOut,
    PriorityOut,
    RulesOut,
    RuleTextOut,
    SideOut,
)
from janus.cds import cards
from janus.cds.fhir import Origin
from janus.notes.phrases import LANGUAGES, violations

ORIGINS: list[Origin] = ["selected", "draft", "active", "statement"]
# Generated names stand in for real ingredient names: a name that itself contains a word from
# the medical-language lists (e.g. "SIN PROBLEMA") is not a wording defect of the card template.
LABELS = st.one_of(
    st.none(),
    st.text(min_size=1, max_size=120).filter(
        lambda t: t.strip() != "" and all(violations(t, lang) == ([], []) for lang in LANGUAGES)
    ),
)


def side(items: list[int], label: str | None, index: bool, confirmed: bool = True) -> Any:
    data: dict[str, Any] = {
        "ingredient_key": "Q1",
        "label_en": label,
        "items": items,
        "matched_codes": ["C08CA01"],
        "form_confirmed": confirmed,
        "start": None,
    }
    return IndexSideOut(**data, via_form_extension=False) if index else SideOut(**data)


@st.composite
def findings(draw: st.DrawFn, n_items: int) -> FindingOut:
    row = draw(st.integers(1, 65))
    i_items = draw(st.lists(st.integers(0, n_items - 1), min_size=1, max_size=2, unique=True))
    m_items = draw(st.lists(st.integers(0, n_items - 1), min_size=1, max_size=2, unique=True))
    priority = draw(
        st.none()
        | st.builds(
            PriorityOut,
            measure=st.sampled_from(["incidence", "adjusted_sequence_ratio"]),
            value=st.just("1.9"),
            ci_low=st.just("1.7"),
            ci_high=st.just("2.1"),
            unit=st.sampled_from(["percent", "ratio"]),
            locator=st.just("Abstract, results"),
            evidence_id=st.just("paper:bmj_2026:e100499"),
        )
    )
    return FindingOut(
        finding_id=f"f{row}-{draw(st.integers(0, 9))}",
        rule_id=f"pipc:{row}",
        rule_evidence_id=f"rule:pipc:{row}",
        rule_text=RuleTextOut(
            system="Cardiovascular system",
            kind="drug_class",
            drug_a="Calcium channel blocker",
            adverse_event="Peripheral oedema",
            drug_b="Diuretic",
            locator=f"Table 1, row {row}",
        ),
        index=side(i_items, draw(LABELS), True, draw(st.booleans())),
        marker=side(m_items, draw(LABELS), False, draw(st.booleans())),
        status=draw(st.sampled_from(["possible", "probable"])),
        timing="date_unknown",
        months_between=None,
        low_priority=False,
        form_confirmed=True,
        via_form_extension=False,
        priority=priority,
        abrupt_stop=draw(st.lists(st.sampled_from(["index", "marker"]), unique=True)),
        evidence_ids=[f"rule:pipc:{row}", "dataset:pipc"]
        + (["dataset:faers"] if draw(st.booleans()) else []),
        excluded_evidence=[],
        integrity_codes=[],
    )


def result(fs: list[FindingOut]) -> CascadeResult:
    return CascadeResult(
        rule_base_version="rb",
        dataset_version="0" * 64,
        integrity_version="iv",
        as_of_month="2026-11",
        window_months=12,
        findings=fs,
        chains=[],
        same_product=[],
        item_warnings=[],
        not_checked=[],
        rules=RulesOut(total=65, checked=63, disabled=[], not_matchable=[]),
        statement=None,
        notices=[],
    )


@st.composite
def scenarios(
    draw: st.DrawFn,
) -> tuple[CascadeResult, list[frozenset[Origin]], frozenset[Origin], int]:
    n = draw(st.integers(1, 6))
    origins = [
        frozenset(draw(st.lists(st.sampled_from(ORIGINS), min_size=1, max_size=2)))
        for _ in range(n)
    ]
    fs = draw(st.lists(findings(n), max_size=4, unique_by=lambda f: f.finding_id))
    focus = draw(st.sampled_from([frozenset[Origin]({"selected"}), frozenset[Origin]({"draft"})]))
    return result(fs), origins, focus, draw(st.integers(0, 3))


def row_of(f: FindingOut) -> str:
    return f.rule_id.split(":")[1]


CARD_KEYS = {"summary", "detail", "indicator", "source", "links"}


@given(scenarios())
def test_p2_card_schema(
    s: tuple[CascadeResult, list[frozenset[Origin]], frozenset[Origin], int],
) -> None:
    """P2: every card has the CDS Hooks 2.0 required fields, an allowed indicator, the source
    label, absolute links only, and no suggestions or actions."""
    out = cards.build(*s).model_dump(mode="json")
    assert set(out) == {"cards"}
    for card in out["cards"]:
        assert set(card) == CARD_KEYS
        assert card["indicator"] in ("info", "warning")
        assert card["source"]["label"] == "Janus (research prototype, not a medical device)"
        assert card["source"]["url"].startswith("https://")
        assert all(link["type"] == "absolute" for link in card["links"])
        assert all(link["url"].startswith("https://") for link in card["links"])


@given(st.integers(1, 65), LABELS, LABELS)
def test_p3_summary_length(row: int, a: str | None, b: str | None) -> None:
    text = cards.summary(row, a or "Calcium channel blocker", b or "Diuretic")
    assert len(text) < 140
    assert text.startswith(f"Possible prescribing cascade (PIPC row {row}): ")


@given(scenarios())
def test_p4_every_card_cites_its_pipc_row(
    s: tuple[CascadeResult, list[frozenset[Origin]], frozenset[Origin], int],
) -> None:
    res, origins, focus, _ = s
    out = cards.build(*s)
    touched = [
        f
        for f in res.findings
        if any(origins[i] & focus for i in [*f.index.items, *f.marker.items])
    ]
    assert len(touched) == len(out.cards)
    for f, card in zip(touched, out.cards, strict=True):
        assert card.summary.startswith(f"Possible prescribing cascade (PIPC row {row_of(f)})")
        assert "PIPC" in card.detail
        assert f.rule_text.locator in card.detail
        assert f.rule_evidence_id in card.detail
        assert "doi:10.1007/s41999-025-01215-x" in card.detail
        assert card.detail.rstrip().endswith(f"{DISCLAIMER} Not for clinical use.")
        assert "not a clinical assessment" in card.detail
        assert card.detail.count(ABRUPT_STOP_TEXT) == len(f.abrupt_stop)
        if f.priority is not None:
            assert "95% CI" in card.detail
        unconfirmed = not (f.index.form_confirmed and f.marker.form_confirmed)
        assert ("Dose form not confirmed" in card.detail) == unconfirmed
        assert "The pattern applies only if" in card.detail
        assert (cards.FAERS_NOTE in card.detail) == ("dataset:faers" in f.evidence_ids)
        assert card.indicator == "info"
        for lang in LANGUAGES:
            assert violations(card.summary + "\n" + card.detail, lang) == ([], []), lang


@given(scenarios())
def test_p5_cards_only_for_findings_in_focus(
    s: tuple[CascadeResult, list[frozenset[Origin]], frozenset[Origin], int],
) -> None:
    res, origins, focus, not_checked = s
    out = cards.build(res, origins, focus, not_checked)

    def touches(f: FindingOut) -> bool:
        items = [*f.index.items, *f.marker.items]
        return any(origins[i] & focus for i in items)

    assert len(out.cards) == len({f.finding_id for f in res.findings if touches(f)})
    assert cards.build(result([]), origins, focus, not_checked).cards == []
