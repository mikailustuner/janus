"""Word lists of the note and the outcome page (doctor-loop design §5.4). Pure.

`FORBIDDEN` mirrors `apps/web/src/i18n/forbidden-phrases.ts` (`medical-safety.md` rule 2); a test
keeps the two equal. `REASSURANCE` holds the words of rule 3 ("no false reassurance") per language;
the lists are proposals reviewed with the glossary (task 15). Matching follows
`findForbiddenPhrases`: whole words, case-insensitive, Unicode letters as word characters.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from functools import cache
from typing import Final

FORBIDDEN: Final[Mapping[str, tuple[str, ...]]] = {
    "en": (
        "stop taking",
        "you should stop",
        "discontinue",
        "unnecessary medicine",
        "cure",
        "cures",
        "treatment for",
        "diagnosis",
        "you have",
        "safe to stop",
        "your medicines are safe",
    ),
    "tr": (
        "ilacı bırakın",
        "ilacınızı kesin",
        "gereksiz ilaç",
        "tedavi eder",
        "tanı",
        "ilaçlarınız güvenli",
    ),
    "de": ("absetzen Sie", "nicht mehr einnehmen", "unnötiges Medikament", "heilt", "Diagnose"),
    "fr": ("arrêtez de prendre", "médicament inutile", "guérit", "diagnostic"),
    "es": ("deje de tomar", "medicamento innecesario", "cura", "diagnóstico"),
}

REASSURANCE: Final[Mapping[str, tuple[str, ...]]] = {
    "en": ("safe", "no problems", "all clear", "harmless", "nothing to worry"),
    "tr": ("güvenli", "sorun yok", "zararsız"),
    "de": ("sicher", "unbedenklich", "harmlos", "keine Probleme"),
    "fr": ("sûr", "sans danger", "aucun problème", "inoffensif"),
    "es": ("seguro", "sin peligro", "sin problemas", "inofensivo"),
}

LANGUAGES: Final = ("en", "tr", "de", "fr", "es")

# A Unicode letter: a word character that is neither a digit nor the underscore (JS `\p{L}`).
_LETTER: Final = r"[^\W\d_]"


@cache
def _pattern(phrase: str) -> re.Pattern[str]:
    return re.compile(rf"(?<!{_LETTER}){re.escape(phrase)}(?!{_LETTER})", re.IGNORECASE)


def find_phrases(text: str, phrases: Iterable[str]) -> list[str]:
    """The phrases found in `text`, as `findForbiddenPhrases` finds them."""
    return [p for p in phrases if _pattern(p).search(text)]


def violations(text: str, language: str) -> tuple[list[str], list[str]]:
    """(forbidden phrases, reassurance words) of `language` found in `text`."""
    return find_phrases(text, FORBIDDEN[language]), find_phrases(text, REASSURANCE[language])
