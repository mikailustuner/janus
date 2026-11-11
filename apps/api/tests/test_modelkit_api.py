"""Model kit API (requirement 5): routes from a release built with DuckDB, errors as codes,
medical-policy routes, no input echoed, the release switch without a restart."""

from __future__ import annotations

import json
import zipfile
from collections.abc import Iterator
from io import BytesIO
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from janus.http_policy.routes import RouteKind, route_kind
from janus.main import create_app
from janus.modelkit.router import router as modelkit_router
from janus.modelkit.store import ModelkitHolder
from tests.modelkit_helpers import RUN_ID, seed_dicts, write_run


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    write_run(tmp_path, seed_dicts())
    return tmp_path


@pytest.fixture
def client(data_dir: Path) -> Iterator[TestClient]:
    app: FastAPI = create_app(configure_logs=False)
    app.state.modelkit = ModelkitHolder(data_dir)
    with TestClient(app) as cl:
        yield cl


def test_routes_are_medical_get_only() -> None:
    assert len(modelkit_router.routes) == 5
    for route in modelkit_router.routes:
        assert route_kind(route) is RouteKind.medical
        assert getattr(route, "methods", set[str]()) == {"GET"}


def test_list_has_statuses_and_statements(client: TestClient) -> None:
    r = client.get("/modelkit/drugs")
    assert r.status_code == 200
    assert r.headers["cache-control"] == "no-store"
    body = r.json()
    assert body["release"]["run_id"] == RUN_ID
    assert body["statements"]["research_use"] == "Research use only. Not for clinical decisions."
    assert body["statements"]["expert_review"] == "Expert review has not yet been done."
    by = {d["key"]: d for d in body["drugs"]}
    assert set(by) == {
        "dolutegravir",
        "ertugliflozin",
        "gabapentin",
        "sunitinib",
        "telmisartan",
        "tramadol",
    }
    assert by["ertugliflozin"]["status"] == "validated" and by["ertugliflozin"]["exportable"]
    assert by["tramadol"]["status"] == "not_validated" and not by["tramadol"]["has_set"]
    assert all(d["experimental"] for d in body["drugs"])


def test_drug_detail_with_set_and_validation(client: TestClient) -> None:
    d = client.get("/modelkit/drugs/sunitinib").json()
    assert d["parameter_set"]["basis"] == "oral_apparent" and d["parameter_set"]["apparent"]
    names = {p["name"]: p for p in d["parameter_set"]["params"]}
    assert set(names) == {"cl", "v", "f", "ka"} and names["ka"]["confidence_class"] == "C"
    assert d["validation"]["metrics"][1]["n_points"] == 2
    assert d["validation"]["band"] == [0.5, 2.0]
    assert d["targets"] == ["janus", "mrgsolve"]
    none = client.get("/modelkit/drugs/telmisartan").json()
    assert none["parameter_set"] is None and none["no_set_reasons"] and none["targets"] == []


def test_evidence_rows_carry_quote_source_and_readers(client: TestClient) -> None:
    body = client.get("/modelkit/drugs/sunitinib/evidence").json()
    rows = body["rows"]
    assert rows and all(
        r["quote"] and r["source_locator"] and r["reader_a"] and r["reader_b"] for r in rows
    )
    roles = {r["role"] for r in rows}
    assert roles == {"building", "validation", "excluded"}
    t_half = [r for r in rows if r["parameter"] == "t_half"]
    assert t_half and all(
        not r["confirmed"] and r["role"] == "excluded" and r["reason"] for r in t_half
    )
    assert any(r["source_url"] for r in rows)
    assert any("ClinicalTrials.gov" in a for a in body["attribution"])


def test_system_report(client: TestClient) -> None:
    s = client.get("/modelkit/validation").json()
    assert s["n_drugs"] == 6 and s["interpretable"] is False
    assert sum(s["by_status"].values()) == 6
    assert "20" in s["conformal"] and s["caveats"]


@pytest.mark.parametrize("target", ["janus", "mrgsolve"])
def test_export_is_a_zip_with_provenance(client: TestClient, target: str) -> None:
    r = client.get(f"/modelkit/drugs/ertugliflozin/export/{target}")
    assert r.status_code == 200 and r.headers["content-type"] == "application/zip"
    assert f"janus-modelkit-ertugliflozin-{target}.zip" in r.headers["content-disposition"]
    with zipfile.ZipFile(BytesIO(r.content)) as z:
        assert "provenance.json" in z.namelist()
        assert json.loads(z.read("provenance.json"))["kit"]["release"] == RUN_ID


def test_errors_are_codes(client: TestClient) -> None:
    assert client.get("/modelkit/drugs/nothing").json() == {"error": "unknown_drug"}
    assert client.get("/modelkit/drugs/nothing").status_code == 404
    bad = client.get("/modelkit/drugs/Bad-Key")
    assert bad.status_code == 422 and bad.json() == {"error": "invalid_request", "fields": ["key"]}
    t = client.get("/modelkit/drugs/sunitinib/export/pksim")
    assert t.status_code == 422 and t.json()["fields"] == ["target"]
    assert client.get("/modelkit/drugs/tramadol/export/janus").json() == {
        "error": "no_parameter_set"
    }
    assert client.get("/modelkit/drugs/tramadol/export/janus").status_code == 409
    assert client.get("/modelkit/drugs?release=nope").status_code == 422
    other = "20250101T000000Z-00000000-0000"
    assert client.get(f"/modelkit/drugs?release={other}").json() == {"error": "unknown_release"}
    assert client.get(f"/modelkit/drugs?release={RUN_ID}").status_code == 200


def test_input_is_never_echoed(client: TestClient) -> None:
    r = client.get("/modelkit/drugs/<script>alert(1)</script>")
    assert "script" not in r.text


def test_unavailable_without_a_release(tmp_path: Path) -> None:
    app = create_app(configure_logs=False)
    app.state.modelkit = ModelkitHolder(tmp_path)
    with TestClient(app) as cl:
        for path in ("/modelkit/drugs", "/modelkit/validation", "/modelkit/drugs/sunitinib"):
            r = cl.get(path)
            assert r.status_code == 503 and r.json() == {"error": "modelkit_unavailable"}


def test_a_new_release_is_picked_up_without_restart(tmp_path: Path) -> None:
    rows = [r for r in seed_dicts() if r["drug_key"] == "sunitinib"]
    write_run(tmp_path, rows)
    holder = ModelkitHolder(tmp_path)
    first = holder.value
    assert first is not None and set(first.drugs) == {"sunitinib"}
    link = tmp_path / "artifacts" / "modelkit_evidence" / "current"
    new = link.parent / "runs" / "20261112T120000Z-0a1b2c3d-0002"
    new.mkdir()
    for f in (link.resolve()).iterdir():
        (new / f.name).write_bytes(f.read_bytes())
    manifest = json.loads((new / "manifest.json").read_text())
    manifest["run_id"] = new.name
    (new / "manifest.json").write_text(json.dumps(manifest))
    tmp_link = link.parent / "tmp"
    tmp_link.symlink_to(new)
    tmp_link.replace(link)
    second = holder.value
    assert second is not None and second.run_id == new.name


def test_a_run_that_is_not_ours_is_ignored(tmp_path: Path) -> None:
    run = write_run(tmp_path, seed_dicts())
    manifest = json.loads((run / "manifest.json").read_text())
    manifest["schema_version"] = "other-1"
    (run / "manifest.json").write_text(json.dumps(manifest))
    assert ModelkitHolder(tmp_path).value is None
