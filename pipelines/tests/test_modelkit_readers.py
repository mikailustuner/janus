"""Readers A and B: each reads the same sources on its own; code decides agreement."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from janus_pipelines.modelkit import reader_a, reader_b
from janus_pipelines.modelkit.model import Candidate, ReaderStats
from janus_pipelines.modelkit.pairing import pair
from janus_pipelines.modelkit.resolver import IdentityTable

REPO = Path(__file__).resolve().parents[2]
TABLE = IdentityTable.from_csv(
    (REPO / "data" / "modelkit" / "identity_m1.csv").read_text(encoding="utf-8")
)


def outcome(title: str, group: str, value: str, unit: str = "ng*h/mL") -> dict[str, Any]:
    return {
        "title": title,
        "description": "",
        "paramType": "GEOMETRIC_MEAN",
        "dispersionType": "Geometric Coefficient of Variation",
        "unitOfMeasure": unit,
        "groups": [{"id": "OG000", "title": group, "description": group}],
        "denoms": [{"counts": [{"groupId": "OG000", "value": "12"}]}],
        "classes": [
            {"categories": [{"measurements": [{"groupId": "OG000", "value": value}]}]}
        ],
    }  # fmt: skip


def study(outcomes: list[dict[str, Any]], interventions: list[str] | None = None) -> dict[str, Any]:
    names = interventions or ["Dolutegravir 50 mg tablets"]
    return {
        "protocolSection": {
            "identificationModule": {"nctId": "NCT00000001"},
            "statusModule": {"lastUpdatePostDate": "2021-03-17"},
            "eligibilityModule": {"healthyVolunteers": True, "stdAges": ["ADULT"]},
            "armsInterventionsModule": {
                "armGroups": [
                    {
                        "label": "Dolutegravir alone",
                        "interventionNames": [f"Drug: {n}" for n in names],
                    }
                ],
                "interventions": [{"type": "DRUG", "name": n, "description": ""} for n in names],
            },
        },
        "resultsSection": {"outcomeMeasuresModule": {"outcomeMeasures": outcomes}},
    }


def read_both(s: dict[str, Any]) -> tuple[list[Candidate], list[Candidate]]:
    return (
        reader_a.read_ctgov(s, "dolutegravir", TABLE, ReaderStats()),
        reader_b.read_ctgov(s, "dolutegravir", TABLE, ReaderStats()),
    )


def test_both_readers_read_a_clear_parent_value_and_agree() -> None:
    s = study([outcome("AUC(0-inf) of Dolutegravir", "Dolutegravir alone 50 mg", "68186")])
    a, b = read_both(s)
    assert len(a) == len(b) == 1 and a[0].parameter == "auc_inf" and a[0].analyte == "parent"
    assert a[0].dose_mg == b[0].dose_mg == 50.0
    paired, left = pair(a, b)
    assert paired[0].result.confirmed and not left


def test_metabolite_partner_and_unknown_subject_are_not_the_parent() -> None:
    for title, expect in (
        ("AUC(0-inf) of Rilpivirine", "combination_partner"),
        ("AUC(0-inf) of the primary metabolite", "metabolite"),
        ("AUC(0-inf) of Tafinlarium", "unconfirmed"),  # a name no table knows: not assumed parent
    ):
        a, b = read_both(study([outcome(title, "Dolutegravir alone 50 mg", "10")]))
        assert [c.analyte for c in a] == [expect], title
        assert all(c.analyte != "parent" for c in b), title
        paired, _ = pair(a, b)
        assert not paired[0].result.confirmed


def test_a_coadministered_arm_is_interaction_evidence_and_never_confirmed_as_plain() -> None:
    s = study(
        [outcome("AUC(0-inf) of Dolutegravir", "Dolutegravir 50 mg with rifampin 600 mg", "30000")]
    )
    a, b = read_both(s)
    assert a[0].context.coadministered and b[0].context.coadministered
    assert "rifampin" in (a[0].context.coadministered or "")


def test_readers_disagreeing_on_context_leave_the_value_unconfirmed() -> None:
    s = study([outcome("AUC(0-inf) of Dolutegravir", "Dolutegravir 50 mg fed", "50000")])
    a, b = read_both(s)
    from dataclasses import replace

    b2 = [replace(b[0], context=replace(b[0].context, food="fasted"))]
    paired, _ = pair(a, b2)
    assert paired[0].result.reason == "context_differs" and not paired[0].result.confirmed


def test_population_pk_ratios_and_non_numbers_are_skipped() -> None:
    s = study(
        [
            outcome("Geometric mean ratio of AUC(0-inf) of Dolutegravir", "x", "1.1", "ratio"),
            outcome(
                "AUC(0-inf) of Dolutegravir estimated by population pharmacokinetic modelling",
                "x",
                "9",
            ),
            outcome("AUC(0-inf) of Dolutegravir", "Dolutegravir 50 mg", "NA"),
        ]
    )
    a, b = read_both(s)
    assert a == [] and b == []


def test_candesartan_case_in_a_label_sentence_both_readers_keep_the_per_kg_value() -> None:
    """0.37 mL/min/kg is a total plasma clearance per kg: never CL/F, never times 70 kg."""
    doc = {
        "version": "1",
        "effective": "20260101",
        "paras": [
            {
                "title": "12.3 Pharmacokinetics",
                "text": "Total plasma clearance of candesartan is 0.37 mL/min/kg.",
            }
        ],
    }
    a = reader_a.read_label(doc, {}, "set1", "candesartan", TABLE, ReaderStats())
    b = reader_b.read_label(doc, {}, "set1", "candesartan", TABLE, ReaderStats())
    for rows in (a, b):
        assert len(rows) == 1 and rows[0].parameter == "cl_per_kg"
        assert rows[0].parameter != "cl_f" and rows[0].value == 0.37
    paired, _ = pair(a, b)
    assert paired[0].result.confirmed


def test_label_ranges_bounds_and_two_analyte_sentences() -> None:
    doc = {
        "version": "1",
        "effective": "20260101",
        "paras": [
            {
                "title": "12.3 Pharmacokinetics",
                "text": "The apparent oral clearance of gabapentin is 34 to 62 L/h. "
                "The half-life is less than 5 hours. "
                "Peak concentrations of gabapentin and M1 occur at two and three hours, "
                "respectively.",
            }
        ],
    }
    a = reader_a.read_label(doc, {}, "set1", "gabapentin", TABLE, ReaderStats())
    b = reader_b.read_label(doc, {}, "set1", "gabapentin", TABLE, ReaderStats())
    assert [c.parameter for c in a if c.analyte == "parent"] == ["cl_f"]
    assert abs(a[0].value - (34 * 62) ** 0.5) < 1e-9 and a[0].stat.spread_type == "range"
    assert all(c.parameter != "t_half" for c in a + b)  # an upper bound is not a value
    assert all(c.analyte != "parent" for c in a + b if c.parameter == "tmax")


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and n.module:
            out.add(n.module + ":" + ",".join(a.name for a in n.names))
        elif isinstance(n, ast.Import):
            out.update(a.name for a in n.names)
    return out


def test_reader_b_shares_no_extraction_code_with_reader_a() -> None:
    root = Path(reader_b.__file__).parent
    b_imports = " ".join(sorted(_imports(root / "reader_b.py")))
    assert "reader_a" not in b_imports
    assert "arm_context" not in b_imports and "classify_analyte" not in b_imports
    assert "pairing" not in b_imports  # B never sees A's output
    assert "reader_b" not in " ".join(sorted(_imports(root / "reader_a.py")))
