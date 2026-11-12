"""Reader B for review PDFs and PMC tables (spec model-kit, milestone M5): structure first,
independent of reader A.

FDA reviews: a table is a block of layout lines with numeric fields; the columns are the merged
character intervals of the numeric fields; every header line above the block is split into fields
that are assigned to the columns they overlap (a spanning header goes to every column it covers); a
column whose header is only a dispersion word (CV, SD, %) is a dispersion column and never a value.
Parameter and unit come from the tokens of the row label (or, for a transposed table, of the column
header), by the unit's dimension and the parameter words. Study: a code token next to study,
protocol, trial or report in the table's title or footnote lines, else in the nearest earlier
heading line. PMC: the JATS grid with the same token rules. Dose only from the column header, the
title or caption, the footnotes, or the study's design text (review section, article methods).
Shares only reference data with reader A (identity table, unit table, value types). Research use
only. Not for clinical decisions."""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Final

from janus_pipelines.modelkit.confirm import Context
from janus_pipelines.modelkit.formref import BrandTable, Resolution, decide
from janus_pipelines.modelkit.formulation_b import _evidence, _Names, _tok  # pyright: ignore[reportPrivateUsage]
from janus_pipelines.modelkit.model import Candidate, ReaderStats
from janus_pipelines.modelkit.pmc_jats import Article
from janus_pipelines.modelkit.reader_b import (
    _classify,  # pyright: ignore[reportPrivateUsage]
    _dose_beside_name,  # pyright: ignore[reportPrivateUsage]
    _doses_in,  # pyright: ignore[reportPrivateUsage]
    _family,  # pyright: ignore[reportPrivateUsage]
    _lex,  # pyright: ignore[reportPrivateUsage]
    _read_unit,  # pyright: ignore[reportPrivateUsage]
    _regimen,  # pyright: ignore[reportPrivateUsage]
    _route,  # pyright: ignore[reportPrivateUsage]
    _tokens,  # pyright: ignore[reportPrivateUsage]
    _word_before,  # pyright: ignore[reportPrivateUsage]
)
from janus_pipelines.modelkit.resolver import PARTNERS, IdentityTable
from janus_pipelines.modelkit.review_text import Page, is_heading
from janus_pipelines.modelkit.units import Center, Refused, Stat, resolve_parameter, to_canonical

_FIELD: Final = re.compile(r"\S(?:.*?\S)?(?=\s{2,}|\s*$)")
_LEAD_NUM: Final = re.compile(r"^[<>~]?\s*(\d[\d,]*(?:\.\d+)?)")
_DISP_TOKENS: Final = frozenset(
    "cv cvw c v sd se sem std dev deviation error min max minimum maximum range ci iqr p pvalue power n no "
    "number count rse rsd inter intra subject subjects variability between within".split()
)
_BAD_TOKENS: Final = frozenset(
    "ratio ratios gmr ci confidence fold difference change predicted simulated simulation model gls ls lsm "
    "statistics statistical anova".split()
)
_STUDY_WORDS: Final = frozenset("study studies protocol trial report csr".split())
_DOSING_TOKENS: Final = frozenset("received administered given dosed took".split())
_DESIGN_TOKENS: Final = frozenset(
    "dose doses dosed administered received given treatment design single regimen".split()
)


def _fields(line: str) -> list[tuple[int, int, str]]:
    return [(m.start(), m.end(), m.group(0)) for m in _FIELD.finditer(line)]


def _spread_words(text: str) -> bool:
    """Only dispersion, bound, count or test words (SD, CV, min, max, n, p ...), no other word."""
    if "=" in text:  # 'n = 12' annotates an arm, it is not a count column
        return False
    words = {t for t in _tokens(text) if not t.isdigit()}
    return bool(words) and words <= _DISP_TOKENS


def _numeric(text: str) -> float | None:
    """The leading number of a field whose other tokens are only dispersion marks; None otherwise."""
    t = text.strip()
    m = _LEAD_NUM.match(t)
    if m is None:
        return None
    rest = t[m.end() :].strip()
    if rest and not re.fullmatch(
        r"(?:±|\+/-|\+)?\s*\(?\s*[\d.,]+\s*%?\s*\)?(?:\s*\(\s*[\d.,]+\s*%?\s*\))?(?:\s*\[[^\]]*\])?",
        rest,
    ):
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


