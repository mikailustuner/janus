"""Reader B: structure-first, an implementation independent of reader A (spec model-kit, plan 6.3).

It shares no extraction code with `reader_a.py` and never sees reader A's output. Strategy: the
structured fields of a record come first (the unit's dimension, the arm-to-intervention links, the
eligibility flags, the table grid with its header rows); text is tokenised into a set of compact
tokens and matched against token rules, not read with sentence patterns. Only reference data is
shared: the identity table (names), the unit table and the value types. Deterministic; no network.
Research use only. Not for clinical decisions.
"""

from __future__ import annotations

import re
from typing import Any, Final

from janus_pipelines.modelkit.confirm import Context
from janus_pipelines.modelkit.model import Candidate, ReaderStats
from janus_pipelines.modelkit.resolver import PARTNERS, AnalyteClass, IdentityTable
from janus_pipelines.modelkit.units import (
    Center,
    Refused,
    Stat,
    parse_stat,
    parse_unit,
    resolve_parameter,
    to_canonical,
)

_BAD: Final = frozenset(
    "ratio ratios difference differences change percent percentage fold accumulation trough "
    "predose cmin ctrough proportion versus vs comparison".split()
)
_POP: Final = (
    "populationpharmacokinetic", "populationpk", "popPK".lower(), "modelbased", "nonmem", "bayesian",
    "simulat", "pharmacometric",
)  # fmt: skip
_METAB_TOKENS: Final = frozenset(
    "metabolite metabolites glucuronide conjugate desmethyl desethyl desacetyl hydroxy noroxy".split()
)
_ANIMALS: Final = frozenset(
    "horse horses equine dog dogs canine beagle beagles rat rats mouse mice murine monkey monkeys "
    "cynomolgus rabbit rabbits pig pigs porcine cattle bovine sheep animal animals".split()
)
_CENTER: Final[dict[str, Center]] = {
    "MEAN": "arithmetic",
    "GEOMETRIC_MEAN": "geometric",
    "MEDIAN": "median",
}


def _tokens(text: str) -> list[str]:
    """Lower-case word tokens with accents and punctuation dropped."""
    return re.findall(r"[a-z0-9]+", text.lower().replace("µ", "u"))


def _compact(text: str) -> str:
    t = text.lower().replace("∞", "inf").replace("τ", "tau").replace("½", "12")
    return re.sub(r"[^a-z0-9]", "", t)


def _all(text: str, sub: str) -> list[int]:
    return [m.start() for m in re.finditer(re.escape(sub), text)]


def _auc_kind(compact: str) -> str | None:
    if compact.count("auc") > 1 and len({compact[i + 3 : i + 8] for i in _all(compact, "auc")}) > 1:
        return None  # two different AUCs in one title: not one parameter

    i = compact.find("auc")
    tail = compact[i + 3 : i + 16]
    if "inf" in tail or "toinfinity" in compact:
        return "auc_inf"
    if "last" in tail or tail.startswith("0t") or "lastmeas" in compact or "lastquant" in compact:
        return "auc_last"
    return "auc_tau"


def parameter_from_structure(title: str, unit: str) -> str | None:
    """Parameter from the unit's dimension first, then the compact title tokens."""
    c = _compact(title)
    if set(_tokens(title)) & _BAD or any(p in c for p in _POP):
        return None
    u = parse_unit(unit)
    if u is None:
        return None
    mass, length, time, body, amount = u.dim
    if amount:
        return None
    if (mass, length, time) == (1, -3, 1):
        return _auc_kind(c) if "auc" in c or "areaunder" in c else None
    if (mass, length, time) == (1, -3, 0):
        return "cmax" if ("cmax" in c or "maximum" in c or "peak" in c) else None
    if (mass, length, time) == (0, 0, 1):
        if "tmax" in c or ("timeto" in c and ("max" in c or "peak" in c)) or "timeofmax" in c:
            return "tmax"
        if "halflife" in c or "t12" in c or "thalf" in c or "eliminationhalf" in c:
            return "t_half"
        return None
    if (mass, length, time) == (0, 3, -1):
        if "clf" in c or "apparent" in c or "oralclearance" in c:
            return "cl_f"
        return "cl" if "clearance" in c or c.startswith("cl") else None
    if (mass, length, time) == (0, 3, 0):
        if "vf" in c or "vzf" in c or "apparentvolume" in c or "vdf" in c:
            return "v_f"
        if "vss" in c or "steadystatevolume" in c:
            return "vss"
        return "vd" if "volume" in c or "vz" in c or "vd" in c else None
    if (mass, length, time, body) == (0, 0, 0, 0) and "bioavailab" in c:
        return "f"
    return None


