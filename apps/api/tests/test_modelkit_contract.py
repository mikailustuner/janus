"""Model kit API contract (M3): exact fields, headers and error codes of every route; intervals only
from 20 independent held-out studies; the system report with counts, precision and gaps."""

from __future__ import annotations

import math
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from janus.main import create_app
from janus.modelkit import router as r
from janus.modelkit.store import ModelkitHolder
from janus.modelkit.validate import (
    MIN_STUDIES_FOR_INTERVAL,
    Point,
    Validation,
    conformal_fold_width,
    conformal_intervals,
    wilson,
)
from tests.modelkit_helpers import RUN_ID, seed_dicts, write_run

PRECISION = {
    "measured_on": "2026-11-12",
    "n": 100,
    "correct": 80,
    "n_conservative": 120,
    "correct_conservative": 90,
    "formulation_n": 50,
    "formulation_correct": 45,
    "target": 0.9,
}


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    write_run(tmp_path, seed_dicts(), {"precision": PRECISION})
    app: FastAPI = create_app(configure_logs=False)
    app.state.modelkit = ModelkitHolder(tmp_path)
    with TestClient(app) as cl:
        yield cl


ROUTES: list[tuple[str, type[r._Out]]] = [  # pyright: ignore[reportPrivateUsage]
    ("/modelkit/drugs", r.DrugsOut),
    ("/modelkit/drugs/sunitinib", r.DrugOut),
    ("/modelkit/drugs/sunitinib/evidence", r.EvidenceOut),
    ("/modelkit/validation", r.SystemOut),
]


@pytest.mark.parametrize(("path", "model"), ROUTES)
def test_json_routes_answer_with_exactly_the_documented_fields(
    client: TestClient,
    path: str,
    model: type[r._Out],  # pyright: ignore[reportPrivateUsage]
) -> None:
    resp = client.get(path)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/json")
    assert resp.headers["cache-control"] == "no-store"
    body = resp.json()
    assert set(body) == set(model.model_fields)
    model.model_validate(body)
    assert body["release"]["run_id"] == RUN_ID
    assert body["statements"]["expert_review"] == "Expert review has not yet been done."


@pytest.mark.parametrize(
    "path",
    [
        "/modelkit/drugs",
        "/modelkit/drugs/sunitinib",
        "/modelkit/drugs/sunitinib/evidence",
        "/modelkit/drugs/sunitinib/export/janus",
        "/modelkit/validation",
    ],
)
def test_every_route_is_read_only_and_takes_the_release(client: TestClient, path: str) -> None:
    for method in ("post", "put", "patch", "delete"):
        assert client.request(method.upper(), path, json={}).status_code == 405
    ok = client.get(path, params={"release": RUN_ID})
    assert ok.status_code == 200 and ok.headers["cache-control"] == "no-store"
    gone = client.get(path, params={"release": "20250101T000000Z-00000000-0000"})
    assert gone.status_code == 404 and gone.json() == {"error": "unknown_release"}
    bad = client.get(path, params={"release": "x"})
    assert bad.status_code == 422 and bad.json() == {
        "error": "invalid_request",
        "fields": ["release"],
    }
    assert gone.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    ("params", "fields"),
    [
        ({"limit": 0}, ["limit"]),
        ({"limit": 201}, ["limit"]),
        ({"offset": -1}, ["offset"]),
        ({"offset": 100001}, ["offset"]),
        ({"status": "great"}, ["status"]),
        ({"q": "<b>"}, ["q"]),
        ({"q": "x" * 33}, ["q"]),
        ({"limit": 0, "status": "x"}, ["status", "limit"]),
    ],
)
def test_list_refuses_bad_parameters_naming_only_fields(
    client: TestClient, params: dict[str, Any], fields: list[str]
) -> None:
    resp = client.get("/modelkit/drugs", params=params)
    assert resp.status_code == 422
    assert resp.json()["error"] == "invalid_request"
    assert sorted(resp.json()["fields"]) == sorted(fields)
    assert str(params.get("q", "<none>")) not in resp.text or "q" not in params


def test_evidence_rows_have_the_documented_fields_including_formulation(client: TestClient) -> None:
    rows = client.get("/modelkit/drugs/sunitinib/evidence").json()["rows"]
    assert rows
    for row in rows:
        assert set(row) == set(r.EvidenceRowOut.model_fields)
        assert row["formulation"] in {
            "immediate_release",
            "solution",
            "modified_release",
            "fixed_dose_combination",
            "other_route",
            "unspecified",
        }
        assert row["role"] in {"building", "validation", "excluded"}
        assert (row["reason"] is None) == (row["role"] != "excluded")


def test_export_contract(client: TestClient) -> None:
    ok = client.get("/modelkit/drugs/ertugliflozin/export/janus")
    assert ok.status_code == 200 and ok.headers["content-type"] == "application/zip"
    assert ok.headers["x-janus-release"] == RUN_ID
    assert 'filename="janus-modelkit-ertugliflozin-janus.zip"' in ok.headers["content-disposition"]
    assert client.get("/modelkit/drugs/ertugliflozin/export/nope").status_code == 422
    assert client.get("/modelkit/drugs/nothing/export/janus").status_code == 404
    assert client.get("/modelkit/drugs/Bad-Key/export/janus").status_code == 422
    assert client.get("/modelkit/drugs/tramadol/export/janus").status_code == 409


