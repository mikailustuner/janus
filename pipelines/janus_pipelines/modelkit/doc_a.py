"""Reader A for review PDFs and PMC tables (spec model-kit, milestone M5): pattern based.

FDA reviews: every readable layout line that starts with a parameter label followed by numbers is a
table row; its cells are the runs of text separated by two or more spaces. The arm header of a row
is taken from the header lines above whose number of cells equals the number of value cells (by
order); a header naming a mean and a CV or SD column pair makes the cells alternate (value,
dispersion). The table title is the nearest line above starting with "Table"; footnotes are the
lines below the table. The study is the code after "study" (or "study report", "protocol", "trial")
in the title, the footnotes, or the nearest earlier mention within three pages. PMC tables: each
cell flattened to "row label | column header | cell" and read with the same patterns. Dose only from
the column header, the title or caption, the footnotes or the study design text (review: lines of
the study's own section; article: the methods), never a summary. Reader B (`doc_b.py`) is separate
code and never sees this output. Research use only. Not for clinical decisions."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Final

from janus_pipelines.modelkit.confirm import Context
from janus_pipelines.modelkit.formref import BrandTable, Resolution, decide
from janus_pipelines.modelkit.formulation_a import _classes, _Drug  # pyright: ignore[reportPrivateUsage]
from janus_pipelines.modelkit.model import Candidate, ReaderStats
from janus_pipelines.modelkit.pmc_jats import Article
from janus_pipelines.modelkit.reader_a import dose_mg_near, parameter_of
from janus_pipelines.modelkit.resolver import IdentityTable, arm_context, classify_analyte, norm
from janus_pipelines.modelkit.review_text import Page
from janus_pipelines.modelkit.units import (
    Center,
    Refused,
    Stat,
    parse_stat,
    resolve_parameter,
    to_canonical,
)

_NUMCELL: Final = re.compile(
    r"^[<>~]?\s*\d[\d,]*(?:\.\d+)?(?:\s*(?:±|\+/-|\+|\()\s*[\d.,]+\s*%?\s*\)?)?(?:\s*\(\s*[\d.,]+\s*%?\s*\))?"
    r"(?:\s*\[[^\]]*\])?$"
)
_UNIT_IN_LABEL: Final = re.compile(
    r"\(([^()]*(?:/|%|\bh(?:ou)?rs?\b|\bh\b|\bmin\b|\bL\b|\bmL\b)[^()]*)\)|,\s*([a-zA-Zµμ·•*./% ]{1,20})$"
)
_STUDY: Final = re.compile(
    r"\b(?:stud(?:y|ies)|protocol|trial|csr)(?:\s+(?:report|no\.?|number|id|code))?\s*[#:]?\s*"
    r"([A-Z][A-Z0-9]*(?:[-_./][A-Z0-9]+)*|\d[A-Z0-9]*(?:[-_./][A-Z0-9]+)+)",
    re.I,
)
_TITLE: Final = re.compile(r"^\s*table\s+[\w.\-]+\b", re.I)
_FOOT: Final = re.compile(
    r"^\s*(?:source|note|notes|abbreviations?|data|\*|†|‡|§|[a-e][.)]?\s|mean|cv|sd|n\s*=)", re.I
)
_DISP_HEAD: Final = re.compile(r"\b(?:c\.?v\.?|cv%|%cv|sd|s\.d\.|std|se)\b", re.I)
_SPREAD_HEAD: Final = re.compile(
    r"\b(?:s\.?d\.?|sem?|std\.?|c\.?v\.?\s*%?|%\s*cv|cv\s*w|cvw|cv\s*intra|min(?:imum)?|max(?:imum)?|range|ci|iqr|p[ -]?value|p|"
    r"power|n|no\.|number|count|"
    r"standard deviation|standard error|coefficient of variation)\b",
    re.I,
)
_CENTER_HEAD: Final = re.compile(r"\b(?:mean|median|geometric|gm|average)\b", re.I)


_DOSE_NORMALISED: Final = re.compile(
    r"/\s*(?:d|dw|dose)\b|dose[- ]normali[sz]ed|\bdn\b|/\s*mg\b|[·*.]\s*mg\b|\bmg\s*[·*.]", re.I
)


def other_drug_table(caption: str, drug_key: str, table: IdentityTable) -> bool:
    """The table title or caption names another drug of the pool and not this one: its values are
    not this drug's."""
    named = table.drugs_in(caption)
    return bool(named) and drug_key not in named


