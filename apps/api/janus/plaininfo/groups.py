"""Covered ATC groups and their fixed sentences (plain-medicine-info design §3). Pure.

`groups.csv` (Janus, Apache-2.0) lists the ATC groups Janus describes in plain words, with a
group name and one use text per language, written once and never generated at run time. A group
is a set of ATC prefixes minus single excluded codes; an ATC code belongs to at most one group.
No WHO index text is copied: the names are common class names and Janus's own words.

Every row has a review status. `not_reviewed` means no health professional has checked the
wording; the API passes the status on with every sentence and the page shows it. No sentence
names a dose or says how to take a medicine: the loader refuses a use text with a digit, a
forbidden phrase or a reassurance word (medical-safety rules 2 and 3).
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast, get_args

from janus.notes.phrases import violations
from janus.resolution.atc import ATC_PREFIX, INGREDIENT_LEVEL

GROUPS_FILE = Path(__file__).parent / "groups.csv"
Language = Literal["en", "tr", "de", "fr", "es"]
LANGUAGES: tuple[Language, ...] = get_args(Language)
ReviewStatus = Literal["not_reviewed", "expert_reviewed"]
HEADER = [
    "id",
    "prefixes",
    "exclude",
    *(f"name_{lang}" for lang in LANGUAGES),
    *(f"use_{lang}" for lang in LANGUAGES),
    "status",
    "note",
]
MAX_TEXT = 400
_ID = re.compile(r"^[a-z][a-z0-9_]{1,39}$")
_AI = re.compile(r"(?<![^\W\d_])(AI|KI|IA|YZ)(?![^\W\d_])")


class GroupsFileError(ValueError):
    """`groups.csv` is not usable; the message names the row and the column, never a text."""


@dataclass(frozen=True)
class Group:
    id: str
    prefixes: tuple[str, ...]
    exclude: frozenset[str]
    names: Mapping[Language, str]
    uses: Mapping[Language, str]
    status: ReviewStatus

    def prefix_of(self, code: str) -> str | None:
        """The group's prefix that `code` falls under, unless the code is excluded."""
        if code in self.exclude:
            return None
        return next((p for p in self.prefixes if code.startswith(p)), None)


@dataclass(frozen=True)
class GroupTable:
    groups: tuple[Group, ...]
    version: str  # sha256 of the file text

    def group_of(self, code: str) -> Group | None:
        """The one group an ingredient-level ATC code belongs to, if any."""
        if not INGREDIENT_LEVEL.match(code):
            return None
        return next((g for g in self.groups if g.prefix_of(code) is not None), None)


Status = Literal["single", "mixed", "none"]


@dataclass(frozen=True)
class Described:
    """The covered groups of one ingredient's ATC codes.

    `single`: every code is in the same covered group. `mixed`: at least one code is in a covered
    group, and the codes are in more than one group or some are in none; the page then says that
    the ingredient is in more than one kind of medicine. `none`: no code is covered.
    """

    status: Status
    groups: tuple[tuple[Group, tuple[str, ...]], ...]  # (group, its codes), in table order
    uncovered: tuple[str, ...]


def describe(table: GroupTable, codes: Iterable[str]) -> Described:
    by_group: dict[str, list[str]] = {}
    uncovered: list[str] = []
    for code in sorted(set(codes)):
        group = table.group_of(code)
        if group is None:
            uncovered.append(code)
        else:
            by_group.setdefault(group.id, []).append(code)
    groups = tuple((g, tuple(by_group[g.id])) for g in table.groups if g.id in by_group)
    status: Status = (
        "none" if not groups else "single" if len(groups) == 1 and not uncovered else "mixed"
    )
    return Described(status, groups, tuple(uncovered))


def _texts(row: Mapping[str, str], kind: str, n: int) -> dict[Language, str]:
    out: dict[Language, str] = {}
    for lang in LANGUAGES:
        column = f"{kind}_{lang}"
        text = row[column]
        if not text or text != text.strip() or len(text) > MAX_TEXT or "\n" in text:
            raise GroupsFileError(f"row {n}: {column} is empty, padded or too long")
        forbidden, reassuring = violations(text, lang)
        if forbidden or reassuring or _AI.search(text):
            raise GroupsFileError(f"row {n}: {column} holds a word the safety rules exclude")
        if kind == "use" and (any(ch.isdigit() for ch in text) or not text.endswith(".")):
            raise GroupsFileError(f"row {n}: {column} must be sentences without a number")
        out[lang] = text
    return out


def parse(text: str) -> GroupTable:
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames != HEADER:
        raise GroupsFileError("header differs from the expected columns")
    groups: list[Group] = []
    ids: set[str] = set()
    prefixes: list[str] = []
    for n, row in enumerate(reader, start=2):
        if None in row or any(v is None for v in row.values()):
            raise GroupsFileError(f"row {n}: wrong number of columns")
        gid = row["id"]
        if not _ID.match(gid) or gid in ids:
            raise GroupsFileError(f"row {n}: id is malformed or repeated")
        ids.add(gid)
        own = tuple(row["prefixes"].split())
        if not own or any(len(p) < 3 or not ATC_PREFIX.match(p) for p in own):
            raise GroupsFileError(f"row {n}: prefixes must be ATC prefixes of 3 to 7 characters")
        # No prefix may repeat or contain another: a code then has at most one group.
        if any(p.startswith(q) or q.startswith(p) for p in own for q in prefixes) or any(
            a != b and a.startswith(b) for a in own for b in own
        ):
            raise GroupsFileError(f"row {n}: a prefix overlaps another prefix")
        if len(set(own)) != len(own):
            raise GroupsFileError(f"row {n}: a prefix is repeated")
        prefixes.extend(own)
        exclude = row["exclude"].split()
        if len(set(exclude)) != len(exclude) or any(
            not INGREDIENT_LEVEL.match(c) or not any(c.startswith(p) for p in own) for c in exclude
        ):
            raise GroupsFileError(f"row {n}: exclude must be codes under the row's prefixes")
        if row["status"] not in get_args(ReviewStatus):
            raise GroupsFileError(f"row {n}: unknown status")
        groups.append(
            Group(
                id=gid,
                prefixes=own,
                exclude=frozenset(exclude),
                names=_texts(row, "name", n),
                uses=_texts(row, "use", n),
                status=cast(ReviewStatus, row["status"]),
            )
        )
    if not groups:
        raise GroupsFileError("no group")
    return GroupTable(tuple(groups), hashlib.sha256(text.encode("utf-8")).hexdigest())


def load(path: Path = GROUPS_FILE) -> GroupTable:
    return parse(path.read_text(encoding="utf-8"))
