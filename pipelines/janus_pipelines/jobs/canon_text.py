"""Canon Book 2: OpenITI mARkdown → headings, sections, theme spans, rule extraction (séance
design §3). Pure: no I/O.

OpenITI notes typos and missing passages in this text (`MANY_TYPOS, PAGINATION, MISSING_PARTS`);
every locator points back to the exact source lines so a reader can check the passage.

Page markers (`# PageV01P345`) close a printed page in OpenITI mARkdown: a line belongs to the
first page marker that follows it.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Final

BOOK2_TITLE: Final = "الكتاب الثاني الأدوية المفردة"
NEXT_BOOK_TITLE: Final = "الكتاب الثالث"
EXPECTED_HEADINGS: Final = 844  # data-sources.md, checked 2026-11-08 on the pinned version

_HEADING = re.compile(r"^### (\|+)\s?(.*)$")
_PAGE = re.compile(r"^# Page(V\d+P\d+)\s*$")
_MILESTONE = re.compile(r"\s*\bms\d{3,5}\b\s*")
_SPACES = re.compile(r"\s+")
_DIACRITICS = re.compile(r"[ً-ٰٟـ]")
_ALEFS = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا"})


class CanonShapeError(ValueError):
    """The text does not have the expected Book 2 structure."""


# --- normalisation ------------------------------------------------------------------------


def normalize(text: str) -> str:
    """Matching form: no diacritics or tatweel, one alef. Not used for display."""
    return _DIACRITICS.sub("", text).translate(_ALEFS)


def normalize_with_map(text: str) -> tuple[str, list[int]]:
    """`normalize(text)` plus, for each output character, its index in `text`."""
    out: list[str] = []
    index: list[int] = []
    for i, ch in enumerate(text):
        if _DIACRITICS.fullmatch(ch):
            continue
        out.append(ch.translate(_ALEFS))
        index.append(i)
    return "".join(out), index


def clean_line(line: str) -> str:
    """Body text of one source line: no paragraph/continuation mark, no milestones."""
    if line.startswith("~~"):
        line = line[2:]
    elif line.startswith("# "):
        line = line[2:]
    return _SPACES.sub(" ", _MILESTONE.sub(" ", line)).strip()


def clean_heading(text: str) -> str:
    return _SPACES.sub(" ", _MILESTONE.sub(" ", text)).strip().rstrip(":.").strip()


# --- headings and entries -----------------------------------------------------------------


@dataclass(frozen=True)
class Entry:
    """One heading of Book 2 and its body, with a locator into the source file."""

    index: int  # 1-based position among Book 2 headings
    level: int  # number of `|` in the heading mark
    heading: str
    parent: int | None  # index of the nearest heading with a smaller level
    line_start: int  # 1-based source line of the heading
    line_end: int  # last source line of the body (inclusive)
    page: str | None  # printed page (OpenITI `V01P345`) the heading is on
    text: str  # cleaned body; paragraphs separated by "\n"
    line_of: tuple[int, ...] = field(repr=False)  # source line of every character of `text`

    @property
    def entry_id(self) -> str:
        return entry_id(self.index)


def entry_id(index: int) -> str:
    return f"canon.b2.h{index:04d}"


def _book2_bounds(lines: Sequence[str]) -> tuple[int, int]:
    start = end = None
    for i, line in enumerate(lines):
        m = _HEADING.match(line)
        if m is None or len(m.group(1)) != 1:
            continue
        title = clean_heading(m.group(2))
        if start is None and title.startswith(BOOK2_TITLE):
            start = i
        elif start is not None and title.startswith(NEXT_BOOK_TITLE):
            end = i
            break
    if start is None or end is None:
        raise CanonShapeError("Book 2 or the start of Book 3 not found")
    return start, end


def _page_after(lines: Sequence[str], start: int, stop: int) -> str | None:
    for i in range(start, stop):
        m = _PAGE.match(lines[i])
        if m:
            return m.group(1)
    return None


def split_book2(source: str) -> list[Entry]:
    """One entry per Book 2 heading (any level), in order. Raises `CanonShapeError`."""
    lines = source.split("\n")
    start, end = _book2_bounds(lines)
    heads = [i for i in range(start, end) if _HEADING.match(lines[i])]
    entries: list[Entry] = []
    stack: list[tuple[int, int]] = []  # (level, index)
    for n, h in enumerate(heads):
        m = _HEADING.match(lines[h])
        if m is None:  # pragma: no cover - `heads` holds heading lines only
            raise CanonShapeError("heading line expected")
        level = len(m.group(1))
        nxt = heads[n + 1] if n + 1 < len(heads) else end
        while stack and stack[-1][0] >= level:
            stack.pop()
        parent = stack[-1][1] if stack else None
        index = n + 1
        stack.append((level, index))
        chars: list[str] = []
        line_of: list[int] = []
        for i in range(h + 1, nxt):
            raw = lines[i]
            if _PAGE.match(raw) or not raw.strip():
                continue
            body = clean_line(raw)
            if not body:
                continue
            sep = "\n" if raw.startswith("# ") else " "
            if chars:
                chars.append(sep)
                line_of.append(i + 1)
            chars.append(body)
            line_of.extend([i + 1] * len(body))
        last = nxt  # 1-based number of the last body line is index nxt (0-based nxt - 1)
        entries.append(
            Entry(
                index=index,
                level=level,
                heading=clean_heading(m.group(2)),
                parent=parent,
                line_start=h + 1,
                line_end=max(h + 1, last),
                page=_page_after(lines, h, len(lines)),
                text="".join(chars),
                line_of=tuple(line_of),
            )
        )
    return entries


def source_lines(source: str, start: int, end: int) -> list[str]:
    """Source lines `start..end` (1-based, inclusive) — what a locator resolves to."""
    return source.split("\n")[start - 1 : end]


# --- sections inside an entry ---------------------------------------------------------------

# Section labels of the simple-drug entries (normalised spelling) -> section id. The English ids
# follow the section names used by the published English translation of Book 2 (cited only).
SECTION_LABELS: Final[dict[str, str]] = {
    "الماهية": "nature",
    "الاختيار": "choice",
    "الطبع": "temperament",
    "الافعال والخواص": "actions",
    "الخواص والافعال": "actions",
    "الخواص": "actions",
    "الزينة": "cosmetics",
    "الاورام والبثور": "swellings_pustules",
    "الاورام": "swellings_pustules",
    "الجراح والقروح": "wounds_ulcers",
    "القروح": "wounds_ulcers",
    "الات المفاصل": "joints",
    "اعضاء الراس": "head",
    "اعضاء العين": "eye",
    "اعضاء النفس والصدر": "chest",
    "اعضاء النفس": "chest",
    "اعضاء الصدر": "chest",
    "اعضاء الغذاء": "alimentary",
    "اعضاء النفض": "excretory",
    "الحميات": "fevers",
    "السموم": "poisons",
    "الابدال": "substitutes",
}
_LABEL_RE = re.compile(
    r"(?:^|(?<=[.\n:؛]))\s*("
    + "|".join(sorted((re.escape(k) for k in SECTION_LABELS), key=len, reverse=True))
    + r")\s*:"
)


@dataclass(frozen=True)
class Section:
    section: str  # id from SECTION_LABELS, or "body" before the first label
    start: int  # offsets in the entry text (content after the label)
    end: int


def sections(text: str) -> list[Section]:
    norm, idx = normalize_with_map(text)
    marks: list[tuple[str, int, int]] = []  # (id, label start, content start) in `text`
    for m in _LABEL_RE.finditer(norm):
        label_start = idx[m.start(1)]
        content = idx[m.end() - 1] + 1 if m.end() - 1 < len(idx) else len(text)
        marks.append((SECTION_LABELS[m.group(1)], label_start, content))
    out: list[Section] = []
    first = marks[0][1] if marks else len(text)
    if text[:first].strip():
        out.append(Section("body", 0, first))
    for n, (sid, _ls, cs) in enumerate(marks):
        stop = marks[n + 1][1] if n + 1 < len(marks) else len(text)
        out.append(Section(sid, cs, stop))
    return out


# --- themes ---------------------------------------------------------------------------------

THEMES: Final = ("wound", "burn", "ulcer", "infection")
_PRE = r"(?<![\w])(?:و|ف|ب|ل|وب|ول|فب)?"
_POST = r"(?![\w])"

# Normalised Arabic terms per theme -> English gloss (Janus's own short glosses).
# "infection" is an interpretive bridge: the text knows putrefaction, pus and spreading or
# malignant ulcers, not infection in the modern sense (design DP4).
THEME_TERMS: Final[dict[str, dict[str, str]]] = {
    "burn": {
        "حرق النار": "fire burns",
        "حرق الماء": "scalds",
        "الحرق": "burns",
        "حرق": "burns",
        "احراق الماء الحار": "scalds",
        "احراق النار": "fire burns",
        "التنفط": "blistering",
        "تنفط": "blistering",
    },
    "wound": {
        "الجراحات": "wounds",
        "جراحات": "wounds",
        "الجراح": "wounds",
        "جراح": "wounds",
        "الجرح": "a wound",
        "جرح": "a wound",
    },
    "ulcer": {
        "القروح": "ulcers",
        "قروح": "ulcers",
        "القرحة": "an ulcer",
        "قرحة": "an ulcer",
    },
    "infection": {
        "العفونة": "putrefaction",
        "عفونة": "putrefaction",
        "العفن": "putrefaction",
        "المتعفنة": "putrefying (ulcers)",
        "متعفنة": "putrefying (ulcers)",
        "الغانغرينا": "gangrene",
        "القيح": "pus",
        "قيح": "pus",
        "الاكلة": "spreading (eating) ulcer",
        "اكلة": "spreading (eating) ulcer",
        "القروح الخبيثة": "malignant ulcers",
        "القروح الساعية": "creeping ulcers",
        "القروح الوسخة": "foul ulcers",
        "القروح العفنة": "putrid ulcers",
        "النار الفارسية": "'Persian fire' (a spreading skin inflammation)",
        "الجمرة": "carbuncle",
        "الداحس": "whitlow",
        "الناصور": "fistula",
        "النواصير": "fistulas",
    },
}


def _variants(term: str) -> list[str]:
    """`term` plus its form after the preposition li- (`ل` + `ال...` is written `لل...`)."""
    return [term, "لل" + term[2:]] if term.startswith("ال") else [term]


# Written variant -> canonical term, per theme.
_TERM_FORMS: Final[dict[str, dict[str, str]]] = {
    theme: {v: t for t in terms for v in _variants(t)} for theme, terms in THEME_TERMS.items()
}
_THEME_RE: Final[dict[str, re.Pattern[str]]] = {
    theme: re.compile(
        _PRE
        + "("
        + "|".join(sorted((re.escape(v) for v in forms), key=len, reverse=True))
        + ")"
        + r"(?:ها|ه|هما)?"
        + _POST
    )
    for theme, forms in _TERM_FORMS.items()
}
_BOUNDARY = re.compile(r"[.؛\n]")
SPAN_MAX: Final = 260


@dataclass(frozen=True)
class Span:
    """One clause of an entry that names at least one theme term."""

    section: str
    start: int  # offsets of the clause in the entry text
    end: int
    line_start: int  # source lines the clause covers
    line_end: int
    themes: tuple[str, ...]  # in THEMES order
    terms: tuple[str, ...]  # normalised matched terms, in text order


def _clause(text: str, at: int, lo: int, hi: int) -> tuple[int, int]:
    """Sentence around offset `at`, inside [lo, hi), at most SPAN_MAX characters."""
    s = lo
    for m in _BOUNDARY.finditer(text, lo, at):
        s = m.end()
    e = hi
    m2 = _BOUNDARY.search(text, at, hi)
    if m2:
        e = m2.start() + (1 if text[m2.start()] == "." else 0)
    if e - s > SPAN_MAX:
        s = max(s, at - SPAN_MAX // 2)
        e = min(e, s + SPAN_MAX)
    while s < e and text[s].isspace():
        s += 1
    while e > s and text[e - 1].isspace():
        e -= 1
    return s, e


def theme_spans(entry: Entry) -> list[Span]:
    """Clauses of the entry body with theme terms (label words themselves never count)."""
    text = entry.text
    found: dict[tuple[int, int], tuple[str, set[str], list[tuple[int, str]]]] = {}
    for sec in sections(text):
        chunk = text[sec.start : sec.end]
        norm, idx = normalize_with_map(chunk)
        for theme, rx in _THEME_RE.items():
            for m in rx.finditer(norm):
                at = sec.start + idx[m.start(1)]
                s, e = _clause(text, at, sec.start, sec.end)
                if e <= s or not (s <= at < e):
                    continue
                _sec, themes, terms = found.setdefault((s, e), (sec.section, set(), []))
                themes.add(theme)
                terms.append((at, _TERM_FORMS[theme][m.group(1)]))
    out: list[Span] = []
    for (s, e), (sec_id, themes, terms) in sorted(found.items()):
        ordered = tuple(dict.fromkeys(t for _at, t in sorted(terms)))
        out.append(
            Span(
                section=sec_id,
                start=s,
                end=e,
                line_start=entry.line_of[s],
                line_end=entry.line_of[e - 1],
                themes=tuple(t for t in THEMES if t in themes),
                terms=ordered,
            )
        )
    return out


def term_gloss(term: str) -> str:
    for terms in THEME_TERMS.values():
        if term in terms:
            return terms[term]
    raise KeyError(term)


# --- deterministic extraction (the rule half of the reader step) ----------------------------

# Normalised cue words -> English tag. Janus's own glosses, not a translation.
FORMS: Final[dict[str, str]] = {
    "ضماد": "plaster",
    "ضمادا": "plaster",
    "يضمد": "plaster",
    "ضمد": "plaster",
    "طلاء": "liniment",
    "طلي": "liniment",
    "يطلي": "liniment",
    "يطلى": "liniment",
    "طلى": "liniment",
    "لطوخ": "embrocation",
    "لطوخا": "embrocation",
    "ذرور": "dusting powder",
    "ذر": "dusting powder",
    "يذر": "dusting powder",
    "مرهم": "ointment",
    "المراهم": "ointment",
    "مراهم": "ointment",
    "القيروطي": "cerate",
    "قيروطي": "cerate",
    "نطول": "affusion",
    "نطولا": "affusion",
    "شرب": "taken by mouth",
    "شربا": "taken by mouth",
    "مشروبا": "taken by mouth",
}
VEHICLES: Final[dict[str, str]] = {
    "بالخل": "with vinegar",
    "خل": "with vinegar",
    "بالعسل": "with honey",
    "عسل": "with honey",
    "بالزيت": "with olive oil",
    "زيت": "with olive oil",
    "بدهن الورد": "with rose oil",
    "دهن ورد": "with rose oil",
    "ببياض البيض": "with egg white",
    "بياض البيض": "with egg white",
    "بالشمع": "with wax",
    "شمع": "with wax",
    "بالشراب": "with wine",
    "بشراب": "with wine",
    "بالخمر": "with wine",
    "خمر": "with wine",
    "بالماء": "with water",
}
PARTS: Final[dict[str, str]] = {
    "ورقه": "leaves",
    "ورق": "leaves",
    "ورقة": "leaves",
    "ثمرته": "fruit",
    "ثمره": "fruit",
    "ثمر": "fruit",
    "رماده": "ash",
    "رماد": "ash",
    "دهنه": "oil",
    "عصارته": "juice",
    "عصارة": "juice",
    "طبيخه": "decoction",
    "طبيخ": "decoction",
    "صمغه": "gum",
    "اصله": "root",
    "قشره": "bark or peel",
    "زهره": "flowers",
    "بزره": "seeds",
    "حبه": "seeds",
}
ACTIONS: Final[dict[str, str]] = {
    "يدمل": "closes (cicatrises)",
    "يلحم": "agglutinates (closes)",
    "ينبت اللحم": "grows flesh",
    "ينقي": "cleans",
    "يجلو": "cleans",
    "يجفف": "dries",
    "ينشف": "dries",
    "يبرئ": "heals",
    "ابرا": "heals",
    "ابرات": "heals",
    "يبرا": "heals",
    "يمنع": "prevents",
    "ينفع": "is useful",
    "يسكن": "soothes",
    "ياكل اللحم": "eats away flesh",
}


def _tags(norm_span: str, table: dict[str, str]) -> list[str]:
    found: list[str] = []
    for cue in sorted(table, key=len, reverse=True):
        rx = _PRE + "(?:ال|ل)?" + re.escape(cue) + _POST
        if re.search(rx, norm_span) and table[cue] not in found:
            found.append(table[cue])
    return found


@dataclass(frozen=True)
class RuleExtraction:
    substance: str  # the entry heading
    themes: tuple[str, ...]
    conditions_en: tuple[str, ...]  # glosses of the matched terms
    forms: tuple[str, ...]
    vehicles: tuple[str, ...]
    parts: tuple[str, ...]
    actions: tuple[str, ...]


def rule_extract(entry: Entry, span: Span) -> RuleExtraction:
    text = normalize(entry.text[span.start : span.end])
    return RuleExtraction(
        substance=entry.heading,
        themes=span.themes,
        conditions_en=tuple(dict.fromkeys(term_gloss(t) for t in span.terms)),
        forms=tuple(_tags(text, FORMS)),
        vehicles=tuple(_tags(text, VEHICLES)),
        parts=tuple(_tags(text, PARTS)),
        actions=tuple(_tags(text, ACTIONS)),
    )
