"""Special populations, reader A (spec model-kit, milestone M4): sentence level, pattern based.

Splits the label sections into sentences; in a sentence that names exactly one population class and a measure (AUC or
Cmax) it takes magnitudes ("30 % higher", "increased by 30 %", "2-fold increase", "ratio of 1.5", a percentage range),
ties each to its measure and population grade by position (and by order for "respectively" lists) and converts it to a
ratio (population / reference) by the convention of the pre-registration. Tables are read row by row with regular
expressions. Shares nothing with reader B except the result type in `sp_model`. Pure. Research use only. Not for
clinical decisions.
"""

from __future__ import annotations

import math
import re
from html import unescape

from janus_pipelines.modelkit.sp_model import (
    RATIO_MAX,
    RATIO_MIN,
    SECTION_FIELDS,
    TABLE_FIELDS,
    SpCandidate,
    SpLabel,
    SpStats,
)

_UP = r"(?:higher|greater|increase[ds]?|increasing|elevated|more|larger|rise[ns]?|raised)"
_DN = r"(?:lower|less|decrease[ds]?|decreasing|reduc(?:ed|tion)|smaller|declin(?:ed|e)|dropped|reduce[ds]?)"
_N = r"(\d+(?:\.\d+)?)"

_POP = {
    "renal": re.compile(
        r"renal (?:impairment|insufficiency|dysfunction|failure|disease)|kidney (?:impairment|disease)|"
        r"creatinine clearance|\bCL\s?cr\b|\bCrCl\b|\beGFR\b|end[- ]stage renal|\bESRD\b",
        re.I,
    ),
    "hepatic": re.compile(
        r"hepatic (?:impairment|insufficiency|dysfunction|disease)|liver (?:impairment|disease|dysfunction)|"
        r"child[- ]?pugh|cirrho",
        re.I,
    ),
    "geriatric": re.compile(
        r"\belderly\b|\bgeriatric|\bolder (?:adult|subject|patient|volunteer|healthy|people|individual|male|female|men|women)s?\b|"
        r"\baged\s+(?:≥|>)?\s?\d{2}|≥\s?65|>\s?65 years|65 years (?:of age )?(?:and|or) (?:older|over|above)|\bage[ds]?\s+65",
        re.I,
    ),
}
_MEASURE = {
    "auc": re.compile(r"\bAUC\w*|area under the (?:plasma |serum )?(?:concentration|curve)", re.I),
    "cmax": re.compile(r"\bC\s?max\b|peak (?:plasma |serum )?concentration", re.I),
}
_OTHER = re.compile(
    r"half-life|\bt\s?1/2\b|t½|clearance|\bCL\b|\bCL/F\b|volume of distribution|\bVd\b|\bT\s?max\b|protein binding|"
    r"unbound fraction|bioavailability|excretion|elimination|urinary|oral dose",
    re.I,
)
_PCT_AFTER = re.compile(
    rf"{_N}\s?%\s*(?:\([^)]*\)\s*)?(?:was |were |is |are )?(?:{_UP}|{_DN})\b", re.I
)
_PCT_BEFORE = re.compile(
    rf"\b({_UP}|{_DN})\b[^.;%\d(]{{0,45}}?{_N}\s?%((?:\s?,?\s?(?:and |or )?\d+(?:\.\d+)?\s?%)*)",
    re.I,
)
_PCT_RANGE_BEFORE = re.compile(
    rf"\b({_UP}|{_DN})\b[^.;%\d(]{{0,45}}?{_N}\s?%?\s?(?:to|-|and)\s?{_N}\s?%", re.I
)
_FOLD_PAIR = re.compile(rf"{_N}-?\s+(?:and|or|to)\s+{_N}[- ]?(?:fold|times)\b", re.I)
_PCT_RANGE = re.compile(
    rf"{_N}\s?(?:%\s?(?:to|-)|(?:to|-|and))\s?{_N}\s?%\s*(?:\([^)]*\)\s*)?(?:was |were )?({_UP}|{_DN})\b",
    re.I,
)
_PCT_LIST_AFTER = re.compile(
    rf"{_N}\s?%((?:\s?,?\s?(?:and |or )?\d+(?:\.\d+)?\s?%)+)\s*(?:\([^)]*\)\s*)?(?:was |were |is |are )?({_UP}|{_DN})\b",
    re.I,
)
_FOLD = re.compile(rf"{_N}[- ]?(?:fold|times)\b", re.I)
_RATIO = re.compile(rf"\bratio\b[^.;]{{0,80}}?(?:of|was|were|=|:)\s*{_N}\b", re.I)
_GRADE = re.compile(
    r"\b(mild|moderate|severe|end[- ]stage)\b|child[- ]?pugh(?: class| grade| score| category)?\s*([ABC])\b",
    re.I,
)
_REF = re.compile(
    r"(?:compared (?:to|with)|relative to|versus|\bvs_?\b|as compared with|than(?:\s+(?:in|that in|those in|seen in))?)\s+"
    r"([^.;,()]{3,90})",
    re.I,
)
_FLAGS = {
    "metabolite": re.compile(
        r"metabolite|glucuronide|conjugate|prodrug|active moiety|\bM\d\b|\b[A-Z]{2,5}-?\d{3,}[A-Z]?\b|\bepoxide\b|"
        r"\b(?:and|or) its\b",
        re.I,
    ),
    "enantiomer": re.compile(r"enantiomer|\b[RS]\)?-(?=[a-z])", re.I),
    "unbound": re.compile(r"unbound|free (?:drug|fraction|concentration)", re.I),
    "pediatric": re.compile(r"pediatric|paediatric|children|infant|adolescent|neonat", re.I),
    "interaction": re.compile(
        r"co-?administ|concomitant|inhibitor|inducer|in combination with|ketoconazole|rifampin|when given with",
        re.I,
    ),
    "animal": re.compile(r"\b(?:rats?|mice|mouse|dogs?|monkeys?|rabbits?|animals?)\b", re.I),
    "pregnancy": re.compile(r"pregnan|postpartum|lactat", re.I),
    "dose_change": re.compile(
        r"dose[- ]adjust|dose reduction|reduced dose|lower dose|dose of \d", re.I
    ),
}
_PROTECT = (
    ("e.g.", "e_g_"),
    ("i.e.", "i_e_"),
    ("vs.", "vs_"),
    ("approx.", "approx_"),
    ("et al.", "et al_"),
)


