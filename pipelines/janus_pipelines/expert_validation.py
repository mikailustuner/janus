"""Expert validation round (plan E, measurement B3b): the fixed parts of the pre-registered protocol
`docs/research/expert-validation-protocol.md` that the packet sampler and the scorer share.

Sections, time per item, expert groups, answer scales and columns (protocol sections 2 and 4),
the round-robin assignment with the time cap and the dropping rule (section 5), consensus and
Cohen's kappa with a bootstrap interval (section 6), and the answer files (CSV and XLSX, one per
expert, identified by E01, E02, ...; never a name). Pure functions apart from the file helpers.
Research use only. Not for clinical decisions. Expert review has not yet been done.
"""

from __future__ import annotations

import csv
import math
import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

SEED: Final = 20261113
PROTOCOL: Final = "docs/research/expert-validation-protocol.md"
CAP_MINUTES: Final = 225.0  # 3 h 45 min per expert
GROUPS: Final = ("pharmacologist", "clinician", "pharmacist")
GROUP_LABELS: Final = {
    "pharmacologist": "clinical pharmacologist",
    "clinician": "geriatrician or family physician",
    "pharmacist": "clinical pharmacist",
}
SECTIONS: Final = ("A1", "A2", "B", "C1", "C2", "D", "E", "F")
MINUTES: Final = {
    "A1": 1.0,
    "A2": 0.5,
    "B": 2.0,
    "C1": 1.0,
    "C2": 8.0,
    "D": 2.5,
    "E": 0.5,
    "F": 3.0,
}
SECTION_GROUPS: Final = {
    "A1": ("clinician", "pharmacist"),
    "A2": ("clinician", "pharmacist"),
    "B": ("clinician", "pharmacist"),
    "C1": ("pharmacologist",),
    "C2": ("pharmacologist",),
    "D": ("pharmacologist",),
    "E": ("pharmacist",),
    "F": ("pharmacologist",),
}
PER_EXPERT_LIMIT: Final = {"C2": 6}  # documents per expert (protocol section 4)
EXPERTS_PER_ITEM: Final = 2
LANGUAGES: Final = ("en", "tr")

SCALE: Final = ("1", "2", "3", "4", "5")
PK_PARAMETERS: Final = (
    "cmax", "auc_inf", "auc_last", "auc_tau", "tmax", "t_half", "cl", "cl_f", "cl_per_kg",
    "v", "v_f", "vss", "vd", "vd_per_kg", "ka", "f", "other",
)  # fmt: skip
DOSE_FORM_GROUPS: Final = (
    "oral_solid", "oral_solid_delayed_release", "oral_solid_prolonged_release", "oral_liquid",
    "injection", "inhaled", "nasal", "ophthalmic", "otic", "cutaneous", "transdermal", "rectal",
    "vaginal", "other", "no_group",
)  # fmt: skip


@dataclass(frozen=True)
class Field:
    """One answer column. kind: scale (1-5), choice (fixed list), number or text."""

    name: str
    kind: str
    choices: tuple[str, ...] = ()
    judged: bool = False  # enters consensus and kappa


FIELDS: Final[dict[str, tuple[Field, ...]]] = {
    "A1": (Field("realistic", "scale", SCALE, True), Field("comment", "text")),
    "A2": (
        Field("describes_class", "choice", ("yes", "no", "unsure"), True),
        Field("comment", "text"),
    ),
    "B": (
        Field("accuracy", "scale", SCALE, True),
        Field("harm", "scale", SCALE, True),
        Field("clarity", "scale", SCALE, True),
        Field("suggested_wording", "text"),
    ),
    "C1": (
        Field("verdict", "choice", ("correct", "incorrect", "cannot_judge"), True),
        Field(
            "error",
            "choice",
            ("value", "unit", "parameter", "drug_or_analyte", "population", "other"),
        ),
        Field("corrected_value", "text"),
        Field("comment", "text"),
    ),
    "C2": (
        Field("drug", "text"),
        Field("parameter", "choice", PK_PARAMETERS),
        Field("value", "number"),
        Field("unit", "text"),
        Field("population", "text"),
        Field("comment", "text"),
    ),
    "D": (
        Field("says_label", "choice", ("yes", "no"), True),
        Field("direction", "choice", ("yes", "no"), True),
        Field("comment", "text"),
    ),
    "E": (
        Field("decision", "choice", ("accept", "reject", "unsure"), True),
        Field("correct_group", "choice", DOSE_FORM_GROUPS),
        Field("comment", "text"),
    ),
    "F": (
        Field("method_sound", "choice", ("yes", "no"), True),
        Field("status_justified", "choice", ("yes", "no"), True),
        Field("unsound_parameters", "text"),
        Field("comment", "text"),
    ),
}
BASE_COLUMNS: Final = ("expert_id", "section", "item_id", "item")
C2_ROWS_PER_DOCUMENT: Final = 25  # blank rows offered per document in the XLSX file


