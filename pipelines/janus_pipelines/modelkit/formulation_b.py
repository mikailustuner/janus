"""Formulation and route resolver B (spec model-kit, milestone M3): token and structure based.

Independent of resolver A: it shares only the result type, the shared decision rule and the product table
(`formref`) and the drug names (`IdentityTable`). It works on token sequences against a word list instead of
patterns on text, links the results group to the protocol arm by the overlap of their label tokens, and links
an arm to its interventions through the `interventionNames` of the record. Its reading of the evidence is
layered the same way as the rule of the pre-registration says (results group, outcome measure, then arm and its
interventions for this drug, then all interventions for this drug); the matching and the linking are its own. Research use
only. Not for clinical decisions.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Final

from janus_pipelines.modelkit.formref import UNRESOLVED, BrandTable, Resolution, decide
from janus_pipelines.modelkit.resolver import IdentityTable

_LOC: Final = re.compile(r"^(NCT\d+)#outcome-(\d+)/(OG\d+)")
_SPLIT: Final = re.compile(r"[.;\n|]")

_OTHER_STEMS: Final = (
    "intramuscular", "subcutaneous", "topical", "inhal", "intranasal", "vaginal", "rectal", "sublingual",
    "buccal", "intrathecal", "intradermal", "intraperitoneal", "nebul", "suppositor", "intravitreal",
    "intraocular", "transdermal",
)  # fmt: skip
_OTHER_WORDS: Final = frozenset(
    "cream gel ointment patch patches nasal ophthalmic epidural implant implants lozenge im sc".split()
)
_RELEASE_PREFIX: Final = frozenset(
    "extended modified sustained prolonged delayed controlled slow".split()
)
_ABBR: Final = frozenset("xr xl sr er cr mr cd la xt".split())
_DOSAGE_WORD: Final = frozenset("tablet tablets capsule capsules formulation form".split())
_SOLUTION_WORDS: Final = frozenset(
    "solution solutions suspension suspensions syrup elixir drops".split()
)
_EXCIPIENT: Final = frozenset(
    "saline dextrose glucose ringer ringers chloride sucrose bicarbonate buffer water sterile diluent dilution diluted".split()
)
_SPECIAL_WORDS: Final = frozenset("chewable dispersible dissolvable effervescent".split())
_TABLETS: Final = frozenset(
    "tablet tablets capsule capsules caplet caplets softgel softgels pill pills".split()
)
_IV_WORDS: Final = frozenset("iv infusion infusions infused".split())
_NOT_IV_BEFORE: Final = frozenset("stage phase grade type class part group cohort arm".split())
_ORAL_WORDS: Final = frozenset("po syrup elixir tablet tablets capsule capsules".split())
_BRAND_CLASS: Final = {
    "fixed_dose_combination": "fdc",
    "other_route": "other_route",
    "modified_release": "mr",
    "solution": "solution",
    "immediate_release": "ir_weak",
}


def _tok(text: str) -> list[str]:
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").lower()
    return re.findall(r"[a-z0-9]+", t)


def _has(toks: list[str], seq: tuple[str, ...]) -> bool:
    n = len(seq)
    return any(tuple(toks[i : i + n]) == seq for i in range(len(toks) - n + 1))


def _evidence(toks: list[str], brand_hits: list[tuple[str, str]]) -> tuple[set[str], set[str]]:
    cls: set[str] = set()
    routes: set[str] = set()
    for i, w in enumerate(toks):
        prev = toks[i - 1] if i else ""
        nxt = toks[i + 1] if i + 1 < len(toks) else ""
        if w.startswith(_OTHER_STEMS) or w in _OTHER_WORDS:
            cls.add("other_route")
        if w == "release" and prev in _RELEASE_PREFIX:
            cls.add("mr")
        if w in ("depot", "retard") or w.startswith("liposom"):
            cls.add("mr")
        if w in _ABBR and (
            nxt in _DOSAGE_WORD or nxt.isdigit() or prev in _DOSAGE_WORD or prev == "mg"
        ):
            cls.add("mr")
        if w == "coated" and prev == "enteric":
            cls.add("mr")
        if w in _SOLUTION_WORDS and not any(x in _EXCIPIENT for x in toks[max(0, i - 3) : i]):
            cls.add("solution")
        if w in _SPECIAL_WORDS:
            cls.add("special")
        if w == "release" and prev in ("immediate", "rapid"):
            cls.add("ir")
        if w in _IV_WORDS or w.startswith("intravenous"):
            if not (w == "iv" and prev in _NOT_IV_BEFORE):
                routes.add("iv")
        if w.startswith("oral") or w in _ORAL_WORDS or w.startswith("peroral"):
            routes.add("oral")
    if (
        _has(toks, ("fixed", "dose"))
        or "fdc" in toks
        or _has(toks, ("single", "tablet", "regimen"))
    ):
        cls.add("fdc")
    if any(_has(toks, ("combination", x)) for x in ("tablet", "product", "capsule")):
        cls.add("fdc")
    if _has(toks, ("long", "acting", "injectable")) or _has(
        toks, ("gastro", "resistant", "release")
    ):
        cls.add("mr")
    if _has(toks, ("orally", "disintegrating")) or _has(toks, ("for", "oral", "suspension")):
        cls.add("special")
    if _has(toks, ("oral", "liquid")) or _has(toks, ("liquid", "formulation")):
        cls.add("solution")
    if any(
        _has(toks, (a, b))
        for a in ("conventional",)
        for b in ("tablet", "tablets", "capsule", "capsules")
    ):
        cls.add("ir")
    if "ir" in toks:
        j = toks.index("ir")
        if j + 1 < len(toks) and toks[j + 1] in _DOSAGE_WORD:
            cls.add("ir")
    if _has(toks, ("by", "mouth")) or _has(toks, ("per", "os")):
        routes.add("oral")
    if _has(toks, ("i", "v")):
        routes.add("iv")
    if any(w in _TABLETS for w in toks) and "special" not in cls:
        cls.add("ir_weak")
    if _has(toks, ("film", "coated")) and "special" not in cls:
        cls.add("ir_weak")
    for fc, route in brand_hits:
        cls.add(_BRAND_CLASS[fc])
        if route:
            routes.add(route)
    return cls, routes


class _Names:
    def __init__(self, drug_key: str, table: IdentityTable, brands: BrandTable) -> None:
        ident = table.by_key[drug_key]
        self.names = sorted(
            {tuple(_tok(n)) for n in ident.names | ident.codes if _tok(n)}, key=len, reverse=True
        )
        self.brands = {tuple(_tok(p.brand)): p for p in brands.products(drug_key) if _tok(p.brand)}

    def in_toks(self, toks: list[str]) -> bool:
        return any(_has(toks, n) for n in self.names) or any(_has(toks, b) for b in self.brands)

    def brand_hits(self, toks: list[str]) -> list[tuple[str, str]]:
        # a longer brand that contains a shorter one ("seroquel xr" and "seroquel") hides the shorter
        found = [b for b in self.brands if _has(toks, b)]
        found = [b for b in found if not any(len(o) > len(b) and _has(list(o), b) for o in found)]
        return [(self.brands[b].form_class, self.brands[b].route) for b in found]


def _clauses(texts: list[str], names: _Names, single: bool) -> list[str]:
    out: list[str] = []
    for text in texts:
        for part in _SPLIT.split(text):
            toks = _tok(part)
            if not toks or "placebo" in toks:
                continue
            if single or names.in_toks(toks):
                out.append(" ".join(toks))
    return out


def _overlap(a: str, b: str) -> float:
    x, y = set(_tok(a)), set(_tok(b))
    return len(x & y) / len(x | y) if x and y else 0.0


def resolve(
    study: dict[str, Any], drug_key: str, locator: str, table: IdentityTable, brands: BrandTable
) -> Resolution:
    m = _LOC.match(locator)
    if m is None:
        return UNRESOLVED
    ai = study["protocolSection"].get("armsInterventionsModule", {})
    arms: list[dict[str, Any]] = ai.get("armGroups", [])
    intervs: dict[str, dict[str, Any]] = {i["name"]: i for i in ai.get("interventions", [])}
    om = study["resultsSection"]["outcomeMeasuresModule"]["outcomeMeasures"][int(m.group(2)) - 1]
    group: dict[str, Any] = {}
    for g in om.get("groups", []):
        if g["id"] == m.group(3):
            group = g
    names = _Names(drug_key, table, brands)

    def iv_toks(i: dict[str, Any]) -> list[str]:
        return _tok(" ".join([i["name"], *i.get("otherNames", [])]))

    def active(i: dict[str, Any]) -> bool:
        return i.get("type") not in (
            "BEHAVIORAL",
            "PROCEDURE",
            "DEVICE",
            "OTHER",
        ) and "placebo" not in _tok(i["name"])

    own = {n: i for n, i in intervs.items() if names.in_toks(iv_toks(i))}
    gtitle = group.get("title", "")
    scored = sorted(((_overlap(gtitle, a.get("label", "")), a) for a in arms), key=lambda x: -x[0])
    arm = (
        scored[0][1]
        if scored and scored[0][0] >= 0.6 and (len(scored) < 2 or scored[1][0] < scored[0][0])
        else None
    )
    linked = {n.split(":", 1)[-1].strip() for n in (arm or {}).get("interventionNames", [])}
    if arm is not None:
        arm_own = [i for n, i in own.items() if n in linked]
        arm_other = [i for n, i in intervs.items() if n in linked and n not in own and active(i)]
    else:
        arm_own = list(own.values())
        arm_other = [i for n, i in intervs.items() if n not in own and active(i)]
    single = not arm_other

    def body(i: dict[str, Any]) -> list[str]:
        return [i["name"], *i.get("otherNames", []), i.get("description", "") or ""]

    def layer(texts: list[str], single_flag: bool) -> tuple[set[str], set[str]]:
        cl = _clauses(texts, names, single_flag)
        # brand and word checks run per clause so a word never joins two clauses
        classes: set[str] = set()
        routes: set[str] = set()
        for c in cl:
            ts = c.split()
            k, r = _evidence(ts, names.brand_hits(ts))
            classes |= k
            routes |= r
        return classes, routes

    own_texts = [t for i in own.values() for t in body(i)]
    layers: list[tuple[set[str], set[str]]] = [
        layer([gtitle, group.get("description", "") or ""], single),
        layer(
            [om.get("title", ""), om.get("description", "") or ""],
            not [i for n, i in intervs.items() if n not in own and active(i)],
        ),
        layer(
            [(arm or {}).get("label", ""), (arm or {}).get("description", "") or ""]
            + [t for i in arm_own for t in body(i)],
            single,
        )
        if arm is not None
        else (set(), set()),
        layer(own_texts, True),
    ]
    first_route = next((next(iter(r)) for _, r in layers if len(r) == 1), "unknown")
    weak: Resolution | None = None
    for cls, routes in layers:
        res = decide(frozenset(cls), frozenset(routes))
        if res.why.startswith("conflict"):
            return res
        if res.why == "ir_weak":
            weak = weak or res
            continue
        if res.why == "":
            continue
        route = (
            res.route if res.route != "unknown" or res.formulation == "other_route" else first_route
        )
        return Resolution(res.formulation, route, res.why)
    if weak is not None:
        return Resolution(
            weak.formulation, weak.route if weak.route != "unknown" else first_route, weak.why
        )
    return Resolution("unspecified", first_route, "")
