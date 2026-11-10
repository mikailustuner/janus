"""Label interaction text (safety-check design §6, Req 4). Pure.

For two different ingredients A and B standing in different list items: when the "Drug
Interactions" section of the US label kept for A contains a name of B as whole words, the
passage is quoted. That is all this module states: the label of A names B, and here is the
text. No severity, no direction, no class inference; a passage may just as well say that no
effect was seen.

Names of B (`search_names`) are names Janus holds for B and nothing else: its English label,
and the leading words of the US substance names mapped to B, each only when the resolution
dataset knows that name for B and for no other ingredient.
"""

from __future__ import annotations

import csv
import re
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from janus.cascades.model import EngineItem
from janus.resolution.atc import DATA_DIR
from janus.resolution.names import fold

RULES_VERSION = "label-interactions-1"
MIN_NAME_LENGTH = 4
PASSAGE_MAX = 600  # characters of one quoted passage
PASSAGES_PER_FINDING = 3
MAX_FINDINGS = 30

EXCLUSIONS_FILE = DATA_DIR / "label_interaction_name_exclusions.csv"


def load_exclusions(path: Path = EXCLUSIONS_FILE) -> frozenset[str]:
    """Names that are not searched although they name one ingredient: in label text they
    mostly stand for something else (a level, a salt, a class, a laboratory test). A reviewed
    list with reasons; a malformed file stops the import."""
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames != ["name", "reason"]:
            raise ValueError("label_interaction_name_exclusions.csv: header must be name,reason")
        names = [(r["name"] or "").strip() for r in reader]
    if any(not n or n != n.lower() for n in names) or len(set(names)) != len(names):
        raise ValueError("label_interaction_name_exclusions.csv: names are lower case and unique")
    return frozenset(names)


NOT_SEARCHED: frozenset[str] = load_exclusions()

# A sentence ends at ". " (or ! ?) before a capital, a digit or an opening bracket. Label text
# in the download is flattened to one line per section, so this is the only structure left.
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9(\[])")


@dataclass(frozen=True)
class Label:
    substance_name: str  # as published
    set_id: str
    version: str | None
    effective_date: str | None  # ISO
    product_type: str | None
    text: str  # the "Drug Interactions" section as published


@dataclass(frozen=True)
class Subject:
    """One checked ingredient of the list."""

    key: str
    label_en: str | None
    items: tuple[int, ...]  # ascending
    names: tuple[str, ...]  # names searched in other labels, lower case
    us_names: tuple[str, ...]  # US substance names mapped to the key, case-folded


@dataclass(frozen=True)
class Passage:
    text: str  # an exact piece of the label text
    cut_start: bool
    cut_end: bool


@dataclass(frozen=True)
class Finding:
    label_of: Subject  # A: the ingredient whose label is quoted
    names: Subject  # B: the ingredient the passage names
    matched_name: str
    label: Label
    passages: tuple[Passage, ...]
    total_passages: int

    @property
    def finding_id(self) -> str:
        return f"label:{self.label_of.key}:{self.names.key}"


@dataclass(frozen=True)
class Result:
    findings: tuple[Finding, ...]  # at most MAX_FINDINGS
    total_findings: int
    labels_read: tuple[tuple[Subject, Label], ...]
    labels_not_found: tuple[Subject, ...]


def name_candidates(label_en: str | None, us_names: Collection[str]) -> set[str]:
    """Names that may be searched: the English label, and every leading run of words of a US
    substance name ("albuterol sulfate" gives "albuterol sulfate" and "albuterol")."""
    candidates: set[str] = set()
    if label_en:
        candidates.add(" ".join(label_en.lower().split()))
    for name in us_names:
        words = name.lower().split()
        candidates.update(" ".join(words[:n]).rstrip(",;") for n in range(1, len(words) + 1))
    return {c for c in candidates if c}


def search_names(
    key: str,
    label_en: str | None,
    us_names: Collection[str],
    keys_of_name: Mapping[str, Collection[str]],
) -> tuple[str, ...]:
    """The names of `key` that are searched in label text, lower case, longest first.

    A candidate (`name_candidates`) is kept when it has at least four characters and a letter,
    is not on `NOT_SEARCHED`, and `keys_of_name[fold(candidate)]` is exactly `{key}`: the
    dataset knows the name, for this ingredient only."""
    candidates = name_candidates(label_en, us_names)
    kept = {
        c
        for c in candidates
        if len(c) >= MIN_NAME_LENGTH
        and any(ch.isalpha() for ch in c)
        and c not in NOT_SEARCHED
        and set(keys_of_name.get(fold(c), ())) == {key}
    }
    return tuple(sorted(kept, key=lambda c: (-len(c), c)))


