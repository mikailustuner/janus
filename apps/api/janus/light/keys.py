"""OnSIDES ingredient id → Janus ingredient key (design §5.1, DP3; P12). Pure.

An RxNorm id maps through the Wikidata items' RxCUIs when exactly one item carries it; otherwise
the OnSIDES name maps when exactly one item has that English label (case-folded). Anything else is
unmapped. No fuzzy matching: two different substances are never merged.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Literal

Method = Literal["rxcui", "label_en", "unmapped"]


@dataclass(frozen=True)
class Item:
    qid: str
    rxcuis: tuple[str, ...]
    label_en: str


@dataclass(frozen=True)
class KeyMap:
    by_rxcui: Mapping[str, str]
    by_label: Mapping[str, str]

    def key_for(self, onsides_id: str, name: str) -> tuple[str | None, Method]:
        if not onsides_id.startswith("OMOP"):
            qid = self.by_rxcui.get(onsides_id)
            if qid is not None:
                return qid, "rxcui"
        qid = self.by_label.get(name.casefold())
        if qid is not None:
            return qid, "label_en"
        return None, "unmapped"


def _unique(pairs: Iterable[tuple[str, str]]) -> dict[str, str]:
    seen: dict[str, set[str]] = {}
    for k, v in pairs:
        seen.setdefault(k, set()).add(v)
    return {k: next(iter(v)) for k, v in seen.items() if len(v) == 1}


def build_key_map(items: Iterable[Item]) -> KeyMap:
    items = list(items)
    return KeyMap(
        by_rxcui=_unique((r, it.qid) for it in items for r in it.rxcuis),
        by_label=_unique((it.label_en.casefold(), it.qid) for it in items if it.label_en),
    )


def map_ingredients(
    names: Mapping[str, str], key_map: KeyMap
) -> tuple[dict[str, str], dict[Method, int]]:
    """OnSIDES id → key for every mapped id, and the count per method."""
    out: dict[str, str] = {}
    counts: dict[Method, int] = {"rxcui": 0, "label_en": 0, "unmapped": 0}
    for oid in sorted(names):
        key, method = key_map.key_for(oid, names[oid])
        counts[method] += 1
        if key is not None:
            out[oid] = key
    return out, counts