def _doses_in(tokens: list[str]) -> list[tuple[int, float]]:
    """(token index, dose in mg) for every 'number unit' in the tokens; per kg, per m2 and per day
    doses are skipped."""
    out: list[tuple[int, float]] = []
    i = 0
    while i < len(tokens) - 1:
        if tokens[i].isdigit():
            num = tokens[i]
            j = i + 1
            if j < len(tokens) - 1 and tokens[j].isdigit() and tokens[j + 1] in _MASS:
                num, j = f"{num}.{tokens[j]}", j + 1  # 0.5 is tokenised as 0 / 5
            if j < len(tokens) and tokens[j] in _MASS:
                nxt = tokens[j + 1] if j + 1 < len(tokens) else ""
                if nxt not in ("kg", "m", "m2", "day", "d"):
                    out.append((i, float(num) * _MASS[tokens[j]]))
                i = j
        i += 1
    return out


_MASS: Final = {"mg": 1.0, "mcg": 1e-3, "ug": 1e-3, "g": 1e3}


_OTHER_ROUTE_TOKENS: Final = frozenset(
    "intramuscular intramuscularly subcutaneous subcutaneously topical topically cream gel ointment "
    "transdermal patch inhaled inhalation nasal intranasal ophthalmic vaginal rectal perianal "
    "sublingual buccal intrathecal epidural intradermal intraocular im sc suppository".split()
)


def _route(toks: set[str]) -> str:
    if toks & _OTHER_ROUTE_TOKENS:
        return "other"
    if toks & {"intravenous", "iv", "infusion"}:
        return "iv"
    if toks & {"oral", "orally", "tablet", "tablets", "capsule", "capsules", "po"}:
        return "oral"
    return "unknown"


def _regimen(toks: set[str], joined: str) -> str:
    """Multiple only on explicit evidence (steady state, repeated, days N to M, for 2+ days);
    single on 'single', 'day 1' or 'one day'; both or neither is unknown."""
    multiple = bool(
        {"multiple", "steady", "repeated", "maintenance"} & toks
        or re.search(
            r"\bdays? \d+ (?:to|and|\d+)|\bfor (?:[2-9]|\d\d+) (?:days|weeks|months)\b", joined
        )
        or re.search(r"\bx (?:[2-9]|\d\d+) days\b", joined)
    )
    single = bool(
        "single" in toks
        or re.search(
            r"\bon day 1\b|\bfor (?:1|one) day\b|\b1 day\b|\bone dose\b|\bday 1 only\b", joined
        )
    )
    return (
        "multiple"
        if multiple and not single
        else "single"
        if single and not multiple
        else "unknown"
    )


def _dose_beside_name(
    text: str, own: set[str], others: frozenset[str] = frozenset()
) -> float | None:
    """The one dose in mg whose nearest name is this drug (a dose nearer to another drug's name
    belongs to that drug; a count such as '2 x 20 mg' is not a dose)."""
    toks = _tokens(text)
    own_tokens = {w for n in own for w in _tokens(n)}
    other_tokens = {w for n in others for w in _tokens(n)} - own_tokens
    found: set[float] = set()
    for pos, d in _doses_in(toks):
        if pos > 0 and toks[pos - 1] == "x":
            return None
        best: tuple[int, bool] | None = None
        for i, t in enumerate(toks):
            mine = t in own_tokens
            if not (mine or t in other_tokens):
                continue
            gap = i - pos if i > pos else (pos - i) + 3  # a name after the dose is nearer
            if best is None or gap < best[0]:
                best = (gap, mine)
        if best is None or (best[1] and best[0] <= 8):
            found.add(d)
    return next(iter(found)) if len(found) == 1 else None


def _arm_for(group_title: str, arms: list[dict[str, Any]]) -> dict[str, Any] | None:
    gt = " ".join(_tokens(group_title))
    best: dict[str, Any] | None = None
    for a in arms:
        al = " ".join(_tokens(a.get("label", "")))
        if al and (al == gt or al in gt or gt in al):
            if best is None or len(al) > len(" ".join(_tokens(best.get("label", "")))):
                best = a
    return best