def _code_tokens(text: str) -> str | None:
    """A study code: a token of at least 5 letters and digits with at least 2 digits, within three
    tokens after a study word."""
    toks = re.findall(r"[A-Za-z0-9][A-Za-z0-9\-_./]*", text)
    for i, t in enumerate(toks):
        if t.lower() not in _STUDY_WORDS:
            continue
        for cand in toks[i + 1 : i + 4]:
            code = re.sub(r"[^A-Z0-9]", "", cand.upper())
            if (
                len(code) >= 5
                and sum(ch.isdigit() for ch in code) >= 2
                and cand.lower() not in _STUDY_WORDS
            ):
                return code
    return None


def _center(toks: set[str]) -> Center:
    return (
        "geometric"
        if "geometric" in toks
        else "median"
        if "median" in toks
        else "arithmetic"
        if "mean" in toks
        else "unspecified"
    )


def _others(text: str, drug_key: str, table: IdentityTable) -> str | None:
    """Another active drug named in the text (pool drugs and known partners), else None."""
    toks = set(_tokens(text))
    own = {w for n in table.by_key[drug_key].names for w in _tokens(n)}
    named = [k for k in table.drugs_in(text) if k != drug_key]
    named += [p for p in PARTNERS if p in toks and p not in own]
    return ", ".join(sorted(set(named))) or None


def _context(
    head_toks: set[str], all_toks: set[str], joined: str, coadmin: str | None = None
) -> Context:
    form = (
        "modified_release"
        if {"extended", "modified", "sustained", "prolonged", "delayed", "controlled"} & all_toks
        else "solution"
        if {"solution", "suspension", "syrup"} & all_toks
        else "immediate_release"
        if {"tablet", "tablets", "capsule", "capsules"} & all_toks
        else "unspecified"
    )
    route = _route(all_toks)
    pop = (
        "special"
        if {
            "children",
            "pediatric",
            "paediatric",
            "elderly",
            "renal",
            "hepatic",
            "impairment",
            "infants",
            "adolescents",
        }
        & all_toks
        else "healthy_adult"
        if "healthy" in all_toks
        else "patients"
        if "patients" in all_toks
        else "unspecified"
    )
    food = (
        "fed"
        if {"fed", "meal", "breakfast"} & head_toks
        else "fasted"
        if {"fasted", "fasting"} & head_toks
        else "unspecified"
    )
    sex = (
        "female"
        if {"female", "females", "women"} & head_toks and not {"male", "males", "men"} & head_toks
        else (
            "male"
            if {"male", "males", "men"} & head_toks
            and not {"female", "females", "women"} & head_toks
            else "all"
        )
    )
    arm = next((t for t in ("test", "reference", "crossover") if t in head_toks), None)
    species = (
        "animal"
        if {
            "rat",
            "rats",
            "dog",
            "dogs",
            "monkey",
            "monkeys",
            "mouse",
            "mice",
            "rabbit",
            "rabbits",
            "horse",
        }
        & all_toks
        else "human"
    )
    return Context(
        arm,
        coadmin,
        "other_route" if route == "other" else form,
        food,
        pop,
        sex,
        species,
        route,
        _regimen(all_toks, joined),
    )


def _normalised(unit: str, label: str) -> bool:
    """A dose- or weight-normalised quantity (a mass of drug in the denominator, '/D', 'DN'), not a
    value."""
    ut = _tokens(unit)
    lt = set(_tokens(re.sub(r"\(.*?\)", " ", label)))
    return (
        ("mg" in ut and ("kg" in ut or unit.find("mg") > unit.find("/") >= 0))
        or bool(lt & {"dn", "dw", "dose"})
        or bool(re.search(r"/\s*D\b", label))
    )


_SKIP_TOKENS: Final = frozenset(
    "model estimate estimates simulation simulated simulations toxicokinetic toxicokinetics radioactivity "
    "radiolabeled elderly geriatric pediatric paediatric children adolescents adolescent infants infant impairment "
    "impaired insufficiency rat rats dog dogs monkey monkeys mouse mice rabbit rabbits minipig minipigs animal "
    "animals".split()
)


