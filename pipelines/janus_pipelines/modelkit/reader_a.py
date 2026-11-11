"""Reader A: pattern-based, sentence-first (spec model-kit, plan 6.3). It works on text: titles,
descriptions and sentences, with regular expressions for the parameter, the quantity and its unit,
and the analyte and context resolver for who the value is about. It does not use structured fields
beyond the value, the unit and the group text. Reader B (`reader_b.py`) is a separate
implementation: it shares no extraction code with this module. Deterministic; no network.
Research use only. Not for clinical decisions.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any, Final

from janus_pipelines.modelkit.confirm import Context
from janus_pipelines.modelkit.model import Candidate, ReaderStats
from janus_pipelines.modelkit.resolver import (
    ArmContext,
    IdentityTable,
    arm_context,
    classify_analyte,
    norm,
)
from janus_pipelines.modelkit.units import (
    Center,
    Refused,
    Stat,
    parse_stat,
    resolve_parameter,
    to_canonical,
)

_RATIO: Final = re.compile(
    r"\bratio\b|\bdifference\b|\bchange\b|\bpercent(?:age)?\b|\bfold\b|\baccumulation\b|\btrough\b|\bcmin\b"
    r"|\bctrough\b|\bpredose\b|\bpre dose\b|\bcomparison\b|\bgeometric mean ratio\b|\bproportion\b"
)
_POPPK: Final = re.compile(
    r"population pharmacokinetic|population pk|popPK|model[- ]based|nonmem|bayesian|simulat|"
    r"estimated (?:using|from|by) (?:a )?(?:population|model)|pharmacometric",
    re.I,
)
_PARAM_PATTERNS: Final[list[tuple[str, re.Pattern[str]]]] = [
    (
        "auc_inf",
        re.compile(
            r"auc\s*\(?\s*(?:0\s*(?:-|to|–)?\s*)?(?:inf|∞|infinity)|aucinf|auc\s*0\s*-\s*∞|to infinity|extrapolated to infinity"
        ),
    ),
    (
        "auc_last",
        re.compile(
            r"auc\s*\(?\s*(?:0\s*-\s*t\b|last)|auclast|last (?:measurable|quantifiable|measured)"
        ),
    ),
    (
        "auc_tau",
        re.compile(
            r"auc\s*\(?\s*(?:tau|τ|0\s*-\s*(?:tau|τ|6|8|12|24)\b)|dosing interval|auctau|auc\s*\(?\s*0\s*-\s*24|auc\s*\(?\s*0\s*-\s*12"
        ),
    ),
    (
        "cmax",
        re.compile(
            r"\bc\s?max\b|maximum (?:observed |measured )?(?:plasma |serum |blood )?concentration|peak (?:plasma |serum )?concentration|cmax"
        ),
    ),
    ("tmax", re.compile(r"\bt\s?max\b|time (?:to|of|at) (?:maximum|peak|maximal)|time to reach")),
    ("t_half", re.compile(r"half[- ]?life|\bt\s?(?:1/2|½|half)\b|terminal elimination half")),
    ("cl_f", re.compile(r"\bcl\s?/\s?f\b|apparent (?:oral |total )?clearance|oral clearance")),
    ("v_f", re.compile(r"\bv(?:z|d)?\s?/\s?f\b|apparent (?:oral )?volume")),
    ("vss", re.compile(r"\bvss\b|steady[- ]state volume")),
    ("cl", re.compile(r"\bcl\b|clearance")),
    ("vd", re.compile(r"\bvz\b|\bvd\b|volume of distribution")),
    ("f", re.compile(r"(?:absolute |oral )?bioavailability")),
]
_DOSE: Final = re.compile(
    r"(?<![\d.])(\d+(?:\.\d+)?)\s*(mg|mcg|µg|ug|g)\b(?!\s*/\s*(?:kg|m|day|d\b|m2|ml))", re.I
)
_DOSE_FACTOR: Final = {"mg": 1.0, "mcg": 1e-3, "µg": 1e-3, "ug": 1e-3, "g": 1e3}


def parameter_of(title: str) -> str | None:
    """The parameter a title names, or None (a ratio, a trough, a change, nothing PK)."""
    t = norm(title)
    if _RATIO.search(t):
        return None
    hits = [name for name, rx in _PARAM_PATTERNS if rx.search(t)]
    if len([h for h in hits if h.startswith("auc")]) > 1:
        return None  # two different AUCs in one title: not one parameter
    return hits[0] if hits else None


def dose_mg_near(
    text: str, names: frozenset[str], others: Sequence[str] = (), table: IdentityTable | None = None
) -> float | None:
    """The dose in mg whose nearest drug name (in either direction) is this drug; None when the
    nearest name is another drug, when the dose is a count of tablets ('2 x 20 mg'), or when it is
    ambiguous. With one dose and no other drug named, that dose."""
    doses = [
        (
            m.start(),
            m.end(),
            float(m.group(1)) * _DOSE_FACTOR[m.group(2).lower().replace("\u03bc", "\u00b5")],
        )
        for m in _DOSE.finditer(text)
    ]
    if not doses:
        return None
    t = norm(text)
    other_names = [norm(o) for o in others if norm(o)]
    if table is not None:
        other_names += [n for k in table.by_key.values() for n in k.names if n not in names]
        other_names += list(table.partners_in(text))
    mentions: list[tuple[int, int, bool]] = []
    for n in names:
        mentions += [(m.start(), m.end(), True) for m in re.finditer(rf"\b{re.escape(n)}\b", t)]
    for n in set(other_names):
        mentions += [(m.start(), m.end(), False) for m in re.finditer(rf"\b{re.escape(n)}\b", t)]
    found: set[float] = set()
    for pos, end, d in doses:
        if re.search(r"\d\s*[x\u00d7]\s*$", text[max(0, pos - 4) : pos]):
            return None  # '2 x 20 mg': a count of units, not the dose
        if not mentions:
            found.add(d)
            continue
        near = min(
            mentions,
            key=lambda m: (
                min(abs(pos - m[1]), abs(m[0] - end)) + (0 if m[0] >= end else 8),
                not m[2],
            ),
        )
        if near[2] and min(abs(pos - near[1]), abs(near[0] - end)) <= 45:
            found.add(d)
    return next(iter(found)) if len(found) == 1 else None


def interval_of(text: str) -> float | None:
    t = norm(text)
    if m := re.search(r"every (\d+) hours|\bq(\d+)h\b|\bq(\d+) h\b", t):
        return float(next(g for g in m.groups() if g))
    if re.search(r"\b(?:once daily|qd|once a day|daily)\b", t):
        return 24.0
    if re.search(r"\b(?:twice daily|bid|twice a day)\b", t):
        return 12.0
    return None


_CENTER: Final[dict[str, Center]] = {
    "MEAN": "arithmetic",
    "GEOMETRIC_MEAN": "geometric",
    "MEDIAN": "median",
}


def _num(text: Any) -> float | None:
    try:
        x = float(str(text).replace(",", ""))
    except ValueError:
        return None
    return x if x == x and abs(x) != float("inf") else None


def read_ctgov(
    study: dict[str, Any], drug_key: str, table: IdentityTable, stats: ReaderStats
) -> list[Candidate]:
    proto = study["protocolSection"]
    nct = proto["identificationModule"]["nctId"]
    updated = proto.get("statusModule", {}).get("lastUpdatePostDate") or proto.get(
        "statusModule", {}
    ).get("lastUpdateSubmitDate", "")
    active = [
        i["name"]
        for i in proto.get("armsInterventionsModule", {}).get("interventions", [])
        if i.get("type") not in ("BEHAVIORAL", "PROCEDURE", "DEVICE", "OTHER")
        and "placebo" not in norm(i["name"])
    ]
    study_actives = {k for n in active for k in table.drugs_in(n)}
    single_active = len(active) == 1 and study_actives == {drug_key}
    elig = norm(proto.get("eligibilityModule", {}).get("eligibilityCriteria", "") or "")
    healthy_flag = proto.get("eligibilityModule", {}).get("healthyVolunteers")
    names = table.by_key[drug_key].names
    out: list[Candidate] = []
    for oi, om in enumerate(study["resultsSection"]["outcomeMeasuresModule"]["outcomeMeasures"], 1):
        title = om.get("title", "")
        parameter = parameter_of(title)
        if parameter is None:
            continue
        stats.seen += 1
        text = f"{title} {om.get('description', '')}"
        if _POPPK.search(text):
            stats.skip("population_pk_output")
            continue
        center = _CENTER.get(om.get("paramType", ""))
        if center is None:
            stats.skip("not_mean_geomean_or_median")
            continue
        unit = om.get("unitOfMeasure", "")
        groups = {g["id"]: g for g in om.get("groups", [])}
        denoms = {
            c["groupId"]: _num(c["value"])
            for d in om.get("denoms", [])[:1]
            for c in d.get("counts", [])
        }
        for ci, cls in enumerate(om.get("classes", [])):
            for ki, cat in enumerate(cls.get("categories", [])):
                for meas in cat.get("measurements", []):
                    value = _num(meas.get("value"))
                    g = groups.get(meas.get("groupId", ""))
                    if value is None or g is None:
                        stats.skip("no_number_or_group")
                        continue
                    label = f"{title} {cls.get('title', '')} {cat.get('title', '')}".strip()
                    analyte, why = classify_analyte(label, drug_key, table)
                    if analyte == "unspecified" and single_active:
                        analyte = "parent"
                    arm_text = f"{g.get('title', '')} {g.get('description', '')}"
                    others_named = [n for n in active if drug_key not in table.drugs_in(n)]
                    ac = arm_context(f"{arm_text} {title}", drug_key, table, others_named)
                    if (
                        analyte in ("parent", "unspecified")
                        and drug_key not in table.drugs_in(f"{title} {g.get('title', '')}")
                        and any(
                            re.search(
                                rf"\b{re.escape(norm(n))}\b", norm(f"{title} {g.get('title', '')}")
                            )
                            for n in others_named
                        )
                    ):
                        analyte, why = "unconfirmed", "the title or group names another substance"
                    ctx = ac.context
                    if ctx.population == "unspecified" and (
                        re.search(r"\bhealthy\b", elig) or healthy_flag is True
                    ):
                        ctx = _with(ctx, population="healthy_adult")
                    if ctx.formulation == "unspecified":
                        own_iv = " ".join(n for n in active if drug_key in table.drugs_in(n))
                        ctx = _with(
                            ctx,
                            formulation=arm_context(own_iv, drug_key, table).context.formulation,
                        )
                    dose = dose_mg_near(arm_text, names, others_named, table) or dose_mg_near(
                        title, names, others_named, table
                    )
                    if parameter == "f":
                        dose = None
                    parsed = parse_stat(
                        f"{meas['value']} ({meas['spread']})"
                        if meas.get("spread")
                        else str(meas["value"])
                    )
                    if parsed is None:
                        continue
                    stat = Stat(
                        value, center, parsed.spread_type, parsed.spread_low, parsed.spread_high
                    )
                    param = resolve_parameter(parameter, unit)
                    conv = to_canonical(param, value, unit)
                    if isinstance(conv, Refused):
                        stats.skip(conv.issue)
                        continue
                    n_raw = denoms.get(g["id"])
                    n_subj = int(n_raw) if n_raw else None
                    where = f"{nct}#outcome-{oi}/{g['id']}" + (
                        f"/c{ci}.{ki}"
                        if len(om.get("classes", [])) > 1 or len(cls.get("categories", [])) > 1
                        else ""
                    )
                    quote = f"{title} | group: {g.get('title', '')} ({(g.get('description', '') or '')[:160]}) | value {meas['value']} {unit} ({om.get('paramType')})"
                    out.append(
                        Candidate(
                            drug_key, "clinicaltrials_gov", nct, g["id"], where, param, value, unit,
                            stat, analyte, ctx, dose, n_subj,
                            quote, f"record last updated {updated}", interval_of(f"{arm_text} {title} {om.get('timeFrame', '')}"),
                            (why,),
                        )
                    )  # fmt: skip
    return out


def _with(ctx: Context, **changes: str) -> Context:
    from dataclasses import replace

    return replace(ctx, **changes)


# --- DailyMed label text: sentences and flattened table rows -------------------------------------

_WORDNUM: Final = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
    "nine": 9, "ten": 10, "twelve": 12,
}  # fmt: skip
_NUMX: Final = r"(?:\d+(?:\.\d+)?|" + "|".join(_WORDNUM) + r")"
_UNITX: Final = (
    r"(?:L/h/kg|L/kg|L/h|mL/min/kg|mL/min|mL/h|mL/kg/min|L/min|ng·h/mL|ng•h/mL|ng\*h/mL|ng\s?h/mL|"
    r"mcg·h/mL|mcg\*h/mL|mcg\s?h/mL|µg·h/mL|ug\*h/mL|ng/mL|mcg/mL|µg/mL|ug/mL|mg/L|"
    r"hours?|hrs?|h\b|minutes?|min\b|days?|L\b|mL\b|%)"
)
_QTY: Final = re.compile(
    rf"(?P<bound>(?:greater than|more than|at least|>|≥|less than|<|up to|≤)\s*)?(?:approximately\s+|about\s+|~\s*)?"
    rf"(?P<n1>{_NUMX})(?:\s*(?:to|-|–|and)\s*(?P<n2>{_NUMX}))?\s*(?P<unit>{_UNITX})",
    re.I,
)
_LABEL_PARAM: Final[list[tuple[str, re.Pattern[str]]]] = [
    (
        "cl_f",
        re.compile(
            r"\bcl\s?/\s?f\b|apparent (?:oral |total )?(?:plasma )?clearance|oral (?:plasma )?clearance",
            re.I,
        ),
    ),
    (
        "v_f",
        re.compile(
            r"\bv(?:z|d)?\s?/\s?f\b|apparent (?:oral )?volume of distribution|apparent volume", re.I
        ),
    ),
    ("vss", re.compile(r"steady[- ]state volume of distribution|\bvss\b", re.I)),
    ("cl", re.compile(r"(?:total|systemic|plasma|renal|body)?\s*clearance\b", re.I)),
    ("vd", re.compile(r"volume of distribution", re.I)),
    ("t_half", re.compile(r"half[- ]?life|\bt\s?(?:1/2|½)\b|\bt\s?1/2\b", re.I)),
    (
        "tmax",
        re.compile(
            r"\bt\s?max\b|time to (?:peak|maximum)|peak (?:plasma |serum |blood )?(?:concentrations?|levels?)[^.]{0,80}?\b(?:occurs?|occurred|reached|observed|attained|within|at)\b",
            re.I,
        ),
    ),
    (
        "cmax",
        re.compile(
            r"\bc\s?max\b|(?:maximum|peak) (?:observed )?(?:plasma |serum |blood )?(?:concentrations?|levels?)",
            re.I,
        ),
    ),
    ("auc_inf", re.compile(r"auc\s*\(?\s*(?:0\s*-?\s*)?(?:inf|∞)|aucinf|auc0\s*-\s*∞", re.I)),
    ("auc_tau", re.compile(r"auc\s*\(?\s*(?:tau|τ|0\s*-\s*(?:12|24|8|6))", re.I)),
    ("auc_last", re.compile(r"auc\s*\(?\s*(?:0\s*-\s*t\b|last)", re.I)),
    ("f", re.compile(r"(?:absolute |oral )?bioavailability", re.I)),
]
_FAMILY: Final = {
    "cl_f": "cl", "cl": "cl", "v_f": "v", "vss": "v", "vd": "v", "t_half": "time", "tmax": "time",
    "cmax": "conc", "auc_inf": "auc", "auc_tau": "auc", "auc_last": "auc", "f": "pct",
}  # fmt: skip


def _unit_family(unit: str) -> str:
    u = unit.lower()
    if ("h/" in u.replace(" ", "") and "ml" in u) or "·h" in u or "*h" in u:
        return "auc"
    if "/min" in u or ("/h" in u and "kg" not in u.split("/")[0] and "ml" not in u.split("/h")[0]):
        return "cl"
    if "/kg" in u and ("l/kg" in u) and "/h" not in u:
        return "v"
    if u in ("l", "ml") or u.startswith("l/kg"):
        return "v"
    if "/ml" in u or "/l" in u:
        return "conc"
    if u == "%":
        return "pct"
    return "time"


def _val(tok: str) -> float:
    return float(_WORDNUM[tok.lower()]) if tok.lower() in _WORDNUM else float(tok)


def label_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.;])\s+(?=[A-Z\[(])", text)
    return [p.strip() for p in parts if p.strip()]


def _label_candidates(
    sentence: str,
    drug_key: str,
    table: IdentityTable,
    locator: str,
    set_id: str,
    version: str,
    context_text: str,
    stats: ReaderStats,
) -> list[Candidate]:
    out: list[Candidate] = []
    names = table.by_key[drug_key].names
    for qm in _QTY.finditer(sentence):
        fam = _unit_family(qm["unit"])
        before = sentence[max(0, qm.start() - 160) : qm.start()]
        param: str | None = None
        best = -1
        if (
            re.search(r"creatinine|renal|dialysis|\bcrcl\b|hepatic clearance", before[-60:], re.I)
            and fam == "cl"
        ):
            stats.skip("renal_or_creatinine_clearance")
            continue
        for name, rx in _LABEL_PARAM:
            if _FAMILY[name] != fam:
                continue
            for m in rx.finditer(before):
                if m.end() > best:
                    best, param = m.end(), name
        if param is None:
            continue
        if (
            "respectively" in sentence.lower()
            or len(re.findall(r"\b(?:m\d|metabolite)\b", sentence.lower())) > 0
        ):
            # two analytes in one sentence, assigned by position: A does not guess
            analyte, why = "unconfirmed", "two analytes in one sentence"
        else:
            analyte, why = classify_analyte(sentence[: qm.start()], drug_key, table)
            if analyte == "unspecified":
                analyte = "parent"  # a label is about one drug
        n1 = _val(qm["n1"])
        n2 = _val(qm["n2"]) if qm["n2"] else None
        bound = (qm["bound"] or "").strip().lower()
        if bound in ("less than", "<", "up to", "≤"):
            stats.skip("upper_bound")
            continue
        unit = qm["unit"].replace("•", "·")
        if n2 is not None and n2 > n1:
            value = (n1 * n2) ** 0.5
            spread = ("range", n1, n2)
        else:
            value, spread = n1, ("none", None, None)
        param = resolve_parameter(param, unit)
        conv = to_canonical(param, value, unit)
        if isinstance(conv, Refused):
            stats.skip(conv.issue)
            continue
        ac = arm_context(f"{sentence} {context_text}", drug_key, table)
        ctx = ac.context
        dose = (
            dose_mg_near(sentence, names)
            if param in ("cmax", "auc_inf", "auc_tau", "auc_last")
            else None
        )
        notes = (why,) + (("bound",) if bound else ())
        out.append(
            Candidate(
                drug_key, "dailymed_spl", set_id, "", locator, param, value, qm["unit"],
                Stat(value, "unspecified", spread[0], spread[1], spread[2]),  # type: ignore[arg-type]
                analyte, ctx, dose, None, sentence[:300], version, None, notes,
            )
        )  # fmt: skip
    return out


def read_label(
    doc: dict[str, Any],
    tables: dict[str, dict[str, Any]],
    set_id: str,
    drug_key: str,
    table: IdentityTable,
    stats: ReaderStats,
) -> list[Candidate]:
    """Paragraphs of label sections 12.x read by sentence; each table flattened to one line per
    cell ('row label (column header): cell') and read by the same sentence rules."""
    version = f"label version {doc['version']}, effective {doc['effective']}"
    base = f"dailymed:{set_id}/version-{doc['version']}/effective-{doc['effective']}"
    out: list[Candidate] = []
    for pi, p in enumerate(doc["paras"]):
        if not p["title"].startswith("12.3"):
            continue
        for sentence in label_sentences(p["text"]):
            out += _label_candidates(
                sentence, drug_key, table, f"{base}#12.3-p{pi}", set_id, version, p["title"], stats
            )
    for tid, tb in sorted(tables.items()):
        if not tb.get("title", "").startswith("12"):
            continue
        out += _table_candidates(tb, tid, base, set_id, version, drug_key, table, stats)
    return out


def _table_candidates(
    tb: dict[str, Any],
    tid: str,
    base: str,
    set_id: str,
    version: str,
    drug_key: str,
    table: IdentityTable,
    stats: ReaderStats,
) -> list[Candidate]:
    """One line per cell: 'row label  column header: cell', read like a sentence."""
    grid: list[list[str]] = tb["grid"]
    caption = f"{tb.get('caption', '')} {tb.get('prev_para', '')}"
    cap_l = caption.lower()
    center: Center = (
        "geometric"
        if "geometric" in cap_l
        else "median"
        if "median" in cap_l
        else "arithmetic"
        if "mean" in cap_l
        else "unspecified"
    )
    first_data = next(
        (
            r
            for r, row in enumerate(grid)
            if r > 0
            and sum(
                1
                for c in row[1:]
                if re.fullmatch(r"[\d.,]+(?:\s*(?:\u00b1|\()[^)]*\)?)?", c.strip())
            )
            >= 1
        ),
        len(grid),
    )
    out: list[Candidate] = []
    names = table.by_key[drug_key].names
    for r in range(first_data, len(grid)):
        row = grid[r]
        label = row[0] if row else ""
        pname = parameter_of(re.sub(r"\(.*?\)", " ", label) + " " + label)
        um = re.search(r"\(([^()]*(?:/|%|hours?|h\b)[^()]*)\)", label)
        if pname is None or um is None:
            continue
        unit = um.group(1).replace("\u2022", "\u00b7")
        for c in range(1, len(row)):
            cell = row[c].strip()
            st = parse_stat(cell, center)
            if st is None or st.center <= 0:
                continue
            header = " ".join(
                dict.fromkeys(grid[h][c] for h in range(first_data) if c < len(grid[h]))
            )
            ctx_text = f"{header} {caption}"
            analyte, why = classify_analyte(f"{label}", drug_key, table)
            if analyte == "unspecified":
                analyte = "parent"
            param = resolve_parameter(pname, unit)
            conv = to_canonical(param, st.center, unit)
            if isinstance(conv, Refused):
                stats.skip(conv.issue)
                continue
            ac = arm_context(ctx_text, drug_key, table)
            # a caption that lists every condition ("light breakfast, high-fat or fasted") does not
            # say which column is which: food comes from the column header alone
            ac = ArmContext(
                _with(ac.context, food=arm_context(header, drug_key, table).context.food),
                ac.interaction,
                ac.route,
                ac.notes,
            )
            dose = (
                dose_mg_near(ctx_text, names)
                if param in ("cmax", "auc_inf", "auc_tau", "auc_last")
                else None
            )
            out.append(
                Candidate(
                    drug_key, "dailymed_spl", set_id, f"c{c}", f"{base}#{tid.split('#')[-1]}/r{r}c{c}",
                    param, st.center, unit, st, analyte, ac.context, dose, None,
                    f"{caption.strip()[:120]} | {label} | {header[:100]} | {cell}", version, None, (why,),
                )
            )  # fmt: skip
    return out
