"""Human-only filter for articles and tables (spec model-kit, milestone M5, pre-registered).

An article is dropped if its title, journal title, keywords or abstract name a non-human species or
a veterinary context; a table is dropped if its caption, footnotes or header cells name one; an
article is kept only if its abstract or methods contain a human cue. Applied before both readers.
Pilot 2 let a horse case report through; the test suite has a case modelled on it. Research use
only. Not for clinical decisions."""

from __future__ import annotations

import re
from typing import Final

ANIMAL: Final = re.compile(
    r"\b(?:horses?|equines?|equids?|pon(?:y|ies)|foals?|mares?|stallions?|geldings?|dogs?|canines?|beagles?|puppies|"
    r"cats?|felines?|kittens?|rats?|mouse|mice|murine|rodents?|rabbits?|leporine|pigs?|piglets?|porcine|swine|"
    r"minipigs?|monkeys?|macaques?|cynomolgus|rhesus|primates?|non[- ]human|cattle|bovine|cows?|calves|"
    r"heifers?|steers?|sheep|ovine|ewes?|lambs?|goats?|caprine|camels?|alpacas?|llamas?|chickens?|broilers?|"
    r"poultry|turkeys?|ducks?|fish|salmon|trout|zebrafish|tilapia|carp|veterinary|animals?|in vivo animal|"
    r"guinea pigs?|hamsters?|ferrets?|gerbils?|birds?|avian|reptiles?|turtles?|tortoises?|elephants?|dolphins?)\b",
    re.I,
)
HUMAN: Final = re.compile(
    r"\b(?:healthy (?:human )?(?:volunteers?|subjects?|adults?|participants?|men|women|males?|females?)|"
    r"human (?:volunteers?|subjects?|participants?)|volunteers?|subjects?|participants?|patients?|"
    r"\bmen\b|\bwomen\b|humans?|adults?)\b",
    re.I,
)


def names_animal(*texts: str) -> bool:
    return any(ANIMAL.search(t or "") for t in texts)


def article_is_human(title: str, journal: str, keywords: str, abstract: str, methods: str) -> bool:
    """True only if nothing names a non-human species and the abstract or methods name people."""
    if names_animal(title, journal, keywords, abstract):
        return False
    return bool(HUMAN.search(abstract or "") or HUMAN.search(methods or ""))


def table_is_human(caption: str, footnotes: str, header: str) -> bool:
    return not names_animal(caption, footnotes, header)
