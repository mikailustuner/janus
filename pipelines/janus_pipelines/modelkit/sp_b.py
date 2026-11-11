"""Special populations, reader B (spec model-kit, milestone M4): structure first, then clauses and token windows.

Independent of reader A (`sp_a`): it shares only the result type and vocabulary of `sp_model`. It first cuts a section
into blocks at the sub-section headings of the label (Geriatric Use, Renal Impairment, Hepatic Impairment ...), so a
block carries its population class even when a sentence does not say it; then it tokenises each sentence and finds the
magnitudes (number followed by a percent sign or "fold", ratios, lists) by scanning token positions, ties each to the
nearest measure, direction word, population cue and grade token, and converts it by the pre-registered convention.
Tables are read with the standard HTML parser. Pure. Research use only. Not for clinical decisions.
"""

from __future__ import annotations

import math
import re
from html import unescape
from html.parser import HTMLParser

from janus_pipelines.modelkit.sp_model import (
    RATIO_MAX,
    RATIO_MIN,
    SECTION_FIELDS,
    TABLE_FIELDS,
    SpCandidate,
    SpLabel,
    SpStats,
)

_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9/'½-]*|\d+(?:\.\d+)?|[%≥≤<>(),;:]|\.")
_UP = frozenset(
    "higher greater increase increased increases increasing elevated more larger rise rises raised".split()
)
_DOWN = frozenset(
    "lower less decrease decreased decreases decreasing reduced reduction reduce smaller declined dropped".split()
)
_OTHER_WORDS = frozenset(
    "half-life half t1/2 t½ clearance cl cl/f volume vd tmax binding unbound bioavailability excretion elimination "
    "urinary".split()
)
_IMPAIR = frozenset("impairment insufficiency dysfunction failure disease impaired".split())
_ABBR = frozenset({"e.g", "i.e", "vs", "approx", "al", "fig", "no"})
_HEADINGS = (
    (
        "geriatric",
        (
            "Geriatric Use",
            "Geriatric Patients",
            "Geriatrics",
            "Elderly",
            "Older Adults",
            "Older Patients",
        ),
    ),
    (
        "renal",
        (
            "Patients with Renal Impairment",
            "Renal Impairment",
            "Renal Insufficiency",
            "Renal Dysfunction",
            "Renal Failure",
        ),
    ),
    (
        "hepatic",
        (
            "Patients with Hepatic Impairment",
            "Hepatic Impairment",
            "Hepatic Insufficiency",
            "Hepatic Dysfunction",
            "Liver Impairment",
        ),
    ),
    (
        "other",
        (
            "Pediatric Use",
            "Pediatric Patients",
            "Pregnancy",
            "Lactation",
            "Nursing Mothers",
            "Gender",
            "Sex",
            "Race",
            "Drug Interactions",
            "Body Weight",
            "Obesity",
            "Absorption",
            "Distribution",
            "Metabolism",
            "Elimination",
            "Excretion",
            "Females and Males of Reproductive Potential",
            "Overdosage",
            "Specific Populations",
            "Special Populations",
            "Pharmacokinetics",
        ),
    ),
)
_HEADING_RX = re.compile(
    r"(?:(?<=\s)|^)(?:\d{1,2}\.\d{1,2}(?:\.\d{1,2})?\s+)?("
    + "|".join(sorted((h for _, hs in _HEADINGS for h in hs), key=len, reverse=True))
    + r")(?=\s*:|\s+[A-Z][a-z]|\s*$)"
)
_FLAG_WORDS = {
    "metabolite": frozenset(
        "metabolite metabolites glucuronide conjugate conjugates prodrug moiety".split()
    ),
    "unbound": frozenset({"unbound", "free"}),
    "pediatric": frozenset(
        "pediatric paediatric children child infants infant adolescents adolescent neonates neonatal".split()
    ),
    "interaction": frozenset(
        "coadministration co-administration coadministered co-administered concomitant concomitantly inhibitor "
        "inducer ketoconazole rifampin".split()
    ),
    "animal": frozenset(
        "rat rats mice mouse dog dogs monkey monkeys rabbit rabbits animals animal".split()
    ),
    "pregnancy": frozenset("pregnant pregnancy postpartum lactation lactating".split()),
}


