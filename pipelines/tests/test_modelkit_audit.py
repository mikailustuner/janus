"""Expert sample audit scoring (milestone M6): Wilson intervals, the strict consensus, the plan 12.3
criterion and the `expert_audit` record, on synthetic fills (no real answer exists yet)."""

from __future__ import annotations

import csv
import json
import random
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

import pytest
from hypothesis import given
from hypothesis import strategies as st

from janus_pipelines.modelkit.audit import (
    check_record,
    consensus,
    criterion_met,
    kappa,
    make_record,
    read_answers,
    score,
    share,
    wilson,
)

TOOL = Path(__file__).resolve().parents[1] / "tools" / "score_modelkit_audit.py"
STRATA = [
    ("E", "ctgov|cmax|healthy"), ("E", "ctgov|half_life|unspecified"), ("E", "label_pk|tmax|any"),
    ("E", "m0_documents|auc|healthy"), ("S", "S|renal|auc"), ("S", "S|hepatic|cmax"),
]  # fmt: skip


def synthetic_key(n: int, seed: int = 1) -> list[dict[str, str]]:
    rnd = random.Random(seed)  # noqa: S311 - synthetic data
    out: list[dict[str, str]] = []
    for i in range(1, n + 1):
        frame, stratum = rnd.choice(STRATA)
        out.append({"item_id": f"A{i:03d}", "frame": frame, "stratum": stratum})
    return out


def fill(key: list[dict[str, str]], correct: int, incorrect: int, cannot: int) -> dict[str, str]:
    verdicts = ["correct"] * correct + ["incorrect"] * incorrect + ["cannot_judge"] * cannot
    verdicts += [""] * (len(key) - len(verdicts))
    return {k["item_id"]: v for k, v in zip(key, verdicts, strict=True)}


def test_wilson_matches_known_values() -> None:
    lo, hi = wilson(95, 100) or (0, 0)
    assert lo == pytest.approx(0.8883, abs=1e-4) and hi == pytest.approx(0.9785, abs=1e-4)
    assert wilson(0, 0) is None
    lo, hi = wilson(10, 10) or (0, 0)
    assert hi == 1.0 and 0.69 < lo < 0.73


@given(st.integers(0, 400), st.integers(1, 400))
def test_wilson_contains_the_share(k: int, n: int) -> None:
    k = min(k, n)
    lo, hi = wilson(k, n) or (0, 0)
    assert 0 <= lo <= k / n <= hi <= 1


def test_criterion_of_plan_12_3() -> None:
    assert criterion_met(share(["correct"] * 300))
    # 0.95 with n = 300: Wilson lower about 0.918
    assert criterion_met(share(["correct"] * 285 + ["incorrect"] * 15))
    assert not criterion_met(share(["correct"] * 284 + ["incorrect"] * 15))  # n = 299
    assert not criterion_met(share(["correct"] * 282 + ["incorrect"] * 18))  # 0.94
    # cannot-judge items leave n: 366 items, 70 cannot judge, 296 judged -> not met
    assert not criterion_met(share(["correct"] * 296 + ["cannot_judge"] * 70))


def test_score_per_stratum_margin_and_overall() -> None:
    key = synthetic_key(366)
    res = cast(dict[str, Any], score(fill(key, 330, 10, 20), key))
    o = res["overall"]
    assert o["n"] == 340 and o["correct"] == 330 and o["cannot_judge"] == 20 and o["blank"] == 6
    assert o["precision"] == pytest.approx(330 / 340)
    assert o["conservative"] == pytest.approx(330 / 360)
    assert res["criterion"] == {
        "precision_min": 0.95,
        "wilson_low_min": 0.9,
        "n_min": 300,
        "met": True,
    }
    strata = cast(dict[str, dict[str, int]], res["stratum"])
    assert set(strata) == {s for _, s in STRATA}
    assert sum(v["n"] for v in strata.values()) == 340
    assert set(res["source"]) == {"ctgov", "label_pk", "m0_documents", "S"}
    assert set(res["population"]) == {"healthy", "unspecified", "any"}
    assert set(res["sp_class"]) == {"renal", "hepatic"}


def test_frame_weighted_estimate_uses_the_frame_sizes() -> None:
    key = [
        {"item_id": "A001", "frame": "E", "stratum": "ctgov|cmax|healthy"},
        {"item_id": "A002", "frame": "E", "stratum": "ctgov|tmax|healthy"},
    ]
    res = score(
        {"A001": "correct", "A002": "incorrect"},
        key,
        {"ctgov|cmax|healthy": 300, "ctgov|tmax|healthy": 100},
    )
    assert res["frame_weighted_precision"] == {"E": pytest.approx(0.75)}


def test_answers_for_unknown_items_are_refused() -> None:
    with pytest.raises(ValueError, match="not in the key"):
        score({"Z999": "correct"}, synthetic_key(3))