_FILLER: Final = frozenset(
    "plasma serum blood the a an drug study participants subjects patients treatment total parent "
    "part cycle day dose single multiple oral after before during following when with alone group "
    "arm period steady state healthy adult tablet tablets capsule capsules fasted fed zero last "
    "quantifiable concentration curve area under maximum observed peak time cmax auc tmax half life "
    "clearance volume distribution apparent systemic hydrochloride hcl sodium mesylate besylate "
    "maleate tartrate sulfate succinate acid anhydrous monohydrate reference test formulation week "
    "hours hour visit phase cohort overall".split()
)
_STOPS: Final = frozenset(
    "in after when following with during on at from under versus vs while and".split()
)


def _unknown_subject(title: str, own: set[str]) -> bool:
    """True when the words after the last 'of' or 'for' of a title include a name that is neither
    the drug nor ordinary vocabulary (so the value may be about another substance)."""
    bare = re.sub(r"\([^)]*\)", " ", title)
    toks = _tokens(bare)
    cut = max((i for i, t in enumerate(toks) if t in ("of", "for")), default=-1)
    if cut < 0:
        return False
    rest: list[str] = []
    for t in toks[cut + 1 :]:
        if t in _STOPS:
            break
        rest.append(t)
    own_tokens = {w for n in own for w in _tokens(n)}
    return any(
        len(t) > 2 and not t.isdigit() and t not in _FILLER and t not in own_tokens for t in rest
    )


def _classify(
    title: str, arm_drugs: set[str], single_arm: bool, drug_key: str, table: IdentityTable
) -> AnalyteClass:
    toks = set(_tokens(title))
    named = set(table.drugs_in(title))
    if toks & _METAB_TOKENS or any(
        _compact(m) in _compact(title) for m in table.by_key[drug_key].metabolites if m
    ):
        return "metabolite"
    if any(_compact(p) in _compact(title) for p in table.by_key[drug_key].prodrugs if p):
        return "prodrug"
    others = named - {drug_key}
    if named and drug_key not in named:
        return "combination_partner"
    if drug_key in named and others:
        return "unconfirmed"
    own = set(table.by_key[drug_key].names | table.by_key[drug_key].codes)
    if _unknown_subject(title, own):
        return "unconfirmed"
    if re.search(r"\b[a-z]{1,5}[ -]?\d{3,}\b", title.lower()) and drug_key not in named:
        return "unconfirmed"
    if re.search(r"\b(?:r|s)\b", title.lower()) and re.search(r"\(\s*[rs+-]\s*\)", title.lower()):
        return "enantiomer"
    if {"unbound", "free"} & toks:
        return "parent_unbound"
    if drug_key in named or (arm_drugs == {drug_key} and single_arm):
        return "parent"
    return "unspecified"