def _skip(text: str) -> bool:
    """Iteration 2 (M5): a table of a model, a simulation, an animal or radioactivity study, or of a special
    population, is not read."""
    toks = set(_tokens(text))
    return bool(toks & _SKIP_TOKENS) or ("population" in toks and "pharmacokinetic" in toks)


def _moiety_title(title: str) -> bool:
    """The title names a metabolite or a code token (letters then at least three digits, or M and a number)."""
    bare = re.sub(r"(?i)\b(?:study|studies|protocol|trial|report|table)\s+\S+", " ", title)
    toks = _tokens(bare)
    return any(
        t.startswith("metabolit")
        or re.fullmatch(r"m\d{1,2}", t)
        or re.fullmatch(r"[a-z]{1,5}\d{3,}[a-z]?", t)
        for t in toks
    ) or bool(re.search(r"\b[A-Za-z]{1,5}-\d{3,}", bare))


def _counts(cell: str, column: list[str]) -> bool:
    """An integer that repeats in another row of the same column: a number of subjects."""
    c = cell.strip()
    return bool(re.fullmatch(r"\d{1,4}", c)) and column.count(c) > 1


def _foreign_table(title: str, drug_key: str, table: IdentityTable) -> bool:
    named = set(table.drugs_in(title))
    return bool(named) and drug_key not in named


def _unit_param(label: str) -> tuple[str, str] | None:
    """(parameter, unit) from a label's bracketed unit and its words, else None."""
    for br in re.findall(r"\(([^()]*)\)", label):
        toks = _lex(br)
        ru = _read_unit(toks, 0)
        if ru is None or ru[1] != len(toks):
            continue
        fam = _family(ru[0])
        words = _lex(re.sub(r"\(.*?\)", " ", label))
        p = _word_before(words, len(words), fam) if fam else None
        if p:
            return p, ru[0]
    if "," in label:
        head, tail = label.rsplit(",", 1)
        toks = _lex(tail)
        ru = _read_unit(toks, 0)
        if ru is not None and ru[1] == len(toks):
            fam = _family(ru[0])
            words = _lex(head)
            p = _word_before(words, len(words), fam) if fam else None
            if p:
                return p, ru[0]
    return None


def _layers(layers: Sequence[str], names: _Names) -> Resolution:
    """Formulation and route from text layers with the M3 resolver B's token evidence and the shared
    rule (layer order, a conflict stops, a bare tablet word only as the last resort)."""
    found: list[Resolution] = []
    routes_seen: list[str] = []
    for text in layers:
        toks = _tok(text)
        if not toks:
            continue
        cls, routes = _evidence(toks, names.brand_hits(toks))
        if len(routes) == 1:
            routes_seen.append(next(iter(routes)))
        res = decide(frozenset(cls), frozenset(routes))
        if res.why.startswith("conflict"):
            return res
        found.append(res)
    fallback_route = routes_seen[0] if routes_seen else "unknown"
    for res in found:
        if res.why not in ("ir_weak", ""):
            route = (
                res.route
                if res.route != "unknown" or res.formulation == "other_route"
                else fallback_route
            )
            return Resolution(res.formulation, route, res.why)
    for res in found:
        if res.why == "ir_weak":
            return Resolution(
                res.formulation, res.route if res.route != "unknown" else fallback_route, res.why
            )
    return Resolution("unspecified", fallback_route, "")


def _with_form(ctx: Context, res: Resolution) -> Context:
    route = (
        "unknown" if res.why == "conflict:iv_and_oral"
        else "other" if res.formulation == "other_route"
        else res.route if res.route != "unknown" else ctx.route
    )  # fmt: skip
    return Context(
        ctx.arm,
        ctx.coadministered,
        res.formulation,
        ctx.food,
        ctx.population,
        ctx.sex,
        ctx.species,
        route,
        ctx.regimen,
    )


def _dose(sources: Sequence[str], own: set[str]) -> float | None:
    for src in sources:
        if not src:
            continue
        d = _dose_beside_name(src, own)
        if d is None:
            ds = {x for _, x in _doses_in(_tokens(src))}
            d = next(iter(ds)) if len(ds) == 1 else None
        if d is not None:
            return d
    return None