_DASHES = {0x2013: "-", 0x2212: "-"}  # en dash and minus sign read as a hyphen


def _norm(text: str) -> str:
    t = unescape(text).translate(_DASHES)
    return re.sub(r"\s+", " ", t).strip()


# --- structure: blocks ---------------------------------------------------------------------------------------------


def blocks(text: str, default: str | None) -> list[tuple[str | None, str]]:
    """(population class from the sub-section heading or the field default, text) of each block of a section."""
    t = _norm(text)
    marks = [(m.start(1), m.end(1), m.group(1)) for m in _HEADING_RX.finditer(t)]
    cls_of = {h: c for c, hs in _HEADINGS for h in hs}
    if not marks:
        return [(default, t)]
    out: list[tuple[str | None, str]] = []
    if marks[0][0] > 0 and t[: marks[0][0]].strip():
        out.append((default, t[: marks[0][0]]))
    for i, (_, end, title) in enumerate(marks):
        stop = marks[i + 1][0] if i + 1 < len(marks) else len(t)
        c = cls_of[title]
        out.append((None if c == "other" else c, t[end:stop]))
    return out


def split_sentences(t: str) -> list[str]:
    out: list[str] = []
    last = 0
    for m in re.finditer(r"[.!?]\s+(?=[A-Z0-9(\[])", t):
        words = re.findall(r"[A-Za-z.]+$", t[: m.start()])
        if words and words[0].lower().rstrip(".") in _ABBR:
            continue
        out.append(t[last : m.start() + 1].strip())
        last = m.end()
    out.append(t[last:].strip())
    return [s for s in out if s]


# --- tokens --------------------------------------------------------------------------------------------------------


def _tok(s: str) -> list[str]:
    return _TOKEN.findall(s)


def _low(toks: list[str]) -> list[str]:
    return [t.lower() for t in toks]


def _is_num(t: str) -> bool:
    return re.fullmatch(r"\d+(?:\.\d+)?", t) is not None


def _measure_tokens(low: list[str]) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    for i, t in enumerate(low):
        if t.startswith("auc"):
            out.append((i, "auc"))
        elif t == "cmax" or (t == "c" and i + 1 < len(low) and low[i + 1] == "max"):
            out.append((i, "cmax"))
        elif (
            t == "peak" and i + 1 < len(low) and low[i + 1] in ("plasma", "serum", "concentration")
        ):
            out.append((i, "cmax"))
        elif t == "area" and low[i + 1 : i + 3] == ["under", "the"]:
            out.append((i, "auc"))
        elif t in _OTHER_WORDS and not (t == "half" and low[i + 1 : i + 2] != ["life"]):
            out.append((i, "other"))
    return out


def _direction(low: list[str], i: int, window: int = 6) -> str | None:
    best: tuple[int, str] | None = None
    for j in range(max(0, i - window), min(len(low), i + window + 1)):
        w = "up" if low[j] in _UP else "down" if low[j] in _DOWN else None
        if w and j != i:
            d = abs(j - i) + (0 if j < i else 0.5)
            if best is None or d < best[0]:
                best = (int(d * 2), w)
    return best[1] if best else None


def _to_ratio(
    direction: str | None, pct: float | None = None, fold: float | None = None
) -> float | None:
    if direction is None:
        return None
    if pct is not None:
        r = 1 + pct / 100 if direction == "up" else 1 - pct / 100
    elif fold is not None and fold > 0:
        r = fold if direction == "up" else 1 / fold
    else:
        return None
    return r if RATIO_MIN < r <= RATIO_MAX else None


