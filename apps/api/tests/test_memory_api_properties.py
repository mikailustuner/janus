"""`/memory` routes: contracts, validation, fail-closed, statelessness (design §10: P20-P22, P24).

The counts file is built from a tiny fixed set of reports; the vocabulary is the real packaged one.
No PostgreSQL: the resolution dataset is "not served" (`served_resolution_dataset_version` null).
"""

from __future__ import annotations

import copy
import json
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from hypothesis import given, settings
from hypothesis import strategies as st

from janus.main import create_app
from janus.memory import reader as reader_module
from janus.settings import Settings
from tests.harness import capture_logs, tmp_snapshot
from tests.memory_counts import make_counts, mk
from tests.sentinels import ascii_sentinels, leaked
from tests.test_faers_build_properties import ReportFact

FACTS = [
    ReportFact(
        "100001", "2026Q3", "US", (("PS", ("ASPIRIN",)), ("C", ("METFORMIN",))), ("Cough", "Rash")
    ),
    ReportFact("100002", "2026Q3", "US", (("PS", ("ASPIRIN",)),), ("Cough",)),
    ReportFact("100003", "2026Q3", "EU", (("PS", ("ASPIRIN", "METFORMIN")),), ("Cough", "Nausea")),
    ReportFact("100004", "2026Q3", "TR", (("PS", ("METFORMIN",)),), ("Nausea",)),
    ReportFact("100005", "2026Q3", "OTHER", (("SS", ("AMLODIPINE BESYLATE",)),), ("Rash",)),
    ReportFact("100006", "2026Q3", "UNKNOWN", (("PS", ("ASPIRIN",)),), ("Cough",)),
]


@pytest.fixture(scope="module")
def data_dir() -> Iterator[Path]:
    with tempfile.TemporaryDirectory() as d:
        make_counts(Path(d), FACTS)
        yield Path(d)


def client_for(data_dir: Path) -> TestClient:
    settings_ = Settings.from_env({"JANUS_DATA_DIR": str(data_dir)})
    return TestClient(create_app(settings_, configure_logs=False), raise_server_exceptions=False)


@pytest.fixture(scope="module")
def client(data_dir: Path) -> TestClient:
    return client_for(data_dir)


PAIR = {"ingredient": "Q1", "event": {"key": "cough"}, "region": "ALL", "scope": "suspect"}


def test_pair_contract(client: TestClient) -> None:
    r = client.post("/memory/pair", json=PAIR)
    assert r.status_code == 200
    assert r.headers["cache-control"] == "no-store"
    assert r.headers["x-request-id"]
    body = r.json()
    assert body["layer"] == "faers" and body["status"] == "ok" and body["ingredient"] == "Q1"
    assert body["event"]["key"] == "cough" and body["event"]["pts"] == ["Cough"]
    assert body["event"]["reported_in_window"] is True
    snap = body["snapshot"]
    assert snap["served_resolution_dataset_version"] is None and snap["counts_match_served"] is None
    assert snap["window"] == ["2025Q4", "2026Q1", "2026Q2", "2026Q3"]
    assert (
        "screening_statistic" in body["notices"]
        and "deduplicated_by_case_version_only" in body["notices"]
    )
    assert body["meddra_notice"] == "MedDRA® trademark is registered by IFPMA on behalf of ICH."
    assert body["disclaimer"].startswith("Janus provides information, not medical advice.")
    assert body["citation"] == {
        "evidence_id": "dataset:faers",
        "locator": "faers:ingredient=Q1;event=cough;region=ALL;scope=suspect",
    }
    stats = body["stats"]
    assert stats["cells"]["a"] == 4 and stats["assessment"] in (
        "weak",
        "not_disproportionate",
        "disproportionate",
    )
    assert set(stats) >= {
        "sensitivity",
        "denominator_sensitive",
        "haldane_applied",
        "evans_met",
        "ror_signal",
    }
    # counts are reports, never people
    assert not leaked(r.text.lower(), ["people", "patient", "person"])


def test_responses_are_byte_identical(client: TestClient) -> None:
    for path, body in (
        ("/memory/pair", PAIR),
        ("/memory/combination", {"ingredients": ["Q1", "Q2"], "region": "ALL", "scope": "any"}),
        ("/memory/combination", {"ingredients": ["Q2", "Q1"], "region": "ALL", "scope": "any"}),
        ("/memory/regions", {"ingredients": ["Q1"], "event": {"pt": "Cough"}}),
    ):
        first = client.post(path, json=body).content
        assert client.post(path, json=body).content == first
    a = client.post("/memory/combination", json={"ingredients": ["Q1", "Q2"]}).content
    b = client.post("/memory/combination", json={"ingredients": ["Q2", "Q1"]}).content
    assert a == b


