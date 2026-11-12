"""Text layer of Drugs@FDA review PDFs (spec model-kit, milestone M5): the shared input of both
review readers.

`pdftotext -layout` (poppler) keeps the column layout of tables as spaces. A page is a text page if
it has at least `MIN_TEXT_CHARS` characters; a PDF is born-digital if at least 50 % of its pages are
text pages. Lines of the table of contents (dot leaders) and every line inside a section whose
heading names a summary, recommendation, conclusion, overview or labeling are marked as not
readable: values and doses are never taken from there (pre-registered). This module only prepares
text; it reads no value. Research use only. Not for clinical decisions."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Final

MIN_TEXT_CHARS: Final = 300
BORN_DIGITAL_SHARE: Final = 0.5
_HEADING: Final = re.compile(
    r"^\s{0,12}(?:(?:\d{1,2}(?:\.\d{1,2}){0,4}\.?|[IVX]{1,4}\.|[A-H]\.)\s+)?([A-Z][A-Za-z0-9 ,&/()'\-:]{2,90})\s*$"
)
_SUMMARY: Final = re.compile(
    r"\b(?:summary|summaries|executive|recommendations?|conclusions?|overview|label(?:l)?ing|"
    r"labell?ing (?:comments|recommendations)|phase (?:iv|4) commitments?|signatures?)\b",
    re.I,
)
_TOC_LINE: Final = re.compile(r"\.{5,}\s*\d+\s*$|(?:\. ){4,}")


@dataclass(frozen=True)
class Page:
    number: int  # 1-based page number of the PDF
    lines: tuple[str, ...]
    readable: tuple[bool, ...]  # False inside a summary-like section or a table-of-contents line
    text_page: bool


def pdf_pages(path: Path, timeout: float = 300.0) -> list[str]:
    """The layout text of every page (form feed separated)."""
    out = subprocess.run(  # noqa: S603 - fixed program, file path argument
        ["pdftotext", "-layout", "-enc", "UTF-8", str(path), "-"],  # noqa: S607
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    text = out.stdout.decode("utf-8", "replace")
    pages = text.split("\f")
    if pages and not pages[-1].strip():
        pages = pages[:-1]
    return pages


def born_digital(pages: list[str]) -> bool:
    if not pages:
        return False
    text_pages = sum(1 for p in pages if len(p.strip()) >= MIN_TEXT_CHARS)
    return text_pages / len(pages) >= BORN_DIGITAL_SHARE


def is_heading(line: str) -> bool:
    """A short line that looks like a section heading (numbered or title-like, no sentence end, few
    words)."""
    s = line.strip()
    if not s or len(s) > 95 or s.endswith((".", ",", ";")) or re.search(r"\s{3,}", s):
        return False
    m = _HEADING.match(line)
    if m is None:
        return False
    words = m.group(1).split()
    return 1 <= len(words) <= 12 and not re.search(r"\d+\.\d+\s*(?:mg|ng|h)\b", s)


def mark_pages(pages: list[str]) -> list[Page]:
    """Pages with the readable flag of every line. The summary state carries over page breaks."""
    out: list[Page] = []
    in_summary = False
    for i, text in enumerate(pages, 1):
        lines = tuple(text.split("\n"))
        flags: list[bool] = []
        for line in lines:
            if _TOC_LINE.search(line):
                flags.append(False)
                continue
            if is_heading(line):
                in_summary = bool(_SUMMARY.search(line))
            flags.append(not in_summary)
        out.append(Page(i, lines, tuple(flags), len(text.strip()) >= MIN_TEXT_CHARS))
    return out