def spread_column(head: str) -> bool:
    """A column of a dispersion, a bound or a test statistic (SD, CV, min, max, range, CI, p value),
    not a value: the header cell is only such a word (with brackets or a percent sign)."""
    rest = _SPREAD_HEAD.sub(" ", head)
    return rest != head and not _CENTER_HEAD.search(head) and not re.search(r"[A-Za-z0-9]", rest)


_N: Final = re.compile(r"\b[nN]\s*=\s*(\d{1,4})\b")
_DOSING: Final = re.compile(
    r"\b(?:received|administered|given|dosed|single (?:oral )?doses? of|took)\b", re.I
)
_DESIGN: Final = re.compile(
    r"\b(?:dose|doses|dosed|administered|received|given|treatment|design|single|regimen)\b", re.I
)
_RATIO: Final = re.compile(
    r"\bratio|\bgmr\b|\bt\s*/\s*r\b|test\s*/\s*reference|\bg?ls ?means?\b|least[- ]squares|statistic|anova|90\s*%\s*ci|\bci\b|confidence|\bfold\b|% change|difference|predicted|simulat|model",
    re.I,
)


def cell_stat(cell: str, center: Center) -> Stat | None:
    """The statistic of a cell: 'm ± sd', 'm + sd' (a lost ±), 'm ± sd (cv%)' (the CV dropped), 'm
    (cv)', 'm (lo-hi)'."""
    t = cell.replace(",", "").strip()
    t = re.sub(r"^([\d.]+)\s*\+\s*([\d.]+)", r"\1 ± \2", t)
    t = re.sub(r"^([\d.]+\s*±\s*[\d.]+)\s*\(\s*[\d.]+\s*%?\s*\)$", r"\1", t)
    return parse_stat(t, center)


def _hyphen_dose(text: str) -> str:
    """'160-mg' as '160 mg' (the review style) before the dose pattern reads it."""
    return re.sub(r"(\d)\s*-\s*(mg|mcg|µg|g)\b", r"\1 \2", text)


def study_code(text: str) -> str | None:
    """The normalised study code named in the text (upper case, letters and digits), or None."""
    for m in _STUDY.finditer(text):
        code = re.sub(r"[^A-Z0-9]", "", m.group(1).upper())
        if len(code) >= 5 and sum(ch.isdigit() for ch in code) >= 2:
            return code
    return None


def _split2(text: str, start: int) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    for m in re.finditer(r"\S(?:.*?\S)?(?=\s{2,}|$)", text[start:]):
        out.append((m.start() + start, m.group(0)))
    return out


def _unit_of(label: str, next_line: str) -> str | None:
    if m := _UNIT_IN_LABEL.search(label):
        return (m.group(1) or m.group(2) or "").strip() or None
    if m := re.match(
        r"^\s*\(([^()]{1,25})\)\s*$", next_line.split("  ")[0] if next_line.strip() else ""
    ):
        return m.group(1).strip()
    if m := re.match(r"^\s*\(([^()]{1,25})\)", next_line.strip()):
        return m.group(1).strip()
    return None


@dataclass(frozen=True)
class ReviewDoc:
    drug_key: str
    appl_no: str
    url: str  # the PDF
    file: str
    version: str  # what the row says about the source version and its licence


def _doc_study(doc: ReviewDoc) -> str:
    return f"FDA NDA {doc.appl_no} {doc.file.rsplit('.', 1)[0]}"