_DASHES = {0x2013: "-", 0x2212: "-"}  # en dash and minus sign read as a hyphen


def _clean(text: str) -> str:
    t = unescape(text).translate(_DASHES)
    return re.sub(r"\s+", " ", t).strip()


def sentences(text: str) -> list[str]:
    t = _clean(text)
    for a, b in _PROTECT:
        t = t.replace(a, b)
    t = re.sub(r"(?<=[a-z.)\]])\s+(?=\d{1,2}(?:\.\d{1,2})+\s+[A-Z][a-z])", "\n", t)
    parts = re.split(r"\n|(?<=[.!?])\s+(?=[A-Z\[(0-9])", t)
    out = [p.strip() for p in parts if p.strip()]
    for a, b in _PROTECT:
        out = [p.replace(b, a) for p in out]
    return out


def _grade_of(pop: str, text: str) -> str:
    cp = re.search(r"child[- ]?pugh(?: class| grade| score| category)?\s*([ABC])\b", text, re.I)
    if pop == "hepatic" and cp:  # "moderate (Child-Pugh B)": the class letter decides
        return "cp_" + cp.group(1).lower()
    m = _GRADE.search(text)
    if pop in ("renal", "hepatic") and m:
        if m.group(2):
            return "cp_" + m.group(2).lower()
        w = m.group(1).lower()
        return "esrd" if w.startswith("end") else w
    if pop == "geriatric":
        a = re.search(
            r"≥\s?(\d{2})|(\d{2}) years (?:of age )?(?:and|or) (?:older|over|above)|aged?\s+(\d{2})",
            text,
            re.I,
        )
        if a:
            n = int(next(g for g in a.groups() if g))
            return "age80" if n >= 80 else "age75" if n >= 75 else "age65"
        return "age65"
    return ""