def read_ctgov(
    study: dict[str, Any], drug_key: str, table: IdentityTable, stats: ReaderStats
) -> list[Candidate]:
    proto = study["protocolSection"]
    nct = proto["identificationModule"]["nctId"]
    st = proto.get("statusModule", {})
    updated = st.get("lastUpdatePostDate") or st.get("lastUpdateSubmitDate", "")
    ai = proto.get("armsInterventionsModule", {})
    arms: list[dict[str, Any]] = ai.get("armGroups", [])
    intervs: dict[str, dict[str, Any]] = {i["name"]: i for i in ai.get("interventions", [])}
    elig = proto.get("eligibilityModule", {})
    ages = set(elig.get("stdAges", []))
    healthy = elig.get("healthyVolunteers")
    study_others = [
        n for n in intervs if drug_key not in table.drugs_in(n) and "placebo" not in n.lower()
    ]
    other_name_set = frozenset(
        {
            *study_others,
            *PARTNERS,
            *(x for k in table.by_key.values() for x in k.names if k.drug_key != drug_key),
        }
    )
    out: list[Candidate] = []
    for oi, om in enumerate(study["resultsSection"]["outcomeMeasuresModule"]["outcomeMeasures"], 1):
        center = _CENTER.get(om.get("paramType", ""))
        unit = om.get("unitOfMeasure", "")
        title = om.get("title", "")
        parameter = parameter_from_structure(title, unit)
        if parameter is None:
            continue
        stats.seen += 1
        if center is None:
            stats.skip("not_mean_geomean_or_median")
            continue
        if any(p in _compact(f"{title} {om.get('description', '')}") for p in _POP):
            stats.skip("population_pk_output")
            continue
        groups = {g["id"]: g for g in om.get("groups", [])}
        counts = {
            c["groupId"]: c["value"] for d in om.get("denoms", [])[:1] for c in d.get("counts", [])
        }
        classes = om.get("classes", [])
        for ci, cls in enumerate(classes):
            for ki, cat in enumerate(cls.get("categories", [])):
                for meas in cat.get("measurements", []):
                    g = groups.get(meas.get("groupId", ""))
                    try:
                        value = float(str(meas.get("value")).replace(",", ""))
                    except ValueError:
                        stats.skip("no_number_or_group")
                        continue
                    if g is None:
                        stats.skip("no_number_or_group")
                        continue
                    arm = _arm_for(g.get("title", ""), arms)
                    arm_names: list[str] = [
                        n.split(":", 1)[-1].strip()
                        for n in (arm or {}).get("interventionNames", [])
                    ]
                    arm_drugs = {k for n in arm_names for k in table.drugs_in(n)}
                    real = [n for n in arm_names if "placebo" not in n.lower()]
                    single_arm = len(real) == 1 and arm_drugs == {drug_key}
                    label = f"{title} {cls.get('title', '')} {cat.get('title', '')}"
                    analyte = _classify(label, arm_drugs, single_arm, drug_key, table)
                    head_toks = set(_tokens(title + " " + g.get("title", "")))
                    if (
                        analyte in ("parent", "unspecified")
                        and drug_key not in table.drugs_in(title + " " + g.get("title", ""))
                        and any(
                            {w for w in _tokens(n) if len(w) > 2} <= head_toks for n in study_others
                        )
                    ):
                        analyte = "unconfirmed"
                    gtext = f"{g.get('title', '')} {g.get('description', '')}"
                    toks = set(_tokens(gtext + " " + (arm or {}).get("label", "")))
                    clean = re.sub(r"[^.;()]*placebo[^.;()]*", " ", gtext, flags=re.I)
                    named_here = set(table.drugs_in(clean)) | arm_drugs
                    other_active = named_here - {drug_key}
                    real_other = [
                        n
                        for n in arm_names
                        if "placebo" not in n.lower() and drug_key not in table.drugs_in(n)
                    ]
                    ctoks = set(_tokens(clean))
                    named_study_other = [
                        n for n in study_others if {w for w in _tokens(n) if len(w) > 2} <= ctoks
                    ]
                    inter = bool(other_active) or bool(real_other) or bool(named_study_other)
                    inter = inter or bool(table.partners_in(clean))
                    form = "unspecified"
                    ftoks = toks | set(_tokens(" ".join(arm_names)))
                    if {"fixed", "fdc"} & ftoks or ("combination" in ftoks and "tablet" in ftoks):
                        form = "fixed_dose_combination"
                    elif {
                        "extended",
                        "modified",
                        "sustained",
                        "prolonged",
                        "depot",
                        "transdermal",
                        "patch",
                        "xr",
                        "sr",
                        "er",
                        "cr",
                    } & ftoks:
                        form = "modified_release"
                    elif {"solution", "suspension", "syrup", "liquid", "drops"} & ftoks:
                        form = "solution"
                    elif {"tablet", "tablets", "capsule", "capsules"} & ftoks:
                        form = "immediate_release"
                    food = (
                        "fed"
                        if {"fed", "meal", "breakfast"} & toks or "highfat" in _compact(gtext)
                        else "fasted"
                        if {"fasted", "fasting"} & toks
                        else "unspecified"
                    )
                    if toks & {
                        "children",
                        "child",
                        "pediatric",
                        "paediatric",
                        "adolescents",
                        "infants",
                        "neonates",
                        "elderly",
                        "renal",
                        "hepatic",
                        "impairment",
                        "cirrhosis",
                    }:
                        pop = "special"
                    elif "healthy" in toks or (
                        healthy is True
                        and ages <= {"ADULT", "OLDER_ADULT"}
                        and "patients" not in toks
                    ):
                        pop = "healthy_adult"
                    elif (
                        "patients" in toks
                        or "patient" in toks
                        or "participants with" in " ".join(_tokens(gtext))
                    ):
                        pop = "patients"
                    elif ages and ages <= {"CHILD"}:
                        pop = "special"
                    else:
                        pop = "unspecified"
                    sex = (
                        "female"
                        if {"women", "female"} & toks and not {"men", "male"} & toks
                        else "male"
                        if {"men", "male"} & toks and not {"women", "female"} & toks
                        else "all"
                    )
                    species = "animal" if (toks | set(_tokens(title))) & _ANIMALS else "human"
                    ttoks = set(_tokens(title + " " + gtext))
                    jt = " ".join(_tokens(title + " " + gtext))
                    regimen = _regimen(ttoks, jt)
                    route = _route(ttoks)
                    if route == "other":
                        form = "other_route"
                    arm_tag = next(
                        (t for t in ("test", "reference", "crossover") if t in toks), None
                    )
                    gl = _tokens(g.get("title", ""))
                    for i, t in enumerate(gl[:-1]):
                        if t in ("treatment", "period", "sequence") and len(gl[i + 1]) <= 3:
                            arm_tag = f"{t} {gl[i + 1]}"
                    ctx = Context(
                        arm_tag,
                        ", ".join(sorted(other_active | set(real_other) | set(table.partners_in(clean))))
                        if inter
                        else None,
                        form, food, pop, sex, species, route, regimen,
                    )  # fmt: skip
                    dose = None
                    if parameter != "f":
                        own = set(table.by_key[drug_key].names | table.by_key[drug_key].codes)
                        dose = _dose_beside_name(gtext, own, other_name_set)
                        if dose is None:
                            ds = {d for _, d in _doses_in(_tokens(gtext))}
                            dose = next(iter(ds)) if len(ds) == 1 else None
                        if dose is None and arm is not None:
                            for n in arm_names:
                                if drug_key in table.drugs_in(n) and n in intervs:
                                    iv = intervs[n]
                                    dose = _dose_beside_name(
                                        f"{n} {iv.get('description', '')}", own
                                    )
                                    break
                    param = resolve_parameter(parameter, unit)
                    conv = to_canonical(param, value, unit)
                    if isinstance(conv, Refused):
                        stats.skip(conv.issue)
                        continue
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
                    multi = len(classes) > 1 or len(cls.get("categories", [])) > 1
                    where = f"{nct}#outcome-{oi}/{g['id']}" + (f"/c{ci}.{ki}" if multi else "")
                    n_raw = counts.get(g["id"])
                    out.append(
                        Candidate(
                            drug_key, "clinicaltrials_gov", nct, g["id"], where, param, value, unit,
                            stat, analyte, ctx, dose, int(float(n_raw)) if n_raw else None, "",
                            f"record last updated {updated}", None, (),
                        )
                    )  # fmt: skip
    return out


