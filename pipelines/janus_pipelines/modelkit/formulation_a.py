"""Formulation and route resolver A (spec model-kit, milestone M3): pattern based.

Reads, for one (study, drug, results group), the evidence of the study record in four layers, most specific first:
(1) the results group (title, description), (2) the outcome measure (title, description), (3) the protocol arm group that
matches the results group (label, description) with the interventions of that arm that name the drug, (4) every
intervention of the study that names the drug. Only text about
the drug counts: clauses that name the drug (a name, a code or a marketed brand) or, where the arm gives no other active
drug, every clause; a placebo clause never counts. The evidence classes found in a layer are turned into a formulation
by the shared rule `formref.decide`. A layer in conflict stops the search (unresolved); the first layer with evidence
that is not a bare tablet or capsule word decides; a bare tablet or capsule word counts only if nothing else is found.
Nothing stated stays `unspecified`. Research use only. Not for clinical decisions.
"""

from __future__ import annotations

import re
from typing import Any, Final

from janus_pipelines.modelkit.formref import UNRESOLVED, BrandTable, Resolution, decide
from janus_pipelines.modelkit.resolver import IdentityTable, norm

_LOCATOR: Final = re.compile(r"^(NCT\d+)#outcome-(\d+)/(OG\d+)")
_PLACEBO: Final = re.compile(r"placebo")
_CLAUSE: Final = re.compile(r"[.;\n]| \| ")

_FDC: Final = re.compile(
    r"\bfixed dose\b|\bfdc\b|\bsingle tablet regimen\b|\bcombination (?:tablet|product|capsule)\b"
)
_OTHER: Final = re.compile(
    r"\b(?:intramuscular\w*|subcutaneous\w*|topical\w*|cream|gel|ointment|transdermal|patch(?:es)?|inhal\w*|"
    r"nasal|intranasal\w*|ophthalmic|vaginal\w*|rectal\w*|perianal|sublingual\w*|buccal\w*|intrathecal\w*|"
    r"epidural|intradermal\w*|intraocular|intravitreal|intraperitoneal\w*|intra articular|implants?|"
    r"nebuli[sz]\w*|suppositor\w*|lozenge|im|sc|s c)\b"
)
_MR_WORD: Final = re.compile(
    r"\b(?:extended|modified|sustained|prolonged|delayed|controlled|slow|gastro resistant) release\b|"
    r"\benteric coated\b|\bdepot\b|\bretard\b|\bliposom\w*|\blong acting injectable\b"
)
# a release abbreviation counts only next to a dosage word, a number with a unit or a drug name
_MR_ABBR: Final = re.compile(
    r"\b(?:xr|xl|sr|er|cr|mr|cd|la|xt)\b(?= (?:tablets?|capsules?|formulation|form|\d))"
    r"|(?:tablets?|capsules?|formulation|mg) (?:xr|xl|sr|er|cr|mr|cd|la|xt)\b"
)
_SPECIAL: Final = re.compile(
    r"\b(?:orally disintegrating|chewable|dispersible|dissolvable|effervescent|for oral suspension|"
    r"tablets? for suspension|rapidly dissolving)\b"
)
_EXCIPIENT_SOLUTION: Final = re.compile(
    r"\b(?:saline|dextrose|glucose|ringer\w*|sodium chloride|sucrose|bicarbonate|buffer\w*|water|sterile|"
    r"diluent|dilut\w*)\b(?: \w+){0,2} (?:solution|suspension)"
)
_SOLUTION: Final = re.compile(
    r"\b(?:solutions?|suspensions?|syrup|elixir|oral liquid|liquid formulation|drops)\b"
)
_IR: Final = re.compile(
    r"\bimmediate release\b|\bir (?=tablets?|capsules?|formulation|form)\b|\bconventional (?:tablets?|capsules?)\b"
    r"|\brapid release\b"
)
_TABLET: Final = re.compile(r"\b(?:tablets?|capsules?|caplets?|softgels?|film coated|pills?)\b")
_IV: Final = re.compile(
    r"(?<!stage )(?<!phase )(?<!grade )(?<!type )(?<!class )(?<!part )(?<!group )(?<!cohort )(?<!arm )"
    r"\b(?:intravenous\w*|iv|i v|infusions?|infused)\b"
)
_ORAL: Final = re.compile(
    r"\b(?:oral\w*|by mouth|po|per os|peroral\w*|tablets?|capsules?|syrup|elixir)\b"
)


def _classes(text: str, brand_hits: list[tuple[str, str]]) -> tuple[frozenset[str], frozenset[str]]:
    """(evidence classes, route words) of one text (normalised, placebo clauses removed)."""
    cls: set[str] = set()
    routes: set[str] = set()
    t = _EXCIPIENT_SOLUTION.sub(" ", text)
    if _FDC.search(t):
        cls.add("fdc")
    if _OTHER.search(t):
        cls.add("other_route")
    if _MR_WORD.search(t) or _MR_ABBR.search(t):
        cls.add("mr")
    if _SPECIAL.search(t):
        cls.add("special")
    if _SOLUTION.search(t):
        cls.add("solution")
    if _IR.search(t):
        cls.add("ir")
    if _TABLET.search(t) and "special" not in cls:
        cls.add("ir_weak")
    if _IV.search(t):
        routes.add("iv")
    if _ORAL.search(t):
        routes.add("oral")
    for form_class, route in brand_hits:
        cls.add(
            {
                "fixed_dose_combination": "fdc",
                "other_route": "other_route",
                "modified_release": "mr",
                "solution": "solution",
                "immediate_release": "ir_weak",
            }[form_class]
        )
        if route:
            routes.add(route)
    return frozenset(cls), frozenset(routes)