def test_regions_and_combination_contracts(client: TestClient) -> None:
    r = client.post(
        "/memory/regions", json={"ingredients": ["Q1"], "event": {"pt": "Cough"}}
    ).json()
    assert [row["region"] for row in r["rows"]] == ["TR", "EU", "US", "OTHER", "UNKNOWN", "ALL"]
    assert r["adrreports_url"] == "https://www.adrreports.eu"
    assert {
        "region_is_report_origin",
        "eu_member_states_not_separable",
        "regions_not_comparable",
    } <= set(r["notices"])
    assert r["unknown"]["reports"] == 1
    c = client.post(
        "/memory/combination", json={"ingredients": ["Q1", "Q2"], "scope": "any"}
    ).json()
    assert c["level"] == "single" and [s["reason"] for s in c["skipped"]] == [
        "below_display_threshold"
    ]
    assert "combination_caveat" in c["notices"] and c["exposure"] == "all_of_set"
    assert {i["key"] for i in c["ingredients"]} == {"Q1", "Q2"}


def test_snapshot_is_operational(client: TestClient) -> None:
    r = client.get("/memory/snapshot")
    assert r.status_code == 200
    body = r.json()
    assert (
        body["layers"]["faers"] == "ok" and body["layers"]["outcomes"] == "unavailable"
    )  # no database here
    assert [t["region"] for t in body["totals"]] == ["TR", "EU", "US", "OTHER", "UNKNOWN", "ALL"]
    assert body["totals"][-1]["reports_all"] == 6
    assert "MedDRA" in body["meddra_notice"] and "Not an FDA endorsement" in body["attribution"]


def test_unknown_or_benefit_event_keys(client: TestClient) -> None:
    bad = client.post("/memory/pair", json={**PAIR, "event": {"key": "no_such_key"}})
    assert bad.status_code == 422 and bad.json() == {
        "error": "invalid_request",
        "fields": ["event.key"],
    }
    benefit = client.post("/memory/pair", json={**PAIR, "event": {"key": "improvement_pain"}})
    assert benefit.status_code == 200
    assert benefit.json()["status"] == "not_available" and benefit.json()["stats"] is None
    assert "benefit_not_in_faers" in benefit.json()["notices"]


# --- P20 ---------------------------------------------------------------------------------------


def _mutations() -> list[tuple[str, dict[str, Any]]]:
    base = copy.deepcopy(PAIR)
    out: list[tuple[str, dict[str, Any]]] = [
        ("extra", {**base, "extra": 1}),
        ("badkey", {**base, "ingredient": "q1"}),
        ("badkey2", {**base, "ingredient": "Q0"}),
        ("noevent", {k: v for k, v in base.items() if k != "event"}),
        ("both", {**base, "event": {"pt": "Cough", "key": "cough"}}),
        ("neither", {**base, "event": {}}),
        ("region", {**base, "region": "FR"}),
        ("scope", {**base, "scope": "all"}),
        ("longpt", {**base, "event": {"pt": "x" * 201}}),
        ("emptypt", {**base, "event": {"pt": ""}}),
    ]
    return out


@pytest.mark.parametrize(("name", "body"), _mutations())
def test_invalid_pair_requests_get_422_and_touch_nothing(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, name: str, body: dict[str, Any]
) -> None:
    """Feature: collective-memory, Property P20 — Validates: Req 7.3."""
    calls: list[str] = []
    real = reader_module.CountsReader.session

    def counting(self: reader_module.CountsReader) -> reader_module.Session:
        calls.append(name)
        return real(self)

    monkeypatch.setattr(reader_module.CountsReader, "session", counting)
    r = client.post("/memory/pair", json=body)
    assert r.status_code == 422, name
    assert r.json()["error"] == "invalid_request" and isinstance(r.json()["fields"], list)
    assert calls == []