def _mags(toks: list[str], low: list[str]) -> list[tuple[int, float, str]]:
    """(token index, ratio, text) of the magnitudes of a sentence, by scanning token positions."""
    out: list[tuple[int, float, str]] = []
    used: set[int] = set()
    n = len(toks)
    i = 0
    while i < n:
        if _is_num(toks[i]) and i not in used:
            # range: N to N %   /   N - N %  (the dash is not a token: "25 to 45 %" or "25 % to 45 %")
            j = i + 1
            if j < n and low[j] == "%":
                j += 1
            plain_first = j == i + 1  # "25 and 45 %" is a range; "25 % and 45 %" is a list
            if (
                j + 1 < n
                and (low[j] == "to" or (low[j] == "and" and plain_first))
                and _is_num(toks[j + 1])
                and j + 2 < n
                and low[j + 2] == "%"
            ):
                d = _direction(low, i, 7) or _direction(low, j + 2, 7)
                a, b = _to_ratio(d, pct=float(toks[i])), _to_ratio(d, pct=float(toks[j + 1]))
                if a and b:
                    out.append((i, math.sqrt(a * b), f"{toks[i]} to {toks[j + 1]} %"))
                    used |= set(range(i, j + 3))
                    i = j + 3
                    continue
            # fold pair: "1.5 and 2.1 fold"
            if (
                i + 3 < n
                and low[i + 1] in ("and", "or", "to")
                and _is_num(toks[i + 2])
                and low[i + 3] in ("fold", "times")
            ):
                d = _direction(low, i, 8)
                a, b = _to_ratio(d, fold=float(toks[i])), _to_ratio(d, fold=float(toks[i + 2]))
                if a and b:
                    out += [(i, a, f"{toks[i]}-fold"), (i + 2, b, f"{toks[i + 2]}-fold")]
                    used |= {i, i + 2}
                    i += 4
                    continue
            if i + 1 < n and low[i + 1] in ("fold", "times"):
                r = _to_ratio(_direction(low, i, 6), fold=float(toks[i]))
                if r:
                    out.append((i, r, f"{toks[i]}-fold"))
                    used.add(i)
            elif i + 1 < n and (low[i + 1] == "%" or low[i + 1] == "percent"):
                if low[i + 2 : i + 3] in (
                    ["ci"],
                    ["confidence"],
                ):  # a confidence level, not a magnitude
                    i += 1
                    continue
                d = _direction(low, i, 6)
                if (
                    d is None
                ):  # list: "by 40 %, 70 % and 130 %": take the direction of the first number of the list
                    k = i - 1
                    while k >= 0 and (
                        low[k] in (",", "and", "or", "%", "percent") or _is_num(toks[k])
                    ):
                        k -= 1
                    d = _direction(low, k + 1, 3) if k + 1 < n else None
                r = _to_ratio(d, pct=float(toks[i]))
                if r:
                    out.append((i, r, f"{toks[i]} %"))
                    used.add(i)
        elif low[i] == "ratio":
            for j in range(i + 1, min(n, i + 10)):
                if _is_num(toks[j]) and (j + 1 >= n or low[j + 1] not in ("%", "fold")):
                    v = float(toks[j])
                    if RATIO_MIN < v <= RATIO_MAX:
                        out.append((j, v, f"ratio {toks[j]}"))
                        used.add(j)
                    break
        i += 1
    return sorted(out)


