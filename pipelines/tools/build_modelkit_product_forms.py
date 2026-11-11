"""Build `data/modelkit/product_forms.csv`: dosage form class of marketed products of the pool.

The source is the public US product directory (openFDA NDC, CC0, local `us_ndc` artifact).

One row per (brand, drug): `brand` (normalised), `drug_key`, `form_class` (immediate_release,
solution, modified_release, fixed_dose_combination, other_route) and `route` (oral, iv or empty).
A brand is kept only if all its directory products fall in ONE class; a brand whose name contains a
pool drug's own name (a generic label) or is shorter than 5 characters is left out; only human
prescription products. Research use only.

    python tools/build_modelkit_product_forms.py NDC_PARQUET IDENTITY_M2_CSV OUT_CSV
"""

from __future__ import annotations

import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

import polars as pl

from janus_pipelines.modelkit.resolver import IdentityTable, norm

_MR = re.compile(
    r"EXTENDED|DELAYED|CONTROLLED|SUSTAINED|MODIFIED|LIPOSOM|IMPLANT|PELLET|INSERT|RING|SYSTEM|PATCH"
)
_LIQUID = re.compile(
    r"SOLUTION|SUSPENSION|SYRUP|ELIXIR|LIQUID|DROPS|CONCENTRATE|EMULSION|INJECTION"
)
_SOLID = re.compile(
    r"^(?:TABLET|CAPSULE)(?:, (?:FILM COATED|COATED|GELATIN COATED|SUGAR COATED))?$"
)


def product_class(forms: list[str], routes: list[str], n_ingredients: int) -> str | None:
    """One class for one directory product, None where no class applies (a special oral form)."""
    f = " ".join(forms).upper()
    r = {x.upper() for x in routes}
    if n_ingredients >= 2:
        return "fixed_dose_combination"
    if _MR.search(f):
        return "modified_release"
    if r and not r <= {"ORAL", "INTRAVENOUS"}:
        return "other_route"
    if r == {"INTRAVENOUS"}:
        return "solution"
    if r == {"ORAL"}:
        if _LIQUID.search(f) and "FOR " not in f and not f.startswith(("TABLET", "CAPSULE")):
            return "solution"
        if _SOLID.match(f.strip()):
            return "immediate_release"
    return None


def main(ndc: str, identity_csv: str, out_csv: str) -> None:
    table = IdentityTable.from_csv(Path(identity_csv).read_text(encoding="utf-8"))
    by: dict[tuple[str, str], list[tuple[str | None, str]]] = defaultdict(list)
    for p in pl.read_parquet(ndc).to_dicts():
        brand = norm(p["brand_name"] or "")
        if (
            p["product_type"] != "HUMAN PRESCRIPTION DRUG"
            or len(brand) < 5
            or table.drugs_in(brand)
        ):
            continue
        ings = p["active_ingredients"] or []
        keys = {k for i in ings for k in table.drugs_in(norm(i["name"]))}
        cls = product_class([p["dosage_form"] or ""], list(p["route"] or []), len(ings))
        route = "oral" if p["route"] == ["ORAL"] else "iv" if p["route"] == ["INTRAVENOUS"] else ""
        for k in keys:
            by[(brand, k)].append((cls, route))
    rows = []
    for (brand, key), items in sorted(by.items()):
        classes = {c for c, _ in items}
        routes = {r for _, r in items}
        if len(classes) != 1 or None in classes:
            continue
        rows.append(
            {"brand": brand, "drug_key": key, "form_class": classes.pop(),
             "route": routes.pop() if len(routes) == 1 else ""}
        )  # fmt: skip
    with Path(out_csv).open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, ["brand", "drug_key", "form_class", "route"], lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(len(rows), "brand-drug rows,", len({r["drug_key"] for r in rows}), "drugs")


if __name__ == "__main__":
    main(*sys.argv[1:4])
