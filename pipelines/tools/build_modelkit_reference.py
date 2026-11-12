"""Build the model-kit reference tables (precision work, round 3). Research use only.

1. `data/modelkit/combination_products.csv` (brand, components, source): every product of the
   public US product directory (openFDA NDC, CC0, local `us_ndc` artifact; prescription and OTC
   human drugs) with two or more active ingredients, at least one a pool drug, plus the brands of
   multi-ingredient labels in the openFDA drug label files (CC0). Components are pool drug keys,
   or the normalised ingredient name when it is not a pool drug.
2. `data/modelkit/analytes.csv` (drug_key, name, relation, source): names that are NOT the parent
   drug itself but appear next to it in PK texts: named metabolites (patterns over the
   single-substance label sections pharmacokinetics and clinical pharmacology, kept only when
   the name is metabolite-shaped), prodrug esters (ingredient names = pool drug name + a prodrug
   ester word, from the directory) and reversal agents (labels whose indication reverses
   anticoagulation, with the drugs that indication names). Generic moieties ("total", "free",
   "unbound") are not listed: the strict check catches those words.

Usage: python tools/build_modelkit_reference.py NDC_PARQUET LABEL_DIR IDENTITY_M2_CSV OUT_DIR
One process, one label file in memory at a time.
"""

from __future__ import annotations

import csv
import io
import re
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

import polars as pl

from janus_pipelines.jobs.us_ndc import iter_results
from janus_pipelines.modelkit.resolver import IdentityTable, norm

# prodrug esters only; salts and depot esters (acetate, valerate ...) are the dosed drug itself
ESTERS = (
    "etexilate", "alafenamide", "disoproxil", "dipivoxil", "medoxomil", "marboxil", "fosamil",
    "mofetil", "pivoxil", "axetil", "proxetil", "lauroxil",
)  # fmt: skip
SALTS = re.compile(
    r"\b(hydrochloride|hcl|sodium|potassium|calcium|magnesium|mesylate|maleate|besylate|tartrate|sulfate|"
    r"citrate|succinate|fumarate|phosphate|bromide|chloride|monohydrate|dihydrate|anhydrous|hydrobromide)\b"
)
STOP = frozenset(
    "the a an of and or is was were are its this that which with in to for by as be been "
    "metabolite metabolites active inactive major minor main principal circulating primary "
    "pharmacologically drug parent compound form forms also both two three several other "
    "plasma human".split()
)
_MET = [
    re.compile(
        r"\b(?:active|major|main|principal|primary|inactive|circulating|"
        r"pharmacologically active)\s+metabolites?,?\s*"
        r"(?:\(|called |named |known as |designated )?([A-Za-z0-9][\w\-',]{1,40})"
    ),
    re.compile(
        r"\b([A-Za-z0-9][\w\-']{2,40}),?\s+(?:an?|the|its)\s+"
        r"(?:active |major |main |principal |inactive |primary )?metabolite\b"
    ),
    re.compile(r"\bmetabolites?\s+(M-?[0-9]{1,2}|M-?[IVX]{1,4})\b"),
]
_METABOLITE_SHAPE = re.compile(
    r"\d|^(?:nor|des|desmethyl|didesmethyl|hydroxy|dihydroxy|dehydro|dihydro|oxo|keto|carboxy|"
    r"desacetyl|desethyl|n desmethyl|o desmethyl|n oxide|monodesethyl)|"
    r"(?:ol|ic acid|acid|glucuronide|sulfone|sulfide|phosphate|oxide|sulfate|amide|amine|lactone)$"
)


def metabolite_like(name: str, drug: str) -> bool:
    """A captured word looks like a metabolite name: a code, a chemical prefix or suffix, or the
    drug's own stem with a change (daunorubicinol); plain English words are not."""
    if _METABOLITE_SHAPE.search(name) and len(name) <= 40:
        return (
            not re.fullmatch(r"[\d .,%-]+", name)
            and len(name.replace(" ", "")) >= 2
            and not re.fullmatch(r"\d+ [a-z]", name)
        )
    stem = norm(drug)[:5]
    return len(stem) == 5 and stem in name and name != norm(drug)