def _ratio(direction: str, pct: float | None = None, fold: float | None = None) -> float | None:
    up = re.fullmatch(_UP, direction, re.I) is not None
    if pct is not None:
        r = 1 + pct / 100 if up else 1 - pct / 100
    elif fold is not None and fold > 0:
        r = fold if up else 1 / fold
    else:
        return None
    return r if RATIO_MIN < r <= RATIO_MAX else None


_CI = re.compile(r"^\s?(?:CI\b|confidence)", re.I)


def _near_direction(sentence: str, start: int, end: int) -> str | None:
    window = sentence[max(0, start - 30) : end + 30]
    m = re.search(rf"\b({_UP}|{_DN})\b", window, re.I)
    return m.group(1) if m else None


def _magnitudes(s: str) -> list[tuple[int, float, str]]:
    """(position, ratio, text) of each magnitude in the sentence."""
    out: list[tuple[int, float, str]] = []
    taken: list[tuple[int, int]] = []

    def free(a: int, b: int) -> bool:
        return all(b <= x or a >= y for x, y in taken) and not _CI.match(
            s[b:]
        )  # "90 % CI" is a level

    for m in _PCT_RANGE.finditer(s):
        lo, hi = float(m.group(1)), float(m.group(2))
        a, b = _ratio(m.group(3), pct=lo), _ratio(m.group(3), pct=hi)
        if a and b and free(m.start(), m.end()):
            out.append((m.start(), math.sqrt(a * b), m.group(0)))
            taken.append((m.start(), m.end()))
    for m in _PCT_LIST_AFTER.finditer(s):  # "up to 40 % and 67 % higher, respectively"
        if not free(m.start(), m.end()):
            continue
        nums = [m.group(1), *re.findall(r"\d+(?:\.\d+)?", m.group(2))]
        rs = [_ratio(m.group(3), pct=float(x)) for x in nums]
        if all(rs):
            for k, r in enumerate(rs):
                out.append((m.start() + k, r or 0, nums[k] + " %"))
            taken.append((m.start(), m.end()))
    for m in _PCT_AFTER.finditer(s):
        d = re.search(rf"{_UP}|{_DN}", m.group(0)[len(m.group(1)) :], re.I)
        r = _ratio(d.group(0), pct=float(m.group(1))) if d else None
        if r and free(m.start(), m.end()):
            out.append((m.start(), r, m.group(0)))
            taken.append((m.start(), m.end()))
    for m in _PCT_RANGE_BEFORE.finditer(s):
        a, b = _ratio(m.group(1), pct=float(m.group(2))), _ratio(m.group(1), pct=float(m.group(3)))
        if a and b and free(m.start(), m.end()):
            out.append((m.start(), math.sqrt(a * b), m.group(0)))
            taken.append((m.start(), m.end()))
    for m in _PCT_BEFORE.finditer(s):
        if not free(m.start(), m.end()):
            continue
        r = _ratio(m.group(1), pct=float(m.group(2)))
        if r:
            out.append((m.start(), r, m.group(0)))
            taken.append((m.start(), m.end()))
            for k, extra in enumerate(re.findall(r"\d+(?:\.\d+)?", m.group(3) or "")):
                r2 = _ratio(m.group(1), pct=float(extra))
                if r2:  # "increased by 40 %, 70 % and 130 %": the listed percentages share the direction
                    out.append((m.end() - len(m.group(3)) + k, r2, extra + " %"))
    for m in _FOLD_PAIR.finditer(s):
        d = _near_direction(s, m.start(), m.end())
        pair = [_ratio(d, fold=float(m.group(i))) for i in (1, 2)] if d else []
        if pair and all(pair) and free(m.start(), m.end()):
            out.append((m.start(), pair[0] or 0, m.group(1) + "-fold"))
            out.append((m.start() + 1, pair[1] or 0, m.group(2) + "-fold"))
            taken.append((m.start(), m.end()))
    for m in _FOLD.finditer(s):
        d = _near_direction(s, m.start(), m.end())
        r = _ratio(d, fold=float(m.group(1))) if d else None
        if r and free(m.start(), m.end()):
            out.append((m.start(), r, m.group(0)))
            taken.append((m.start(), m.end()))
    for m in _RATIO.finditer(s):
        v = float(m.group(1))
        if RATIO_MIN < v <= RATIO_MAX and free(m.start(), m.end()):
            out.append((m.start(), v, m.group(0)))
            taken.append((m.start(), m.end()))
    return sorted(out)