def fields_of(section: str) -> tuple[Field, ...]:
    return FIELDS[section]


def columns_for(sections: Sequence[str]) -> list[str]:
    """CSV columns of an answer file that holds these sections (union, fixed order)."""
    out: list[str] = list(BASE_COLUMNS)
    for s in SECTIONS:
        if s in sections:
            out += [f.name for f in FIELDS[s] if f.name not in out]
    return out


# ---------------------------------------------------------------- experts and assignment


@dataclass(frozen=True)
class Expert:
    id: str
    group: str
    languages: frozenset[str] = frozenset(LANGUAGES)


def make_experts(
    counts: Mapping[str, int], languages: Mapping[str, frozenset[str]] | None = None
) -> list[Expert]:
    """E01, E02, ... numbered group by group in the order of GROUPS."""
    out: list[Expert] = []
    for g in GROUPS:
        n = counts.get(g, 0)
        if n < 0:
            raise ValueError(f"{g}: number of experts must be >= 0")
        for _ in range(n):
            eid = f"E{len(out) + 1:02d}"
            langs = (languages or {}).get(eid, frozenset(LANGUAGES))
            if not langs or not langs <= frozenset(LANGUAGES):
                raise ValueError(f"{eid}: languages must be a non-empty subset of {LANGUAGES}")
            out.append(Expert(eid, g, langs))
    unknown = set(languages or {}) - {e.id for e in out}
    if unknown:
        raise ValueError(f"languages given for unknown experts: {sorted(unknown)}")
    return out


def eligible(experts: Sequence[Expert], section: str) -> list[Expert]:
    """Experts of the section's groups in round-robin order: groups interleaved (first expert of
    each group, then the second of each, ...), so a pair of a shared section mixes the groups."""
    by = [[e for e in experts if e.group == g] for g in SECTION_GROUPS[section]]
    out: list[Expert] = []
    for i in range(max((len(b) for b in by), default=0)):
        out += [b[i] for b in by if i < len(b)]
    return out


@dataclass
class Assignment:
    assigned: dict[str, dict[str, list[str]]] = field(
        default_factory=dict[str, dict[str, list[str]]]
    )
    dropped: dict[str, list[str]] = field(default_factory=dict[str, list[str]])
    minutes: dict[str, float] = field(default_factory=dict[str, float])


def assign(
    sections: Mapping[str, Sequence[tuple[str, str | None]]],
    experts: Sequence[Expert],
    cap: float = CAP_MINUTES,
) -> Assignment:
    """Protocol section 5. `sections` maps a section to its items in the fixed random order, each
    (item id, language or None). Sections are filled in protocol order; inside a section each item
    goes to the next two experts of the round robin who read its language, have time left under
    the cap and are under the section limit (C2: 6 documents). An item that cannot get two experts
    is dropped; because items are taken in order, dropped items are the end of the order."""
    res = Assignment(minutes={e.id: 0.0 for e in experts})
    for s in SECTIONS:
        if s not in sections:
            continue
        pool = eligible(experts, s)
        taken: dict[str, int] = {e.id: 0 for e in pool}
        res.assigned[s] = {}
        res.dropped[s] = []
        ptr = 0
        for item_id, lang in sections[s]:
            chosen: list[int] = []
            for step in range(len(pool)):
                j = (ptr + step) % len(pool)
                e = pool[j]
                if lang is not None and lang not in e.languages:
                    continue
                if res.minutes[e.id] + MINUTES[s] > cap + 1e-9:
                    continue
                if taken[e.id] >= PER_EXPERT_LIMIT.get(s, math.inf):
                    continue
                chosen.append(j)
                if len(chosen) == EXPERTS_PER_ITEM:
                    break
            if len(chosen) < EXPERTS_PER_ITEM:
                res.dropped[s].append(item_id)
                continue
            ids = [pool[j].id for j in chosen]
            for eid in ids:
                res.minutes[eid] += MINUTES[s]
                taken[eid] += 1
            res.assigned[s][item_id] = ids
            ptr = (chosen[-1] + 1) % len(pool)
    return res


