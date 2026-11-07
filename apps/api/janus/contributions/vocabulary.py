"""Event vocabulary (privacy design §5.8, DP6 d).

Until the collective-memory spec defines the Janus vocabulary (PIPC adverse events plus
improvement terms for "benefit"), the bundled `placeholder_events.txt` is used.
"""

from __future__ import annotations

import re
from pathlib import Path

from janus.contributions.models import EVENT_PATTERN

_EVENT_RE = re.compile(EVENT_PATTERN)


class VocabularyError(ValueError):
    pass


def parse_vocabulary(text: str) -> frozenset[str]:
    keys: set[str] = set()
    for number, line in enumerate(text.splitlines(), start=1):
        item = line.strip()
        if not item or item.startswith("#"):
            continue
        if not _EVENT_RE.fullmatch(item):
            raise VocabularyError(f"invalid event key on line {number}")
        keys.add(item)
    if not keys:
        raise VocabularyError("event vocabulary is empty")
    return frozenset(keys)


def load_vocabulary(path: Path) -> frozenset[str]:
    return parse_vocabulary(path.read_text(encoding="utf-8"))