def form_route(layers: Sequence[str], drug: _Drug) -> Resolution:
    """Formulation and route from text layers, most specific first, with the M3 resolver A's
    evidence classes and the shared rule: a conflict stops the search, the first layer with evidence
    other than a bare tablet word decides, a bare tablet word counts only if nothing else is found.
    """
    weak: Resolution | None = None
    first_route = ""
    for text in layers:
        t = norm(text)
        if not t:
            continue
        cls, routes = _classes(t, drug.brand_hits(t))
        if not first_route and len(routes) == 1:
            first_route = next(iter(routes))
        res = decide(cls, routes)
        if res.why.startswith("conflict"):
            return res
        if res.why in ("ir_weak", ""):
            weak = weak or (res if res.why == "ir_weak" else None)
            continue
        route = (
            res.route
            if res.route != "unknown" or res.formulation == "other_route"
            else first_route or "unknown"
        )
        return Resolution(res.formulation, route, res.why)
    if weak is not None:
        return Resolution(
            weak.formulation,
            weak.route if weak.route != "unknown" else first_route or "unknown",
            weak.why,
        )
    return Resolution("unspecified", first_route or "unknown", "")


def apply_form(ctx: Context, res: Resolution) -> Context:
    if res.why == "conflict:iv_and_oral":
        route = "unknown"
    elif res.formulation == "other_route":
        route = "other"
    else:
        route = res.route if res.route != "unknown" else ctx.route
    return replace(ctx, formulation=res.formulation, route=route)


def _center(text: str) -> Center:
    t = text.lower()
    return (
        "geometric"
        if "geometric" in t
        else "median"
        if "median" in t
        else "arithmetic"
        if "mean" in t
        else "unspecified"
    )


