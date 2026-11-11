"""Analyte and study-arm context resolver (spec model-kit, plan 6.1).

Names come from the committed identity file `data/modelkit/identity_m1.csv` (labels and aliases of the
Wikidata item of each drug, CC0, plus a short curated list of named metabolites and prodrugs). The
analyte of a value is one of: parent, parent_unbound, metabolite, enantiomer, total, prodrug,
combination_partner, unconfirmed (an unknown code), or unspecified (the text names no drug). Only
`parent` ever feeds a parent parameter set. The arm context (co-administered drug, food, formulation,
population, sex, species) is read from the arm or group text; an arm that gives another active drug
is interaction evidence only. Pure functions; no network. Research use only. Not for clinical decisions.
"""

from __future__ import annotations

import csv
import io
import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Literal

from janus_pipelines.modelkit.confirm import Context

AnalyteClass = Literal[
    "parent",
    "parent_unbound",
    "metabolite",
    "enantiomer",
    "total",
    "prodrug",
    "combination_partner",
    "unconfirmed",
    "unspecified",
]


def norm(text: str) -> str:
    """Lower case, accents removed, dashes and spaces unified."""
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"\s+", " ", t.replace("-", " ").replace("_", " ")).strip()


@dataclass(frozen=True)
class Identity:
    drug_key: str
    qid: str
    names: frozenset[str]  # normalised
    codes: frozenset[str]  # normalised company codes
    metabolites: frozenset[str]
    prodrugs: frozenset[str]


# Drugs that appear as combination partners or co-medications in PK studies. Not exhaustive: the
# identity table's own drugs are also known as "other drugs" when they are not the target.
PARTNERS: Final = frozenset(
    norm(x)
    for x in (
        "rilpivirine abacavir lamivudine tenofovir emtricitabine efavirenz ritonavir cobicistat "
        "darunavir atazanavir lopinavir raltegravir etravirine nevirapine zidovudine metformin "
        "sitagliptin linagliptin empagliflozin dapagliflozin ezetimibe atorvastatin simvastatin "
        "rosuvastatin pravastatin amlodipine hydrochlorothiazide chlorthalidone valsartan losartan "
        "olmesartan irbesartan lisinopril enalapril ramipril verapamil ketoconazole itraconazole "
        "fluconazole voriconazole posaconazole clarithromycin erythromycin rifampin rifampicin "
        "carbamazepine phenytoin phenobarbital midazolam omeprazole esomeprazole pantoprazole "
        "famotidine ranitidine digoxin warfarin aspirin acetylsalicylic ibuprofen paracetamol "
        "acetaminophen naproxen diclofenac celecoxib morphine codeine fentanyl buprenorphine "
        "naloxone naloxegol ondansetron granisetron aprepitant dexamethasone prednisone "
        "cyclosporine tacrolimus sirolimus everolimus imatinib gemcitabine cisplatin carboplatin "
        "paclitaxel docetaxel letrozole anastrozole tamoxifen alectinib osimertinib fluoxetine "
        "paroxetine sertraline quinidine bupropion probenecid cimetidine antacid sevelamer "
        "calcium iron magnesium aluminum fexofenadine colchicine dabigatran apixaban clopidogrel "
        "ticagrelor prasugrel insulin glimepiride glipizide pioglitazone sulfonylurea"
    ).split()
)

_METABOLITE_GENERIC: Final = re.compile(
    r"\bmetabolites?\b|\bactive moiety\b|\bglucuronides?\b|\bconjugates?\b|\bdes[a-z]*(?:methyl|ethyl|acetyl)"
    r"|\b[nos] ?(?:de)?(?:methyl|ethyl|acetyl|hydroxy|oxide)\b|\bhydroxy ?[a-z]{4,}|\bmetabolized to\b"
)
_ENANTIOMER: Final = re.compile(
    r"\((?:r|s|\+|-|\+/-|rs)\)|\b(?:r|s) ?(?:enantiomer|isomer)|\b(?:enantiomers?|stereoisomers?)\b"
    r"|\b(?:dextro|levo)[a-z]*|\b[dl] ?(?:methadone|threo)"
)
_UNBOUND: Final = re.compile(r"\b(?:unbound|free (?:drug|concentration|fraction|plasma))\b")
_TOTAL: Final = re.compile(r"\btotal\b[^.;]*(?:\+|\bplus\b|\band\b|\bsum\b)|\bsum of\b")
_CODE: Final = re.compile(r"\b[a-z]{1,5} ?\d{3,}[a-z]?\b")
_SPLIT: Final = re.compile(
    r"\b(?:when|following|after|in the presence|co ?administered|combined|plus|with)\b|\+"
)


