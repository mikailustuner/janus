"""Strict publication check for confirmed ClinicalTrials.gov values (selective prediction).

A third, separate check that runs after the two readers agree. It does not read values; it reads the
record's structure (interventions, the result group, the outcome measure) and abstains whenever the
context of a confirmed value is not plain: another agent in the record, words that point to another
analyte, matrix, clearance type, transformed value, special population, release-modifying product,
non-oral non-intravenous route, combination or body-size dosing, or a regimen cue that contradicts the
claimed regimen. It shares no code with reader A or reader B (only the identity table and `norm`).

Each rule has a code; `check` returns the codes of the rules a value fails, and `tier` maps them to the
pre-registered levels (precision-coverage study, `docs` of the model kit). Research use only. Not for
clinical decisions.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import replace
from typing import Any, Final

from janus_pipelines.modelkit.confirm import Confirmation
from janus_pipelines.modelkit.formref import BrandTable
from janus_pipelines.modelkit.pairing import Paired
from janus_pipelines.modelkit.resolver import IdentityTable, norm

_DRUGLIKE: Final = frozenset(
    {"DRUG", "BIOLOGICAL", "COMBINATION_PRODUCT", "DIETARY_SUPPLEMENT", "GENETIC"}
)
_PLACEBO: Final = re.compile(r"\b(placebo|vehicle|sham|saline|no (?:treatment|intervention))\b")


def _rx(*words: str) -> re.Pattern[str]:
    return re.compile(r"(?<![a-z0-9])(?:" + "|".join(words) + r")(?![a-z0-9])")


# Patterns run on `norm` text (lower case, dashes as spaces).
_ANALYTE: Final = _rx(
    r"metabolites?", "total", "unbound", "free", r"enantiomers?", "racemic", "racemate",
    r"\([rs+-]\)", r"(?<!')[rs] (?=[a-z]{4})",
    r"glucuronides?", r"hydroxy\w*", r"\w*desmethyl\w*", r"conjugat\w*", r"m\d{1,2}", "active moiety",
    "sum", "parent and", r"\w*ide metabolite",
)  # fmt: skip
_MATRIX: Final = _rx(
    "urine", "urinary", "csf", "cerebrospinal", r"dialys\w*", "dialysate", r"hemodialys\w*", "milk",
    "intracellular", "pbmcs?", "tissue", "saliva", "dried blood", "epithelial", "elf", "sputum", "semen",
    "bile", "feces", "faeces", "intraperitoneal", "peritoneal", "vitreous", "aqueous humor", "emptying",
    "transit",
)  # fmt: skip
_CLEARANCE_TYPE: Final = _rx(
    r"renal", "creatinine", "clr", "cl r", "glomerular", "hepatic clearance"
)
_TRANSFORM: Final = _rx(
    "ln", "log", r"log\w*", "ratio", "percent", "percentage", "change", "dose normali[sz]ed",
    "normali[sz]ed", "geometric mean ratio", "relative", "fold", "difference", "accumulation",
    "predicted", "simulated", "model based", "population pk", "poppk",
)  # fmt: skip
_POPULATION: Final = _rx(
    "impairment", "impaired", "child pugh", "esrd", "end stage", "pediatric", "paediatric", "children",
    "child", "infants?", r"neonat\w*", "adolescents?", "elderly", "older", "obese", "obesity", "pregnan\\w*",
    "poor metabo\\w*", "cirrhosis",
)  # fmt: skip
_PRODUCT: Final = _rx(
    "extended", "prolonged", "sustained", "controlled", "delayed", "modified", "xr", "er", "sr", "cr",
    "xl", "la", "depot", "long acting", "patch", "transdermal", "cream", "gel", "ointment", "topical",
    r"inhal\w*", "nasal", "intranasal", "intramuscular", "im", "subcutaneous", "sc", "subq", "s c",
    "ophthalmic", "rectal", "vaginal", "intrathecal", "buccal", "sublingual", r"liposom\w*",
    r"nanoparticles?", "crushed", "chewed", "implant", "microspheres?", "pellet",
)  # fmt: skip
_COMBINATION: Final = re.compile(
    r"\+|(?<=[a-z])\s*/\s*(?=[a-z]{3})(?!(?:kg|day|dose|week|hour|min)\b)|(?<![a-z0-9])(?:plus|combination|combined"
    r"|cocktail|fixed dose|fdc|co ?administ\w*|coadminist\w*|together with|in addition to)(?![a-z0-9])"
)
_ENANTIOMER_PREFIX: Final = ("dextro", "levo", "dex", "lev", "es", "ar")
# Iteration 2 (after the first fresh sample): pharmacodynamic read-outs, model estimates, the cell naming
# another parameter.
_PD: Final = _rx(
    "5 ht", "serotonin", "inhibition", r"t ?e ?max", "emax", "effect", "receptor", "occupancy", "proteasome",
    "biomarker", "activity", "response",
)  # fmt: skip
_MODEL: Final = re.compile(
    r"(?<!non )(?<!non)compartment(?:al)? (?:model|analysis|fit)|\bnlme\b|nonlinear mixed|population (?:pk|pharmacokinetic)"
    r"|model (?:based|estimated|derived|predicted)|\bfitted\b|\bmodell?ing\b|adjusted (?:geometric )?mean"
)
_PARAM_WORDS: Final = {
    "t_half": re.compile(r"half ?life|t ?half|t ?1/2|t1 2|\bt 1 2\b"),
    "tmax": re.compile(r"\bt ?max\b|time to (?:maximum|peak)"),
    "cmax": re.compile(
        r"\bc ?max\b|maximum (?:observed )?(?:plasma |serum )?concentration|peak (?:plasma |serum )?concentration"
    ),
    "auc": re.compile(r"\bauc|area under"),
    "cl": re.compile(r"clearance|\bcl\b"),
    "v": re.compile(r"volume|\bv ?z\b|\bvss\b|\bv ?d\b"),
}
_PARAM_GROUP: Final = {
    "t_half": "t_half", "tmax": "tmax", "cmax": "cmax", "auc_inf": "auc", "auc_last": "auc", "auc_tau": "auc",
    "cl": "cl", "cl_f": "cl", "cl_per_kg": "cl", "vss": "v", "vd": "v", "vd_per_kg": "v", "v_f": "v",
}  # fmt: skip
_PER_SIZE: Final = re.compile(r"mg\s*/\s*(?:m2|m 2|m²|kg)|per (?:m2|kg|square)|/\s*kg\b|mg/m")
_SINGLE_CUE: Final = re.compile(
    r"single dose|single oral dose|single iv dose|\bday 1\b(?! (?:to|through|and))"
)
_MULTI_CUE: Final = re.compile(
    r"steady state|multiple dose|multiple doses|repeated|once daily for|twice daily|\bbid\b|\bqd\b|\btid\b"
    r"|daily for|\bcycle \d+ day (?!1\b)\d+|\bday (?:[2-9]|\d{2,})\b"
)

PUBLISHABLE_FORMS: Final = frozenset({"immediate_release", "solution"})
PUBLISHABLE_ROUTES: Final = frozenset({"oral", "iv"})

# Pre-registered levels: a value is at level L if it fails no rule of levels 1..L.
LEVELS: Final = {
    1: frozenset({"cell_names_other_parameter", "analyte_word", "matrix_word", "clearance_type_word", "transform_word", "population_word", "other_drug_named", "drug_not_named", "racemate_or_sibling_named"}),
    2: frozenset({"product_word", "combination_word", "per_size_dose", "regimen_conflict", "route_not_plain", "coadministered_claimed"}),
    3: frozenset({"not_single_agent_group"}),
    4: frozenset({"form_not_plain"}),
    5: frozenset({"not_single_agent_record"}),
}  # fmt: skip


def _locate(study: dict[str, Any], locator: str) -> tuple[dict[str, Any], dict[str, Any]] | None:
    m = re.match(r"NCT\d+#outcome-(\d+)/(OG\d+)", locator)
    if not m:
        return None
    measures = (
        study.get("resultsSection", {}).get("outcomeMeasuresModule", {}).get("outcomeMeasures", [])
    )
    i = int(m.group(1)) - 1
    if not 0 <= i < len(measures):
        return None
    om = measures[i]
    groups = [g for g in om.get("groups", []) if g.get("id") == m.group(2)]
    return (om, groups[0]) if groups else None


def _agents(study: dict[str, Any], table: IdentityTable) -> list[list[str]]:
    """For every drug-like intervention that is not a placebo: the pool drugs its names resolve to."""
    arms = study.get("protocolSection", {}).get("armsInterventionsModule", {})
    out: list[list[str]] = []
    for iv in arms.get("interventions", []):
        if iv.get("type") not in _DRUGLIKE:
            continue
        text = " ; ".join([iv.get("name", ""), *iv.get("otherNames", [])])
        if _PLACEBO.search(norm(iv.get("name", ""))):
            continue
        out.append(table.drugs_in(text))
    return out


def _group_agents(
    study: dict[str, Any], group: dict[str, Any], table: IdentityTable
) -> list[list[str]] | None:
    """Agents of the one arm whose label matches the group title (None if no single arm matches)."""
    arms = study.get("protocolSection", {}).get("armsInterventionsModule", {})
    title = norm(group.get("title", ""))
    hits = [
        a
        for a in arms.get("armGroups", [])
        if (lab := norm(a.get("label", "")))
        and (lab == title or (len(lab) > 3 and (lab in title or title in lab)))
    ]
    if len(hits) != 1:
        return None
    out: list[list[str]] = []
    for name in hits[0].get("interventionNames", []):
        kind, _, bare = name.partition(":")
        if kind.strip().upper().replace(" ", "_") not in _DRUGLIKE or _PLACEBO.search(norm(bare)):
            continue
        out.append(table.drugs_in(bare))
    return out


def _other_intervention_named(
    study: dict[str, Any], drug_key: str, text: str, table: IdentityTable
) -> bool:
    """The text names a drug-like intervention of the record that is not the drug."""
    arms = study.get("protocolSection", {}).get("armsInterventionsModule", {})
    for iv in arms.get("interventions", []):
        if iv.get("type") not in _DRUGLIKE:
            continue
        name = norm(iv.get("name", ""))
        if _PLACEBO.search(name) or table.drugs_in(name) == [drug_key] or len(name) < 4:
            continue
        if drug_key in table.drugs_in(name):
            continue  # a product that contains the drug is caught by the combination words
        if re.search(r"(?<![a-z0-9])" + re.escape(name) + r"(?![a-z0-9])", text):
            return True
    return False


def _cell_titles(om: dict[str, Any], locator: str) -> str:
    """Class and category titles of the measurement the locator points at ('/c<class>.<category>')."""
    m = re.search(r"/c(\d+)\.(\d+)$", locator)
    classes = om.get("classes", [])
    if not m or int(m.group(1)) >= len(classes):
        return ""
    c = classes[int(m.group(1))]
    cats = c.get("categories", [])
    cat = cats[int(m.group(2))].get("title", "") if int(m.group(2)) < len(cats) else ""
    return " . ".join([c.get("title", ""), cat])


def _drug_product_modified(
    study: dict[str, Any], drug_key: str, table: IdentityTable, brands: BrandTable | None
) -> bool:
    """An intervention naming the drug is described with a release-modifying or non-oral word, or names
    a marketed product of the drug whose directory class is not immediate release or solution."""
    arms = study.get("protocolSection", {}).get("armsInterventionsModule", {})
    mr: set[str] = set()
    if brands is not None:
        mr = {
            norm(p.brand)
            for p in brands.products(drug_key)
            if p.form_class not in PUBLISHABLE_FORMS
        }
    for iv in arms.get("interventions", []):
        names = " ; ".join([iv.get("name", ""), *iv.get("otherNames", [])])
        if drug_key not in table.drugs_in(names):
            continue
        text = norm(names + " . " + (iv.get("description") or ""))
        if _PRODUCT.search(text) or any(
            re.search(rf"(?<![a-z0-9]){re.escape(b)}(?![a-z0-9])", text) for b in mr if b
        ):
            return True
    return False


def _racemate_only(study: dict[str, Any], drug_key: str, text: str) -> bool:
    """A single-enantiomer drug (esomeprazole, levocetirizine ...) whose texts name only the racemate."""
    key = norm(drug_key)
    prefix = next(
        (p for p in _ENANTIOMER_PREFIX if key.startswith(p) and len(key) - len(p) >= 5), None
    )
    if prefix is None:
        return False
    arms = study.get("protocolSection", {}).get("armsInterventionsModule", {})
    names = " . ".join(norm(i.get("name", "")) for i in arms.get("interventions", []))
    full = text + " . " + names
    base = key[len(prefix) :]
    return (
        key not in full.replace(" ", "")
        and re.search(rf"(?<![a-z]){re.escape(base)}", full) is not None
    )


def check(
    study: dict[str, Any],
    drug_key: str,
    locator: str,
    formulation: str,
    route: str,
    regimen: str,
    table: IdentityTable,
    dose_claimed: bool = True,
    coadministered: bool = False,
    parameter: str = "",
    brands: BrandTable | None = None,
) -> tuple[str, ...]:
    """Codes of the strict rules this confirmed value fails (empty = passes every level)."""
    found = _locate(study, locator)
    if found is None:
        return ("not_located",)
    om, group = found
    outcome = norm(
        " . ".join([om.get("title", ""), om.get("description", ""), _cell_titles(om, locator)])
    )
    gtext = norm(" . ".join([group.get("title", ""), group.get("description", "")]))
    both = outcome + " . " + gtext
    fails: list[str] = []
    if _ANALYTE.search(outcome) or _PD.search(outcome):
        fails.append("analyte_word")
    cells = norm(_cell_titles(om, locator))
    group_of = _PARAM_GROUP.get(parameter)
    if group_of and any(rx.search(cells) for g, rx in _PARAM_WORDS.items() if g != group_of):
        fails.append("cell_names_other_parameter")
    if _MATRIX.search(both):
        fails.append("matrix_word")
    if _CLEARANCE_TYPE.search(outcome):
        fails.append("clearance_type_word")
    if _TRANSFORM.search(outcome) or _MODEL.search(outcome):
        fails.append("transform_word")
    ages = study.get("protocolSection", {}).get("eligibilityModule", {}).get("stdAges", [])
    if _POPULATION.search(both) or "CHILD" in ages or ages == ["OLDER_ADULT"]:
        fails.append("population_word")
    named = table.drugs_in(both)
    if any(k != drug_key for k in named) or _other_intervention_named(study, drug_key, both, table):
        fails.append("other_drug_named")
    agents = _agents(study, table)
    if _racemate_only(study, drug_key, both):
        fails.append("racemate_or_sibling_named")
    if drug_key not in named and not (len(agents) == 1 and agents[0] == [drug_key]):
        fails.append(
            "drug_not_named"
        )  # neither the text nor a single-agent record ties it to the drug
    if _PRODUCT.search(both) or _drug_product_modified(study, drug_key, table, brands):
        fails.append("product_word")
    if _COMBINATION.search(gtext) or _COMBINATION.search(norm(om.get("title", ""))):
        fails.append("combination_word")
    if dose_claimed and (_PER_SIZE.search(gtext.replace(" ", "")) or _PER_SIZE.search(gtext)):
        fails.append("per_size_dose")
    if (regimen == "multiple" and _SINGLE_CUE.search(both)) or (
        regimen == "single" and _MULTI_CUE.search(both)
    ):
        fails.append("regimen_conflict")
    if coadministered:
        fails.append("coadministered_claimed")
    if route not in PUBLISHABLE_ROUTES:
        fails.append("route_not_plain")
    if formulation not in PUBLISHABLE_FORMS:
        fails.append("form_not_plain")
    record_single = bool(agents) and all(a == [drug_key] for a in agents)
    garms = _group_agents(study, group, table)
    if not record_single and (not garms or any(a != [drug_key] for a in garms)):
        fails.append("not_single_agent_group")
    if not record_single:
        fails.append("not_single_agent_record")
    return tuple(fails)


def level(fails: tuple[str, ...]) -> int:
    """Highest pre-registered level whose rules (and those of all lower levels) the value passes."""
    if "not_located" in fails:
        return 0
    got = 0
    for lv in sorted(LEVELS):
        if any(f in LEVELS[lv] for f in fails):
            break
        got = lv
    return got


# Shipped level (precision study, addendum 2): a confirmed value below it becomes unconfirmed.
PUBLISH_LEVEL: Final = 3


def apply(
    pairs: list[Paired],
    study: dict[str, Any],
    table: IdentityTable,
    brands: BrandTable,
    counts: Counter[str],
) -> list[Paired]:
    """Confirmed pairs of one study whose strict level is below PUBLISH_LEVEL become unconfirmed with
    reason `strict_check` and the failed rule codes; every other pair is returned unchanged."""
    out: list[Paired] = []
    for p in pairs:
        if not p.result.confirmed:
            out.append(p)
            continue
        a, ctx = p.a, p.a.context
        fails = check(
            study,
            a.drug_key,
            a.locator,
            ctx.formulation,
            ctx.route if ctx.route in PUBLISHABLE_ROUTES else "unknown",
            ctx.regimen if ctx.regimen in ("single", "multiple") else "unknown",
            table,
            a.dose_mg is not None,
            bool(ctx.coadministered),
            a.parameter,
            brands,
        )
        if level(fails) >= PUBLISH_LEVEL:
            counts["strict_check_passed"] += 1
            out.append(p)
            continue
        counts["strict_check_abstained"] += 1
        out.append(replace(p, result=Confirmation(False, "strict_check", fails)))
    return out