def name_pattern(name: str) -> re.Pattern[str]:
    """`name` as whole words: not inside a longer word or number; spaces match any whitespace."""
    body = r"\s+".join(re.escape(w) for w in name.split())
    return re.compile(rf"(?<![A-Za-z0-9]){body}(?![A-Za-z0-9])", re.IGNORECASE)


def _cut(text: str, start: int, end: int, a: int, b: int) -> Passage:
    """The sentence `text[start:end]`, shortened around the match `text[a:b]` when too long."""
    if end - start <= PASSAGE_MAX:
        return Passage(text[start:end], False, False)
    room = max(0, PASSAGE_MAX - (b - a)) // 2
    lo, hi = max(start, a - room), min(end, b + room)
    # Do not cut inside a word.
    while lo > start and lo < a and not text[lo - 1].isspace():
        lo += 1
    while hi < end and hi > b and not text[hi].isspace():
        hi -= 1
    return Passage(text[lo:hi].strip(), lo > start, hi < end)


def passages(text: str, name: str) -> list[Passage]:
    """The sentences of `text` that contain `name` as whole words, in text order, each once."""
    bounds = [0, *(m.end() for m in _SENTENCE_END.finditer(text)), len(text)]
    out: list[Passage] = []
    done: set[int] = set()
    for m in name_pattern(name).finditer(text):
        i = max(k for k, pos in enumerate(bounds[:-1]) if pos <= m.start())
        if i in done:
            continue
        done.add(i)
        start, end = bounds[i], bounds[i + 1]
        while end > start and text[end - 1].isspace():
            end -= 1
        out.append(_cut(text, start, max(end, m.end()), m.start(), m.end()))
    return out


def label_for(subject: Subject, labels: Mapping[str, Label]) -> Label | None:
    """The label kept for one of the subject's US substance names: the most recently effective
    one, then the smaller set id."""
    found = [labels[n] for n in subject.us_names if n in labels]
    if not found:
        return None
    return min(found, key=lambda lab: (_neg(lab.effective_date), lab.set_id))


def _neg(date: str | None) -> tuple[int, ...]:
    return tuple(-int(p) for p in date.split("-")) if date else (0,)


def subjects(
    items: Sequence[EngineItem],
    us_names: Mapping[str, Collection[str]],
    keys_of_name: Mapping[str, Collection[str]],
) -> list[Subject]:
    """The checked ingredients of the list, by key."""
    where: dict[str, set[int]] = {}
    labels: dict[str, str | None] = {}
    for item in items:
        for ing in item.ingredients:
            where.setdefault(ing.key, set()).add(item.index)
            labels[ing.key] = labels.get(ing.key) or ing.label_en
    return [
        Subject(
            key=key,
            label_en=labels[key],
            items=tuple(sorted(where[key])),
            names=search_names(key, labels[key], us_names.get(key, ()), keys_of_name),
            us_names=tuple(sorted({n.casefold() for n in us_names.get(key, ())})),
        )
        for key in sorted(where)
    ]


def find(subs: Sequence[Subject], labels: Mapping[str, Label]) -> Result:
    """Findings ordered by the key of the label's ingredient, then the named ingredient."""
    read: list[tuple[Subject, Label]] = []
    missing: list[Subject] = []
    findings: list[Finding] = []
    ordered = sorted(subs, key=lambda s: s.key)
    for a in ordered:
        label = label_for(a, labels)
        if label is None:
            missing.append(a)
            continue
        read.append((a, label))
        for b in ordered:
            if b.key == a.key or not any(i != j for i in a.items for j in b.items):
                continue
            for name in b.names:  # longest first; the first name that is found is reported
                found = passages(label.text, name)
                if found:
                    findings.append(
                        Finding(a, b, name, label, tuple(found[:PASSAGES_PER_FINDING]), len(found))
                    )
                    break
    return Result(tuple(findings[:MAX_FINDINGS]), len(findings), tuple(read), tuple(missing))