def _pop_cues(low: list[str]) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    n = len(low)
    for i, t in enumerate(low):
        nxt = low[i + 1] if i + 1 < n else ""
        if (t in ("renal", "kidney") and nxt in _IMPAIR) or t in ("clcr", "crcl", "egfr", "esrd"):
            out.append((i, "renal"))
        elif t == "creatinine" and nxt == "clearance":
            out.append((i, "renal"))
        elif t == "end-stage" and nxt == "renal":
            out.append((i, "renal"))
        elif (
            (t in ("hepatic", "liver") and nxt in _IMPAIR)
            or t.startswith("child-pugh")
            or t in ("cirrhosis", "cirrhotic")
        ):
            out.append((i, "hepatic"))
        elif t in ("elderly", "geriatric", "geriatrics"):
            out.append((i, "geriatric"))
        elif (
            t == "older"
            and nxt
            in "adults adult subjects subject patients patient volunteers volunteer people individuals men women".split()
        ):
            out.append((i, "geriatric"))
        elif t == "≥" and nxt in ("65", "75", "80", "70", "60"):
            out.append((i, "geriatric"))
        elif (t == "aged" and nxt.isdigit()) or (t in ("age", "ages") and nxt == "65"):
            out.append((i, "geriatric"))
        elif (
            t.isdigit()
            and int(t) >= 60
            and nxt in ("years", "yrs")
            and low[i + 2 : i + 3] in (["and"], ["or"], ["of"])
        ):
            out.append((i, "geriatric"))
    return out


def _grade_tokens(low: list[str], pop: str) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    for i, t in enumerate(low):
        if pop in ("renal", "hepatic"):
            if t.startswith("child-pugh"):
                for j in range(i + 1, min(len(low), i + 4)):
                    if low[j] in ("a", "b", "c"):
                        out.append((i, "cp_" + low[j]))
                        break
            elif t in ("mild", "moderate", "severe"):
                out.append((i, t))
            elif t == "end-stage":
                out.append((i, "esrd"))
            elif t == "esrd":
                out.append((i, "esrd"))
    if pop == "hepatic" and any(g.startswith("cp_") for _, g in out):
        out = [x for x in out if x[1].startswith("cp_")]
    return out


def _geri_grade(low: list[str]) -> str:
    for i, t in enumerate(low):
        if t == "≥" and i + 1 < len(low) and low[i + 1].isdigit():
            n = int(low[i + 1])
            return "age80" if n >= 80 else "age75" if n >= 75 else "age65"
        if t == "aged" and i + 1 < len(low) and low[i + 1].isdigit():
            n = int(low[i + 1])
            return "age80" if n >= 80 else "age75" if n >= 75 else "age65"
        if t.isdigit() and int(t) >= 60 and i + 1 < len(low) and low[i + 1] in ("years", "yrs"):
            n = int(t)
            return "age80" if n >= 80 else "age75" if n >= 75 else "age65"
    return "age65"


def _flags(low: list[str], text: str, drug: str = "") -> tuple[str, ...]:
    out = [k for k, ws in _FLAG_WORDS.items() if ws & set(low)]
    name = drug.replace("_", " ")
    if name and any(
        (t.endswith("-" + name) and len(t) > len(name) + 1)
        or (
            t == name
            and low[k + 1 : k + 2]
            and low[k + 1] in ("glucuronide", "sulfoxide", "sulfone", "n-oxide", "conjugate")
        )
        for k, t in enumerate(low)
    ):
        out.append("metabolite")
    if re.search(r"enantiomer|\b[RS]\)?-[a-z]", text):
        out.append("enantiomer")
    if re.search(r"\b[A-Z]{2,5}-?\d{3,}[A-Z]?\b|\bM\d\b|\bepoxide\b", text) or re.search(
        r"\b(?:and|or) its\b", text, re.I
    ):
        out.append("metabolite")
    if re.search(r"dose[- ](?:adjust|reduction)|reduced dose|lower dose", text, re.I):
        out.append("dose_change")
    if "in combination with" in text.lower() or "when given with" in text.lower():
        out.append("interaction")
    return tuple(sorted(set(out)))


def _reference(toks: list[str], low: list[str]) -> str:
    for i, t in enumerate(low):
        start: int | None = None
        if t in ("versus", "vs") or t == "than":
            start = i + 1
        elif t == "compared" and i + 1 < len(low) and low[i + 1] in ("to", "with"):
            start = i + 2
        elif t == "relative" and i + 1 < len(low) and low[i + 1] == "to":
            start = i + 2
        if start is None:
            continue
        while start < len(low) and low[start] in ("in", "that", "those", "seen"):
            start += 1
        end = start
        while end < len(low) and end - start < 12 and low[end] not in (",", ";", ".", "(", ")"):
            end += 1
        if end - start >= 1:
            return " ".join(toks[start:end])
    return ""


