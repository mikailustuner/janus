"""Ingredient-name normalisation (drug-resolution design §5.2, §15, Req 5.3, 5.7, 12). Pure.

- `fold`: one key for case, Turkish dotted/dotless i and diacritic variants.
- `strip_salts`: remove salt, ester, hydrate and counter-ion words ("amlodipin besilat" →
  "amlodipin"), so that different salts of one active substance meet (WHO ATC usually gives
  different salts one code). Per language (Phase 2): the Phase 1 lists apply to every language,
  the per-language additions and connector words live in `name_lists`.
- `spelling_key`: remove regular Turkish / English / INN spelling differences
  ("siprofloksasin" and "ciprofloxacin" → "siprofloksasin"); for Spanish and French names two
  reviewed, switchable rules (final vowel, acid word order).

The word lists and rewrite rules are data, reviewed by the pharmacologist agent; any change
changes `rules_version()` and therefore the dataset version. For `tr` and `en`, and while the
Phase 2 lists and switches are empty, every function returns exactly what Phase 1 returned
(property P34, oracle `tests/frozen_names.py`).
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata

from janus.resolution import name_lists
from janus.resolution.name_lists import Lang

# Phase 1 names kept for callers and tests.
SALT_WORDS = name_lists.BASE_SALT_WORDS
NOT_ALONE = name_lists.BASE_NOT_ALONE

# Letters that NFKD does not decompose.
_EXTRA = str.maketrans({"æ": "ae", "œ": "oe", "ø": "o", "đ": "d", "ł": "l", "\u0131": "i"})
_NON_KEY = re.compile(r"[^a-z0-9%+]+")


def fold(text: str) -> str:
    """Lower-case, Turkish-aware, without diacritics; only `[a-z0-9%+]` and single spaces."""
    s = unicodedata.normalize("NFKC", text)
    # Turkish: dotted capital I, ASCII I and dotless i all fold to "i".
    s = s.replace("\u0130", "i").replace("I", "i").replace("\u0131", "i")
    s = s.casefold().translate(_EXTRA)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.translate(_EXTRA)
    return " ".join(_NON_KEY.sub(" ", s).split())


_HYDRATE = re.compile(r"^[0-9]*h2o$")
_HYDRATE_WORD = re.compile(r"^(?:[a-z]*hidrat|[a-z]*hydrate|anhidr[a-z]*|anhydrous|susuz)$")


def is_salt_word(token: str, lang: Lang = "en") -> bool:
    """A salt, ester, hydrate or counter-ion word of the language (Phase 1 list + additions)."""
    return token in name_lists.BASE_SALT_WORDS or token in name_lists.EXTRA_SALT_WORDS[lang]


def is_not_alone(token: str, lang: Lang = "en") -> bool:
    """A counter-ion that is a substance in its own right (kept when nothing else is left)."""
    return token in name_lists.BASE_NOT_ALONE or token in name_lists.EXTRA_NOT_ALONE[lang]


def is_connector(token: str, lang: Lang = "en") -> bool:
    return token in name_lists.CONNECTORS[lang]


def _is_hydrate(token: str, lang: Lang) -> bool:
    """`2h2o`, or a hydrate/anhydrous word from the salt list."""
    if _HYDRATE.match(token):
        return True
    return is_salt_word(token, lang) and _HYDRATE_WORD.match(token) is not None


def strip_salts(folded: str, lang: Lang = "en") -> str:
    """Remove salt words from a folded name.

    Hydrate words are always removed (water of crystallisation is never the substance). Other
    salt words are removed unless that would leave nothing, or only words in `NOT_ALONE`; then
    the hydrate-free name is returned ("kalsiyum klorür dihidrat" → "kalsiyum klorur").
    Connector words (`de`, `d`, `du`, `del`, …) are removed only at the start or end of what is
    left after the salt words, and count like salt words for the "nothing left" test, so
    `SODIUM (CHLORURE DE)` is never reduced to `de` (Req 12.3).
    """
    tokens = folded.split()
    base = [t for t in tokens if not _is_hydrate(t, lang)] or tokens
    keep = [t for t in base if not is_salt_word(t, lang)]
    connectors = name_lists.CONNECTORS[lang]
    if connectors:
        while keep and keep[0] in connectors:
            keep = keep[1:]
        while keep and keep[-1] in connectors:
            keep = keep[:-1]
    if not keep or all(is_not_alone(t, lang) or t in connectors for t in keep):
        return " ".join(base)
    return " ".join(keep)


# Whole-token rewrites before spaces are removed: Roman numerals would otherwise collapse
# (iron ii / iron iii), and Turkish "asit" should meet English "acid".
TOKEN_RULES: dict[str, str] = {"ii": "2", "iii": "3", "iv": "4", "asit": "acid"}

# Applied in order, repeatedly, until nothing changes (so the key is idempotent).
SPELLING_RULES: tuple[tuple[str, str], ...] = (
    (r"ph", "f"),
    (r"th", "t"),
    (r"ch", "k"),
    (r"x", "ks"),
    (r"qu", "k"),
    (r"c(?=[eiy])", "s"),
    (r"c", "k"),
    (r"y", "i"),
    (r"z", "s"),
    (r"w", "v"),
    (r"ae", "e"),
    (r"oe", "e"),
    (r"([a-z0-9])\1+", r"\1"),
    (r"e$", ""),
    (r"d$", "t"),  # Turkish final devoicing: hidroklorotiyazit / hydrochlorothiazide
)
_COMPILED = tuple((re.compile(p), r) for p, r in SPELLING_RULES)

# Phase 2 rules (switchable, Req 12.5). Spanish INN stems end in -a or -o where the English
# label ends in -e or in a consonant (duloxetina / duloxetine, sildenafilo / sildenafil); the
# rule drops that vowel from the end of the whole key, inside the fixed-point loop, so the key
# stays idempotent. The acid word order maps `acide ascorbique` and `ascorbico acido` to the
# English `ascorbic acid`.
_ES_FINAL_VOWEL = re.compile(r"(?<=[a-z0-9]{4})[ao]$")
_ACID_WORDS = frozenset({"acide", "acido"})
_ACID_ADJECTIVE = re.compile(r"(ique|ico|ica)$")


def _acid_word_order(tokens: list[str]) -> list[str]:
    """`[acide, X-ique]` or `[X-ico, acido]` → `[X-ic, acid]`; anything else is unchanged."""
    if len(tokens) != 2:
        return tokens
    a, b = tokens
    if a in _ACID_WORDS and b not in _ACID_WORDS:
        adjective = b
    elif b in _ACID_WORDS and a not in _ACID_WORDS:
        adjective = a
    else:
        return tokens
    return [_ACID_ADJECTIVE.sub("ic", adjective), "acid"]


def spelling_key(folded: str, lang: Lang = "en") -> str:
    """Spelling-insensitive key of a folded name (spaces removed)."""
    tokens = [TOKEN_RULES.get(t, t) for t in folded.split()]
    if name_lists.ACID_WORD_ORDER_ENABLED and lang in ("fr", "es"):
        tokens = _acid_word_order(tokens)
    s = re.sub(r"[^a-z0-9]", "", "".join(tokens))
    vowel = name_lists.ES_FINAL_VOWEL_ENABLED and lang == "es"
    for _ in range(32):
        before = s
        for pattern, repl in _COMPILED:
            s = pattern.sub(repl, s)
        if vowel:
            s = _ES_FINAL_VOWEL.sub("", s)
        if s == before:
            return s
    raise AssertionError("spelling rules did not reach a fixed point")  # pragma: no cover


def _words(d: dict[Lang, frozenset[str]]) -> dict[str, list[str]]:
    return {k: sorted(v) for k, v in sorted(d.items())}


def _phase2_parts() -> dict[str, object]:
    """Phase 2 lists and switches; absent while empty, so a Phase 1 state hashes as in Phase 1."""
    parts: dict[str, object] = {}
    extra_salt = _words(name_lists.EXTRA_SALT_WORDS)
    extra_alone = _words(name_lists.EXTRA_NOT_ALONE)
    connectors = _words(name_lists.CONNECTORS)
    if any(extra_salt.values()):
        parts["extra_salt_words"] = extra_salt
    if any(extra_alone.values()):
        parts["extra_not_alone"] = extra_alone
    if any(connectors.values()):
        parts["connectors"] = connectors
    switches = {
        "biologic_suffix": name_lists.BIOLOGIC_SUFFIX_ENABLED,
        "es_final_vowel": name_lists.ES_FINAL_VOWEL_ENABLED,
        "acid_word_order": name_lists.ACID_WORD_ORDER_ENABLED,
    }
    if any(switches.values()):
        parts["switches"] = switches
    return parts


def rules_version() -> str:
    """Hash of every list, switch and rule of this module and `name_lists` as they are now."""
    return hashlib.sha256(
        json.dumps(
            {
                "salt_words": sorted(name_lists.BASE_SALT_WORDS),
                "not_alone": sorted(name_lists.BASE_NOT_ALONE),
                "hydrate": _HYDRATE.pattern,
                "tokens": TOKEN_RULES,
                "spelling": SPELLING_RULES,
                **_phase2_parts(),
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()


RULES_VERSION = rules_version()