def read_review(
    pages: Sequence[Page], doc: object, table: IdentityTable, brands: BrandTable, stats: ReaderStats
) -> list[Candidate]:
    """`doc` is a review document record with drug_key, appl_no, url, file, version (duck typed: B
    imports nothing from reader A)."""
    drug_key: str = getattr(doc, "drug_key")  # noqa: B009
    appl: str = getattr(doc, "appl_no")  # noqa: B009
    url: str = getattr(doc, "url")  # noqa: B009
    file: str = getattr(doc, "file")  # noqa: B009
    version: str = getattr(doc, "version")  # noqa: B009
    own = set(table.by_key[drug_key].names | table.by_key[drug_key].codes)
    names = _Names(drug_key, table, brands)
    lines: list[tuple[int, int, str, bool]] = []
    for p in pages:
        if p.text_page:
            lines += [
                (p.number, i, t, r)
                for i, (t, r) in enumerate(zip(p.lines, p.readable, strict=True))
            ]

    def is_data(t: str) -> bool:
        fs = _fields(t)
        return (
            len(fs) >= 2
            and _numeric(fs[0][2]) is None
            and any(_numeric(f[2]) is not None for f in fs[1:])
        )

    out: list[Candidate] = []
    k = 0
    while k < len(lines):
        if not (lines[k][3] and is_data(lines[k][2])):
            k += 1
            continue
        first = k
        last = k
        j = k + 1
        gap = 0
        while j < len(lines) and lines[j][0] == lines[first][0] and gap <= 2:
            if not lines[j][3]:
                break
            if is_data(lines[j][2]):
                last, gap = j, 0
            else:
                gap += 1
            j += 1
        block = list(range(first, last + 1))
        k = last + 1
        data_rows = [b for b in block if is_data(lines[b][2])]
        intervals: list[list[int]] = []
        for b in data_rows:
            for s, e, t in _fields(lines[b][2])[1:]:
                if _numeric(t) is None:
                    continue
                for iv in intervals:
                    if s < iv[1] + 1 and e > iv[0] - 1:
                        iv[0], iv[1] = min(iv[0], s), max(iv[1], e)
                        break
                else:
                    intervals.append([s, e])
        intervals.sort()
        merged: list[list[int]] = []
        for iv in intervals:
            if merged and iv[0] <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], iv[1])
            else:
                merged.append(iv)
        if not merged:
            continue
        # header and title above the block
        head_idx: list[int] = []
        title_idx: list[int] = []
        h = first - 1
        blanks = 0
        while h >= 0 and first - h <= 14 and lines[h][0] == lines[first][0]:
            t = lines[h][2]
            if not lines[h][3]:
                break
            if not t.strip():
                blanks += 1
                if blanks > 2:
                    break
            elif re.match(r"^\s*table\s+\S+", t, re.I):
                title_idx = [h]
                for x in range(h + 1, min(first, h + 4)):
                    if not lines[x][2].strip():
                        break
                    title_idx.append(x)
                break
            else:
                blanks = 0
                head_idx.insert(0, h)
            h -= 1
        head_idx = [x for x in head_idx if x not in title_idx]
        col_head = [""] * len(merged)
        col_low = [""] * len(merged)  # the lowest header field over each column
        for x in head_idx:
            for s, e, t in _fields(lines[x][2]):
                for ci, (cs, ce) in enumerate(merged):
                    if s < ce + 2 and e > cs - 2:
                        col_head[ci] = f"{col_head[ci]} {t}".strip()
                        col_low[ci] = t
        title = " ".join(lines[x][2].strip() for x in title_idx)
        foot_lines: list[str] = []
        f = last + 1
        while f < len(lines) and f - last <= 12 and lines[f][0] == lines[first][0]:
            t = lines[f][2]
            if re.match(r"^\s*table\s+\S+", t, re.I) or is_data(t):
                break
            if t.strip():
                foot_lines.append(t.strip())
            f += 1
        foot = " ".join(foot_lines[:8])
        code = _code_tokens(title) or _code_tokens(foot)
        start = first
        if code is None:
            for x in range(first - 1, -1, -1):
                if lines[x][0] < lines[first][0] - 3:
                    break
                t = lines[x][2]
                if (
                    lines[x][3]
                    and (is_heading(t) or re.match(r"^\s*stud(?:y|ies)\b", t, re.I))
                    and (c := _code_tokens(t))
                ):
                    code, start = c, x
                    break
        study = f"FDA study {code}" if code else f"FDA NDA {appl} {file.rsplit('.', 1)[0]}"
        design = ""
        if code and start < first:
            design = " ".join(
                lines[x][2].strip()
                for x in range(start, first)
                if lines[x][3] and _DESIGN_TOKENS & set(_tokens(lines[x][2]))
            )
        title_toks = set(_tokens(title))
        if _skip(f"{title} {foot}"):
            continue
        column_cells: dict[int, list[str]] = {}
        for b in data_rows:
            for s0, _e0, t0 in _fields(lines[b][2])[1:]:
                ci0 = next((i for i, (cs, ce) in enumerate(merged) if cs <= s0 < ce + 1), None)
                if ci0 is not None:
                    column_cells.setdefault(ci0, []).append(t0.strip())
        for ci in range(len(merged)):
            if _spread_words(col_low[ci]):
                col_head[ci] = "\x00dispersion"
        for b in data_rows:
            pno, li, t, _ = lines[b]
            fs = _fields(t)
            label = fs[0][2]
            if fs[0][0] >= merged[0][0]:
                continue
            if (
                b + 1 < len(lines)
                and re.match(r"^\s*\([^()]+\)\s*$", lines[b + 1][2])
                and not is_data(lines[b + 1][2])
            ):
                label = f"{label} {lines[b + 1][2].strip()}"
            if set(_tokens(label)) & _BAD_TOKENS:
                continue
            up = _unit_param(label)
            if up is None:
                stats.skip("no_parameter_or_unit")
                continue
            param0, unit = up
            if _normalised(unit, label):
                continue
            stats.seen += 1
            for s, _e, cell in fs[1:]:
                ci = next((i for i, (cs, ce) in enumerate(merged) if cs <= s < ce + 1), None)
                if ci is None or col_head[ci] == "\x00dispersion":
                    continue
                if _counts(cell, column_cells.get(ci, [])):
                    continue
                value = _numeric(cell)
                if value is None or value <= 0:
                    continue
                head = col_head[ci]
                head_toks = set(_tokens(head))
                if head_toks & _BAD_TOKENS:
                    continue
                param = resolve_parameter(param0, unit)
                conv = to_canonical(param, value, unit)
                if isinstance(conv, Refused):
                    stats.skip(conv.issue)
                    continue
                analyte = _classify(f"{label} {head}", {drug_key}, True, drug_key, table)
                if analyte == "unspecified":
                    analyte = "parent"
                if _foreign_table(title, drug_key, table):
                    analyte = "combination_partner"
                elif _moiety_title(title):
                    analyte = "unconfirmed"
                all_toks = head_toks | title_toks | set(_tokens(foot))
                ctx = _context(
                    head_toks | title_toks,
                    all_toks,
                    " ".join(_tokens(f"{head} {title} {foot}")),
                    _others(f"{head} {title} {foot}", drug_key, table),
                )
                ctx = _with_form(ctx, _layers([head, title, foot, design], names))
                dose = (
                    _dose([head, title, foot, design], own)
                    if param in ("cmax", "auc_inf", "auc_tau", "auc_last")
                    else None
                )
                nm = re.search(r"\bn\s*=\s*(\d{1,4})\b", head, re.I)
                out.append(
                    Candidate(
                        drug_key, "drugsatfda_review", study, f"c{ci + 1}", f"{url}#page={pno}&line={li + 1}&col={s + 1}",
                        param, value, unit, Stat(value, _center(head_toks | title_toks), "none"), analyte, ctx, dose,
                        int(nm.group(1)) if nm else None, "", version, None, (),
                    )
                )  # fmt: skip
    return out