def read_review(
    pages: Sequence[Page],
    doc: ReviewDoc,
    table: IdentityTable,
    brands: BrandTable,
    stats: ReaderStats,
) -> list[Candidate]:
    out: list[Candidate] = []
    drug = _Drug(doc.drug_key, table, brands)
    names = table.by_key[doc.drug_key].names
    flat: list[tuple[int, int, str, bool]] = []  # (page, line index, text, readable)
    for p in pages:
        if not p.text_page:
            continue
        flat += [
            (p.number, i, t, r) for i, (t, r) in enumerate(zip(p.lines, p.readable, strict=True))
        ]
    for k, (pno, li, line, readable) in enumerate(flat):
        if not readable:
            continue
        m = re.match(r"^(\s*)(\S.*?)(\s{2,})(?=[<>~]?\s*\d)", line)
        if m is None:
            continue
        label = m.group(2).strip()
        pname = parameter_of(re.sub(r"\(.*?\)", " ", label) + " " + label)
        if pname is None or _RATIO.search(label):
            continue
        stats.seen += 1
        nxt = flat[k + 1][2] if k + 1 < len(flat) else ""
        unit = _unit_of(label, nxt)
        if unit is None:
            stats.skip("no_unit")
            continue
        if _DOSE_NORMALISED.search(unit) or _DOSE_NORMALISED.search(re.sub(r"\(.*?\)", " ", label)):
            stats.skip("dose_normalised")
            continue
        cells = _split2(line, m.end())
        if not cells or not _NUMCELL.match(cells[0][1].strip()):
            stats.skip("not_a_numeric_row")
            continue
        # header lines: walk up over table lines until the title or a blank gap of two lines
        above: list[str] = []
        title = ""
        blanks = 0
        j = k - 1
        while j >= 0 and k - j <= 25 and flat[j][0] >= pno - 1:
            t = flat[j][2]
            if not flat[j][3]:
                break
            if _TITLE.match(t):
                parts = [t.strip()]
                for x in flat[j + 1 : min(k, j + 4)]:
                    if not x[2].strip() or re.search(r"\S\s{3,}\S", x[2].strip()):
                        break
                    parts.append(x[2].strip())
                title = " ".join(parts)
                above = [a for a in above if a.strip() not in parts]
                break
            if not t.strip():
                blanks += 1
                if blanks >= 3:
                    break
                j -= 1
                continue
            blanks = 0
            above.append(t)
            j -= 1
        above.reverse()
        head_lines = [
            h for h in above if not re.match(r"^\s*\S.*?\s{2,}[<>~]?\s*\d", h) or _N.search(h)
        ]
        disp = any(
            len(_DISP_HEAD.findall(h)) >= 1 and re.search(r"\bmean\b|\bmedian\b", h, re.I)
            for h in head_lines
        )
        values = cells[0::2] if disp and len(cells) % 2 == 0 else cells
        if disp and len(cells) % 2:
            stats.skip("dispersion_columns_unpaired")
            continue
        arm_heads = [""] * len(values)
        arm_last = [""] * len(values)  # the cell of the lowest header line over each value
        for h in head_lines:
            hc = _split2(h, 0)
            if len(hc) == len(values) + 1:
                hc = hc[1:]
            if len(hc) == len(values):
                arm_heads = [f"{a} {c}".strip() for a, (_, c) in zip(arm_heads, hc, strict=True)]
                arm_last = [c for _, c in hc]
        # footnotes below the table
        foot: list[str] = []
        j = k + 1
        gap = 0
        while j < len(flat) and j - k <= 30 and flat[j][0] <= pno + 1:
            t = flat[j][2]
            if not t.strip():
                gap += 1
                if gap > 2 and foot:
                    break
            elif re.match(r"^\s*(?:table|figure)\s+\S+", t, re.I):
                break
            elif _FOOT.match(t):
                foot.append(t.strip())
            elif foot:
                if len(foot) < 6 and not re.match(r"^\s*\S.*?\s{2,}\d", t):
                    foot.append(t.strip())
                else:
                    break
            j += 1
        foot_text = " ".join(foot)
        code = study_code(title) or study_code(foot_text)
        start_k = k
        if code is None:
            for j in range(k - 1, -1, -1):
                if flat[j][0] < pno - 3:
                    break
                if flat[j][3] and (c := study_code(flat[j][2])):
                    code, start_k = c, j
                    break
        study = f"FDA study {code}" if code else _doc_study(doc)
        design = ""
        if code and start_k < k:
            design = " ".join(
                flat[j][2].strip()
                for j in range(start_k, k)
                if flat[j][3] and _DESIGN.search(flat[j][2])
            )
        center = _center(" ".join(head_lines) + " " + title)
        for ci, (col, cell) in enumerate(values):
            if not _NUMCELL.match(cell.strip()):
                stats.skip("cell_not_a_value")
                continue
            st = cell_stat(cell, center)
            if st is None or st.center <= 0:
                stats.skip("cell_not_a_value")
                continue
            head = arm_heads[ci]
            if _RATIO.search(head):
                stats.skip("ratio_column")
                continue
            if spread_column(arm_last[ci]):
                stats.skip("spread_column")
                continue
            param = resolve_parameter(pname, unit)
            conv = to_canonical(param, st.center, unit)
            if isinstance(conv, Refused):
                stats.skip(conv.issue)
                continue
            analyte, why = classify_analyte(f"{label} {head}", doc.drug_key, table)
            if analyte == "unspecified":
                analyte = "parent"
            if other_drug_table(title, doc.drug_key, table):
                analyte, why = "combination_partner", "the table title names another drug"
            ctx_text = f"{head} . {title} . {foot_text}"
            ac = arm_context(ctx_text, doc.drug_key, table)
            food = arm_context(f"{head} . {title}", doc.drug_key, table).context.food
            ctx = apply_form(
                replace(ac.context, food=food), form_route([head, title, foot_text, design], drug)
            )
            dose = None
            if param in ("cmax", "auc_inf", "auc_tau", "auc_last"):
                for src in (head, title, foot_text, design):
                    if src and (dose := dose_mg_near(_hyphen_dose(src), names)) is not None:
                        break
            nm = _N.search(head)
            n_subj = int(nm.group(1)) if nm else None
            locator = f"{doc.url}#page={pno}&line={li + 1}&col={col + 1}"
            quote = " | ".join(x for x in (title[:200], label, head[:120], cell) if x)
            out.append(
                Candidate(
                    doc.drug_key, "drugsatfda_review", study, f"c{ci + 1}", locator, param, st.center, unit, st,
                    analyte, ctx, dose, n_subj, quote, doc.version, None, (why,),
                )
            )  # fmt: skip
    return out


# --- PMC tables -------------------------------------------------------------------------------


def _pmc_head_rows(grid: Sequence[Sequence[str]], declared: int) -> int:
    if declared:
        return declared
    for r, row in enumerate(grid):
        if r > 0 and any(_NUMCELL.match(c.strip()) for c in row[1:]):
            return r
    return 1