def test_read_answers_checks_verdicts_and_error_classes() -> None:
    ok = read_answers(
        [
            {"item_id": "A001", "verdict": "Correct"},
            {"item_id": "A002", "verdict": "incorrect", "error_class": "analyte; population"},
            {"item_id": "A003", "verdict": "cannot judge"},
            {"item_id": "A004", "verdict": ""},
        ],
        "sheet",
    )
    assert ok == {"A001": "correct", "A002": "incorrect", "A003": "cannot_judge", "A004": ""}
    for bad in (
        [{"item_id": "A001", "verdict": "maybe"}],
        [{"item_id": "A001", "verdict": "incorrect", "error_class": ""}],
        [{"item_id": "A001", "verdict": "incorrect", "error_class": "typo"}],
        [{"item_id": "A001", "verdict": "correct"}, {"item_id": "A001", "verdict": "correct"}],
        [{"item_id": "", "verdict": "correct"}],
    ):
        with pytest.raises(ValueError):
            read_answers(bad, "sheet")


def test_consensus_is_strict() -> None:
    a = {"1": "correct", "2": "correct", "3": "cannot_judge", "4": "", "5": "incorrect"}
    b = {"1": "correct", "2": "incorrect", "3": "cannot_judge", "4": "", "5": "cannot_judge"}
    assert consensus([a, b]) == {
        "1": "correct", "2": "incorrect", "3": "cannot_judge", "4": "", "5": "incorrect"
    }  # fmt: skip
    assert consensus([{"1": "cannot_judge"}, {"1": "correct"}]) == {"1": "correct"}


def test_kappa() -> None:
    a = {str(i): "correct" for i in range(10)} | {"10": "incorrect"}
    assert kappa(a, a) == 1.0
    b = dict(a) | {"10": "correct", "0": "incorrect"}
    k = kappa(a, b)
    assert k is not None and k < 0.1
    assert kappa({"1": "cannot_judge"}, {"1": "correct"}) is None


def test_record_is_checked_and_holds_no_name() -> None:
    key = synthetic_key(366)
    res = score(fill(key, 330, 10, 20), key)
    rec = make_record(res, date="2027-01-15", release="20261112T135125Z-8ac5398b-3c00",
                      roles=["pharmacometrician", "clinical_pharmacologist"], n_items=366,
                      reviewers_met=True)  # fmt: skip
    assert rec["criterion_met"] is True and rec["n"] == 340
    assert rec["reviewer_roles"] == ["clinical_pharmacologist", "pharmacometrician"]
    check_record(rec)
    lo, hi = wilson(280, 340) or (0.0, 0.0)
    changes: list[dict[str, object]] = [
        {"reviewer_name": "someone"},
        {"precision": 0.99},
        {"correct": 341},
        {"date": "15.01.2027"},
        {"reviewer_roles": ["Dr. Someone"]},
        {"reviewer_roles": []},
        # criterion claimed although 280 of 340 (0.82) is below it
        {"criterion_met": True, "correct": 280, "precision": 280 / 340, "wilson_low": lo,
         "wilson_high": hi},
    ]  # fmt: skip
    for change in changes:
        with pytest.raises(ValueError):
            check_record({**rec, **change})
    # a reviewer below the criterion keeps the record's criterion unmet
    low = make_record(res, date="2027-01-15", release="r", roles=["pharmacist"], n_items=366,
                      reviewers_met=False)  # fmt: skip
    assert low["criterion_met"] is False


def test_tool_end_to_end_with_two_synthetic_reviewers(tmp_path: Path) -> None:
    key = synthetic_key(366, seed=7)
    with (tmp_path / "key.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, ["item_id", "frame", "stratum"])
        w.writeheader()
        w.writerows(key)
    (tmp_path / "sizes.json").write_text(json.dumps({s: 100 for _, s in STRATA}))
    rnd = random.Random(3)  # noqa: S311 - synthetic data
    for name, p_wrong in (("a", 0.02), ("b", 0.03)):
        with (tmp_path / f"{name}.csv").open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, ["item_id", "verdict", "error_class"])
            w.writeheader()
            for k in key:
                u = rnd.random()
                v = (
                    "incorrect"
                    if u < p_wrong
                    else "cannot_judge"
                    if u < p_wrong + 0.03
                    else "correct"
                )
                error = "value" if v == "incorrect" else ""
                w.writerow({"item_id": k["item_id"], "verdict": v, "error_class": error})
    out, rec = tmp_path / "result.json", tmp_path / "expert_audit.json"
    args = [
        str(TOOL), str(tmp_path / "key.csv"), str(tmp_path / "sizes.json"), str(out),
        f"{tmp_path / 'a.csv'}:pharmacometrician",
        f"{tmp_path / 'b.csv'}:clinical_pharmacologist",
        "--record", str(rec), "--date", "2027-01-15", "--release", "run-x",
    ]  # fmt: skip
    subprocess.run([sys.executable, *args], check=True, capture_output=True, timeout=60)  # noqa: S603
    result: dict[str, Any] = json.loads(out.read_text())
    assert len(result["reviewers"]) == 2 and "0-1" in result["kappa"]
    cons = result["consensus"]["overall"]
    assert cons["n"] + cons["cannot_judge"] + cons["blank"] == 366
    record: dict[str, Any] = json.loads(rec.read_text())
    check_record(record)
    assert record["n"] == cons["n"] and record["criterion_met"] == result["criterion_met"]
    assert "name" not in json.dumps(record)
