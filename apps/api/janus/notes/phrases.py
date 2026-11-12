"""Word lists of the note and the outcome page (doctor-loop design §5.4). Pure.

`FORBIDDEN` mirrors `apps/web/src/i18n/forbidden-phrases.ts` (`medical-safety.md` rule 2); a test
keeps the two equal. `REASSURANCE` holds the words of rule 3 ("no false reassurance") per
language; accepted by the owner on 2026-11-08 with the localization review's additions (P1-P5).
Matching follows `findForbiddenPhrases`: whole words, case-insensitive, Unicode letters as word
characters.
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
    "pt": (
        "pare de tomar", "deixe de tomar", "interrompa", "medicamento desnecessário", "cura",
        "diagnóstico",
    ),
}

REASSURANCE: Final[Mapping[str, tuple[str, ...]]] = {
    "en": (
        "safe", "safely", "no problem", "no problems", "no issues", "all clear", "harmless",
        "risk-free", "no risk", "nothing wrong", "nothing to worry", "no cause for concern",
        "no need to worry",
    ),
    "tr": (
        "güvenli", "güvenlidir", "güvenle", "zararsız", "zararsızdır", "sorun yok", "sorun yoktur",
        "sorun bulunmamaktadır", "risk yok", "risksiz", "tehlikesiz", "endişelenecek bir şey yok",
    ),
    "de": (
        "sicher", "sichere", "sicheren", "sicheres", "unbedenklich", "unbedenkliche",
        "unbedenklichen", "harmlos", "harmlose", "harmlosen", "ungefährlich", "unproblematisch",
        "keine Probleme", "kein Problem", "keine Bedenken", "kein Risiko", "risikolos",
        "bedenkenlos", "alles in Ordnung", "kein Grund zur Sorge",
    ),
    "fr": (
        "sûr", "sûre", "sûrs", "sûres", "sans danger", "aucun problème", "pas de problème",
        "sans problème", "inoffensif", "inoffensive", "inoffensifs", "inoffensives",
        "sans risque", "aucun risque", "rien à craindre", "rien d'inquiétant",
    ),
    "es": (
        "seguro", "segura", "seguros", "seguras", "sin peligro", "sin problemas", "sin problema",
        "ningún problema", "no hay problema", "inofensivo", "inofensiva", "inofensivos",
        "inofensivas", "inocuo", "inocua", "inocuos", "inocuas", "sin riesgo", "sin riesgos",
        "nada de qué preocuparse", "todo en orden",
    ),
    "pt": (
        "seguro", "segura", "seguros", "seguras", "com segurança", "sem perigo", "sem problemas",
        "sem problema", "nenhum problema", "não há problema", "inofensivo", "inofensiva",
        "inofensivos", "inofensivas", "inócuo", "inócua", "inócuos", "inócuas", "sem risco",
        "sem riscos", "nada com que se preocupar", "tudo em ordem",
    ),
}  # fmt: skip

LANGUAGES: Final = ("en", "tr", "de", "fr", "es", "pt")

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