# ---------------------------------------------------------------- consensus and agreement


def bucket(kind: str, value: str) -> str:
    """Category used for consensus: on 1-5 scales high (>= 4), low (<= 2) or mid (3)."""
    if kind != "scale":
        return value
    v = int(value)
    return "high" if v >= 4 else "low" if v <= 2 else "mid"


def consensus(answers: Sequence[str], kind: str) -> tuple[str, str | None]:
    """Protocol section 6. `answers` are the non-blank answers in order: the two assigned experts
    first, then a third expert. The first two agree (same category; on 1-5 scales both >= 4 or both
    <= 2) -> ("agreed", category). Otherwise a third answer decides -> ("third", its category);
    a third answer of 3 on a 1-5 scale decides nothing. Else ("not_settled", None)."""
    cats = [bucket(kind, a) for a in answers if a != ""]
    if len(cats) >= 2 and cats[0] == cats[1] and cats[0] != "mid":
        return "agreed", cats[0]
    if len(cats) >= 3 and cats[2] != "mid":
        return "third", cats[2]
    return "not_settled", None


def kappa(
    pairs: Sequence[tuple[str, str]], categories: Sequence[str], weighted: bool = False
) -> float | None:
    """Cohen's kappa of two raters; quadratic weights over the ordered categories when
    `weighted` (the 1-5 scales). None when undefined (no pair, or chance agreement is 1)."""
    n = len(pairs)
    k = len(categories)
    if n == 0 or k < 2:
        return None
    idx = {c: i for i, c in enumerate(categories)}

    def w(i: int, j: int) -> float:
        if weighted:
            return 1 - ((i - j) / (k - 1)) ** 2
        return 1.0 if i == j else 0.0

    pa = [0.0] * k
    pb = [0.0] * k
    po = 0.0
    for a, b in pairs:
        i, j = idx[a], idx[b]
        pa[i] += 1 / n
        pb[j] += 1 / n
        po += w(i, j) / n
    pe = sum(w(i, j) * pa[i] * pb[j] for i in range(k) for j in range(k))
    if pe >= 1 - 1e-12:
        return None
    return (po - pe) / (1 - pe)


def kappa_interval(
    pairs: Sequence[tuple[str, str]],
    categories: Sequence[str],
    weighted: bool = False,
    resamples: int = 2000,
    seed: int = SEED,
) -> tuple[float, float] | None:
    """Percentile 95 % interval of kappa when the items are resampled with replacement."""
    if len(pairs) < 2:
        return None
    rnd = random.Random(seed)  # noqa: S311 - resampling, not cryptography
    stats: list[float] = []
    for _ in range(resamples):
        draw = [pairs[rnd.randrange(len(pairs))] for _ in pairs]
        kv = kappa(draw, categories, weighted)
        if kv is not None:
            stats.append(kv)
    if len(stats) < resamples / 2:
        return None
    stats.sort()
    return stats[math.floor(0.025 * (len(stats) - 1))], stats[math.ceil(0.975 * (len(stats) - 1))]


# ---------------------------------------------------------------- answer files