class IdentityTable:
    def __init__(self, identities: list[Identity]) -> None:
        self.by_key = {i.drug_key: i for i in identities}
        self._names: dict[str, str] = {}
        for i in identities:
            for n in i.names | i.codes:
                self._names.setdefault(n, i.drug_key)
        alts = sorted(self._names, key=len, reverse=True)
        self._rx = re.compile(r"\b(?:" + "|".join(re.escape(a) for a in alts) + r")\b")

    @classmethod
    def from_csv(cls, text: str) -> IdentityTable:
        out: list[Identity] = []
        for r in csv.DictReader(io.StringIO(text)):

            def split(col: str, r: dict[str, str] = r) -> frozenset[str]:
                return frozenset(norm(x) for x in r[col].split("|") if x.strip())

            names = split("names") | {norm(r["drug_key"])}
            out.append(
                Identity(
                    r["drug_key"],
                    r["qid"],
                    names,
                    split("codes"),
                    split("metabolites"),
                    split("prodrugs"),
                )
            )
        return cls(out)

    def drugs_in(self, text: str) -> list[str]:
        """Drug keys named in the text (names, aliases, company codes), in order of appearance."""
        seen: list[str] = []
        for m in self._rx.finditer(norm(text)):
            k = self._names[m.group(0)]
            if k not in seen:
                seen.append(k)
        return seen

    def partners_in(self, text: str) -> list[str]:
        t = norm(text)
        return [p for p in sorted(PARTNERS) if re.search(rf"\b{re.escape(p)}\b", t)]

    def metabolite_hit(self, text: str, drug_key: str | None) -> bool:
        t = norm(text)
        ids = [self.by_key[drug_key]] if drug_key in self.by_key else list(self.by_key.values())
        return any(re.search(rf"\b{re.escape(m)}\b", t) for i in ids for m in i.metabolites if m)

    def prodrug_hit(self, text: str, drug_key: str) -> bool:
        i = self.by_key.get(drug_key)
        t = norm(text)
        return bool(i) and any(re.search(rf"\b{re.escape(p)}\b", t) for p in i.prodrugs if p)  # type: ignore[union-attr]


_GENERIC: Final = frozenset(
    "plasma serum blood the a an of for in on at by drug drugs study studies participants subjects "
    "patients treatment total parent part cycle day days dose doses single multiple oral after before "
    "during following when with without alone group arm period steady state healthy adult adults "
    "tablet tablets capsule capsules fasted fed mg ug g kg ml l h hr and or to from time zero last "
    "quantifiable concentration curve under area maximum observed peak concentrations hydrochloride "
    "hcl sodium mesylate besylate maleate tartrate sulfate succinate acid anhydrous monohydrate "
    "pharmacokinetic pharmacokinetics parameter parameters cmax auc tmax t12 half life clearance "
    "volume distribution apparent systemic reference test formulation week weeks hours hour minutes "
    "min visit overall phase part cohort dtg".split()
)
_STOP: Final = re.compile(
    r"\b(?:in|after|when|following|with|during|on|at|from|under|versus|vs|while)\b|[:;(]"
)


def subject_words(title: str) -> list[str]:
    """Words naming the subject after the last 'of' or 'for' of a title, once abbreviations in
    brackets, generic words and numbers are left out; what remains may be a drug that is not known."""
    t = norm(re.sub(r"\([^)]*\)", " ", title))
    idx = max(t.rfind(" of "), t.rfind(" for "))
    if idx < 0:
        return []
    tail = _STOP.split(t[idx + 4 :], maxsplit=1)[0]
    return [w for w in re.findall(r"[a-z][a-z0-9]{2,}", tail) if w not in _GENERIC]