def _measure_at(s: str, pos: int) -> tuple[str | None, bool]:
    """The measure a magnitude belongs to: the nearest measure or other-quantity word before it (else after)."""
    cands: list[tuple[int, str]] = []
    for name, rx in _MEASURE.items():
        cands += [(m.start(), name) for m in rx.finditer(s)]
    cands += [(m.start(), "other") for m in _OTHER.finditer(s)]
    before = [c for c in cands if c[0] < pos and pos - c[0] <= 160]
    pick = max(before) if before else None
    if pick is None:
        after = [c for c in cands if c[0] >= pos and c[0] - pos <= 60]
        pick = min(after) if after else None
    if pick is None or pick[1] == "other":
        return None, pick is not None
    return pick[1], False


def _definition(pop: str, s: str) -> str:
    if pop == "renal":
        m = re.search(
            r"(?:CL\s?cr|CrCl|creatinine clearance|eGFR)[^.;)]{0,50}?(?:\d+(?:\.\d+)?\s?(?:to|-)\s?\d+(?:\.\d+)?|[<>≤≥]\s?\d+)"
            r"[^.;)]{0,24}",
            s,
            re.I,
        )
        if m:
            return m.group(0).strip()
    if pop == "hepatic":
        m = re.search(
            r"child[- ]?pugh(?: class| grade| score| category)?\s?(?:[ABC]\b|\d+(?:-\d+)?)(?:\s?\([^)]*\))?",
            s,
            re.I,
        )
        if m:
            return m.group(0).strip()
    if pop == "geriatric":
        m = re.search(
            r"(?:aged?\s+)?(?:≥|>)?\s?\d{2}\s?(?:-\s?\d{2}\s?)?years?(?: of age)?(?: and (?:older|over))?|elderly|older [a-z]+",
            s,
            re.I,
        )
        if m:
            return m.group(0).strip()
    g = _GRADE.search(s)
    return g.group(0).strip() if g else pop


def _flags(s: str, drug: str = "") -> tuple[str, ...]:
    out = [k for k, rx in _FLAGS.items() if rx.search(s)]
    d = re.escape(drug.replace("_", " "))
    if (
        drug
        and "metabolite" not in out
        and re.search(
            rf"\b[a-z]+-{d}\b|\b{d}[ -](?:glucuronide|sulfoxide|sulfone|n-oxide|conjugate)\b",
            s,
            re.I,
        )
    ):
        out.append(
            "metabolite"
        )  # "hydroxy-<drug>", "<drug> glucuronide": another analyte named like the drug
    return tuple(out)


def _reference(s: str) -> str:
    m = _REF.search(s)
    return m.group(1).strip() if m else ""