# --- DailyMed label text: a token stream, quantity first -------------------------------------------

_WORDS_NUM: Final = {
    "one": 1.0, "two": 2.0, "three": 3.0, "four": 4.0, "five": 5.0, "six": 6.0, "seven": 7.0,
    "eight": 8.0, "nine": 9.0, "ten": 10.0, "twelve": 12.0,
}  # fmt: skip
_TOK: Final = re.compile(r"\d+(?:\.\d+)?|[A-Za-zµμ∞•·][A-Za-z0-9µμ·•*]*|[/%.;<>≥≤\-–]")
_UNIT_TOK: Final = {
    "h", "hr", "hrs", "hour", "hours", "min", "minute", "minutes", "day", "days", "l", "ml", "%",
}  # fmt: skip


def _lex(text: str) -> list[str]:
    return _TOK.findall(text)


def _read_unit(toks: list[str], i: int) -> tuple[str, int] | None:
    """A unit made of tokens at i: 'ng h / mL', 'mL / min / kg', 'hours', '%'. (text, next index)."""
    parts: list[str] = []
    j = i
    while j < len(toks):
        t = toks[j]
        low = t.lower()
        if low in ("/",) and parts and j + 1 < len(toks):
            parts.append("/")
        elif re.fullmatch(
            r"(?:ng|mcg|ug|µg|mg|g|pg|l|ml|dl|h|hr|hrs|hour|hours|min|minute|minutes|day|days|kg|%|[a-z]+[·•*][a-z]+)",
            low,
        ):
            if (
                parts
                and parts[-1] not in ("/",)
                and not (low in ("h", "hr") and parts[-1] in ("ng", "mcg", "ug", "µg", "pg"))
            ):
                break
            parts.append(t)
        else:
            break
        j += 1
    if not parts or parts[-1] == "/":
        return None
    text = "".join(
        p if p == "/" else (" " + p if k and parts[k - 1] != "/" else p)
        for k, p in enumerate(parts)
    )
    return text.replace(" ", "*"), j