def _join(span: list[str]) -> str:
    stop = next((k for k, x in enumerate(span) if x in (")", ",", ";", ".")), len(span))
    t = " ".join(span[:stop])
    return re.sub(r"([<>≥≤])\s+", r"\1", t).strip()


def _definition(toks: list[str], low: list[str], pop: str, grade: str) -> str:
    if pop == "renal":
        for i, t in enumerate(low):
            if t in ("clcr", "crcl", "egfr") or (
                t == "creatinine" and low[i + 1 : i + 2] == ["clearance"]
            ):
                span = toks[i : i + 9]
                if any(_is_num(x) for x in span):
                    return _join(span)
    if pop == "hepatic":
        for i, t in enumerate(low):
            if t.startswith("child-pugh"):
                return _join(toks[i : i + 3])
    if pop == "geriatric":
        for i, t in enumerate(low):
            if (
                t == "≥"
                or t == "aged"
                or (t.isdigit() and low[i + 1 : i + 2] in (["years"], ["yrs"]))
            ):
                return _join(toks[i : i + 4])
        return "elderly"
    return grade or pop


_COMPARE = frozenset(
    "healthy normal young younger control controls matched without unimpaired non-impaired".split()
)
BLOCK_SENTENCES = 5  # a heading gives its class to at most this many following sentences


def read_sentence(
    label: SpLabel, section: str, block_class: str | None, s: str, stats: SpStats
) -> list[SpCandidate]:
    toks = _tok(s)
    low = _low(toks)
    if not _COMPARE & set(low):
        block_class = (
            None  # the heading's class only reaches sentences that compare with a reference group
        )
    meas = _measure_tokens(low)
    if not any(m != "other" for _, m in meas):
        return []
    mags = _mags(toks, low)
    if not mags:
        return []
    cues = _pop_cues(low)
    out: list[SpCandidate] = []
    names = [m for _, m in meas if m != "other"]
    ordered: list[str] = []
    for m in names:
        if m not in ordered:
            ordered.append(m)
    respectively = "respectively" in low
    for idx, (pos, ratio, text) in enumerate(mags):
        # population: the nearest cue to the magnitude, else the class of the block (heading) the sentence is in
        pop = block_class
        if cues:
            pop = min(cues, key=lambda c: abs(c[0] - pos))[1]
        if pop not in ("geriatric", "renal", "hepatic"):
            stats.add("b_skip_no_population")
            continue
        # measure
        if len(mags) == len(ordered) > 1:
            measures = [ordered[idx]]
        else:
            before = [m for m in meas if m[0] < pos and pos - m[0] <= 30]
            pick = max(before) if before else None
            if pick is None:
                after = [m for m in meas if m[0] >= pos and m[0] - pos <= 10]
                pick = min(after) if after else None
            if pick is None or pick[1] == "other":
                stats.add("b_skip_magnitude_of_another_quantity" if pick else "b_skip_no_measure")
                continue
            measures = [pick[1]]
            if len(mags) == 1 and len(ordered) == 2 and not respectively:
                measures = list(ordered)
        grades = _grade_tokens(low, pop)
        if pop == "geriatric":
            grade = _geri_grade(low)
        elif respectively and len(grades) == len(mags) > 1:
            grade = grades[idx][1]
        elif grades:
            prior = [g for g in grades if g[0] <= pos]
            grade = (prior[-1] if prior else grades[0])[1]
        else:
            grade = ""
        for measure in measures:
            out.append(
                SpCandidate(
                    "b",
                    label.drug_key,
                    label.set_id,
                    label.version,
                    section,
                    pop,
                    grade,
                    measure,
                    round(ratio, 4),
                    text,
                    _definition(toks, low, pop, grade),
                    _reference(toks, low),
                    s,
                    _flags(low, s, label.drug_key),
                )
            )
    return out


