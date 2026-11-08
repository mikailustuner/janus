"""Label-effect signals: OnSIDES side effect → goal (design §5.2, Req 2.2, 2.3; P2, P6). Pure.

Only single-ingredient labels count (DP2): a label whose OnSIDES ingredients map to more than one
Janus key, or to none, gives no signal and no denominator. For each (key, goal) the signal counts
the distinct labels listing a mapped term, the key's labels, the regions and sections. Row order
and duplicate rows never change the result.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field

from janus.light.model import LABEL_REGIONS, ONSIDES_EVIDENCE_ID, Label, LabelSignal, MappingRow


def single_key(label: Label, key_of: Mapping[str, str]) -> str | None:
    """The one Janus key of a label, or None (no mapped ingredient, or several keys)."""
    keys = {key_of.get(i) for i in label.ingredients}
    if None in keys or len(keys) != 1:
        return None
    (key,) = keys
    return key


@dataclass
class _Acc:
    labels: set[int] = field(default_factory=set[int])
    regions: set[str] = field(default_factory=set[str])
    sections: set[str] = field(default_factory=set[str])
    terms: set[str] = field(default_factory=set[str])
    evidence: set[str] = field(default_factory=set[str])


def label_signals(
    labels: Iterable[Label],
    mapping: Mapping[str, MappingRow],
    key_of: Mapping[str, str],
    keep: Callable[[Label], bool] = lambda _label: True,
) -> dict[tuple[str, str], LabelSignal]:
    """Signals per (key, goal). `mapping` holds the active rows by term; `keep` filters labels."""
    totals: dict[str, set[int]] = {}
    acc: dict[tuple[str, str], _Acc] = {}
    for label in labels:
        if not keep(label):
            continue
        key = single_key(label, key_of)
        if key is None:
            continue
        totals.setdefault(key, set()).add(label.label_id)
        for term, section in label.effects:
            row = mapping.get(term)
            if row is None:
                continue
            a = acc.setdefault((key, row.goal), _Acc())
            a.labels.add(label.label_id)
            a.regions.add(label.source)
            a.sections.add(section)
            a.terms.add(term)
            a.evidence.update(row.evidence)
    out: dict[tuple[str, str], LabelSignal] = {}
    for (key, goal), a in sorted(acc.items()):
        out[(key, goal)] = LabelSignal(
            key=key,
            goal=goal,
            regions=tuple(r for r in LABEL_REGIONS if r in a.regions),
            labels_with_effect=len(a.labels),
            labels_total=len(totals[key]),
            sections=tuple(sorted(a.sections)),
            terms=tuple(sorted(a.terms)),
            evidence=(ONSIDES_EVIDENCE_ID, *sorted(a.evidence)),
        )
    return out


def labels_of_key(labels: Iterable[Label], key: str, key_of: Mapping[str, str]) -> list[Label]:
    return [lb for lb in labels if single_key(lb, key_of) == key]