_PARAM_WORDS: Final[list[tuple[str, tuple[str, ...]]]] = [
    ("cl_f", ("clf", "apparentoralclearance", "apparentclearance", "oralclearance", "apparenttotalclearance")),
    ("v_f", ("vf", "vzf", "apparentvolume")),
    ("vss", ("vss", "steadystatevolume")),
    ("cl", ("clearance",)),
    ("vd", ("volumeofdistribution", "vd", "vz")),
    ("t_half", ("halflife", "t12", "thalf")),
    ("tmax", ("tmax", "timetopeak", "timetomaximum", "peakplasmaconcentration", "peakplasmaconcentrations", "peakconcentration", "peakconcentrations")),
    ("cmax", ("cmax", "maximumconcentration", "maximumplasmaconcentration", "peakplasma")),
    ("auc_inf", ("aucinf", "auc0inf", "auc0infinity", "aucinfinity")),
    ("auc_tau", ("auctau", "auc012", "auc024", "auc08", "auc06")),
    ("auc_last", ("auclast", "auc0t")),
    ("f", ("bioavailability",)),
]  # fmt: skip
_FAM: Final = {
    "cl_f": "cl", "cl": "cl", "v_f": "v", "vss": "v", "vd": "v", "t_half": "time", "tmax": "time",
    "cmax": "conc", "auc_inf": "auc", "auc_tau": "auc", "auc_last": "auc", "f": "pct",
}  # fmt: skip


def _word_before(toks: list[str], i: int, family: str) -> str | None:
    """The nearest parameter word of the unit's family before token i, within one sentence."""
    window = toks[max(0, i - 40) : i]
    for cut in range(len(window) - 1, -1, -1):
        if window[cut] in (".", ";"):
            window = window[cut + 1 :]
            break
    best: tuple[int, str] | None = None
    comp = [t.lower() for t in window]
    for end in range(len(comp), 0, -1):
        for span in range(1, 5):
            if end - span < 0:
                break
            c = "".join(re.sub(r"[^a-z0-9]", "", x) for x in comp[end - span : end])
            for name, words in _PARAM_WORDS:
                if _FAM[name] == family and c in words:
                    if best is None or end > best[0]:
                        best = (end, name)
        if best:
            return best[1]
    return None


def _family(unit_text: str) -> str:
    u = parse_unit(unit_text)
    if u is None:
        return ""
    mass, length, time, body, _ = u.dim
    if (mass, length, time) == (1, -3, 1):
        return "auc"
    if (mass, length, time) == (1, -3, 0):
        return "conc"
    if (mass, length, time) == (0, 3, -1):
        return "cl"
    if (mass, length, time) == (0, 3, 0):
        return "v"
    if (mass, length, time, body) == (0, 0, 1, 0):
        return "time"
    if u.dim == (0, 0, 0, 0, 0):
        return "pct"
    return ""