# --- PMC tables -------------------------------------------------------------------------------


def read_pmc(
    art: Article,
    drug_key: str,
    table: IdentityTable,
    brands: BrandTable,
    stats: ReaderStats,
    version: str,
) -> list[Candidate]:
    out: list[Candidate] = []
    own = set(table.by_key[drug_key].names | table.by_key[drug_key].codes)
    names = _Names(drug_key, table, brands)
    sentences = [
        s for s in re.split(r"(?<=[.;])\s+", art.methods) if _DOSING_TOKENS & set(_tokens(s))
    ]
    methods_dose = _dose([" ".join(sentences)], own) if sentences else None
    methods_toks = set(_tokens(art.methods))
    for tb in art.tables:
        grid = tb.grid
        nh = tb.head_rows
        if not nh:
            nh = next(
                (
                    r
                    for r, row in enumerate(grid)
                    if r > 0 and any(_numeric(c) is not None for c in row[1:])
                ),
                1,
            )
        cap_toks = set(_tokens(f"{tb.label} {tb.caption}"))
        if (
            cap_toks & _BAD_TOKENS
            and "pharmacokinetic" not in cap_toks
            and "pharmacokinetics" not in cap_toks
        ):
            continue
        if _skip(f"{tb.label} {tb.caption} {tb.footnotes}"):
            continue
        for r in range(nh, len(grid)):
            row = grid[r]
            label = row[0] if row else ""
            row_up = _unit_param(label)
            for c in range(1, len(row)):
                value = _numeric(row[c])
                if value is None or value <= 0:
                    continue
                head = " ".join(
                    dict.fromkeys(grid[h][c] for h in range(nh) if c < len(grid[h]) and grid[h][c])
                )
                lowest = next(
                    (grid[h][c] for h in range(nh - 1, -1, -1) if c < len(grid[h]) and grid[h][c]),
                    "",
                )
                if _spread_words(lowest) or (not row_up and _spread_words(label)):
                    continue
                column = [grid[x][c] for x in range(nh, len(grid)) if c < len(grid[x])]
                if row_up and _counts(row[c], column):
                    continue
                up = row_up or _unit_param(head)
                if up is None:
                    continue
                arm = head if row_up else label
                if set(_tokens(f"{label} {head}")) & _BAD_TOKENS:
                    continue
                param0, unit = up
                if _normalised(unit, label if row_up else head):
                    continue
                stats.seen += 1
                param = resolve_parameter(param0, unit)
                conv = to_canonical(param, value, unit)
                if isinstance(conv, Refused):
                    stats.skip(conv.issue)
                    continue
                analyte = _classify(f"{label} {head}", {drug_key}, True, drug_key, table)
                if analyte == "unspecified":
                    analyte = "parent"
                if _foreign_table(f"{tb.label} {tb.caption}", drug_key, table):
                    analyte = "combination_partner"
                elif _moiety_title(f"{tb.label} {tb.caption}"):
                    analyte = "unconfirmed"
                arm_toks = set(_tokens(arm))
                all_toks = arm_toks | cap_toks | set(_tokens(tb.footnotes))
                ctx = _context(
                    arm_toks | cap_toks,
                    all_toks,
                    " ".join(_tokens(f"{arm} {tb.caption} {tb.footnotes}")),
                    _others(f"{arm} {tb.caption} {tb.footnotes}", drug_key, table),
                )
                if ctx.population == "unspecified":
                    pop = _context(set(), methods_toks, "").population
                    ctx = Context(
                        ctx.arm,
                        ctx.coadministered,
                        ctx.formulation,
                        ctx.food,
                        pop,
                        ctx.sex,
                        ctx.species,
                        ctx.route,
                        ctx.regimen,
                    )
                ctx = _with_form(
                    ctx,
                    _layers([arm, f"{tb.label} {tb.caption}", tb.footnotes, art.methods], names),
                )
                dose = None
                if param in ("cmax", "auc_inf", "auc_tau", "auc_last"):
                    dose = _dose([arm, f"{tb.label} {tb.caption}", tb.footnotes], own)
                    if dose is None:
                        dose = methods_dose
                nm = re.search(r"\bn\s*=\s*(\d{1,4})\b", arm, re.I)
                out.append(
                    Candidate(
                        drug_key, "pmc_oa", art.pmcid, f"c{c}", f"{art.pmcid}#{tb.table_id}/r{r}c{c}", param, value, unit,
                        Stat(value, _center(cap_toks | set(_tokens(head))), "none"), analyte, ctx, dose,
                        int(nm.group(1)) if nm else None, "", version, None, (),
                    )
                )  # fmt: skip
    return out
