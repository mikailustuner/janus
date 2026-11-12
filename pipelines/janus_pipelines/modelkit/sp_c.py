"""Reader C for special-population label sentences: list alignment (third independent reader).

Readers A and B read one statement at a time; their shared weak spot is a sentence that lists several
values ("AUC increased by 23 %, 47 % and 75 % in mild, moderate and severe impairment, respectively").
Reader C reads only such structures: it finds the ordered grade list and the ordered measure groups of
a sentence, collects the magnitudes that follow each measure group, and aligns them position by
position when the counts match (with "respectively"), or reads a sentence with one measure group, one
magnitude and at most one grade. Anything else is left unread. It shares no code with readers A and B
(identity table not needed). The ratio convention is the pre-registered one (30 % higher = 1.30,
2-fold lower = 0.5). Research use only. Not for clinical decisions.
"""

from __future__ import annotations

import re
from typing import Final

_GRADE: Final = re.compile(
    r"(?P<mild>\bmild(?:ly)?\b)|(?P<moderate>\bmoderate(?:ly)?\b)|(?P<severe>\bsevere(?:ly)?\b)"
    r"|(?P<esrd>end[- ]stage|\besrd\b)"
    r"|(?P<cp>childs?[- ]pugh (?:class |score )?(?P<cpc>[abc])\b)",
    re.I,
)
_CP: Final = {"a": "mild", "b": "moderate", "c": "severe"}
_MEASURE: Final = re.compile(
    r"(?P<auc>\bAUC\w*|systemic exposure|\bexposure\b|area under)|(?P<cmax>\bC\s?max\w*|peak (?:plasma )?concentration)",
    re.I,
)
_MAG: Final = re.compile(r"(?<![\d.])(\d+(?:\.\d+)?)\s*(%|percent|-?\s*fold|\s*times)", re.I)
_BARE_LIST: Final = re.compile(
    r"\d(?:\.\d+)?\s*(?:,|and|or)\s*(?:\d+(?:\.\d+)?\s*(?:,|and|or)\s*)*\d+(?:\.\d+)?\s*(?:%|-?\s*fold|\s*times)",
    re.I,
)
_RANGE: Final = re.compile(r"\d\s*%?\s*(?:-|to|–)\s*\d+(?:\.\d+)?\s*(?:%|-?\s*fold|\s*times)", re.I)
_UP: Final = re.compile(r"increase|higher|greater|elevat|rise|rose", re.I)
_DOWN: Final = re.compile(r"decrease|lower|reduc|declin|less\b", re.I)
_SENT: Final = re.compile(r"(?<=[.;])\s+(?=[A-Z])")

# The grade vocabulary of readers A and B and the equivalences C accepts.
SAME_GRADE: Final = {
    "mild": "mild", "cp_a": "mild", "moderate": "moderate", "cp_b": "moderate", "severe": "severe",
    "cp_c": "severe", "esrd": "esrd", "": "", "age65": "", "age75": "", "age80": "",
}  # fmt: skip


def _grades(sentence: str) -> list[str]:
    out: list[tuple[int, str]] = []
    for m in _GRADE.finditer(sentence):
        g = (
            _CP[m.group("cpc").lower()]
            if m.group("cp")
            else next(k for k in ("mild", "moderate", "severe", "esrd") if m.group(k))
        )
        if out and out[-1][1] == g and m.start() - out[-1][0] < 40:
            continue  # "mild (Child-Pugh A)" is one grade
        out.append((m.start(), g))
    return [g for _, g in out]


def _ratio(num: float, kind: str, segment: str) -> float | None:
    up, down = _UP.search(segment), _DOWN.search(segment)
    if bool(up) == bool(down):
        return None  # no direction, or both: not read
    if "%" in kind or "percent" in kind.lower():
        r = 1 + num / 100 if up else 1 - num / 100
    else:
        r = num if up else (1 / num if num else 0.0)
    return r if 0 < r <= 50 else None


def read(quote: str) -> dict[tuple[str, str], float]:
    """(measure, grade) -> ratio for the statements C can align; grade '' when the sentence gives none."""
    out: dict[tuple[str, str], float] = {}
    for sentence in _SENT.split(quote):
        if _RANGE.search(sentence) or _BARE_LIST.search(sentence):
            continue  # a range, or "30 and 13 %" (a unit only on the last number): not read
        grades = _grades(sentence)
        found = list(_MEASURE.finditer(sentence))
        groups: list[
            tuple[list[str], list[float]]
        ] = []  # measures of a group, the ratios that follow it
        pending: list[str] = []
        for i, m in enumerate(found):
            kind = "auc" if m.group("auc") else "cmax"
            end = found[i + 1].start() if i + 1 < len(found) else len(sentence)
            seg = sentence[m.end() : end]
            mags = list(_MAG.finditer(seg))
            if kind not in pending:
                pending.append(kind)
            if not mags:
                continue  # "AUC and Cmax ... ": the next measure word joins this group
            vals = [_ratio(float(x.group(1)), x.group(2), seg) for x in mags]
            if any(v is None for v in vals):
                pending = []
                continue
            groups.append((pending, [v for v in vals if v is not None]))
            pending = []
        resp = re.search(r"respectively", sentence, re.I) is not None
        for measures, vals in groups:
            if len(measures) == 1 and len(vals) == 1 and len(grades) <= 1:
                out[(measures[0], grades[0] if grades else "")] = vals[0]
            elif resp and len(measures) == 1 and len(grades) >= 2 and len(vals) == len(grades):
                for g, v in zip(grades, vals, strict=True):
                    out[(measures[0], g)] = v
            elif resp and len(measures) == len(vals) >= 2 and len(grades) <= 1:
                for ms, v in zip(measures, vals, strict=True):
                    out[(ms, grades[0] if grades else "")] = v
            elif not resp and len(measures) >= 2 and len(vals) == 1 and len(grades) <= 1:
                for ms in measures:  # "AUC and Cmax increased by 20 %"
                    out[(ms, grades[0] if grades else "")] = vals[0]
    return out


def agrees(quote: str, measure: str, grade: str, ratio: float) -> bool:
    """Reader C read the same ratio (within 1 %) for this measure and an equivalent grade."""
    g = SAME_GRADE.get(grade)
    if g is None:
        return False
    v = read(quote).get((measure, g))
    return v is not None and abs(v - ratio) <= 0.01 * max(v, ratio)
