"""Strict publication check for confirmed special-population label statements (selective prediction).

Runs after the two label readers agree. It reads only the quote and the claimed class, grade and
measure, never the readers' code, and abstains when the quote is not a plain single statement: more
than one magnitude (per-grade lists, ranges, several measures, day-specific values), another PK
quantity next to the number (clearance, half-life, Tmax ...), a metabolite, company code or
enantiomer, more than one severity grade or population class, a sex comparison, a negation, or a
quote that does not name the drug or names another pool drug. Each rule has a code; `level` maps them
to the pre-registered levels. Research use only. Not for clinical decisions.
"""

from __future__ import annotations

import re
from typing import Final

from janus_pipelines.modelkit import sp_c
from janus_pipelines.modelkit.resolver import IdentityTable, norm

# On the raw quote (case matters for codes such as "M-II", "SN-38").
_MAGNITUDE: Final = re.compile(
    r"\d+(?:[.,]\d+)?\s*(?:%|percent|-?\s*fold|\s*times)|\bratio\b[^.;]{0,30}?\d|\b(?:doubled|tripled|halved)\b",
    re.I,
)
_CODE: Final = re.compile(r"\b(?:M-?[IVX]+|M\d{1,2}|[A-Z]{2,5}-?\d{2,6})\b")
_ANALYTE: Final = re.compile(
    r"metabolite|phosphate\b|glucuronide|hydroxy|desmethyl|enantiomer|racem|\bunbound\b|\bfree\b|\btotal\b"
    r"|\b[RS]-[a-z]|\(\s*[RS+-]\s*\)",
    re.I,
)
_OTHER_QUANTITY: Final = re.compile(
    r"clearance|\bCL\b|\bCL\s*/\s*F\b|\bCLR?\b|half-?\s*life|t\s*½|t\s*1/2|\bT\s*max\b|\btmax\b|volume of distribution"
    r"|\bV[dz]?\b|mean residence|\bMRT\b|\bC\s*min\b|trough|protein binding|fraction|elimination rate|urinary|excretion",
    re.I,
)
_CRCL: Final = re.compile(r"creatinine clearance|\bCL\s*cr\b|\bCrCl\b|\bCLCR\b", re.I)
_GRADES: Final = {
    "mild": re.compile(r"\bmild(?:ly)?\b|childs?[- ]pugh (?:class )?a\b|\bclass a\b", re.I),
    "moderate": re.compile(r"\bmoderate(?:ly)?\b|childs?[- ]pugh (?:class )?b\b|\bclass b\b", re.I),
    "severe": re.compile(r"\bsevere(?:ly)?\b|childs?[- ]pugh (?:class )?c\b|\bclass c\b", re.I),
    "esrd": re.compile(r"end[- ]stage|\besrd\b|dialysis|hemodialysis", re.I),
}
_CLASSES: Final = {
    "geriatric": re.compile(
        r"elderly|older|geriatric|aged? (?:65|70|75)|\b(?:65|70|75) years", re.I
    ),
    "renal": re.compile(r"renal|kidney|creatinine clearance|egfr|dialysis", re.I),
    "hepatic": re.compile(r"hepatic|liver|childs?[- ]pugh|cirrho", re.I),
}
_SEX: Final = re.compile(r"\b(?:female|male|women|men|sex|gender)\b", re.I)
_NEGATION: Final = re.compile(
    r"\bno (?:clinically |significant |relevant |meaningful )*(?:effect|change|difference|increase)|unchanged|"
    r"\bsimilar\b|not (?:significantly |substantially )?(?:affected|altered|changed|different)|comparable",
    re.I,
)
_RANGE: Final = re.compile(
    r"\d+(?:\.\d+)?\s*%?\s*-?\s*(?:-|to|\u2013|and)\s*\d+(?:\.\d+)?\s*(?:%|-?\s*fold|\s*times)",
    re.I,
)
_MEASURE: Final = {
    "auc": re.compile(r"\bAUC|exposure|area under", re.I),
    "cmax": re.compile(
        r"\bC\s*max|peak (?:plasma )?concentration|maximum (?:plasma )?concentration", re.I
    ),
}
# Iteration 2 (after the first fresh sample): modelled or dose-adjusted comparisons, bounds, dialysis
# timing, dosing-interval and cross-study comparisons.
_DOSE_OR_MODEL: Final = re.compile(
    r"dose (?:adjust|reduc)|dosing (?:was|were) reduced|reduced dose|modell?ing|simulat|predict|"
    r"every \d+ ?(?:hours|h)\b|dosing interval",
    re.I,
)
_BOUND: Final = re.compile(
    r"\b(?:at least|up to|more than|less than|as much as|in excess of)\s+(?:approximately |about )?\d",
    re.I,
)
_DIALYSIS: Final = re.compile(r"dialysis|\bHD\b|\bCRRT\b|hemofiltration", re.I)
_CROSS_STUDY: Final = re.compile(r"other stud|previous stud|historical|cross[- ]study", re.I)
_DAY: Final = re.compile(r"\bday \d", re.I)
_DOSE_NORM: Final = re.compile(r"dose[- ]normali[sz]ed|weight[- ]normali[sz]ed|normali[sz]ed", re.I)