def check_value(f: Field, value: str, where: str) -> str:
    """Normalised answer, or ValueError naming the file and row."""
    v = value.strip()
    if v == "" or f.kind == "text":
        return v
    if f.kind == "number":
        try:
            x = float(v.replace(",", "."))
        except ValueError:
            raise ValueError(f"{where}: {f.name} must be a number, got {v!r}") from None
        if not math.isfinite(x):
            raise ValueError(f"{where}: {f.name} must be a finite number")
        return repr(x)
    if f.kind == "scale" and v.endswith(".0"):
        v = v[:-2]  # a spreadsheet may store 4 as 4.0
    v = v.lower().replace(" ", "_").replace("-", "_") if f.kind == "choice" else v
    if v not in f.choices:
        raise ValueError(f"{where}: {f.name} must be one of {', '.join(f.choices)}; got {value!r}")
    return v


def write_csv(path: Path, rows: Sequence[Mapping[str, str]], columns: Sequence[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(columns), extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in columns})


def write_xlsx(path: Path, expert_id: str, rows: Sequence[Mapping[str, str]], note: str) -> None:
    """One sheet per section with drop-down lists for every scale and choice column; C2 offers
    blank rows per document for the values the expert marks."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.datavalidation import DataValidation

    wb = Workbook()
    info = wb.active
    assert info is not None  # noqa: S101 - a new workbook has a sheet
    info.title = "read_me"
    for line in [f"expert_id: {expert_id}", *note.splitlines()]:
        info.append([line])
    info.column_dimensions["A"].width = 120
    head_fill = PatternFill("solid", fgColor="E6F1F3")
    for s in SECTIONS:
        mine = [r for r in rows if r["section"] == s]
        if not mine:
            continue
        ws = wb.create_sheet(s)
        cols = ["expert_id", "item_id", "item", *[f.name for f in FIELDS[s]]]
        ws.append(cols)
        for c in ws[1]:
            c.font = Font(bold=True)
            c.fill = head_fill
        for r in mine:
            for _ in range(C2_ROWS_PER_DOCUMENT if s == "C2" else 1):
                ws.append([r.get(c, "") for c in cols])
        last = ws.max_row
        for i, f in enumerate(FIELDS[s], start=4):
            letter = get_column_letter(i)
            ws.column_dimensions[letter].width = 34 if f.kind == "text" else 16
            if f.choices:
                dv = DataValidation(
                    type="list", formula1='"' + ",".join(f.choices) + '"', allow_blank=True,
                    showErrorMessage=True, errorTitle="Janus", error="Choose a value of the list.",
                )  # fmt: skip
                ws.add_data_validation(dv)
                dv.add(f"{letter}2:{letter}{last}")  # pyright: ignore[reportUnknownMemberType]
            if f.kind == "number":
                dv = DataValidation(type="decimal", operator="greaterThanOrEqual", formula1="0",
                                    allow_blank=True, showErrorMessage=True)  # fmt: skip
                ws.add_data_validation(dv)
                dv.add(f"{letter}2:{letter}{last}")  # pyright: ignore[reportUnknownMemberType]
        ws.column_dimensions["A"].width = 10
        ws.column_dimensions["B"].width = 10
        ws.column_dimensions["C"].width = 60
        for row in ws.iter_rows(min_row=2, max_col=3):
            for c in row:
                c.alignment = Alignment(wrap_text=True, vertical="top")
        ws.freeze_panes = "D2"
    wb.save(path)


def read_answer_file(path: Path) -> list[dict[str, str]]:
    """Rows of a filled answer file (CSV, or XLSX made by write_xlsx) as strings, each with
    expert_id, section, item_id and the answer columns. Values are not checked here."""
    if path.suffix.lower() == ".xlsx":
        from openpyxl import load_workbook

        wb = load_workbook(path, read_only=True, data_only=True)
        out: list[dict[str, str]] = []
        for s in SECTIONS:
            if s not in wb.sheetnames:
                continue
            it = wb[s].iter_rows(values_only=True)
            head = [str(h) if h is not None else "" for h in next(it, ())]
            for vals in it:
                r = {
                    h: "" if v is None else str(v)
                    for h, v in zip(head, vals, strict=False)
                    if h
                }  # fmt: skip
                if any(r.values()):
                    r["section"] = s
                    out.append(r)
        return out
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return [dict(r) for r in csv.DictReader(fh)]