def test_openapi_lists_the_five_routes_with_response_models(client: TestClient) -> None:
    spec = client.get("/openapi.json").json()
    paths = {p: v for p, v in spec["paths"].items() if p.startswith("/modelkit")}
    assert set(paths) == {
        "/modelkit/drugs",
        "/modelkit/drugs/{key}",
        "/modelkit/drugs/{key}/evidence",
        "/modelkit/drugs/{key}/export/{target}",
        "/modelkit/validation",
    }
    assert all(set(v) == {"get"} for v in paths.values())
    assert {p["name"] for p in paths["/modelkit/drugs"]["get"]["parameters"]} == {
        "release", "q", "status", "has_set", "limit", "offset",
    }  # fmt: skip


def test_drug_detail_says_why_no_interval_is_shown(client: TestClient) -> None:
    d = client.get("/modelkit/drugs/sunitinib").json()
    assert [i["metric"] for i in d["intervals"]] == ["auc", "cmax"]
    for i in d["intervals"]:
        assert i["shown"] is False and i["fold_half"] is None
        assert i["reason"] == "interval_n_too_small" and i["min_studies"] == 20
    assert d["reason_text"]["interval_n_too_small"].startswith("No interval is shown")


def test_system_report_counts_precision_and_what_is_missing(client: TestClient) -> None:
    s = client.get("/modelkit/validation").json()
    assert s["n_with_set"] >= s["n_complete_set"] >= 1
    assert s["rows_total"] >= s["rows_confirmed"] >= s["confirmed_parent_rows"] > 0
    assert sum(s["formulation_counts"].values()) == s["confirmed_parent_rows"]
    assert sum(s["route_counts"].values()) == s["confirmed_parent_rows"]
    assert s["interpretable"] is False and "gate_not_interpretable" in s["missing"]
    assert "intervals_not_shown" in s["missing"] and "expert_review_pending" in s["missing"]
    p = s["precision"]
    assert p["n"] == 100 and p["correct"] == 80 and math.isclose(p["share"], 0.8)
    lo, hi = wilson(80, 100) or (0, 0)
    assert math.isclose(p["wilson_low"], lo) and math.isclose(p["wilson_high"], hi)
    assert p["formulation_n"] == 50 and math.isclose(p["formulation_share"], 0.9)
    assert all(code in s["reason_text"] for code in s["missing"])
    assert [i["shown"] for i in s["intervals"]] == [False, False]


def test_system_report_without_a_measured_precision_says_none(tmp_path: Path) -> None:
    write_run(tmp_path, seed_dicts())
    app: FastAPI = create_app(configure_logs=False)
    app.state.modelkit = ModelkitHolder(tmp_path)
    with TestClient(app) as cl:
        assert cl.get("/modelkit/validation").json()["precision"] is None


# --- intervals: shown only from 20 independent held-out studies ---------------------------------


def _val(drug: str, studies: int, ratio: float, metric: str = "auc") -> Validation:
    pts = tuple(
        Point(f"{drug}{i}", metric, f"S{drug}{i}", 100.0, 1.0, ratio, ratio, 0.5 <= ratio <= 2)  # type: ignore[arg-type]
        for i in range(studies)
    )
    empty = Validation(drug, "not_validated", (), None, pts, (), (), "x")  # type: ignore[arg-type]
    return empty


@pytest.mark.parametrize("n", [0, 1, 19])
def test_no_interval_below_twenty_studies(n: int) -> None:
    auc, cmax = conformal_intervals([_val("a", n, 1.2)])
    assert not auc.shown and auc.fold_width is None and auc.n_studies == n
    assert not cmax.shown and cmax.n_studies == 0


def test_interval_appears_at_twenty_studies_and_counts_studies_not_drugs() -> None:
    vals = [_val("a", 10, 1.2), _val("b", 10, 1.5)]
    auc, _ = conformal_intervals(vals)
    assert auc.n_studies == 20 == MIN_STUDIES_FOR_INTERVAL
    assert auc.shown and auc.fold_width is not None and auc.fold_width >= 1.2
    assert auc.fold_width == conformal_fold_width([1.2] * 10 + [1.5] * 10, 0.8)
    one_drug = conformal_intervals([_val("a", 19, 1.2), _val("a", 19, 1.2)])
    assert one_drug[0].n_studies == 19  # the same study ids of one drug are not counted twice


def test_a_drug_that_cannot_predict_the_metric_gets_no_interval() -> None:
    shown = r._interval(conformal_intervals([_val("a", 20, 1.3)])[0], False)  # pyright: ignore[reportPrivateUsage]
    assert not shown.shown and shown.reason == "set_cannot_predict_metric"
    yes = r._interval(conformal_intervals([_val("a", 20, 1.3)])[0], True)  # pyright: ignore[reportPrivateUsage]
    assert yes.shown and yes.fold_half is not None and yes.fold_half >= math.sqrt(1.3)
