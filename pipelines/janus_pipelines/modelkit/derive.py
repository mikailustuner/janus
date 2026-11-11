"""Derived clearance (spec model-kit, plan M1 task 4): CL/F = dose / AUC(0-inf) for an oral dose and
CL = dose / AUC(0-inf) for an intravenous dose, only where ONE study arm gives both a dose (from
the arm definition, a table, a footnote or the methods, never an abstract) and a single-dose AUC to
infinity of the parent drug, confirmed by both readers. The derived row says so ("origin: derived",
with the derivation text) and is never a stated value. Research use only. Not for clinical decisions.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

# 1 mg = 1e6 ng; AUC in ng*h/mL; dose / AUC in mL/h = 1e6 / 1e3 L/h per (mg / (ng*h/mL))
_L_PER_H_PER_MG_PER_AUC = 1e6 / 1e3


def derive_clearance(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """One derived clearance row per eligible AUC-to-infinity row of the same arm."""
    out: list[dict[str, Any]] = []
    for r in rows:
        if (
            r["parameter"] != "auc_inf"
            or r["analyte_class"] != "parent"
            or not r["confirmed"]
            or r.get("evidence_kind", "pk") != "pk"
            or r["coadministered"]
            or r["regimen"] != "single"
            or r["dose"] is None
            or not r.get("arm_id")
            or r["route"] not in ("oral", "iv")
            or r.get("origin") == "derived"
        ):
            continue
        auc = float(r["value_si"])  # ng*h/mL
        dose = float(r["dose"])  # mg
        if auc <= 0 or dose <= 0:
            continue
        name = "cl_f" if r["route"] == "oral" else "cl"
        label = "CL/F" if name == "cl_f" else "CL"
        value = dose * _L_PER_H_PER_MG_PER_AUC / auc
        out.append(
            {
                **r,
                "parameter": name,
                "value": value,
                "value_low": None,
                "value_high": None,
                "unit": "L/h",
                "value_si": value,
                "dose": r["dose"],
                "source_locator": f"{r['source_locator']}#derived-{name}",
                "origin": "derived",
                "derivation": (
                    f"{label} = dose / AUC(0-inf) = {dose:g} mg / {auc:g} ng*h/mL = {value:.4g} L/h; "
                    f"one study arm ({r['arm_id']})"
                ),
                "confirm_reason": "derived from a row confirmed by both readers",
                "dispersion_type": "none",
                "dispersion_low": None,
                "dispersion_high": None,
            }
        )
    return out