def read_pmc(
    art: Article,
    drug_key: str,
    table: IdentityTable,
    brands: BrandTable,
    stats: ReaderStats,
    version: str,
) -> list[Candidate]:
    out: list[Candidate] = []
    drug = _Drug(drug_key, table, brands)
    names = table.by_key[drug_key].names
    dosing = [x for x in re.split(r"(?<=[.;])\s+", art.methods) if _DOSING.search(x)]
    methods_dose = dose_mg_near(_hyphen_dose(" ".join(dosing)), names) if dosing else None
    for tb in art.tables:
        grid = tb.grid
        nh = _pmc_head_rows(grid, tb.head_rows)
        caption = f"{tb.label} {tb.caption}".strip()
        if _RATIO.search(caption) and not re.search(r"pharmacokinetic", caption, re.I):
            stats.skip("ratio_table")
            continue
        for r in range(nh, len(grid)):
            row = grid[r]
            label = row[0] if row else ""
            row_param = parameter_of(re.sub(r"\(.*?\)", " ", label) + " " + label)
            for c in range(1, len(row)):
                cell = row[c].strip()
                header = " ".join(
                    dict.fromkeys(grid[h][c] for h in range(nh) if c < len(grid[h]) and grid[h][c])
                )
                pname, unit_src = (
                    (row_param, label)
                    if row_param
                    else (parameter_of(re.sub(r"\(.*?\)", " ", header) + " " + header), header)
                )
                if pname is None:
                    continue
                arm = header if row_param else label
                if _RATIO.search(label + " " + header):
                    continue
                last_head = next(
                    (grid[h][c] for h in range(nh - 1, -1, -1) if c < len(grid[h]) and grid[h][c]),
                    "",
                )
                if spread_column(last_head) or (not row_param and spread_column(label)):
                    stats.skip("spread_column")
                    continue
                unit = _unit_of(unit_src, "")
                if unit is None:
                    stats.skip("no_unit")
                    continue
                if _DOSE_NORMALISED.search(unit) or _DOSE_NORMALISED.search(
                    re.sub(r"\(.*?\)", " ", unit_src)
                ):
                    stats.skip("dose_normalised")
                    continue
                st = cell_stat(cell, _center(caption + " " + header))
                if st is None or st.center <= 0:
                    continue
                stats.seen += 1
                param = resolve_parameter(pname, unit)
                conv = to_canonical(param, st.center, unit)
                if isinstance(conv, Refused):
                    stats.skip(conv.issue)
                    continue
                analyte, why = classify_analyte(f"{label} {header}", drug_key, table)
                if analyte == "unspecified":
                    analyte = "parent"
                if other_drug_table(caption, drug_key, table):
                    analyte, why = "combination_partner", "the caption names another drug"
                ac = arm_context(f"{arm} . {caption} . {tb.footnotes}", drug_key, table)
                food = arm_context(f"{arm} . {caption}", drug_key, table).context.food
                ac = replace(ac, context=replace(ac.context, food=food))
                dose = None
                if param in ("cmax", "auc_inf", "auc_tau", "auc_last"):
                    for src in (arm, caption, tb.footnotes):
                        if src and (dose := dose_mg_near(_hyphen_dose(src), names)) is not None:
                            break
                    if dose is None:
                        dose = methods_dose
                nm = _N.search(arm)
                ctx = apply_form(
                    ac.context, form_route([arm, caption, tb.footnotes, art.methods], drug)
                )
                if norm(art.methods) and ctx.population == "unspecified":
                    ctx = replace(
                        ctx, population=arm_context(art.methods, drug_key, table).context.population
                    )
                out.append(
                    Candidate(
                        drug_key, "pmc_oa", art.pmcid, f"c{c}", f"{art.pmcid}#{tb.table_id}/r{r}c{c}", param,
                        st.center, unit, st, analyte, ctx, dose, int(nm.group(1)) if nm else None,
                        " | ".join(x for x in (caption[:200], label, header[:120], cell) if x), version, None, (why,),
                    )
                )  # fmt: skip
    return out
