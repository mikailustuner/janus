"""FROZEN copy of the Phase 1 janus.resolution.matching (2026-11-08). Do not edit.

Oracle of drug-resolution P34 and of the Phase 2 regression checks. Uses frozen_names.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from functools import cache
from typing import Literal

from tests.frozen_names import fold, spelling_key, strip_salts

Step = Literal[
    "curated_synonym",
    "tr_label",
    "any_label",
    "salt_normalised",
    "spelling_key",
    "spelling_key_salt",
    "titck_atc_bridge",
]
LANGS = ("en", "tr", "de", "fr", "es")


@dataclass(frozen=True)
class IndexItem:
    qid: str
    labels: Mapping[str, str]  # language → label, as published
    aliases: Mapping[str, tuple[str, ...]] = field(default_factory=dict[str, tuple[str, ...]])


type Keys = dict[str, frozenset[str]]
type Tier = tuple[frozenset[str], frozenset[str]]  # (keys hit by a label, keys hit by an alias)
type Tiered = dict[str, Tier]

_EMPTY: frozenset[str] = frozenset()


def _freeze(d: defaultdict[str, set[str]]) -> Keys:
    return {k: frozenset(v) for k, v in d.items() if k}


class _TierBuilder:
    def __init__(self) -> None:
        self.label: defaultdict[str, set[str]] = defaultdict(set)
        self.alias: defaultdict[str, set[str]] = defaultdict(set)

    def add(self, key: str, qid: str, *, is_label: bool) -> None:
        (self.label if is_label else self.alias)[key].add(qid)

    def freeze(self) -> Tiered:
        out: Tiered = {}
        for key in (set(self.label) | set(self.alias)) - {""}:
            out[key] = (frozenset(self.label.get(key, ())), frozenset(self.alias.get(key, ())))
        return out


@dataclass(frozen=True)
class NameIndex:
    synonyms: Keys
    tr_label: Tiered
    any_label: Tiered
    salt: Tiered
    spell: Tiered
    spell_salt: Tiered
    bridge: Keys = field(default_factory=dict[str, frozenset[str]])

    @classmethod
    def build(
        cls,
        items: Iterable[IndexItem],
        synonyms: Iterable[tuple[str, str]] = (),
        bridge: Mapping[str, Iterable[str]] | None = None,
    ) -> NameIndex:
        """`items` must already be restricted to eligible ingredient keys (design §5.3)."""
        syn: defaultdict[str, set[str]] = defaultdict(set)
        tr, anyl, salt, spell, spell_salt = (_TierBuilder() for _ in range(5))
        for name, qid in synonyms:
            syn[fold(name)].add(qid)
        for item in items:
            entries = [(lang, n, True) for lang, n in item.labels.items()]
            entries += [(lang, n, False) for lang, ns in item.aliases.items() for n in ns]
            for lang, name, is_label in entries:
                f = fold(name)
                if not f:
                    continue
                if lang == "tr":
                    tr.add(f, item.qid, is_label=is_label)
                anyl.add(f, item.qid, is_label=is_label)
                salt.add(strip_salts(f), item.qid, is_label=is_label)
                spell.add(spelling_key(f), item.qid, is_label=is_label)
                spell_salt.add(spelling_key(strip_salts(f)), item.qid, is_label=is_label)
        # Keyed by the salt-normalised name, so "x hidroklorür" on a single product and "x" in a
        # combination meet (P5 counterexample: only the salt form was bridged).
        br: defaultdict[str, set[str]] = defaultdict(set)
        for name, qids in (bridge or {}).items():
            br[strip_salts(fold(name))].update(qids)
        return cls(
            _freeze(syn),
            tr.freeze(),
            anyl.freeze(),
            salt.freeze(),
            spell.freeze(),
            spell_salt.freeze(),
            _freeze(br),
        )


def _tier(tiered: Tiered, key: str) -> frozenset[str] | None:
    """Label hits if any, else alias hits, else None."""
    labels, aliases = tiered.get(key, (_EMPTY, _EMPTY))
    return labels or aliases or None


@dataclass(frozen=True)
class Match:
    status: Literal["mapped", "ambiguous", "unsplit", "none"]
    step: Step | None
    keys: tuple[str, ...]  # mapped: one key; ambiguous / unsplit: all candidate keys


NO_MATCH = Match("none", None, ())


def _hit(step: Step, keys: frozenset[str] | None) -> Match | None:
    if not keys:
        return None
    return Match("mapped" if len(keys) == 1 else "ambiguous", step, tuple(sorted(keys)))


def ladder(name: str, index: NameIndex, *, turkish: bool) -> Match | None:
    """Steps 0-5 (design §5.3); None if no step hits."""
    f = fold(name)
    if not f:
        return None
    s = strip_salts(f)
    steps: list[tuple[Step, frozenset[str] | None]] = [
        ("curated_synonym", index.synonyms.get(f)),
        ("tr_label", _tier(index.tr_label, f) if turkish else None),
        ("any_label", _tier(index.any_label, f)),
        ("salt_normalised", _tier(index.salt, s)),
        ("spelling_key", _tier(index.spell, spelling_key(f))),
        ("spelling_key_salt", _tier(index.spell_salt, spelling_key(s))),
    ]
    for step, keys in steps:
        hit = _hit(step, keys)
        if hit is not None:
            return hit
    return None


def _span_key(tokens: tuple[str, ...], index: NameIndex) -> str | None:
    """The single key of a token span by exact or salt-normalised label, else None."""
    f = " ".join(tokens)
    for keys in (
        _tier(index.tr_label, f),
        _tier(index.any_label, f),
        _tier(index.salt, strip_salts(f)),
    ):
        if keys:
            return next(iter(keys)) if len(keys) == 1 else None
    return None


def detect_unsplit(name: str, index: NameIndex) -> tuple[str, ...] | None:
    """Keys of a split into >= 2 consecutive spans that each map to one different key."""
    tokens = tuple(fold(name).split())
    if len(tokens) < 2 or len(tokens) > 12:
        return None

    @cache
    def best(start: int) -> tuple[str, ...] | None:
        # A segmentation of tokens[start:] into spans with one key each (keys in order).
        if start == len(tokens):
            return ()
        for end in range(len(tokens), start, -1):  # longest span first: deterministic
            key = _span_key(tokens[start:end], index)
            if key is None:
                continue
            rest = best(end)
            if rest is not None:
                return (key, *rest)
        return None

    keys = best(0)
    if keys is None or len(keys) < 2 or len(set(keys)) != len(keys):
        return None
    return tuple(sorted(keys))


def map_name(name: str, index: NameIndex, *, turkish: bool) -> Match:
    """Full ladder: steps 0-5, then the unsplit check, then the TİTCK ATC bridge (step 6).

    The unsplit check runs before the bridge so that a name naming two substances is never
    mapped through a product code.
    """
    hit = ladder(name, index, turkish=turkish)
    if hit is not None:
        return hit
    parts = detect_unsplit(name, index)
    if parts is not None:
        return Match("unsplit", None, parts)
    if turkish:
        bridged = _hit("titck_atc_bridge", index.bridge.get(strip_salts(fold(name))))
        if bridged is not None:
            return bridged
    return NO_MATCH