_HEAD = re.compile(
    r"^(?:\d{1,2}(?:\.\d{1,2}){1,2}\s+)?(?:(?:Special|Specific) Populations\s+)?(?:Patients with\s+)?"
    r"(Geriatric(?: Use| Patients| Population)?|Elderly|Older Adults|Renal (?:Impairment|Insufficiency|Dysfunction|Failure)|"
    r"Hepatic (?:Impairment|Insufficiency|Dysfunction)|(?:Pediatric|Paediatric) (?:Use|Patients|Population)|Pregnancy|"
    r"Lactation|Nursing Mothers|Gender|Sex|Race|Drug Interactions|Body Weight|Obesity|Absorption|Distribution|Metabolism|"
    r"Elimination|Excretion)\b"
)


def heading_class(s: str) -> tuple[bool, str | None]:
    """(True, class) if a sub-section heading starts the sentence: the population class it opens, None for
    another heading (it closes the class); (False, None) if the sentence has no heading."""
    m = _HEAD.match(s)
    if not m:
        return False, None
    t = m.group(1).lower()
    if t.startswith(("geriatric", "elderly", "older")):
        return True, "geriatric"
    return True, "renal" if t.startswith("renal") else "hepatic" if t.startswith(
        "hepatic"
    ) else None


_COMPARATOR = re.compile(
    r"\b(?:healthy|normal|young|younger|control|controls|matched|without|unimpaired|non-impaired)\b",
    re.I,
)
CONTEXT_SENTENCES = 5  # a heading gives its class to at most this many following sentences


def read_sentence(
    label: SpLabel, section: str, s: str, stats: SpStats, context: str | None = None
) -> list[SpCandidate]:
    pops = [p for p, rx in _POP.items() if rx.search(s)]
    if not pops and context and _COMPARATOR.search(s):
        pops = [
            context
        ]  # a sentence of that population's sub-section that compares with a reference group
    if not pops:
        return []
    if not any(rx.search(s) for rx in _MEASURE.values()):
        return []
    if len(pops) > 1:
        stats.add("a_skip_two_population_classes")
        return []
    pop = pops[0]
    mags = _magnitudes(s)
    if not mags:
        return []
    gm = list(_GRADE.finditer(s))
    if pop == "hepatic" and any(
        m.group(2) for m in gm
    ):  # "moderate (Child-Pugh B)": the class letter decides
        gm = [m for m in gm if m.group(2)]
    grades = [(m.start(), _grade_of(pop, m.group(0))) for m in gm]
    respectively = "respectively" in s.lower()
    measures_in_order: list[str] = []
    for _, name in sorted([(m.start(), n) for n, rx in _MEASURE.items() for m in rx.finditer(s)]):
        if name not in measures_in_order:
            measures_in_order.append(name)
    out: list[SpCandidate] = []
    for i, (pos, ratio, text) in enumerate(mags):
        measures: list[str]
        if (
            len(mags) == len(measures_in_order) > 1
        ):  # "Cmax and AUC were 1.5- and 2.1-fold higher": by order
            measures = [measures_in_order[i]]
        else:
            one, other_quantity = _measure_at(s, pos)
            if one is None:
                stats.add(
                    "a_skip_magnitude_of_another_quantity"
                    if other_quantity
                    else "a_skip_no_measure"
                )
                continue
            measures = [one]
            # "AUC and Cmax were increased by 30 %": one magnitude, two measures named before it
            if len(mags) == 1 and len(measures_in_order) == 2 and not respectively:
                measures = list(measures_in_order)
        if respectively and len(grades) == len(mags) > 1:
            grade = grades[i][1]
        else:
            before = [g for g in grades if g[0] <= pos]
            grade = (before[-1] if before else grades[0])[1] if grades else _grade_of(pop, s)
        for measure in measures:
            out.append(
                SpCandidate(
                    "a",
                    label.drug_key,
                    label.set_id,
                    label.version,
                    section,
                    pop,
                    grade,
                    measure,
                    round(ratio, 4),
                    text,
                    _definition(pop, s),
                    _reference(s),
                    s,
                    _flags(s, label.drug_key),
                )
            )
    return out