_REVERSAL = re.compile(r"revers\w*[^.]{0,120}anticoagula|anticoagula[^.]{0,120}revers", re.I)


def _strs(v: object) -> list[str]:
    return [str(x) for x in v] if isinstance(v, list) else ([str(v)] if v else [])


def _moiety(name: str) -> str:
    return re.sub(r"\s+", " ", SALTS.sub(" ", norm(name))).strip()


def main(ndc: Path, labels: Path, identity: Path, out: Path) -> None:
    table = IdentityTable.from_csv(identity.read_text("utf-8"))
    combos: dict[str, tuple[frozenset[str], str]] = {}
    analytes: dict[tuple[str, str], tuple[str, str]] = {}

    def comp(ingredient: str) -> str:
        keys = table.drugs_in(_moiety(ingredient))
        return keys[0] if len(keys) == 1 else _moiety(ingredient)

    for r in pl.read_parquet(ndc).iter_rows(named=True):
        ings = [i["name"] for i in (r["active_ingredients"] or []) if i.get("name")]
        brand = norm(r["brand_name"] or "")
        if len(brand) < 4:
            continue
        cs = frozenset(comp(i) for i in ings)
        if len(cs) >= 2 and any(c in table.by_key for c in cs):
            combos.setdefault(brand, (cs, "openFDA NDC directory (CC0)"))
        for ing in ings:  # prodrug esters of a pool drug
            m = _moiety(ing)
            for e in ESTERS:
                if m.endswith(" " + e):
                    base = m[: -len(e) - 1].strip()
                    if base in table.by_key and m != base:
                        analytes.setdefault(
                            (base, m), ("prodrug_ester", "openFDA NDC directory (CC0)")
                        )
    for z in sorted(labels.glob("drug-label-*.json.zip")):
        with zipfile.ZipFile(z) as zf:
            text = zf.read(next(n for n in zf.namelist() if n.endswith(".json"))).decode("utf-8")
        for rec in iter_results(text):
            of = rec.get("openfda") or {}
            subs = _strs(of.get("substance_name"))
            brands = [norm(b) for b in _strs(of.get("brand_name")) if len(b) >= 4]
            if len(subs) >= 2:
                cs = frozenset(comp(s) for s in subs)
                if any(c in table.by_key for c in cs):
                    for b in brands:
                        combos.setdefault(b, (cs, "openFDA drug label (CC0)"))
            if len(subs) != 1:
                continue
            ind = " ".join(_strs(rec.get("indications_and_usage")))
            if _REVERSAL.search(ind):
                agent = _moiety(subs[0])
                for k in table.drugs_in(ind):
                    if k != (table.drugs_in(agent) or [None])[0]:
                        analytes.setdefault(
                            (k, agent), ("reversal_agent", "openFDA drug label (CC0)")
                        )
            keys = table.drugs_in(_moiety(subs[0]))
            if len(keys) != 1:
                continue
            key = keys[0]
            own = table.by_key[key].names
            body = " ".join(
                _strs(rec.get("pharmacokinetics")) + _strs(rec.get("clinical_pharmacology"))
            )
            for rx in _MET:
                for m in rx.finditer(body):
                    name = norm(m.group(1).strip(",'"))
                    if len(name) < 2 or name in STOP or name in own or name.split(" ")[0] in STOP:
                        continue
                    if not metabolite_like(name, key):
                        continue
                    analytes.setdefault((key, name), ("metabolite", "openFDA drug label (CC0)"))
        del text
    out.mkdir(parents=True, exist_ok=True)
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["brand", "components", "source"])
    for b in sorted(combos):
        w.writerow([b, "|".join(sorted(combos[b][0])), combos[b][1]])
    (out / "combination_products.csv").write_text(buf.getvalue(), "utf-8")
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["drug_key", "name", "relation", "source"])
    by: dict[str, int] = defaultdict(int)
    for (k, n), (rel, src) in sorted(analytes.items()):
        w.writerow([k, n, rel, src])
        by[rel] += 1
    (out / "analytes.csv").write_text(buf.getvalue(), "utf-8")
    print("combinations", len(combos), "analytes", dict(by))


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]))
