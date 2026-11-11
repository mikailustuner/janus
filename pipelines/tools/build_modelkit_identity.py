"""Build `data/modelkit/identity_m2.csv`: names of the model-kit drug pool for the analyte resolver.

Names come from the pool's own drug names, the Wikidata labels and aliases (CC0) of the drug's item
(local `wikidata_ingredients` artifact) and, for the drugs of milestone M1, the curated company
codes, metabolites and prodrugs of `identity_m1.csv`. Very short or generic words are left out so that a
common word never names a drug. Research use only.

    python tools/build_modelkit_identity.py POOL_CSV WIKIDATA_PARQUET IDENTITY_M1_CSV OUT_CSV

POOL_CSV has the columns key,name,all_names,qids (one row per pool drug).
"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

import polars as pl

from janus_pipelines.modelkit.resolver import _GENERIC, norm  # pyright: ignore[reportPrivateUsage]

LANGS = ("en", "tr", "de", "fr", "es")
# words that are aliases of a drug item but also name something else in a study text
EXTRA_STOP = frozenset(
    "alcohol water oil salt iron sugar milk vitamin acid soda ice glucose calcium magnesium zinc "
    "potassium lead copper silver gold carbon oxygen air steroid hormone insulin cocaine base blow "
    "chalk coke coca crack crank fast glass speed whiz snow dope grass weed smack horse junk angel "
    "koks goey louee".split()
)  # fmt: skip


def slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    if not s or not s[0].isalpha():
        s = "d_" + s
    return s[:32].rstrip("_")


def usable(name: str, own: str) -> bool:
    n = norm(name)
    if n == norm(own):
        return True
    return len(n) >= 4 and n not in _GENERIC and n not in EXTRA_STOP and not n.isdigit()


def main(pool_csv: str, wikidata: str, m1_csv: str, out_csv: str) -> None:
    wd = {r["qid"]: r for r in pl.read_parquet(wikidata).to_dicts()}
    m1 = {r["drug_key"]: r for r in csv.DictReader(Path(m1_csv).open(encoding="utf-8"))}
    rows: list[dict[str, str]] = []
    used: dict[str, str] = {}
    for r in sorted(csv.DictReader(Path(pool_csv).open(encoding="utf-8")), key=lambda x: x["name"]):
        key = slug(r["name"])
        if key in used and used[key] != r["key"]:
            key = (key[:28] + "_" + r["key"][:3].lower())[:32]
        used[key] = r["key"]
        names = {norm(x) for x in re.split(r"[|;]", r["all_names"]) if x.strip()} | {
            norm(r["name"])
        }
        qids = [q for q in re.split(r"[|;]", r["qids"]) if q.strip()]
        for q in qids:
            item = wd.get(q)
            if not item:
                continue
            for lang in LANGS:
                names.add(norm(item.get(f"label_{lang}") or ""))
                names.update(norm(a) for a in item.get(f"aliases_{lang}") or [])
        old = m1.get(key)
        codes = metabolites = prodrugs = ""
        if old:
            names |= {x for x in old["names"].split("|") if x}
            codes, metabolites, prodrugs = old["codes"], old["metabolites"], old["prodrugs"]
        kept = sorted(n for n in names if n and usable(n, r["name"]))
        rows.append(
            {
                "drug_key": key,
                "qid": qids[0] if qids else (old["qid"] if old else ""),
                "names": "|".join(kept),
                "codes": codes,
                "metabolites": metabolites,
                "prodrugs": prodrugs,
            }
        )
    with Path(out_csv).open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(len(rows), "drugs;", len({r["drug_key"] for r in rows}), "keys")


if __name__ == "__main__":
    main(*sys.argv[1:5])