@pytest.mark.parametrize(
    "body",
    [
        {"ingredients": ["Q1"]},
        {"ingredients": ["Q1", "Q1"]},
        {"ingredients": [f"Q{i}" for i in range(1, 22)]},
        {"ingredients": ["Q1", "Q2"], "top_events": 0},
        {"ingredients": ["Q1", "Q2"], "top_events": 51},
        {"ingredients": ["Q1", "Q2"], "region": "XX"},
    ],
)
def test_invalid_combination_requests(client: TestClient, body: dict[str, Any]) -> None:
    assert client.post("/memory/combination", json=body).status_code == 422


@pytest.mark.parametrize(
    "body",
    [{"ingredients": []}, {"ingredients": ["Q1", "Q1"]}, {"ingredients": ["Q1"], "event": {}}],
)
def test_invalid_regions_requests(client: TestClient, body: dict[str, Any]) -> None:
    assert client.post("/memory/regions", json=body).status_code == 422


@settings(max_examples=40, deadline=None)
@given(ascii_sentinels(), st.sampled_from(["ingredient", "event", "region", "junk"]))
def test_a_422_never_echoes_a_value(client: TestClient, sentinel: str, where: str) -> None:
    """Feature: collective-memory, Property P20 — Validates: Req 7.3."""
    body: dict[str, Any] = copy.deepcopy(PAIR)
    if where == "ingredient":
        body["ingredient"] = sentinel
    elif where == "event":
        body["event"] = {"pt": "Cough", "key": sentinel}
    elif where == "region":
        body["region"] = sentinel
    else:
        body[sentinel] = sentinel
    r = client.post("/memory/pair", json=body)
    assert r.status_code == 422 and sentinel not in r.text


def test_non_json_and_oversized_bodies(client: TestClient) -> None:
    assert (
        client.post(
            "/memory/pair", content=b"x", headers={"content-type": "text/plain"}
        ).status_code
        == 415
    )
    big = json.dumps({**PAIR, "event": {"pt": "A" * 70_000}})
    assert (
        client.post(
            "/memory/pair", content=big, headers={"content-type": "application/json"}
        ).status_code
        == 413
    )
    assert (
        client.post(
            "/memory/pair", content=b"{", headers={"content-type": "application/json"}
        ).status_code
        == 422
    )


# --- P21 ---------------------------------------------------------------------------------------


@settings(max_examples=20, deadline=None)
@given(ascii_sentinels(5, 12), ascii_sentinels(5, 12))
def test_requests_are_stateless_and_silent(
    client: TestClient, data_dir: Path, pt: str, extra: str
) -> None:
    """Feature: collective-memory, Property P21 — Validates: Req 7.2, 7.10."""
    before = tmp_snapshot(data_dir)
    with capture_logs() as logs:
        r1 = client.post("/memory/pair", json={**PAIR, "event": {"pt": pt}})
        r2 = client.post("/memory/combination", json={"ingredients": ["Q1", "Q2"]})
        r3 = client.post("/memory/pair", json={**PAIR, extra: 1})
    assert r1.status_code == 200 and r2.status_code == 200 and r3.status_code == 422
    assert tmp_snapshot(data_dir) == before  # no file written, no spill, no cache on disk
    out = logs.getvalue()
    assert not leaked(out, [pt, extra, "Q1", "Q2", "Cough"])
    assert out.count('"event":"access"') == 3
    assert "no-store" == r1.headers["cache-control"] == r2.headers["cache-control"]


# --- P22 (route) -------------------------------------------------------------------------------


def test_no_counts_file_gives_503_and_no_numbers(tmp_path: Path) -> None:
    """Feature: collective-memory, Property P22 — Validates: Req 7.6."""
    c = client_for(tmp_path)
    for path, body in (
        ("/memory/pair", PAIR),
        ("/memory/combination", {"ingredients": ["Q1", "Q2"]}),
        ("/memory/regions", {"ingredients": ["Q1"]}),
    ):
        r = c.post(path, json=body)
        assert r.status_code == 503 and r.json() == {"error": "memory_unavailable"}
    assert c.get("/memory/snapshot").status_code == 503


def test_route_kinds() -> None:
    from janus.http_policy.routes import OPERATIONAL_ALLOWLIST

    assert "/memory/snapshot" in OPERATIONAL_ALLOWLIST
    assert not {"/memory/pair", "/memory/combination", "/memory/regions"} & OPERATIONAL_ALLOWLIST


# --- P24 ---------------------------------------------------------------------------------------