LEVELS: Final = {
    1: frozenset({"analyte_word", "company_code", "other_drug_named", "sex_comparison", "dose_or_model", "bound_value", "dialysis_context", "cross_study"}),
    2: frozenset({"several_magnitudes", "measure_not_nearest", "range_value", "other_quantity", "several_grades", "several_classes", "negation", "day_specific"}),
    3: frozenset({"drug_not_named", "normalised_value"}),
}  # fmt: skip


def _value_of(m: re.Match[str]) -> float | None:
    """The ratio a magnitude expression states (convention of the readers: % higher -> 1 + x/100)."""
    t = m.group(0).lower()
    num = re.match(r"\d+(?:[.,]\d+)?", t)
    if num is None:
        return {"doubled": 2.0, "tripled": 3.0, "halved": 0.5}.get(t.strip())
    x = float(num.group(0).replace(",", "."))
    return x if ("fold" in t or "times" in t) else None


def aligned(quote: str, measure: str, ratio: float) -> bool:
    """Exactly one magnitude follows the claimed measure word with no other measure word, magnitude
    or 'respectively' between them, and for fold/times expressions it states the claimed ratio (an
    increase or decrease word decides the direction of a percentage, which the readers already did)."""
    if re.search(r"respectively", quote, re.I):
        return False
    own = _MEASURE[measure]
    other = _MEASURE["cmax" if measure == "auc" else "auc"]
    mags = list(_MAGNITUDE.finditer(quote))
    hits = 0
    for m in mags:
        before = quote[max(0, m.start() - 80) : m.start()]
        last_own = max((x.end() for x in own.finditer(before)), default=-1)
        last_other = max((x.end() for x in other.finditer(before)), default=-1)
        prev_mag = any(
            x.end() <= m.start() and x.end() > m.start() - 80 + last_own for x in mags if x is not m
        )
        if last_own > last_other and not prev_mag:
            v = _value_of(m)
            if (
                v is None
                or abs(v - ratio) <= 0.01 * max(v, ratio)
                or abs(1 / v - ratio) <= 0.01 * ratio
            ):
                hits += 1
    return hits == 1


def _nearest_is(quote: str, measure: str) -> bool:
    """With one magnitude: the measure word nearest before it is the claimed one, or both measures are
    named together ("C max and AUC are each 4-fold")."""
    m = _MAGNITUDE.search(quote)
    if m is None:
        return False
    before = quote[: m.start()]
    hits = sorted((x.end(), k) for k, rx in _MEASURE.items() for x in rx.finditer(before))
    if not hits:
        return False
    if len(hits) >= 2 and hits[-1][1] != hits[-2][1] and hits[-1][0] - hits[-2][0] < 30:
        return True
    return hits[-1][1] == measure


def check(
    quote: str,
    drug_key: str,
    pop_class: str,
    table: IdentityTable,
    measure: str = "",
    ratio: float = 0.0,
    grade: str = "",
) -> tuple[str, ...]:
    """Codes of the strict rules this confirmed statement fails (empty = passes every level)."""
    fails: list[str] = []
    if _ANALYTE.search(quote):
        fails.append("analyte_word")
    if _CODE.search(quote):
        fails.append("company_code")
    named = table.drugs_in(quote)
    if any(k != drug_key for k in named):
        fails.append("other_drug_named")
    if _SEX.search(quote):
        fails.append("sex_comparison")
    n_mag = len(_MAGNITUDE.findall(quote))
    c_agrees = bool(measure) and sp_c.agrees(quote, measure, grade, ratio)
    if n_mag != 1 and not c_agrees:
        fails.append("several_magnitudes")
    if n_mag == 1 and measure and not c_agrees and not _nearest_is(quote, measure):
        fails.append("measure_not_nearest")
    if _DOSE_OR_MODEL.search(quote):
        fails.append("dose_or_model")
    if _BOUND.search(quote):
        fails.append("bound_value")
    if _DIALYSIS.search(quote) and grade not in ("esrd", "dialysis"):
        fails.append("dialysis_context")
    if _CROSS_STUDY.search(quote):
        fails.append("cross_study")
    if _RANGE.search(quote):
        fails.append("range_value")
    if _OTHER_QUANTITY.search(_CRCL.sub(" ", quote)):
        fails.append("other_quantity")
    if sum(1 for rx in _GRADES.values() if rx.search(quote)) > 1 and not c_agrees:
        fails.append("several_grades")
    if any(rx.search(quote) for c, rx in _CLASSES.items() if c != pop_class):
        fails.append("several_classes")
    if _NEGATION.search(quote):
        fails.append("negation")
    if _DAY.search(quote):
        fails.append("day_specific")
    if norm(drug_key) not in norm(
        quote
    ):  # the drug's own name, not an alias (quinine is not quinidine)
        fails.append("drug_not_named")
    if _DOSE_NORM.search(quote):
        fails.append("normalised_value")
    return tuple(fails)


def level(fails: tuple[str, ...]) -> int:
    """Highest pre-registered level whose rules (and those of all lower levels) the statement passes."""
    got = 0
    for lv in sorted(LEVELS):
        if any(f in LEVELS[lv] for f in fails):
            break
        got = lv
    return got