class _Drug:
    """The names of one drug as text patterns (own names, codes, marketed brands)."""

    def __init__(self, drug_key: str, table: IdentityTable, brands: BrandTable) -> None:
        ident = table.by_key[drug_key]
        self.table = table
        self.key = drug_key
        names = sorted(ident.names | ident.codes, key=len, reverse=True)
        self.products = sorted(brands.products(drug_key), key=lambda p: len(p.brand), reverse=True)
        words = names + [p.brand for p in self.products]
        self.rx = re.compile(r"\b(?:" + "|".join(re.escape(w) for w in words) + r")\b")
        self.brand_rx = (
            re.compile(r"\b(?:" + "|".join(re.escape(p.brand) for p in self.products) + r")\b")
            if self.products
            else None
        )

    def names_drug(self, text: str) -> bool:
        return bool(self.rx.search(text))

    def brand_hits(self, text: str) -> list[tuple[str, str]]:
        if self.brand_rx is None:
            return []
        out: list[tuple[str, str]] = []
        for m in self.brand_rx.finditer(text):
            for p in self.products:
                if p.brand == m.group(0):
                    out.append((p.form_class, p.route))
                    break
        return out


def _keep(text: str, drug: _Drug, single: bool) -> str:
    """The clauses of `text` that are about the drug: all clauses where the arm has no other active drug,
    else those that name the drug; clauses that mention a placebo are dropped."""
    t = norm(text)
    out = [c for c in _CLAUSE.split(t) if c.strip() and not _PLACEBO.search(c)]
    if not single:
        out = [c for c in out if drug.names_drug(c)]
    return " . ".join(out)


def _arm_for(title: str, arms: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The protocol arm group of a results group: same label, else the one label that contains the title or is contained."""
    t = norm(title)
    if not t:
        return None
    same = [a for a in arms if norm(a.get("label", "")) == t]
    if len(same) == 1:
        return same[0]
    part = [
        a
        for a in arms
        if len(norm(a.get("label", ""))) >= 3 and (norm(a["label"]) in t or t in norm(a["label"]))
    ]
    return part[0] if len(part) == 1 else None


def resolve(
    study: dict[str, Any], drug_key: str, locator: str, table: IdentityTable, brands: BrandTable
) -> Resolution:
    m = _LOCATOR.match(locator)
    if m is None:
        return UNRESOLVED
    proto = study["protocolSection"]
    ai = proto.get("armsInterventionsModule", {})
    arms: list[dict[str, Any]] = ai.get("armGroups", [])
    intervs: list[dict[str, Any]] = ai.get("interventions", [])
    oms = study["resultsSection"]["outcomeMeasuresModule"]["outcomeMeasures"]
    om = oms[int(m.group(2)) - 1]
    group: dict[str, Any] = {}
    for g in om.get("groups", []):
        if g["id"] == m.group(3):
            group = g
    drug = _Drug(drug_key, table, brands)

    def names_drug(i: dict[str, Any]) -> bool:
        return drug.names_drug(norm(" ".join([i.get("name", ""), *i.get("otherNames", [])])))

    def active(i: dict[str, Any]) -> bool:
        return i.get("type") not in (
            "BEHAVIORAL",
            "PROCEDURE",
            "DEVICE",
            "OTHER",
        ) and not _PLACEBO.search(norm(i.get("name", "")))

    own = [i for i in intervs if names_drug(i)]
    others = [i for i in intervs if active(i) and not names_drug(i)]
    arm = _arm_for(group.get("title", ""), arms)
    arm_names = {n.split(":", 1)[-1].strip() for n in (arm or {}).get("interventionNames", [])}
    arm_own = [i for i in own if i["name"] in arm_names] if arm else own
    arm_others = [i for i in others if i["name"] in arm_names] if arm else others
    single = not arm_others

    def layer(texts: list[str], single_flag: bool) -> tuple[frozenset[str], frozenset[str]]:
        kept = [_keep(t, drug, single_flag) for t in texts]
        text = " . ".join(k for k in kept if k)
        return _classes(text, drug.brand_hits(text))

    def iv_text(items: list[dict[str, Any]]) -> list[str]:
        return [
            " . ".join(
                [i.get("name", ""), *i.get("otherNames", []), i.get("description", "") or ""]
            )
            for i in items
        ]

    layers: list[tuple[frozenset[str], frozenset[str]]] = [
        layer([group.get("title", ""), group.get("description", "") or ""], single),
        layer([om.get("title", ""), om.get("description", "") or ""], not others),
        layer(
            [
                (arm or {}).get("label", ""),
                (arm or {}).get("description", "") or "",
                *iv_text(arm_own),
            ],
            single,
        )
        if arm is not None
        else (frozenset(), frozenset()),
        layer(iv_text(own), True),
    ]
    first_route = ""
    for _, routes in layers:
        if not first_route and len(routes) == 1:
            first_route = next(iter(routes))
    weak: Resolution | None = None
    for cls, routes in layers:
        res = decide(cls, routes)
        if res.why.startswith("conflict"):
            return res
        if res.why in ("ir_weak", ""):
            if res.why == "ir_weak" and weak is None:
                weak = res
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