def test_statement_budget_does_not_grow_with_the_request(data_dir: Path) -> None:
    """Feature: collective-memory, Property P24 — Validates: Req 9.6."""
    from janus.memory import service
    from janus.memory.reader import CountsHolder
    from janus.memory.schemas import CombinationIn, PairIn, RegionsIn
    from tests.test_memory_service_properties import ctx

    reader = CountsHolder(data_dir).current()
    keys = [f"Q{i}" for i in range(1, 21)]
    with reader.session() as s:
        service.pair(
            s,
            mk(PairIn, ingredient="Q1", event={"pt": "Cough"}, region="ALL", scope="suspect"),
            ctx(),
        )
        assert s.statements <= 6
    with reader.session() as s:
        service.regions(s, mk(RegionsIn, ingredients=["Q1", "Q2"], event={"key": "cough"}), ctx())
        assert s.statements <= 8
    counts: list[int] = []
    for n in (2, 5, 20):
        with reader.session() as s:
            service.combination(s, mk(CombinationIn, ingredients=keys[:n], top_events=50), ctx())
            counts.append(s.statements)
    assert max(counts) <= 12


# --- safety review (2026-11-08): safety lines on every route, citations, notices -----------------


def test_every_pt_of_a_key_with_a_line_returns_that_line() -> None:
    """Feature: collective-memory, Property P25 (safety lines). Validates: Req 8, experience 7."""
    from janus.memory.vocabulary import SAFETY_LINES, load_events
    from janus.settings import EVENT_VOCABULARY

    vocab = load_events(EVENT_VOCABULARY)
    with_line = [k for k in vocab.keys if k.safety_line]
    assert {k.safety_line for k in with_line} == set(SAFETY_LINES)
    for k in with_line:
        for pt in k.pts:
            got = vocab.line_for_pts((pt,))
            assert got is not None and SAFETY_LINES.index(got) <= SAFETY_LINES.index(k.safety_line)
    assert vocab.line_for_pts(("Cough",)) is None
    assert vocab.line_for_pts(()) is None


def test_safety_line_on_pt_key_and_combination_routes(client: TestClient) -> None:
    by_pt = client.post("/memory/pair", json={**PAIR, "event": {"pt": "Torsade de pointes"}}).json()
    assert by_pt["event"]["safety_line"] == "urgent_care_heart"
    by_key = client.post("/memory/pair", json={**PAIR, "event": {"key": "depression"}}).json()
    assert by_key["event"]["safety_line"] == "crisis_support"
    assert client.post("/memory/pair", json=PAIR).json()["event"]["safety_line"] is None
    combo = client.post(
        "/memory/combination", json={"ingredients": ["Q1", "Q2"], "scope": "any"}
    ).json()
    groups = combo["singles"] + combo["pairs"]
    rows = [e for g in groups for e in g["events"]] + combo["events"]
    assert rows and all("safety_line" in e for e in rows)
    assert {e["pt"]: e["safety_line"] for e in rows}.get("Rash") == "urgent_care_skin"
    assert {e["pt"]: e["safety_line"] for e in rows}.get("Cough") is None


def test_every_count_has_a_citation_and_notices_are_complete(client: TestClient) -> None:
    combo = client.post(
        "/memory/combination", json={"ingredients": ["Q1", "Q2"], "scope": "any"}
    ).json()
    assert combo["citation"]["evidence_id"] == "dataset:faers"
    assert combo["citation"]["locator"] == "faers:ingredient=Q1,Q2;event=;region=ALL;scope=any"
    assert all(i["citation"]["evidence_id"] == "dataset:faers" for i in combo["ingredients"])
    assert all(
        g["citation"]["evidence_id"] == "dataset:faers" for g in combo["singles"] + combo["pairs"]
    )
    tr = client.post("/memory/pair", json={**PAIR, "region": "TR"}).json()
    assert "tr_reports_small_self_selected" in tr["notices"]
    assert (
        "tr_reports_small_self_selected"
        not in client.post("/memory/pair", json=PAIR).json()["notices"]
    )
    regions = client.post("/memory/regions", json={"ingredients": ["Q1"]}).json()
    assert "tr_reports_small_self_selected" in regions["notices"]
    # Q1 has no report in TR in these facts: a 0 row needs the no-reassurance notice
    assert next(r for r in regions["rows"] if r["region"] == "TR")["reports"] == 0
    assert "absence_is_not_reassurance" in regions["notices"]
