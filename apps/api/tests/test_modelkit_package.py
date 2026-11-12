"""Model kit data package (milestone M6): only publishable rows, every source's terms, a hash per
file, deterministic, no DOI and the statements in every text file."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path
from typing import Any

import pytest

from janus.modelkit.package import build, publishable
from janus.modelkit.store import build_release
from janus.paths import repo_root
from tests.modelkit_helpers import ev, seed_dicts, write_run

FORBIDDEN = ("safe dose", "safe to", "recommended dose", " AI ", "artificial intelligence")


def _release(
    tmp: Path, extra: list[dict[str, Any]] | None = None, metrics: dict[str, Any] | None = None
):
    write_run(tmp, seed_dicts() + (extra or []), metrics)
    return build_release(tmp / "artifacts" / "modelkit_evidence" / "current")


def test_the_package_holds_every_published_row_and_its_terms(tmp_path: Path) -> None:
    rel = _release(tmp_path)
    files = build(rel, repo_root())
    assert set(files) == {
        "evidence.csv", "special_populations.csv", "parameter_sets.csv", "parameter_sets.json",
        "validation.json", "licences.json", "README.md", ".zenodo.json", "datapackage.json",
    }  # fmt: skip
    rows = list(csv.DictReader(io.StringIO(files["evidence.csv"].decode())))
    assert len(rows) == sum(len(d.rows) for d in rel.drugs.values())
    assert {r["source_id"] for r in rows} <= {
        "clinicaltrials_gov", "dailymed_spl", "pmc_oa", "drugsatfda_review"
    }  # fmt: skip
    assert all(r["origin"] == "m0_annotation" for r in rows if r["source_id"] == "pmc_oa")
    lic = json.loads(files["licences.json"])
    ct = lic["sources"]["clinicaltrials_gov"]
    assert ct["attribution"] == "Source of the data: ClinicalTrials.gov."
    assert "2026-11-11" in ct["processed"] and "re-typed" in ct["changes"]
    assert lic["sources"]["pmc_oa"]["articles"]
    sets = json.loads(files["parameter_sets.json"])
    assert {s["drug"] for s in sets} >= {"ertugliflozin", "sunitinib", "dolutegravir"}
    val = json.loads(files["validation.json"])
    assert val["drugs"]["sunitinib"]["status"] == "failed"


def test_datapackage_hashes_and_rows_match_and_the_build_is_deterministic(tmp_path: Path) -> None:
    rel = _release(tmp_path)
    files = build(rel, repo_root())
    assert files == build(rel, repo_root())
    desc = json.loads(files["datapackage.json"])
    assert desc["version"].endswith(rel.run_id)
    for res in desc["resources"]:
        data = files[res["path"]]
        assert res["hash"] == "sha256:" + hashlib.sha256(data).hexdigest()
        if res["path"].endswith(".csv"):
            assert res["rows"] == len(list(csv.reader(io.StringIO(data.decode())))) - 1


def test_no_doi_no_creator_and_the_statements_everywhere(tmp_path: Path) -> None:
    files = build(_release(tmp_path), repo_root())
    z = json.loads(files[".zenodo.json"])
    assert "doi" not in z and z["creators"] == [] and "10." not in json.dumps(z)
    readme = files["README.md"].decode()
    for text in (readme, z["description"], json.loads(files["datapackage.json"])["description"]):
        assert "Research use only. Not for clinical decisions." in text
        assert "Expert review has not yet been done." in text
        assert "no person has checked it" in text
        assert not any(f.lower() in f" {text.lower()} " for f in FORBIDDEN)
    assert "A DOI has not been assigned yet." in readme


@pytest.mark.parametrize(
    ("row", "why"),
    [
        (
            {"source_id": "pmc_oa", "origin": "reader_pair", "source_version": "licence CC BY"},
            "held-back",
        ),
        ({"source_id": "drugsatfda_review", "origin": "reader_pair"}, "held-back"),
        (
            {
                "source_id": "pmc_oa",
                "origin": "m0_annotation",
                "source_version": "licence CC BY-NC",
            },
            "PMC",
        ),
        (
            {
                "source_id": "pmc_oa",
                "origin": "m0_annotation",
                "source_version": "licence CC BY-SA 4.0",
            },
            "PMC",
        ),
        ({"source_id": "titck", "origin": "reader_pair"}, "unknown source"),
    ],
)
def test_a_row_that_may_not_be_published_stops_the_build(
    tmp_path: Path, row: dict[str, str], why: str
) -> None:
    bad = {**ev(study_id="X9", source_locator="x9").public(), **row}
    bad.pop("eid")
    rel = _release(tmp_path, [{**bad, "pipeline_version": "t"}])
    with pytest.raises(ValueError, match=why):
        build(rel, repo_root())


def test_publishable_rules() -> None:
    assert publishable(ev(), frozenset()) is None
    assert publishable(ev(source_id="dailymed_spl"), frozenset()) is None
    pmc = ev(source_id="pmc_oa", origin="reader_pair", source_version="licence CC0")
    assert publishable(pmc, frozenset()) is not None
    assert publishable(pmc, frozenset({"pmc_oa"})) is None  # published by its measured precision
    m0 = ev(source_id="pmc_oa", origin="m0_annotation", source_version="licence CC BY (article)")
    assert publishable(m0, frozenset()) is None