def classify_analyte(text: str, drug_key: str, table: IdentityTable) -> tuple[AnalyteClass, str]:
    """The analyte class of a title or label phrase for the target drug, with the reason. Only the
    analyte phrase (before 'with', 'when', 'following', ...) is judged; what follows is context."""
    t = norm(text)
    phrase = _SPLIT.split(t, maxsplit=1)[0] if _SPLIT.search(t) else t
    if table.prodrug_hit(phrase, drug_key):
        return "prodrug", "the phrase names the prodrug"
    if table.metabolite_hit(phrase, drug_key):
        return "metabolite", "a named metabolite of this drug"
    if _TOTAL.search(t):
        return "total", "a sum of the drug and other moieties"
    named = table.drugs_in(phrase)
    others = [k for k in named if k != drug_key]
    partners = [p for p in table.partners_in(phrase) if p not in table.by_key[drug_key].names]
    if _METABOLITE_GENERIC.search(phrase):
        return "metabolite", "metabolite wording"
    if drug_key in named:
        if others or partners:
            return "unconfirmed", "the phrase names the drug and another drug"
        if _ENANTIOMER.search(phrase):
            return "enantiomer", "a single enantiomer or isomer"
        if _UNBOUND.search(phrase):
            return "parent_unbound", "unbound concentration"
        own = table.by_key[drug_key].names | table.by_key[drug_key].codes
        extra = [w for w in subject_words(text) if not any(w in n for n in own)]
        if extra:
            return "unconfirmed", "the subject names something besides this drug"
        return "parent", "the phrase names the drug"
    if others or partners:
        return "combination_partner", "the phrase names another drug"
    if _CODE.search(phrase):
        return "unconfirmed", "an unknown code"
    if subject_words(text):
        return "unconfirmed", "the subject is a name that is not this drug"
    return "unspecified", "the phrase names no drug"


# --- study-arm context -----------------------------------------------------------------------

_MR: Final = re.compile(
    r"\b(?:extended|modified|sustained|prolonged|delayed|controlled)[ -]?release\b|\b(?:er|xr|sr|cr|mr|la|xl)\b"
    r"|\bdepot\b|\btransdermal\b|\bpatch\b|\bgel\b|\binhal|\btopical\b|\bonce[ -]weekly\b|\bonce[ -]monthly\b"
)
_SOLUTION: Final = re.compile(r"\b(?:oral )?(?:solution|suspension|syrup|liquid|drops)\b")
_FDC: Final = re.compile(
    r"\bfixed[ -]dose\b|\bfdc\b|\bsingle[ -]tablet\b|\bcombination (?:tablet|product)\b"
)
_FED: Final = re.compile(
    r"\b(?:high|low)[ -]fat\b|\bfed\b|\bwith (?:a )?(?:meal|food|breakfast)\b|\bafter (?:a )?meal\b|\bstandard meal\b"
)
_FASTED: Final = re.compile(r"\bfasted\b|\bfasting\b|\bunder fasting\b|\bempty stomach\b")
_PEDI: Final = re.compile(
    r"\b(?:pediatric|paediatric|children|child|adolescents?|infants?|neonates?|newborns?)\b"
)
_ELDER: Final = re.compile(r"\b(?:elderly|older adults?|geriatric)\b")
_IMPAIR: Final = re.compile(
    r"\b(?:renal|hepatic|kidney|liver) (?:impairment|insufficiency|failure|disease)\b|\bcirrhosis\b|\bhemodialysis\b|\bchild pugh\b"
)
_PATIENTS: Final = re.compile(r"\bpatients?\b|\bsubjects with\b|\bparticipants with\b")
_HEALTHY: Final = re.compile(r"\bhealthy\b")
_MALE: Final = re.compile(r"\b(?:male|men)\b(?! and female)")
_FEMALE: Final = re.compile(r"\b(?:female|women)\b")
_ANIMAL: Final = re.compile(
    r"\b(?:horses?|equine|dogs?|canine|beagles?|rats?|mouse|mice|murine|monkeys?|cynomolgus|rabbits?|pigs?|porcine|cattle|bovine|sheep|animals?)\b"
)
_COADMIN: Final = re.compile(
    r"\b(?:co ?administ\w*|concomitant\w*|in combination with|combined with|drug interaction|interaction|"
    r"pre ?treat\w*|premedicat\w*|background (?:therapy|treatment)|given with|taken with)\b"
)
_OTHER_ROUTE: Final = re.compile(
    r"\b(?:intramuscular|intramuscularly|subcutaneous|subcutaneously|topical|topically|cream|gel|ointment|"
    r"transdermal|patch|inhaled|inhalation|nasal|intranasal|ophthalmic|vaginal|rectal|perianal|"
    r"sublingual|buccal|intrathecal|epidural|intradermal|intraocular|im|sc|suppository)\b"
)
_ARM: Final = re.compile(
    r"\b(?:test|reference|treatment [a-d]|period [12]|sequence [a-d]+|crossover|cross over|"
    r"test formulation|reference formulation)\b"
)