def read_label(
    doc: dict[str, Any],
    tables: dict[str, dict[str, Any]],
    set_id: str,
    drug_key: str,
    table: IdentityTable,
    stats: ReaderStats,
) -> list[Candidate]:
    version = f"label version {doc['version']}, effective {doc['effective']}"
    base = f"dailymed:{set_id}/version-{doc['version']}/effective-{doc['effective']}"
    out: list[Candidate] = []
    own = set(table.by_key[drug_key].names | table.by_key[drug_key].codes)
    for pi, p in enumerate(doc["paras"]):
        if not p["title"].startswith("12.3"):
            continue
        toks = _lex(p["text"])
        i = 0
        while i < len(toks):
            t = toks[i]
            lowt = t.lower()
            if not (re.fullmatch(r"\d+(?:\.\d+)?", t) or lowt in _WORDS_NUM):
                i += 1
                continue
            n1 = float(t) if lowt not in _WORDS_NUM else _WORDS_NUM[lowt]
            j = i + 1
            n2: float | None = None
            if j + 1 < len(toks) and (toks[j].lower() in ("to", "-", "–", "and")):
                nxt = toks[j + 1]
                if re.fullmatch(r"\d+(?:\.\d+)?", nxt) or nxt.lower() in _WORDS_NUM:
                    n2 = float(nxt) if nxt.lower() not in _WORDS_NUM else _WORDS_NUM[nxt.lower()]
                    j += 2
            ru = _read_unit(toks, j)
            if ru is None:
                i += 1
                continue
            unit, k = ru
            fam = _family(unit)
            param = _word_before(toks, i, fam) if fam else None
            if param is None:
                i = k
                continue
            sent_start = max((x for x in range(i) if toks[x] in (".", ";")), default=-1) + 1
            sent_end = next((x for x in range(k, len(toks)) if toks[x] in (".", ";")), len(toks))
            sent_toks = toks[sent_start:sent_end]
            sent_text = " ".join(sent_toks)
            before = toks[max(sent_start, i - 14) : i]
            before_text = " ".join(before)
            prev = " ".join(toks[max(sent_start, i - 1) : i]).lower()
            bound = (
                prev in ("less than", "than")
                and "less" in " ".join(toks[max(sent_start, i - 3) : i]).lower()
            )
            bound = bound or toks[i - 1] in ("<", "≤") if i else bound
            if bound:
                stats.skip("upper_bound")
                i = k
                continue
            lower = bool(re.search(r"(?:greater|more) than$|at least$|[>≥]$", before_text.lower()))
            analyte = _classify(before_text, {drug_key}, True, drug_key, table)
            two = "respectively" in sent_text.lower() or bool(
                {"m1", "m2", "m3", "metabolite", "metabolites"} & {x.lower() for x in sent_toks}
            )
            if two:
                analyte = "unconfirmed"
            elif analyte == "unspecified":
                analyte = "parent"
            value = (n1 * n2) ** 0.5 if n2 and n2 > n1 else n1
            param = resolve_parameter(param, unit)
            conv = to_canonical(param, value, unit)
            if isinstance(conv, Refused):
                stats.skip(conv.issue)
                i = k
                continue
            ctxt = {x.lower() for x in sent_toks}
            if {"creatinine", "renal", "dialysis", "nonrenal", "crcl", "hepatic"} & {
                x.lower() for x in toks[max(sent_start, i - 8) : i]
            } and param.startswith("cl"):
                stats.skip("renal_or_creatinine_clearance")
                i = k
                continue
            form = (
                "modified_release"
                if {"extended", "modified", "sustained", "prolonged", "delayed", "depot"} & ctxt
                else "solution"
                if {"solution", "suspension", "syrup"} & ctxt
                else "immediate_release"
                if {"tablet", "tablets", "capsule", "capsules"} & ctxt
                else "unspecified"
            )
            ctx = Context(
                None,
                None,
                "other_route" if _route(ctxt) == "other" else form,
                "fed" if {"fed", "meal", "food", "breakfast"} & ctxt else "fasted" if {"fasted", "fasting"} & ctxt else "unspecified",
                "special" if {"children", "pediatric", "elderly", "renal", "hepatic", "impairment"} & ctxt
                else "healthy_adult" if "healthy" in ctxt else "unspecified",
                "all", "human",
                _route(ctxt),
                _regimen(ctxt, " ".join(x.lower() for x in sent_toks)),
            )  # fmt: skip
            dose = None
            if param in ("cmax", "auc_inf", "auc_tau", "auc_last"):
                dose = _dose_beside_name(sent_text, own)
                if dose is None:
                    ds = {d for _, d in _doses_in([x.lower() for x in _tokens(sent_text)])}
                    dose = next(iter(ds)) if len(ds) == 1 else None
            spread = ("range", n1, n2) if n2 and n2 > n1 else ("none", None, None)
            out.append(
                Candidate(
                    drug_key, "dailymed_spl", set_id, "", f"{base}#12.3-p{pi}", param, value, unit,
                    Stat(value, "unspecified", spread[0], spread[1], spread[2]),  # type: ignore[arg-type]
                    analyte, ctx, dose, None, "", version, None, (("bound",) if lower else ()),
                )
            )  # fmt: skip
            i = k
    for tid, tb in sorted(tables.items()):
        if tb.get("title", "").startswith("12"):
            out += _grid_candidates(tb, tid, base, set_id, version, drug_key, table, stats)
    for tid, tb in sorted(tables.items()):
        if tb.get("title", "").startswith("12"):
            out += _grid_candidates(tb, tid, base, set_id, version, drug_key, table, stats)
    return out


