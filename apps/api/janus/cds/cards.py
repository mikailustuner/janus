"""CDS Hooks cards from a cascade result (cds-hooks design §6). Pure.

A card says what the engine found and where the pattern is published; it never assesses the
patient and never changes an order (no suggestions, no actions). English only (design DP13).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from janus.cascades.model import ABRUPT_STOP_TEXT
from janus.cascades.schemas import DISCLAIMER, CascadeResult, FindingOut, PriorityOut, SideOut
from janus.cds.fhir import Origin

SUMMARY_MAX: Final = 139  # CDS Hooks: "<140-character summary"
SOURCE_LABEL: Final = "Janus (research prototype, not a medical device)"
SOURCE_URL: Final = "https://github.com/mikailustuner/janus/blob/main/docs/cds-hooks.md"
PIPC_DOI_URL: Final = "https://doi.org/10.1007/s41999-025-01215-x"
PIPC_CITATION: Final = (
    "Rochon PA et al. Potentially inappropriate prescribing cascades (PIPC) list. "
    "Eur Geriatr Med 2025;16(5):1573-1584. doi:10.1007/s41999-025-01215-x (CC BY 4.0)"
)
BMJ_CITATION: Final = "Rochon PA et al., BMJ 2026;394:e100499 (abstract)"
NOT_FOR_CLINICAL_USE: Final = "Not for clinical use."
FRAMING: Final = (
    "**Possible prescribing cascade.** These medicines match a pattern in the published PIPC list "
    "of potentially inappropriate prescribing cascades. This is a pattern from the literature, "
    "not a clinical assessment of this patient."
)
TIMING: Final = (
    "Timing: Janus does not read start dates here, so it cannot tell which medicine was started "
    "first."
)
REVIEW: Final = "This may be worth considering in a medication review."
ORIGIN_TEXT: Final[dict[Origin, str]] = {
    "selected": "selected order",
    "draft": "draft order",
    "active": "current medication request (active or on hold)",
    "statement": "medication statement",
}
NOT_READ_TEXT: Final[dict[str, str]] = {
    "medicationRequests": "current medication requests",
    "medicationStatements": "medication statements",
}
FAERS_NOTE: Final = (
    "FAERS (in the evidence ids): spontaneous reports, not incidence, not deduplicated across "
    "cases."
)
ORIGIN_ORDER: Final[tuple[Origin, ...]] = ("selected", "draft", "active", "statement")


class _Out(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Source(_Out):
    label: str
    url: str


class Link(_Out):
    label: str
    url: str
    type: Literal["absolute"] = "absolute"


class Card(_Out):
    summary: str = Field(max_length=SUMMARY_MAX)
    detail: str
    # Always "info" (safety review S3): a literature pattern without start dates is not urgent.
    indicator: Literal["info"]
    source: Source
    links: list[Link]


class CardsOut(_Out):
    cards: list[Card]


def row_number(finding: FindingOut) -> int:
    return int(finding.rule_id.split(":", 1)[1])


def _shorten(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: max(limit - 1, 1)].rstrip() + "…"


def summary(row: int, index_label: str, marker_label: str) -> str:
    """`Possible prescribing cascade (PIPC row N): A and B`, labels shortened to fit."""
    prefix = f"Possible prescribing cascade (PIPC row {row}): "
    joiner = " and "
    text = prefix + index_label + joiner + marker_label
    if len(text) <= SUMMARY_MAX:
        return text
    budget = SUMMARY_MAX - len(prefix) - len(joiner)
    a = _shorten(index_label, budget // 2)
    b = _shorten(marker_label, budget - len(a))
    return prefix + a + joiner + b


def _label(side: SideOut, published: str) -> str:
    return side.label_en or published


def _origins(side: SideOut, origins: Sequence[frozenset[Origin]]) -> list[Origin]:
    found = {o for i in side.items if 0 <= i < len(origins) for o in origins[i]}
    return [o for o in ORIGIN_ORDER if o in found]


def _origin_text(found: Sequence[Origin]) -> str:
    return ", ".join(ORIGIN_TEXT[o] for o in found) or "medicine list"


def _priority(p: PriorityOut) -> str:
    if p.measure == "incidence":
        figure = f"incidence {p.value}% (95% CI {p.ci_low}% to {p.ci_high}%)"
    else:
        figure = f"adjusted sequence ratio {p.value} (95% CI {p.ci_low} to {p.ci_high})"
    return f"Population figure for this cascade: {figure}; {BMJ_CITATION}, {p.locator}."


def detail(
    f: FindingOut,
    origins: Sequence[frozenset[Origin]],
    not_checked: int,
    not_read: Sequence[str] = (),
) -> str:
    t = f.rule_text
    index_label = _label(f.index, t.drug_a)
    marker_label = _label(f.marker, t.drug_b)
    lines = [
        FRAMING,
        "",
        f"- PIPC list, {t.locator} ({t.system}): {t.drug_a} → {t.adverse_event} → {t.drug_b}.",
        f"- Matched: **{index_label}** ({_origin_text(_origins(f.index, origins))}) and "
        f"**{marker_label}** ({_origin_text(_origins(f.marker, origins))}).",
        f"- {TIMING} The pattern applies only if {marker_label} was started after {index_label}.",
    ]
    unconfirmed = [
        label
        for label, side in ((index_label, f.index), (marker_label, f.marker))
        if not side.form_confirmed
    ]
    if unconfirmed:
        lines.append(
            f"- Dose form not confirmed: Janus matched {' and '.join(unconfirmed)} by ingredient "
            "only; the pattern may not apply to eye, skin or other local forms."
        )
    if f.priority is not None:
        lines.append(f"- {_priority(f.priority)}")
    for side in f.abrupt_stop:
        label = index_label if side == "index" else marker_label
        lines.append(f"- {label}: {ABRUPT_STOP_TEXT}")
    lines.append(f"- {REVIEW}")
    if not_checked:
        noun = "medicine" if not_checked == 1 else "medicines"
        lines.append(
            f"- Not checked: {not_checked} {noun} in this request (no code Janus could match to "
            "one ingredient, or an ingredient Janus cannot check)."
        )
    if not_read:
        lines.append(
            "- Not read: "
            + " and ".join(NOT_READ_TEXT.get(k, k) for k in not_read)
            + " (not provided by the EHR)."
        )
    evidence = ", ".join(dict.fromkeys([f.rule_evidence_id, *f.evidence_ids]))
    if "dataset:faers" in f.evidence_ids:
        lines.append(f"- {FAERS_NOTE}")
    lines += [
        f"- Source: {PIPC_CITATION}, {t.locator}. Evidence ids: {evidence}.",
        "",
        f"{DISCLAIMER} {NOT_FOR_CLINICAL_USE}",
    ]
    return "\n".join(lines)


def build(
    result: CascadeResult,
    origins: Sequence[frozenset[Origin]],
    focus: frozenset[Origin],
    not_checked: int,
    not_read: Sequence[str] = (),
) -> CardsOut:
    """One card per finding that involves a focus item; none otherwise (Req 4.2). The not-checked
    count adds the medicines the engine could not check (pharmacologist review P8)."""
    not_checked += len({n.item for n in result.not_checked})
    cards: list[Card] = []
    seen: set[str] = set()
    for f in result.findings:
        sides = set(_origins(f.index, origins)) | set(_origins(f.marker, origins))
        if not sides & focus or f.finding_id in seen:
            continue
        seen.add(f.finding_id)
        cards.append(
            Card(
                summary=summary(
                    row_number(f),
                    _label(f.index, f.rule_text.drug_a),
                    _label(f.marker, f.rule_text.drug_b),
                ),
                detail=detail(f, origins, not_checked, not_read),
                indicator="info",
                source=Source(label=SOURCE_LABEL, url=SOURCE_URL),
                links=[Link(label="PIPC list (Rochon et al. 2025)", url=PIPC_DOI_URL)],
            )
        )
    return CardsOut(cards=cards)