# --- tables --------------------------------------------------------------------------------------------------------

_ROW = re.compile(r"<tr\b[^>]*>(.*?)</tr>", re.I | re.S)
_CELL = re.compile(r"<t[dh]\b[^>]*>(.*?)</t[dh]>", re.I | re.S)
_TAG = re.compile(r"<[^>]+>")
_CHANGE = re.compile(r"ratio|fold|change|percent|%|relative", re.I)
_CONC_UNIT = re.compile(
    r"[mnµu]?g\s?/\s?m?[Ll]\b|ng\s?[·*.]\s?h|\bmol", re.I
)  # an absolute concentration or AUC column
_NUMBER = re.compile(r"([+-]?\d+(?:\.\d+)?)")


def _cells(row: str) -> list[str]:
    return [_clean(_TAG.sub(" ", c)) for c in _CELL.findall(row)]


def read_table(label: SpLabel, section: str, html: str, stats: SpStats) -> list[SpCandidate]:
    rows = [_cells(r) for r in _ROW.findall(html)]
    rows = [r for r in rows if r]
    header: list[str] = []
    for r in rows[:3]:
        if sum(1 for c in r if any(rx.search(c) for rx in _MEASURE.values())) >= 1:
            header = r
            break
    if not header:
        return []
    cols: list[tuple[int, str, str]] = []  # column, measure, kind
    for j, c in enumerate(header):
        for name, rx in _MEASURE.items():
            if rx.search(c) and _CHANGE.search(c) and not _CONC_UNIT.search(c):
                kind = (
                    "pct"
                    if re.search(r"%|percent", c, re.I) and not re.search(r"ratio|fold", c, re.I)
                    else "ratio"
                )
                cols.append((j, name, kind))
    out: list[SpCandidate] = []
    for r in rows:
        if r is header or not r:
            continue
        pops = [p for p, rx in _POP.items() if rx.search(r[0])]
        if len(pops) != 1:
            continue
        pop = pops[0]
        for j, name, kind in cols:
            if j >= len(r):
                continue
            m = _NUMBER.search(r[j])
            if not m:
                continue
            v = float(m.group(1))
            ratio = 1 + v / 100 if kind == "pct" else v
            if not RATIO_MIN < ratio <= RATIO_MAX:
                continue
            quote = " | ".join(header) + " || " + " | ".join(r)
            out.append(
                SpCandidate(
                    "a",
                    label.drug_key,
                    label.set_id,
                    label.version,
                    section,
                    pop,
                    _grade_of(pop, r[0]),
                    name,
                    round(ratio, 4),
                    r[j],
                    _definition(pop, r[0]),
                    "",
                    quote,
                    _flags(r[0], label.drug_key),
                    True,
                )
            )
    return out


def read_label(label: SpLabel, stats: SpStats) -> list[SpCandidate]:
    out: list[SpCandidate] = []
    seen: set[tuple[str, str, str, float]] = set()
    for field in SECTION_FIELDS:
        for text in label.sections.get(field, ()):
            context: str | None = "geriatric" if field == "geriatric_use" else None
            since = 0
            for s in sentences(text):
                is_heading, opened = heading_class(s)
                if is_heading:
                    context, since = opened, 0
                since += 1
                keep_context = (
                    context
                    if (field == "geriatric_use" and context == "geriatric")
                    or since <= CONTEXT_SENTENCES
                    else None
                )
                for c in read_sentence(label, field, s, stats, keep_context):
                    k = (c.pop_class, c.grade, c.measure, c.ratio)
                    if k not in seen:
                        seen.add(k)
                        out.append(c)
    for field in TABLE_FIELDS:
        for html in label.tables.get(field, ()):
            for c in read_table(label, field, html, stats):
                k = (c.pop_class, c.grade, c.measure, c.ratio)
                if k not in seen:
                    seen.add(k)
                    out.append(c)
    stats.add("a_candidates", len(out))
    return out