@dataclass(frozen=True)
class ArmContext:
    context: Context
    interaction: bool  # another active drug is given in this arm: interaction evidence only
    route: str  # oral, iv, unknown
    notes: tuple[str, ...] = ()

    @property
    def human(self) -> bool:
        return self.context.species == "human"


def arm_context(
    text: str, drug_key: str, table: IdentityTable, hints: Sequence[str] = ()
) -> ArmContext:
    """Context of one study arm or table column from its title and description text."""
    t = re.sub(
        r"[^.;()]*\bplacebo\b[^.;()]*", " ", norm(text)
    )  # a placebo clause names no active drug
    notes: list[str] = []
    others = [k for k in table.drugs_in(t) if k != drug_key]
    partners = [p for p in table.partners_in(t) if p not in table.by_key[drug_key].names]
    for h in hints:
        if norm(h) and re.search(rf"\b{re.escape(norm(h))}\b", t):
            partners.append(norm(h))
    coadmin = bool(others or partners)  # another active drug named anywhere in the arm text
    other_names = ", ".join(sorted(set(others + partners)))
    formulation = "unspecified"
    if _FDC.search(t):
        formulation = "fixed_dose_combination"
    elif _MR.search(t):
        formulation = "modified_release"
    elif _SOLUTION.search(t):
        formulation = "solution"
    elif re.search(r"\b(?:tablets?|capsules?)\b", t):
        formulation = "immediate_release"
    food = "fed" if _FED.search(t) else "fasted" if _FASTED.search(t) else "unspecified"
    if _PEDI.search(t) or _ELDER.search(t) or _IMPAIR.search(t):
        population = "special"
    elif _HEALTHY.search(t):
        population = "healthy_adult"
    elif _PATIENTS.search(t):
        population = "patients"
    else:
        population = "unspecified"
    sex = (
        "female"
        if _FEMALE.search(t) and not _MALE.search(t)
        else "male"
        if _MALE.search(t) and not _FEMALE.search(t)
        else "all"
    )
    species = "animal" if _ANIMAL.search(t) else "human"
    arm = None
    if m := _ARM.search(t):
        arm = m.group(0)
    route = (
        "other"
        if _OTHER_ROUTE.search(t)
        else "iv"
        if re.search(r"\b(?:intravenous|iv|infusion)\b", t)
        else "oral"
        if re.search(r"\b(?:oral|orally|tablets?|capsules?|po)\b", t)
        else "unknown"
    )
    if route == "other":
        formulation = "other_route"
    _multiple = re.search(
        r"\bmultiple\b|\bsteady state\b|\bcmax ss\b|\brepeated\b|\bmaintenance\b|\bdays? \d+ ?(?:to|and|-) ?\d+\b"
        r"|\bfor (?:[2-9]|\d\d+) (?:days|weeks|months)\b|\bx ?(?:[2-9]|\d\d+) days\b|\bday (?:7|14|15|21|28)\b",
        t,
    )
    _single = re.search(
        r"\bsingle\b|\bone dose\b|\bon day 1\b|\bday 1 only\b|\bfor (?:1|one) day\b|\b1 day\b|\bonce on\b",
        t,
    )
    regimen = (
        "multiple"
        if _multiple and not _single
        else "single"
        if _single and not _multiple
        else "unknown"
    )
    if coadmin:
        notes.append("coadministered_with:" + other_names)
    return ArmContext(
        Context(
            arm,
            other_names if coadmin else None,
            formulation,
            food,
            population,
            sex,
            species,
            route,
            regimen,
        ),
        coadmin,
        route,
        tuple(notes),
    )
