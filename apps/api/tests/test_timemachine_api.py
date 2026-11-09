"""`/timemachine` routes (time-machine design §10, P15-P17)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from janus.http_policy.routes import RouteKind, route_kind
from janus.main import create_app
from janus.timemachine.router import router as timemachine_router
from janus.timemachine.store import ArtifactError, Holder, load

ARTIFACT = Path("/home/aurict/Desktop/janus/.data/timemachine/current/time_machine.json")


def _payload() -> dict[str, Any]:
    return {
        "built_at": "2026-11-09T00:00:00+00:00",
        "seed": 1,
        "simulations": 10,
        "disclaimer": "Not medical advice. Research prototype, not a medical device.",
        "review_status": "Expert review has not yet been done",
        "validation": {"rule": "x", "pbpk": [], "compartmental": []},
        "substances": [{"substance_id": "rhubarb", "constituents": [], "todays_drugs": []}],
        "exposure": [{"substance_id": "rhubarb", "constituent": "rhein"}],
        "cascades": [{"cascade_id": "amlodipine_oedema_diuretic", "method": "compartmental"}],
        "sources": {},
        "references": [],
        "faers_quality": {"usable_pairs": 1},
        "onset_subset_caveat": "The usable subset is not representative of all reports.",
    }


@pytest.fixture
def app(tmp_path: Path) -> FastAPI:
    root = tmp_path / "timemachine" / "current"
    root.mkdir(parents=True)
    (root / "time_machine.json").write_text(json.dumps(_payload()))
    application = create_app(configure_logs=False)
    application.state.timemachine = Holder(tmp_path)
    return application


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


def test_routes_are_medical_and_read_only() -> None:
    routes = list(timemachine_router.routes)
    assert routes
    methods: set[str] = set()
    for route in routes:
        assert isinstance(route, APIRoute)
        assert route.path.startswith("/timemachine")
        assert route_kind(route) is RouteKind.medical
        methods |= route.methods or set()
    assert methods == {"GET"}  # P15: nothing but reads


def test_catalogue_and_detail(client: TestClient) -> None:
    r = client.get("/timemachine/catalogue")
    assert r.status_code == 200
    body = r.json()
    assert body["substance_ids"] == ["rhubarb"]
    assert body["meta"]["review_status"] == "Expert review has not yet been done"
    assert "not a medical device" in body["meta"]["disclaimer"]
    assert r.headers["cache-control"] == "no-store"

    r = client.get("/timemachine/substance/rhubarb")
    assert r.status_code == 200
    assert r.json()["exposure"][0]["constituent"] == "rhein"

    r = client.get("/timemachine/cascade/amlodipine_oedema_diuretic")
    assert r.status_code == 200
    assert r.json()["cascade"]["method"] == "compartmental"


def test_unknown_and_invalid_ids(client: TestClient) -> None:
    assert client.get("/timemachine/substance/nope").status_code == 404
    assert client.get("/timemachine/cascade/nope").status_code == 404
    r = client.get("/timemachine/substance/" + "x" * 65)
    assert r.status_code == 422
    assert r.json()["fields"] == ["substance_id"]
    # P16: an invalid id is never echoed back
    assert "x" * 65 not in r.text


def test_missing_artifact_answers_503(tmp_path: Path) -> None:
    application = create_app(configure_logs=False)
    application.state.timemachine = Holder(tmp_path)
    with TestClient(application) as c:
        r = c.get("/timemachine/catalogue")
        assert r.status_code == 503
        assert r.json() == {"error": "time_machine_not_installed"}


def test_incomplete_artifact_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    payload = _payload()
    del payload["validation"]
    path.write_text(json.dumps(payload))
    with pytest.raises(ArtifactError):
        load(path)


@pytest.mark.skipif(not ARTIFACT.is_file(), reason="built artifact not present")
def test_the_built_artifact_keeps_the_contract() -> None:
    """P17: a model that failed validation never carries an exposure verdict."""
    tm = load(ARTIFACT)
    credible = {
        v["drug"]
        for group in ("pbpk", "compartmental")
        for v in tm.payload["validation"][group]
        if v["credibility"] == "credible"
    }
    for e in tm.payload["exposure"]:
        if e.get("comparison") is not None:
            assert e["model_validated"] is True
            assert e["constituent"] in credible
    for c in tm.payload["cascades"]:
        onset = c.get("onset")
        if onset is not None:
            assert onset["small_sample"] == (onset["reports"] < 30)
            if onset["weibull"] is None:
                assert onset["weibull_omitted_reason"]
    for s in tm.payload["substances"]:
        for con in s["constituents"]:
            for flag in con["interaction_flags"]:
                # An established interaction must cite evidence; a screening hit must not.
                assert bool(flag["evidence_reference_key"]) == flag["established"]
