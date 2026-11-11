"""Milestone M2: the ClinicalTrials.gov bulk intake job and its merge into the evidence store."""

from __future__ import annotations

import datetime as dt
import json
import re
import zipfile
from pathlib import Path
from typing import Any

import polars as pl

from janus_pipelines.core.manifest import Outcome
from janus_pipelines.core.registry import load_registry
from janus_pipelines.core.runner import RunContext, run_job
from janus_pipelines.core.store import Store
from janus_pipelines.jobs.modelkit_ctgov import ModelkitCtgovJob
from janus_pipelines.jobs.modelkit_evidence import ModelkitEvidenceJob
from janus_pipelines.modelkit.resolver import IdentityTable, _trie_pattern, norm  # pyright: ignore[reportPrivateUsage]
from tests.test_modelkit_readers import outcome, study

REPO = Path(__file__).resolve().parents[2]
NOW = dt.datetime(2026, 11, 11, 12, 0, tzinfo=dt.UTC)


def test_identity_pool_covers_609_drugs_and_the_m1_drugs() -> None:
    text = (REPO / "data" / "modelkit" / "identity_m2.csv").read_text("utf-8")
    table = IdentityTable.from_csv(text)
    assert len(table.by_key) == 609
    m1 = IdentityTable.from_csv((REPO / "data" / "modelkit" / "identity_m1.csv").read_text("utf-8"))
    assert set(m1.by_key) <= set(table.by_key)
    assert table.drugs_in("PK of Dolutegravir (GSK1349572) and Rilpivirine")[:1] == ["dolutegravir"]
    assert table.drugs_in("street names: speed, coke and crack") == []  # slang names are left out


def test_prefix_tree_pattern_matches_like_a_sorted_alternation() -> None:
    words = ["ab", "abc", "b", "abd e", "x y z", "xy"]
    old = re.compile(
        r"\b(?:" + "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True)) + r")\b"
    )
    new = re.compile(r"\b(?:" + _trie_pattern(words) + r")\b")
    for text in ("ab abc b abd e xy x y z abx", "abcd ab-c b b", "nothing", "xy z x y z"):
        t = norm(text)
        assert old.findall(t) == new.findall(t), text
    assert re.compile(_trie_pattern([])).search("anything") is None


def _record(nct: str, with_results: bool, title: str) -> dict[str, Any]:
    s = study([outcome(title, "Dolutegravir alone 50 mg", "68186")])
    s["protocolSection"]["identificationModule"]["nctId"] = nct
    if not with_results:
        del s["resultsSection"]
    return s


def _make_zip(path: Path) -> None:
    other = _record("NCT00000003", True, "AUC(0-inf) of Dolutegravir")
    other["protocolSection"]["armsInterventionsModule"] = {
        "interventions": [{"type": "DRUG", "name": "Unknown compound 7", "description": ""}]
    }
    with zipfile.ZipFile(path, "w") as zf:
        for rec in (
            _record("NCT00000001", True, "AUC(0-inf) of Dolutegravir"),
            _record("NCT00000002", False, "AUC(0-inf) of Dolutegravir"),  # no posted results
            _record("NCT00000004", True, "Number of participants with headache"),  # no PK outcome
            other,  # no pool drug named
        ):
            nct = rec["protocolSection"]["identificationModule"]["nctId"]
            zf.writestr(f"{nct[:7]}xxxx/{nct}.json", json.dumps(rec))


def _ctx(tmp_path: Path) -> RunContext:
    return RunContext(
        data_dir=tmp_path / "data_dir",
        repo_root=REPO,
        registry=load_registry(REPO / "pipelines" / "sources.toml"),
        code_version="test",
        now=lambda: NOW,
        is_ignored=lambda _p: True,
    )


def test_job_keeps_only_studies_with_results_a_pk_outcome_and_a_pool_drug(tmp_path: Path) -> None:
    z = tmp_path / "ctg-studies.json.zip"
    _make_zip(z)
    ctx = _ctx(tmp_path)
    ctx.options["input"] = str(z)
    result = run_job(ModelkitCtgovJob(), ctx)
    assert result.outcome in (Outcome.SUCCEEDED, Outcome.NEEDS_REVIEW), result.error
    store = Store(ctx.data_dir, "modelkit_ctgov")
    df = pl.read_parquet(store.run_dir(result.run_id) / "rows.parquet")
    assert set(df["study_id"]) == {"NCT00000001"}
    assert set(df["drug_key"]) == {"dolutegravir"}
    assert df["extracted_at"].unique().to_list() == ["2026-11-11"]
    m = result.manifest.metrics
    assert m["studies"] == 4 and m["studies_with_results"] == 3
    assert m["studies_with_pk_outcome"] == 2 and m["studies_naming_a_pool_drug"] == 1


def test_evidence_job_replaces_the_seed_ctgov_rows_of_covered_drugs(tmp_path: Path) -> None:
    z = tmp_path / "ctg-studies.json.zip"
    _make_zip(z)
    ctx = _ctx(tmp_path)
    ctx.options["input"] = str(z)
    run_job(ModelkitCtgovJob(), ctx)
    ctx.options.pop("input")
    res = run_job(ModelkitEvidenceJob(), ctx)
    assert res.outcome in (Outcome.SUCCEEDED, Outcome.NEEDS_REVIEW), res.error
    df = pl.read_parquet(
        Store(ctx.data_dir, "modelkit_evidence").run_dir(res.run_id) / "rows.parquet"
    )
    rows = df.to_dicts()
    ids = {r["study_id"] for r in rows if r["drug_key"] == "dolutegravir"}
    assert ids >= {"NCT00000001"}
    # the seed's own ClinicalTrials.gov rows of that drug are replaced
    seed_ids = {r["study_id"] for r in rows if r["source_id"] == "clinicaltrials_gov"}
    assert not any(
        r["drug_key"] == "dolutegravir"
        and r["source_id"] == "clinicaltrials_gov"
        and r["study_id"] != "NCT00000001"
        for r in rows
    ), seed_ids
    assert (df["drug_key"] == "gabapentin").sum() > 0  # other drugs keep theirs


def test_the_result_does_not_depend_on_the_number_of_workers(tmp_path: Path) -> None:
    import os
    from collections import Counter

    from janus_pipelines.modelkit.ctgov_bulk import read_bulk
    from janus_pipelines.modelkit.model import ReaderStats

    z = tmp_path / "ctg-studies.json.zip"
    _make_zip(z)
    text = (REPO / "data" / "modelkit" / "identity_m2.csv").read_text("utf-8")
    seen: list[tuple[list[tuple[str, str, float]], dict[str, int]]] = []
    for workers in (1, 2):
        counts: Counter[str] = Counter()
        stats = {"a": ReaderStats(), "b": ReaderStats()}
        pairs, _, kept = read_bulk(z, text, stats, counts, workers)
        seen.append(([(p.a.drug_key, p.a.locator, p.a.value) for p in pairs], dict(counts)))
        assert set(kept) == {"dolutegravir"}
    assert seen[0] == seen[1] and seen[0][0]
    assert os.environ.get("JANUS_MODELKIT_WORKERS") is None
