"""Model kit exports (requirement 4, properties M7 and M9): the Janus engine file, the mrgsolve
model, provenance and licences, deterministic zip; and the mrgsolve round trip when R is present
(`pytest -m mrgsolve`; CI runs it in its own job with `JANUS_REQUIRE_MRGSOLVE=1`)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest

from janus.modelkit import export as ex
from janus.modelkit.builder import ParameterSet, build_set
from janus.modelkit.validate import validate
from janus.simulation.compartmental import explore
from tests.modelkit_helpers import RUN_ID, seed_rows

RELEASE = {"run_id": RUN_ID, "snapshot_date": "2026-11-11"}
HERE = Path(__file__).parent
FORBIDDEN = (
    "stop taking", "you should stop", "discontinue", "unnecessary medicine", "cure", "diagnosis",
    "you have", "safe to stop", "your medicines are safe", "safe dose", "AI ", " AI",
)  # fmt: skip


def complete_sets() -> list[str]:
    rows = seed_rows()
    return [
        d
        for d in sorted({r.drug_key for r in rows})
        if isinstance(s := build_set(d, rows), ParameterSet) and s.complete
    ]


def files_for(drug: str, target: str) -> dict[str, str]:
    rows = seed_rows()
    ps = build_set(drug, rows)
    assert isinstance(ps, ParameterSet)
    return ex.export_files(target, ps, validate(drug, rows, ps), rows, RELEASE)


def test_three_drugs_export_in_m0() -> None:
    assert complete_sets() == ["dolutegravir", "ertugliflozin", "sunitinib"]


@pytest.mark.parametrize("drug", ["dolutegravir", "ertugliflozin", "sunitinib"])
@pytest.mark.parametrize("target", ["janus", "mrgsolve", "pksim"])
def test_export_carries_statements_and_no_forbidden_text(drug: str, target: str) -> None:
    files = files_for(drug, target)
    expected = {"provenance.json", "references.bib", "LICENSES.txt", "README.txt"}
    expected |= {
        "janus": {"janus-model.json"},
        "mrgsolve": {"model.cpp", "example.R"},
        "pksim": {"pksim-compound.snapshot.json", "pksim-inputs.json"},
    }[target]
    assert set(files) == expected
    for name, text in files.items():
        assert ex.RESEARCH_USE in text, name
        if name != "references.bib":
            assert ex.NO_REVIEW in text, name
        low = text.lower()
        for bad in FORBIDDEN:
            assert bad.lower() not in low or bad in ("cure", "you have"), (name, bad)
        assert "stop taking" not in low


def test_janus_engine_file_is_the_engine_params() -> None:
    files = files_for("ertugliflozin", "janus")
    doc = json.loads(files["janus-model.json"])
    p = doc["params"]
    assert p["f_fixed"] is True and p["cl_gsd"] == p["v_gsd"] == p["ka_gsd"] == 1.0
    assert doc["schema"] == "janus.modelkit.engine/1"
    assert doc["validation_status"] == "validated" and doc["warnings"]


def test_provenance_ties_every_parameter_to_evidence_with_quotes() -> None:
    prov = json.loads(files_for("sunitinib", "janus")["provenance.json"])
    ids = {e["id"] for e in prov["evidence"]}
    for p in prov["parameters"]:
        assert set(p["evidence"]) <= ids
        if p["name"] != "f":
            assert p["evidence"]
    assert all(e["quote"] and e["locator"] for e in prov["evidence"])
    assert (
        prov["validation"]["status"] == "failed" and len(prov["validation"]["failed_points"]) == 1
    )
    assert prov["left_out"] and prov["kit"]["status"] == "experimental"


def test_references_and_licences_name_the_terms() -> None:
    f = files_for("ertugliflozin", "janus")
    assert "@article" in f["references.bib"] and "PMC9238437" in f["references.bib"].replace(
        "_", ""
    )
    lic = f["LICENSES.txt"]
    assert (
        "ClinicalTrials.gov" in lic and "Modifications by Janus" in lic and "Public domain" in lic
    )
    assert "Credit the authors" in lic


def test_zip_is_deterministic() -> None:
    a = ex.build_zip(files_for("sunitinib", "mrgsolve"))
    b = ex.build_zip(files_for("sunitinib", "mrgsolve"))
    assert a == b
    with zipfile.ZipFile(BytesIO(a)) as z:
        assert z.testzip() is None and "model.cpp" in z.namelist()


def test_incomplete_set_does_not_export() -> None:
    rows = [r for r in seed_rows() if not (r.drug_key == "dolutegravir" and r.parameter == "tmax")]
    ps = build_set("dolutegravir", rows)
    assert isinstance(ps, ParameterSet) and not ps.complete
    with pytest.raises(ex.NotExportableError):
        ex.engine_params(ps)


# --- PK-Sim compound (milestone M4, properties M24 and M25) ---------------------------------------

# Property names of the PK-Sim snapshot classes (PKSim.Core.Snapshots, PK-Sim 12.3 source, GPL-2.0);
# the export may use only these (the loader ignores or rejects others).
PKSIM_PROJECT_KEYS = {
    "Version",
    "Name",
    "Description",
    "ExpressionProfiles",
    "Individuals",
    "Populations",
    "Compounds",
    "Formulations",
    "Protocols",
    "ObserverSets",
    "Events",
    "Simulations",
    "ParameterIdentifications",
    "ObservedData",
    "SimulationComparisons",
    "QualificationPlans",
}
PKSIM_COMPOUND_KEYS = {
    "Name",
    "Description",
    "Parameters",
    "IsSmallMolecule",
    "PlasmaProteinBindingPartner",
    "Lipophilicity",
    "FractionUnbound",
    "Solubility",
    "IntestinalPermeability",
    "Permeability",
    "PkaTypes",
    "Processes",
    "CalculationMethods",
}


@pytest.mark.parametrize("drug", ["dolutegravir", "ertugliflozin", "sunitinib"])
def test_pksim_snapshot_uses_only_known_properties_and_invents_nothing(drug: str) -> None:
    files = files_for(drug, "pksim")
    snap = json.loads(files["pksim-compound.snapshot.json"])
    assert set(snap) <= PKSIM_PROJECT_KEYS and snap["Version"] == ex.PKSIM_SNAPSHOT_VERSION
    (c,) = snap["Compounds"]
    assert set(c) <= PKSIM_COMPOUND_KEYS and c["Name"] == drug
    # nothing physico-chemical, no process, no alternative: the evidence has none (M24)
    assert not set(c) & {
        "Lipophilicity",
        "FractionUnbound",
        "Solubility",
        "IntestinalPermeability",
        "Permeability",
        "PkaTypes",
        "Processes",
        "Parameters",
        "CalculationMethods",
    }
    assert ex.RESEARCH_USE in c["Description"] and ex.NO_REVIEW in c["Description"]
    inputs = json.loads(files["pksim-inputs.json"])
    missing = {i["key"] for i in inputs["inputs"] if i["status"] == "missing"}
    assert missing == {k for _, _, k in ex.PKSIM_MISSING}
    assert all(i["value"] is None for i in inputs["inputs"])
    assert inputs["pksim"]["simulated"] is False and inputs["screening_values"].startswith("none")


def test_pksim_clearance_is_not_assigned_to_an_organ() -> None:
    inputs = json.loads(files_for("ertugliflozin", "pksim")["pksim-inputs.json"])
    (row,) = [i for i in inputs["inputs"] if i["key"] == "clearance_process"]
    assert row["status"] == "not_assigned" and row["evidence"]["unit"] == "L/h"
    assert "assumption" in row["note"]


def test_pksim_zip_is_deterministic() -> None:
    assert ex.build_zip(files_for("sunitinib", "pksim")) == ex.build_zip(
        files_for("sunitinib", "pksim")
    )


# --- PK-Sim load and round trip (M25), when R with ospsuite and .NET 8 are present ---------


def _have_pksim() -> bool:
    if shutil.which("Rscript") is None or shutil.which("dotnet") is None:
        return False
    r = subprocess.run(
        ["Rscript", "-e", "quit(status = as.integer(!requireNamespace('ospsuite', quietly=TRUE)))"],  # noqa: S607
        capture_output=True,
        check=False,
        timeout=300,
    )
    return r.returncode == 0


def _completed_for_test(snap: dict[str, Any]) -> dict[str, Any]:
    """The export completed with TEST-ONLY numbers (not drug data) and the building blocks a
    simulation needs: shows that the exported compound is a valid base for a PK-Sim simulation once
    a person supplies the missing inputs."""
    name = str(snap["Compounds"][0]["Name"])
    methods = [
        "Cellular partition coefficient method - Rodgers and Rowland",
        "Cellular permeability - PK-Sim Standard",
    ]
    comp: dict[str, Any] = {
        **snap["Compounds"][0],
        "Lipophilicity": [
            {
                "Name": "test",
                "Parameters": [{"Name": "Lipophilicity", "Value": 2.0, "Unit": "Log Units"}],
            }
        ],
        "FractionUnbound": [
            {
                "Name": "test",
                "Species": "Human",
                "Parameters": [
                    {"Name": "Fraction unbound (plasma, reference value)", "Value": 0.5}
                ],
            }
        ],
        "Solubility": [
            {
                "Name": "test",
                "Parameters": [
                    {"Name": "Solubility at reference pH", "Value": 1000.0, "Unit": "mg/l"},
                    {"Name": "Reference pH", "Value": 7.0},
                ],
            }
        ],
        "Processes": [
            {
                "InternalName": "GlomerularFiltration",
                "DataSource": "GFR",
                "Species": "Human",
                "Parameters": [{"Name": "GFR fraction", "Value": 1.0}],
            }
        ],
        "CalculationMethods": methods,
        "Parameters": [{"Name": "Molecular weight", "Value": 300.0, "Unit": "g/mol"}],
    }
    ind = {
        "Name": "Ind",
        "OriginData": {
            "CalculationMethods": ["SurfaceAreaPlsInt_VAR1", "Body surface area - Mosteller"],
            "Species": "Human",
            "Population": "European_ICRP_2002",
            "Gender": "MALE",
            "Age": {"Value": 30.0, "Unit": "year(s)"},
        },
    }
    prot = {
        "Name": "IV bolus",
        "ApplicationType": "IntravenousBolus",
        "DosingInterval": "Single",
        "Parameters": [
            {"Name": "Start time", "Value": 0.0, "Unit": "h"},
            {"Name": "InputDose", "Value": 10.0, "Unit": "mg"},
        ],
    }
    sim: dict[str, Any] = {
        "Name": "Sim",
        "Model": "4Comp",
        "Individual": "Ind",
        "Solver": {},
        "OutputSchema": [
            {
                "Parameters": [
                    {"Name": "Start time", "Value": 0.0, "Unit": "h"},
                    {"Name": "End time", "Value": 24.0, "Unit": "h"},
                    {"Name": "Resolution", "Value": 4.0, "Unit": "pts/h"},
                ]
            }
        ],
        "OutputSelections": [
            f"Organism|PeripheralVenousBlood|{name}|Plasma (Peripheral Venous Blood)"
        ],
        "Compounds": [
            {
                "Name": name,
                "CalculationMethods": methods,
                "Processes": [{"Name": "Glomerular Filtration-GFR", "SystemicProcessType": "GFR"}],
                "Protocol": {"Name": "IV bolus"},
            }
        ],
    }
    return {
        "Version": snap["Version"],
        "Name": "completed",
        "Individuals": [ind],
        "Compounds": [comp],
        "Protocols": [prot],
        "Simulations": [sim],
    }


@pytest.mark.pksim
@pytest.mark.parametrize("drug", ["dolutegravir", "ertugliflozin", "sunitinib"])
def test_pksim_loads_exports_again_and_simulates_when_completed(tmp_path: Path, drug: str) -> None:
    if not _have_pksim():
        if os.environ.get("JANUS_REQUIRE_PKSIM") == "1":
            pytest.fail("R with ospsuite and .NET 8 are required (JANUS_REQUIRE_PKSIM=1)")
        pytest.skip("R with ospsuite and .NET 8 are not installed")
    snap = json.loads(files_for(drug, "pksim")["pksim-compound.snapshot.json"])
    (tmp_path / "export.json").write_text(json.dumps(snap), encoding="utf-8")
    (tmp_path / "completed.json").write_text(
        json.dumps(_completed_for_test(snap)), encoding="utf-8"
    )
    r = subprocess.run(  # noqa: S603
        ["Rscript", str(HERE / "pksim_roundtrip.R"), str(tmp_path)],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
        timeout=900,
    )
    assert r.returncode == 0, (r.stdout + r.stderr)[-3000:]
    out = json.loads((tmp_path / "out.json").read_text(encoding="utf-8"))
    assert out["projects"] and out["snapshots"], out
    back = json.loads((tmp_path / "snap" / out["snapshots"][0]).read_text(encoding="utf-8"))
    (c,) = back["Compounds"]
    # the compound survived load and export: name, description, small molecule
    assert c["Name"] == drug and c["Description"] == snap["Compounds"][0]["Description"]
    assert c["IsSmallMolecule"] is True
    # PK-Sim fills what the snapshot leaves out with its own defaults: they are PK-Sim's, not ours
    assert out["results"], out
    lines = (tmp_path / "sim" / out["results"][0]).read_text(encoding="utf-8-sig").splitlines()
    conc = [float(x.split(",")[2]) for x in lines[1:]]
    assert len(conc) > 20 and max(conc) > 0 and all(v >= 0 for v in conc)


# --- mrgsolve round trip (property M7) ------------------------------------------------------------

RLIB = Path(os.environ.get("R_LIBS_USER", "")) if os.environ.get("R_LIBS_USER") else None


def _have_mrgsolve() -> bool:
    if shutil.which("Rscript") is None:
        return False
    r = subprocess.run(
        ["Rscript", "-e", "quit(status = as.integer(!requireNamespace('mrgsolve', quietly=TRUE)))"],  # noqa: S607
        capture_output=True,
        check=False,
        timeout=120,
    )
    return r.returncode == 0


@pytest.mark.mrgsolve
@pytest.mark.parametrize("drug", ["dolutegravir", "ertugliflozin", "sunitinib"])
@pytest.mark.parametrize(("doses", "interval"), [(1, None), (3, 24)])
def test_mrgsolve_reproduces_the_janus_engine_curve(
    tmp_path: Path, drug: str, doses: int, interval: int | None
) -> None:
    if not _have_mrgsolve():
        if os.environ.get("JANUS_REQUIRE_MRGSOLVE") == "1":
            pytest.fail("R with mrgsolve is required (JANUS_REQUIRE_MRGSOLVE=1)")
        pytest.skip("R with mrgsolve is not installed")
    rows = seed_rows()
    ps = build_set(drug, rows)
    assert isinstance(ps, ParameterSet)
    files = ex.export_files("mrgsolve", ps, validate(drug, rows, ps), rows, RELEASE)
    (tmp_path / "model.cpp").write_text(files["model.cpp"], encoding="utf-8")
    dose = ex.example_dose_mg(validate(drug, rows, ps))
    ref = explore(ex.engine_params(ps), dose, 240.0, 1, interval_h=interval, doses=doses)
    cp = ref["p50_ng_ml"]
    (tmp_path / "ref.json").write_text(
        json.dumps({"dose": dose, "times": ref["hours"], "interval_h": interval, "doses": doses}),
        encoding="utf-8",
    )
    r = subprocess.run(  # noqa: S603
        ["Rscript", str(HERE / "mrgsolve_roundtrip.R"), str(tmp_path)],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
        timeout=600,
    )
    assert r.returncode == 0, r.stderr[-2000:]
    out = json.loads((tmp_path / "out.json").read_text(encoding="utf-8"))
    peak = max(cp)
    assert peak > 0
    for t, a, b in zip(ref["hours"], cp, out["cp"], strict=True):
        if a >= 1e-3 * peak:
            assert abs(b - a) <= 0.01 * a, (drug, t, a, b)
        else:
            assert abs(b - a) <= 1e-3 * peak, (drug, t, a, b)


def test_source_info_of_review_and_article_rows_milestone_m5() -> None:
    from janus.modelkit.export import source_info
    from tests.modelkit_helpers import ev

    pdf = "https://www.accessdata.fda.gov/drugsatfda_docs/nda/2020/123456Orig1s000ClinPharmR.pdf"
    fda = ev(source_id="drugsatfda_review", study_id="FDA study AB1001",
             source_locator=f"{pdf}#page=12&line=30&col=40")  # fmt: skip
    info = source_info(fda, {})
    assert info is not None and info["url"] == f"{pdf}#page=12" and info["type"] == "review"
    art = ev(source_id="pmc_oa", study_id="PMC123456", source_locator="PMC123456#tab2/r1c1",
             source_version="PMC123456; Jane Doe. Title. 2024. Licence CC BY 4.0")  # fmt: skip
    info = source_info(art, {})
    assert info is not None
    assert info["url"] == "https://pmc.ncbi.nlm.nih.gov/articles/PMC123456/"
    assert "CC BY 4.0" in info["licence"]
    assert source_info(ev(source_id="pmc_oa", source_locator="elsewhere"), {}) is None