# --- tables --------------------------------------------------------------------------------------------------------


class _Rows(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self._cell: list[str] | None = None
        self._row: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th"):
            self._cell = []

    def handle_endtag(self, tag: str) -> None:
        if tag in ("td", "th") and self._cell is not None and self._row is not None:
            self._row.append(_norm(" ".join(self._cell)))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if self._row:
                self.rows.append(self._row)
            self._row = None

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)


def read_table(label: SpLabel, section: str, html: str, stats: SpStats) -> list[SpCandidate]:
    p = _Rows()
    p.feed(html)
    rows = p.rows
    head_i = next(
        (
            i
            for i, r in enumerate(rows[:3])
            if any(_measure_tokens(_low(_tok(c))) for c in r)
            and any(m != "other" for c in r for _, m in _measure_tokens(_low(_tok(c))))
        ),
        None,
    )
    if head_i is None:
        return []
    header = rows[head_i]
    cols: list[tuple[int, str, str]] = []
    for j, c in enumerate(header):
        low = _low(_tok(c))
        names = [m for _, m in _measure_tokens(low) if m != "other"]
        if re.search(r"[mnµu]?g\s?/\s?m?[Ll]\b|ng\s?[·*.]\s?h|\bmol", c, re.I):
            continue  # an absolute concentration or AUC column
        if names and (
            {"ratio", "fold", "change", "percent", "%", "relative"} & set(low) or "%" in c
        ):
            kind = (
                "pct"
                if ("%" in c or "percent" in low) and not ({"ratio", "fold"} & set(low))
                else "ratio"
            )
            cols.append((j, names[0], kind))
    out: list[SpCandidate] = []
    for i, r in enumerate(rows):
        if i <= head_i or not r:
            continue
        lowr = _low(_tok(r[0]))
        classes = {c for _, c in _pop_cues(lowr)}
        if len(classes) != 1:
            continue
        pop = next(iter(classes))
        gt = _grade_tokens(lowr, pop)
        grade = _geri_grade(lowr) if pop == "geriatric" else (gt[0][1] if gt else "")
        for j, name, kind in cols:
            if j >= len(r):
                continue
            m = re.search(r"[+-]?\d+(?:\.\d+)?", r[j])
            if not m:
                continue
            v = float(m.group(0))
            ratio = 1 + v / 100 if kind == "pct" else v
            if RATIO_MIN < ratio <= RATIO_MAX:
                quote = " | ".join(header) + " || " + " | ".join(r)
                out.append(
                    SpCandidate(
                        "b",
                        label.drug_key,
                        label.set_id,
                        label.version,
                        section,
                        pop,
                        grade,
                        name,
                        round(ratio, 4),
                        r[j],
                        _definition(_tok(r[0]), lowr, pop, grade),
                        "",
                        quote,
                        _flags(lowr, r[0], label.drug_key),
                        True,
                    )
                )
    return out


def read_label(label: SpLabel, stats: SpStats) -> list[SpCandidate]:
    out: list[SpCandidate] = []
    seen: set[tuple[str, str, str, float]] = set()

    def keep(c: SpCandidate) -> None:
        k = (c.pop_class, c.grade, c.measure, c.ratio)
        if k not in seen:
            seen.add(k)
            out.append(c)

    for field in SECTION_FIELDS:
        default = "geriatric" if field == "geriatric_use" else None
        for text in label.sections.get(field, ()):
            for cls, body in blocks(text, default):
                for k, s in enumerate(split_sentences(body)):
                    limited = (
                        cls
                        if (default is not None and cls == default) or k < BLOCK_SENTENCES
                        else None
                    )
                    for c in read_sentence(label, field, limited, s, stats):
                        keep(c)
    for field in TABLE_FIELDS:
        for html in label.tables.get(field, ()):
            for c in read_table(label, field, html, stats):
                keep(c)
    stats.add("b_candidates", len(out))
    return out