_NUMCELL: Final = re.compile(r"^\s*(\d+(?:\.\d+)?)")


def _grid_candidates(
    tb: dict[str, Any],
    tid: str,
    base: str,
    set_id: str,
    version: str,
    drug_key: str,
    table: IdentityTable,
    stats: ReaderStats,
) -> list[Candidate]:
    """A table as a grid: header rows are the rows above the first row with a numeric cell; the
    parameter comes from the row label's words and the unit from its brackets; the dose and the
    population come from the column's header cells and the caption."""
    grid: list[list[str]] = tb["grid"]
    caption = f"{tb.get('caption', '')} {tb.get('prev_para', '')}"
    ctoks = {t.lower() for t in _tokens(caption)}
    center: Center = (
        "geometric"
        if "geometric" in ctoks
        else "median"
        if "median" in ctoks
        else "arithmetic"
        if "mean" in ctoks
        else "unspecified"
    )
    own = set(table.by_key[drug_key].names | table.by_key[drug_key].codes)
    n_head = 0
    for r, row in enumerate(grid):
        if r > 0 and any(_NUMCELL.match(c) for c in row[1:]):
            n_head = r
            break
    else:
        return []
    out: list[Candidate] = []
    for r in range(n_head, len(grid)):
        row = grid[r]
        label = row[0]
        bracket = re.search(r"\(([^()]*)\)", label)
        if bracket is None:
            continue
        unit_toks = _lex(bracket.group(1))
        ru = _read_unit(unit_toks, 0)
        if ru is None or ru[1] != len(unit_toks):
            continue
        unit = ru[0]
        fam = _family(unit)
        label_toks = _lex(re.sub(r"\(.*?\)", " ", label))
        words = _word_before(label_toks, len(label_toks), fam)
        if not fam or words is None:
            continue
        param = words
        analyte = _classify(label, {drug_key}, True, drug_key, table)
        if analyte == "unspecified":
            analyte = "parent"
        for c in range(1, len(row)):
            m = _NUMCELL.match(row[c])
            if m is None:
                continue
            value = float(m.group(1))
            header_toks = {
                t.lower()
                for h in range(n_head)
                if c < len(grid[h])
                for t in _tokens(grid[h][c] + " " + caption)
            }
            food_toks = {
                t.lower() for h in range(n_head) if c < len(grid[h]) for t in _tokens(grid[h][c])
            }
            conv = to_canonical(resolve_parameter(param, unit), value, unit)
            if isinstance(conv, Refused):
                stats.skip(conv.issue)
                continue
            head_text = " ".join(grid[h][c] for h in range(n_head) if c < len(grid[h]))
            dose = None
            if param in ("cmax", "auc_inf", "auc_tau", "auc_last"):
                dose = _dose_beside_name(head_text + " " + caption, own)
                if dose is None:
                    ds = {
                        d
                        for _, d in _doses_in(
                            [t.lower() for t in _tokens(head_text + " " + caption)]
                        )
                    }
                    dose = next(iter(ds)) if len(ds) == 1 else None
            form = (
                "modified_release"
                if {"extended", "modified", "sustained", "prolonged", "delayed"} & header_toks
                else "immediate_release"
                if {"tablet", "tablets", "capsule", "capsules"} & header_toks
                else "unspecified"
            )
            ctx = Context(
                next((t for t in ("test", "reference", "crossover") if t in header_toks), None),
                None,
                "other_route" if _route(header_toks) == "other" else form,
                "fed" if {"fed", "meal", "breakfast"} & food_toks else "fasted" if {"fasted", "fasting"} & food_toks else "unspecified",
                "special" if {"children", "pediatric", "elderly", "renal", "hepatic", "impairment"} & header_toks
                else "healthy_adult" if "healthy" in header_toks
                else "patients" if "patients" in header_toks else "unspecified",
                "all", "human", _route(header_toks),
                _regimen(header_toks, " ".join(_tokens(head_text + " " + caption)).lower()),
            )  # fmt: skip
            out.append(
                Candidate(
                    drug_key, "dailymed_spl", set_id, f"c{c}", f"{base}#{tid.split('#')[-1]}/r{r}c{c}",
                    resolve_parameter(param, unit), value, unit,
                    Stat(value, center, "none"), analyte, ctx, dose, None, "", version, None, (),
                )
            )  # fmt: skip
    return out
