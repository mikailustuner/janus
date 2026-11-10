"""Name → ingredient key (drug-resolution design §5.3, Req 2.5, 5.3). Pure.

The ladder stops at the first step with a hit. Within a step, a hit on an item's label wins over
a hit on aliases only (most specific first: Wikidata aliases are loose, e.g. an enantiomer item
listing the racemate's name). One key → mapped; several keys → ambiguous (all kept, never
chosen); no hit → possible unsplit combination or no ingredient key. Lookups use dictionaries
of sets, so the result never depends on the order of index entries.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from functools import cache
from typing import Literal

from janus.resolution import name_lists
from janus.resolution.anion_acid import AnionAcidTable
from janus.resolution.name_lists import Lang
from janus.resolution.names import (
    fold,
    is_connector,
    is_salt_word,
    spelling_key,
    strip_salts,
)

Step = Literal[
    "curated_synonym",
    "tr_label",
    "any_label",
    "salt_normalised",
    "spelling_key",
    "spelling_key_salt",
    "anion_acid",
    "biologic_suffix",
    "titck_atc_bridge",
    "national_atc_bridge",  # Canada and Italy, `prepare_national.py`
]
LANGS = ("en", "tr", "de", "fr", "es")


_LABEL_LANGS: dict[str, Lang] = {"tr": "tr", "en": "en", "fr": "fr", "es": "es"}


def label_lang(lang: str) -> Lang:
    """The name functions of a Wikidata label's language (German labels use the neutral ones)."""
    return _LABEL_LANGS.get(lang, "en")


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
    acid: AnionAcidTable = field(default_factory=AnionAcidTable)

    @classmethod
    def build(
        cls,
        items: Iterable[IndexItem],
        synonyms: Iterable[tuple[str, str]] = (),
        bridge: Mapping[str, Iterable[str]] | None = None,
        acid: AnionAcidTable | None = None,
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
                ll = label_lang(lang)
                if lang == "tr":
                    tr.add(f, item.qid, is_label=is_label)
                anyl.add(f, item.qid, is_label=is_label)
                # French and Spanish labels get the keys of their own language and the neutral
                # (English) keys, so a Phase 2 rule can only add keys: a Turkish or English
                # query finds what it found before (design §15.1, P34).
                for v in dict.fromkeys((ll, "en")) if ll in ("fr", "es") else (ll,):
                    salt.add(strip_salts(f, v), item.qid, is_label=is_label)
                    spell.add(spelling_key(f, v), item.qid, is_label=is_label)
                    spell_salt.add(spelling_key(strip_salts(f, v), v), item.qid, is_label=is_label)
        # Keyed by the salt-normalised name, so "x hidroklorür" on a single product and "x" in a
        # combination meet (P5 counterexample: only the salt form was bridged).
        br: defaultdict[str, set[str]] = defaultdict(set)
        for name, qids in (bridge or {}).items():
            br[strip_salts(fold(name), "tr")].update(qids)
        return cls(
            _freeze(syn),
            tr.freeze(),
            anyl.freeze(),
            salt.freeze(),
            spell.freeze(),
            spell_salt.freeze(),
            _freeze(br),
            acid or AnionAcidTable(),
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


_SUFFIX = re.compile(r"^(.+)-([A-Za-z]{4})$")


def label_keys(index: NameIndex, label: str) -> frozenset[str]:
    """The keys the label steps find for a folded label (labels win over aliases)."""
    tier = index.any_label.get(label)
    return (tier[0] or tier[1]) if tier else frozenset()


def _anion_acid(stripped: str, index: NameIndex, lang: Lang) -> Match | None:
    """Step `anion_acid`: the salt-stripped name is a reviewed anion; look its acid up by label."""
    keys: set[str] = set()
    for acid in sorted(set(index.acid.lookup(lang, stripped))):
        hit = _tier(index.any_label, acid) or _tier(index.salt, strip_salts(acid, lang))
        keys |= hit or set()
    return _hit("anion_acid", frozenset(keys))


def _biologic_suffix(name: str, index: NameIndex, lang: Lang) -> Match | None:
    """Step `biologic_suffix`: `BASE-XXXX` maps to the key of BASE if BASE maps by a label step
    to exactly one key. No list of biologic stems is used (Req 12.8)."""
    if lang != "en" or not name_lists.BIOLOGIC_SUFFIX_ENABLED:
        return None
    m = _SUFFIX.match(name.strip())
    base = fold(m.group(1)) if m else ""
    if not base:
        return None
    for keys in (
        index.synonyms.get(base),
        _tier(index.any_label, base),
        _tier(index.salt, strip_salts(base, lang)),
    ):
        if keys:
            return Match("mapped", "biologic_suffix", tuple(keys)) if len(keys) == 1 else None
    return None


def ladder(name: str, index: NameIndex, *, lang: Lang) -> Match | None:
    """Steps 0-5 (design §5.3), then `anion_acid` and `biologic_suffix` (design §15); None if no
    step hits. Later steps never change a name that an earlier step maps."""
    f = fold(name)
    if not f:
        return None
    s = strip_salts(f, lang)
    steps: list[tuple[Step, frozenset[str] | None]] = [
        ("curated_synonym", index.synonyms.get(f)),
        ("tr_label", _tier(index.tr_label, f) if lang == "tr" else None),
        ("any_label", _tier(index.any_label, f)),
        ("salt_normalised", _tier(index.salt, s)),
        ("spelling_key", _tier(index.spell, spelling_key(f, lang))),
        ("spelling_key_salt", _tier(index.spell_salt, spelling_key(s, lang))),
    ]
    for step, keys in steps:
        hit = _hit(step, keys)
        if hit is not None:
            return hit
    return _anion_acid(s, index, lang) or _biologic_suffix(name, index, lang)


def _span_key(tokens: tuple[str, ...], index: NameIndex, lang: Lang) -> str | None:
    """The single key of a token span by exact or salt-normalised label, else None."""
    f = " ".join(tokens)
    for keys in (
        _tier(index.tr_label, f),
        _tier(index.any_label, f),
        _tier(index.salt, strip_salts(f, lang)),
    ):
        if keys:
            return next(iter(keys)) if len(keys) == 1 else None
    return None


def detect_unsplit(name: str, index: NameIndex, lang: Lang = "en") -> tuple[str, ...] | None:
    """Keys of a split into >= 2 consecutive spans that each map to one different key.

    For languages in `name_lists.UNSPLIT_GUARD_LANGS` (French, Spanish) a span made only of salt
    or connector words is not an ingredient span, so `MALÉATE D'ÉNALAPRIL` is never cut into
    `maleate | d | enalapril` (Req 12.12).
    """
    tokens = tuple(fold(name).split())
    if len(tokens) < 2 or len(tokens) > 12:
        return None
    guard = lang in name_lists.UNSPLIT_GUARD_LANGS

    @cache
    def best(start: int) -> tuple[str, ...] | None:
        # A segmentation of tokens[start:] into spans with one key each (keys in order).
        if start == len(tokens):
            return ()
        for end in range(len(tokens), start, -1):  # longest span first: deterministic
            span = tokens[start:end]
            if guard and all(is_salt_word(t, lang) or is_connector(t, lang) for t in span):
                continue
            key = _span_key(span, index, lang)
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


def map_name(name: str, index: NameIndex, *, lang: Lang) -> Match:
    """Full ladder: steps 0-5, `anion_acid`, `biologic_suffix`, then the unsplit check, then the
    TİTCK ATC bridge (Turkish names only).

    The unsplit check runs before the bridge so that a name naming two substances is never
    mapped through a product code.
    """
    hit = ladder(name, index, lang=lang)
    if hit is not None:
        return hit
    parts = detect_unsplit(name, index, lang)
    if parts is not None:
        return Match("unsplit", None, parts)
    if lang == "tr":
        bridged = _hit("titck_atc_bridge", index.bridge.get(strip_salts(fold(name), lang)))
        if bridged is not None:
            return bridged
    return NO_MATCH
