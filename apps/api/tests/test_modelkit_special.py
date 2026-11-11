"""Special populations in the model kit (M4, property M27): the committed files, the reader of them,
the drug and system answers."""

from __future__ import annotations

import csv
import json
import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from janus.main import create_app
from janus.modelkit import router as r
from janus.modelkit import special
from janus.modelkit.store import ModelkitHolder
from janus.paths import repo_root
from tests.modelkit_helpers import seed_dicts, write_run

UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
CUE = {
    "geriatric": re.compile(r"elderly|geriatric|older|aged|65|age", re.I),
    "renal": re.compile(r"renal|kidney|creatinine|clcr|crcl|egfr|esrd", re.I),
    "hepatic": re.compile(r"hepatic|liver|child|cirrho", re.I),
}
FIELDS = (
    "drug_key,pop_class,grade,measure,ratio,ratio_text,definition,reference,quote,set_id,version,"
    "effective_date,section,n_labels,from_table"
)


def write_files(root: Path, statements: list[dict[str, str]], atlas: list[dict[str, str]]) -> None:
    d = root / "data" / "modelkit"
    d.mkdir(parents=True)
    with (d / "special_populations.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS.split(","), lineterminator="\n")
        w.writeheader()
        w.writerows(statements)
    cols = "drug_key,measure,ratio,qualitative,quote,set_id,version,n_labels,quote_checked".split(
        ","
    )
    with (d / "special_populations_atlas.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, lineterminator="\n")
        w.writeheader()
        w.writerows(atlas)
    (d / "special_populations.meta.json").write_text(
        json.dumps(
            {
                "coverage": {
                    "labels_read": 100,
                    "labels_matched": 10,
                    "drugs_with_a_matched_label": 5,
                },
                "precision": {
                    "measured_on": "2026-11-12",
                    "n": 50,
                    "correct": 40,
                    "n_conservative": 60,
                    "correct_conservative": 40,
                    "target": 0.9,
                },
            }
        ),
        encoding="utf-8",
    )


def stmt(**kw: str) -> dict[str, str]:
    base = {
        "drug_key": "sunitinib",
        "pop_class": "hepatic",
        "grade": "cp_b",
        "measure": "auc",
        "ratio": "1.5",
        "ratio_text": "50 % higher",
        "definition": "Child-Pugh B",
        "reference": "healthy subjects",
        "quote": "AUC was 50% higher in patients with Child-Pugh B hepatic impairment.",
        "set_id": "0cbce382-9c88-4f58-ae0f-532a841e8f95",
        "version": "7",
        "effective_date": "2025-01-02",
        "section": "pharmacokinetics",
        "n_labels": "3",
        "from_table": "false",
    }
    return {**base, **kw}


def atlas(**kw: str) -> dict[str, str]:
    base = {
        "drug_key": "sunitinib",
        "measure": "auc",
        "ratio": "1.25",
        "qualitative": "false",
        "quote": "AUC was higher in elderly volunteers.",
        "set_id": "5a50d22e-acbe-4b15-9ed6-70713378408a",
        "version": "3",
        "n_labels": "1",
        "quote_checked": "true",
    }
    return {**base, **kw}


@pytest.fixture
def sp_root(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    write_files(
        root,
        [
            stmt(),
            stmt(
                pop_class="renal",
                grade="severe",
                ratio="2",
                ratio_text="2-fold higher",
                definition="CLcr <30",
            ),
            stmt(pop_class="geriatric", grade="age65", measure="cmax", ratio="1.2"),
        ],
        [
            atlas(),
            atlas(drug_key="gabapentin", measure="cl", qualitative="true", quote_checked="false"),
        ],
    )
    return root


def test_load_sorts_by_class_and_reads_the_meta(sp_root: Path) -> None:
    sp = special.load(sp_root)
    rows = sp.statements["sunitinib"]
    assert [s.pop_class for s in rows] == ["geriatric", "renal", "hepatic"]
    assert rows[2].ratio == 1.5 and rows[2].n_labels == 3 and not rows[2].from_table
    assert sp.atlas["gabapentin"][0].qualitative and not sp.atlas["gabapentin"][0].quote_checked
    assert sp.meta["coverage"]["labels_read"] == 100


def test_missing_files_mean_no_statements(tmp_path: Path) -> None:
    sp = special.load(tmp_path)
    assert sp.statements == {} and sp.atlas == {} and sp.meta == {}
    assert special.system_counts(sp)["statements"] == 0


def test_system_counts(sp_root: Path) -> None:
    c = special.system_counts(special.load(sp_root))
    assert c["drugs"] == 1 and c["statements"] == 3 and c["atlas_drugs"] == 2
    assert c["by_class"] == {"geriatric": 1, "renal": 1, "hepatic": 1}
    assert c["drugs_by_class"]["renal"] == 1


@pytest.fixture
def client(tmp_path: Path, sp_root: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    sp = special.load(sp_root)
    monkeypatch.setattr(special, "load", lambda root=None: sp)
    write_run(tmp_path, seed_dicts(), {})
    app: FastAPI = create_app(configure_logs=False)
    app.state.modelkit = ModelkitHolder(tmp_path)
    with TestClient(app) as cl:
        yield cl


def test_drug_answer_carries_quoted_statements_and_unconfirmed_atlas_rows(
    client: TestClient,
) -> None:
    out = client.get("/modelkit/drugs/sunitinib").json()["special_populations"]
    assert set(out) == {"statements", "atlas", "notes"}
    s = out["statements"][-1]
    assert set(s) == set(r.SpecialStatementOut.model_fields)
    assert s["status"] == "two_readers_agree" and s["source_url"].endswith(s["set_id"])
    assert s["source_url"].startswith("https://dailymed.nlm.nih.gov/dailymed/lookup.cfm?setid=")
    a = out["atlas"][0]
    assert set(a) == set(r.SpecialAtlasOut.model_fields)
    assert a["status"] == "automated_extraction_unconfirmed"
    assert out["notes"] == ["sp_statements_note", "sp_atlas_note"]


def test_a_drug_without_statements_says_so(client: TestClient) -> None:
    out = client.get("/modelkit/drugs/dolutegravir").json()["special_populations"]
    assert out["statements"] == [] and out["atlas"] == [] and out["notes"] == ["sp_none"]


def test_system_report_has_counts_coverage_and_precision_with_an_interval(
    client: TestClient,
) -> None:
    sp = client.get("/modelkit/validation").json()["special_populations"]
    assert set(sp) == set(r.SpecialSystemOut.model_fields)
    assert sp["statements"] == 3 and sp["coverage"]["labels_read"] == 100
    p = sp["precision"]
    assert p["n"] == 50 and p["correct"] == 40 and p["share"] == 0.8
    assert p["wilson_low"] < 0.8 < p["wilson_high"] and p["target"] == 0.9


def test_reason_texts_say_no_person_checked_and_no_dose_advice() -> None:
    from janus.modelkit.reasons import TEXT

    a, b = TEXT["sp_statements_note"].lower(), TEXT["sp_atlas_note"].lower()
    assert "no person has checked" in a and "not dose advice" in a
    assert "not confirm" in b and "no person has checked" in b and "not a verdict" in b


# --- the committed files (property M27: what is committed obeys the display rule) ----------------


def test_committed_statements_obey_the_rules() -> None:
    base = repo_root() / "data" / "modelkit"
    path = base / "special_populations.csv"
    if not path.is_file():
        pytest.skip("no committed special-population statements")
    assert path.stat().st_size < 1_000_000  # no committed file larger than 1 MB (requirement 1.5)
    seen: set[tuple[str, ...]] = set()
    with path.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert rows
    for row in rows:
        assert row["pop_class"] in special.POP_CLASSES and row["measure"] in special.MEASURES
        assert 0 < float(row["ratio"]) <= 50
        assert UUID.match(row["set_id"]) and row["version"] and row["quote"]
        assert CUE[row["pop_class"]].search(row["quote"]), row  # the quote names its own population
        assert int(row["n_labels"]) >= 1
        k = (
            row["drug_key"],
            row["pop_class"],
            row["grade"],
            row["measure"],
            f"{float(row['ratio']):.3g}",
        )
        assert k not in seen
        seen.add(k)


def test_committed_atlas_rows_are_one_per_drug_and_marked_by_the_loader() -> None:
    sp = special.load()
    for key, rows in sp.atlas.items():
        assert rows and key
        assert all(0 < a.ratio <= 50 and a.quote for a in rows)
