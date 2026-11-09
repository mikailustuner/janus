"""CDS Hooks routes: P1, P8, contract and examples (cds-hooks tasks 4-5); the open package route
(mcp-server task 1).

A synthetic dataset (no real TİTCK data) is loaded through the real resolution loader; the
evidence and the real curated rule base through their loaders, as in the cascade API tests.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient
from hypothesis import given, settings
from hypothesis import strategies as st

from janus.cascades.load import load as load_rule_base
from janus.cascades.load import read_files
from janus.cds import router as cds_router
from janus.cds import service
from janus.db.pool import Database
from janus.http_policy.body_limits import MAX_BODY_BYTES
from janus.main import create_app
from janus.open import router as open_router
from janus.resolution.atc import CombinationRules, RouteMap
from janus.resolution.load import Inputs
from janus.resolution.load import load as load_resolution
from janus.settings import Settings
from tests.cds_strategies import (
    ATC,
    NDC,
    RXNORM,
    bundle,
    coding,
    med_request,
    med_statement,
    request,
)
from tests.conftest import DB_EXAMPLES
from tests.harness import assert_stateless, capture_logs, isolated_tempdir
from tests.resolution_db import inputs
from tests.resolution_db import reset as reset_resolution
from tests.resolution_strategies import barcode13, titck_row, us_row, wikidata_row
from tests.sentinels import ascii_sentinels, leaked
from tests.test_cascades_load_properties import TODAY, reset, seed_evidence

SERVICE = "/cds-services/janus-cascade"
SANDBOX = "https://sandbox.cds-hooks.org"

WD = [
    {**wikidata_row("Q411347", ["C08CA01"], {"en": "amlodipine"}), "rxcuis": ["17767"]},
    {**wikidata_row("Q900001", ["C03CA01"], {"en": "furosemide"}), "rxcuis": ["4603"]},
    wikidata_row("Q900002", ["A10BA02"], {"en": "metformin"}),
    wikidata_row("Q412208", ["C09AA03"], {"en": "lisinopril"}),
    wikidata_row("Q900005", ["A02BC01"], {"en": "omeprazole"}),
]
TR = [
    titck_row(
        barcode13(1), "AMLIPIN 10 / 10", ["amlodipin besilat", "lisinopril dihidrat"], "C09BB03"
    ),
    titck_row(barcode13(2), "FURO", ["furosemid"], "C03CA01"),
]
US = [
    {**us_row("11111-111", ["11111-111-11"], ["amlodipine besylate"], ["ORAL"]),
     "rxcuis": ["308135"]},
    {**us_row("44444-444", ["44444-444-44"], ["amlodipine besylate"], ["ORAL"]),
     "rxcuis": ["308135"]},
    {**us_row("22222-222", ["22222-222-22"], ["furosemide"], ["ORAL"]), "rxcuis": ["310429"]},
    us_row("33333-333", ["33333-333-33"], ["metformin hydrochloride"], ["ORAL"]),
]  # fmt: skip


@pytest.fixture(scope="module")
def env(db_url: str) -> Iterator[tuple[TestClient, Database, str]]:
    database = Database(db_url)
    database.open()
    with psycopg.connect(db_url, autocommit=True) as conn:
        reset_resolution(conn)
        reset(conn)
    base = inputs(TR, US, WD)
    load_resolution(
        database,
        Inputs(base.artifacts, CombinationRules.load(), RouteMap.load(), (), "test", base.cadences),
    )
    seed_evidence(database)
    load_rule_base(database, read_files(), TODAY)
    cds_router.today = lambda: TODAY
    app = create_app(Settings.from_env({"JANUS_CDS_CORS_ORIGINS": SANDBOX}), database=database)
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c, database, db_url
    database.close()


@pytest.fixture(scope="module")
def plain() -> Iterator[TestClient]:
    app = create_app(Settings.from_env({}), database=None)
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# --- Discovery (P1) ----------------------------------------------------------------------------


def test_p1_discovery_contract(plain: TestClient) -> None:
    r = plain.get("/cds-services")
    assert r.status_code == 200
    assert r.headers["cache-control"] == "no-store"
    services = r.json()["services"]
    assert [s["hook"] for s in services] == ["order-select", "order-sign"]
    for s in services:
        assert set(s) == {"hook", "title", "description", "id", "prefetch", "usageRequirements"}
        assert s["id"] == "janus-cascade"
        assert "not for clinical use" in s["description"]
        assert "not for clinical use" in s["usageRequirements"]
        assert s["prefetch"] == {
            "medicationRequests": (
                "MedicationRequest?patient={{context.patientId}}&status=active,on-hold"
            ),
            "medicationStatements": (
                "MedicationStatement?patient={{context.patientId}}&status=active,on-hold"
            ),
        }


def test_service_without_database_is_503(plain: TestClient) -> None:
    body = request("order-sign", [med_request("a", [coding(RXNORM, "17767")], "draft")])
    r = plain.post(SERVICE, json=body)
    assert r.status_code == 503
    assert r.json() == {"error": "cascades_unavailable"}


# --- Service examples -------------------------------------------------------------------------


AMLO_NDC = [coding(NDC, "11111-111-11")]
AMLO_RX_PRODUCT = [coding(RXNORM, "308135")]
FURO_RX = [coding(RXNORM, "310429"), coding(ATC, "C03CA01")]
FURO_ATC = [coding(ATC, "C03CA01")]
METFORMIN = [coding(ATC, "A10BA02")]


def cards_of(client: TestClient, body: dict[str, Any]) -> list[dict[str, Any]]:
    r = client.post(SERVICE, json=body)
    assert r.status_code == 200, r.text
    assert r.headers["cache-control"] == "no-store"
    return r.json()["cards"]


@pytest.mark.db
@pytest.mark.parametrize("amlo", [AMLO_NDC, AMLO_RX_PRODUCT, [coding(RXNORM, "17767")]])
def test_selected_diuretic_with_active_ccb_gives_row_5(
    env: Any, amlo: list[dict[str, str]]
) -> None:
    client, _, _ = env
    body = request(
        "order-select",
        [med_request("new", FURO_RX, "draft")],
        active=[med_request("old", amlo)],
    )
    cards = cards_of(client, body)
    assert [c["summary"] for c in cards] == [
        "Possible prescribing cascade (PIPC row 5): amlodipine and furosemide"
    ]
    card = cards[0]
    assert card["indicator"] == "info"
    assert "**amlodipine** (current medication request (active or on hold))" in card["detail"]
    assert "applies only if furosemide was started after amlodipine" in card["detail"]
    assert "**furosemide** (selected order)" in card["detail"]
    assert "Table 1, row 5" in card["detail"]
    assert "rule:pipc:5" in card["detail"]
    assert set(card) == {"summary", "detail", "indicator", "source", "links"}


@pytest.mark.db
def test_order_sign_and_statement(env: Any) -> None:
    client, _, _ = env
    body = request(
        "order-sign",
        [med_request("new", FURO_ATC, "draft")],
        statements=[med_statement("s", AMLO_NDC)],
    )
    cards = cards_of(client, body)
    assert len(cards) == 1
    assert "(medication statement)" in cards[0]["detail"]
    assert "(draft order)" in cards[0]["detail"]


@pytest.mark.db
def test_prefetch_not_provided_is_named(env: Any) -> None:
    """Safety review S2: a card says which prefetch the EHR did not provide."""
    client, _, _ = env
    body = request(
        "order-select",
        [med_request("new", FURO_ATC, "draft")],
        prefetch={"medicationRequests": bundle([med_request("old", AMLO_NDC)])},
    )
    (card,) = cards_of(client, body)
    assert "Not read: medication statements (not provided by the EHR)." in card["detail"]


@pytest.mark.db
def test_no_card_when_focus_is_not_involved(env: Any) -> None:
    """P5: the pattern exists between two active medicines, but the selected order is unrelated."""
    client, _, _ = env
    body = request(
        "order-select",
        [med_request("new", METFORMIN, "draft")],
        active=[med_request("a", AMLO_NDC), med_request("b", FURO_ATC)],
    )
    assert cards_of(client, body) == []
    body = request("order-sign", [med_request("new", METFORMIN, "draft")])
    assert cards_of(client, body) == []


@pytest.mark.db
def test_combination_code_and_other_patient_are_not_used(env: Any) -> None:
    client, _, _ = env
    other = med_request("old", AMLO_NDC, patient="someone-else")
    body = request(
        "order-select",
        [med_request("new", FURO_ATC, "draft")],
        active=[other, med_request("combo", [coding(ATC, "C09BB03")])],
    )
    assert cards_of(client, body) == []


@pytest.mark.db
def test_not_checked_count_is_reported(env: Any) -> None:
    client, _, _ = env
    body = request(
        "order-select",
        [med_request("new", FURO_ATC, "draft")],
        active=[
            med_request("old", AMLO_NDC),
            med_request("x", [coding("http://snomed.info/sct", "1")]),
        ],
    )
    (card,) = cards_of(client, body)
    assert "Not checked: 1 medicine in this request (no code Janus could match" in card["detail"]


@pytest.mark.db
def test_errors(env: Any) -> None:
    client, _, _ = env
    drafts = [med_request("new", FURO_ATC, "draft")]
    r = client.post(SERVICE, json=request("order-sign", drafts, prefetch={}))
    assert (r.status_code, r.json()) == (412, {"error": "prefetch_missing"})
    body = request("order-sign", drafts)
    body["context"]["unknownField"] = "zzsecretzz"
    r = client.post(SERVICE, json=body)
    assert r.status_code == 422
    assert r.json() == {"error": "invalid_request", "fields": ["context.<unknown>"]}
    many = [med_request(f"m{i}", [coding(ATC, "C03CA01")], "draft") for i in range(10)]
    big = request("order-sign", many)
    big["context"]["draftOrders"]["entry"][0]["resource"]["note"] = [{"text": "x" * 300_000}]
    r = client.post(SERVICE, json=big)
    assert r.status_code == 413
    # The CDS limit is larger than the default one.
    mid = request("order-sign", drafts)
    mid["context"]["draftOrders"]["entry"][0]["resource"]["note"] = [
        {"text": "x" * (MAX_BODY_BYTES + 1000)}
    ]
    assert client.post(SERVICE, json=mid).status_code == 200
    r = client.post(SERVICE, content=b"not json", headers={"content-type": "application/json"})
    assert (r.status_code, r.json()) == (422, {"error": "invalid_request", "fields": ["body"]})
    r = client.post(SERVICE, content=b"{}", headers={"content-type": "text/plain"})
    assert r.status_code == 415


@pytest.mark.db
def test_too_many_medications_is_422(env: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """The limit itself is a pure test (`test_cds_mapping_properties`); here the route's answer."""
    client, _, _ = env

    def too_many(*_: Any) -> Any:
        raise service.TooManyMedicationsError

    monkeypatch.setattr(service, "items_of", too_many)
    r = client.post(SERVICE, json=request("order-sign", [med_request("a", FURO_ATC, "draft")]))
    assert (r.status_code, r.json()) == (422, {"error": "too_many_medications"})


@pytest.mark.db
def test_cors_only_for_listed_origin_and_cds_paths(env: Any) -> None:
    client, _, _ = env
    pre = {
        "origin": SANDBOX,
        "access-control-request-method": "POST",
        "access-control-request-headers": "authorization, content-type",
    }
    r = client.options(SERVICE, headers=pre)
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == SANDBOX
    r = client.get("/cds-services", headers={"origin": SANDBOX})
    assert r.headers["access-control-allow-origin"] == SANDBOX
    r = client.get("/cds-services", headers={"origin": "https://evil.example"})
    assert "access-control-allow-origin" not in r.headers
    r = client.get("/health", headers={"origin": SANDBOX})
    assert "access-control-allow-origin" not in r.headers


@settings(max_examples=DB_EXAMPLES, deadline=None)
@given(secret=ascii_sentinels(), hook=st.sampled_from(["order-select", "order-sign"]))
def test_p8_stateless_and_silent(env: Any, secret: str, hook: str) -> None:
    """P8: ids, codes and names of the request reach no log, no error body and no table."""
    client, _, url = env
    draft = med_request(secret, FURO_RX, "draft")
    draft["medicationCodeableConcept"]["text"] = secret
    body = request(hook, [draft], active=[med_request(secret + "a", AMLO_NDC)])
    body["context"]["userId"] = f"Practitioner/{secret}"
    body["hookInstance"] = secret
    bad = json.loads(json.dumps(body))
    bad["context"]["draftOrders"]["entry"][0]["resource"]["subject"] = {"reference": 7}
    bad["context"][secret] = secret
    with (
        isolated_tempdir() as tmp,
        capture_logs() as logs,
        psycopg.connect(url, autocommit=True) as conn,
    ):
        ok = assert_stateless(conn, tmp, lambda: client.post(SERVICE, json=body))
        err = assert_stateless(conn, tmp, lambda: client.post(SERVICE, json=bad))
    assert ok.status_code == 200
    assert err.status_code == 422
    assert set(err.json()) == {"error", "fields"}
    assert not leaked(err.text, [secret])
    assert not leaked(ok.text, [secret])
    assert not leaked(logs.getvalue(), [secret, "11111-111-11", "310429", "C03CA01"])


# --- The open cascade package route (mcp-server task 1) ----------------------------------------


def test_package_rows(plain: TestClient) -> None:
    r = plain.get("/open/cascade-package/pipc")
    assert r.status_code == 200
    out = r.json()
    assert out["package"] == "janus-cascade-package"
    assert [row["position"] for row in out["rows"]] == list(range(1, 66))
    assert out["licenses"]["pipc"][0]["name"] == "CC-BY-4.0"
    assert out["licenses"]["pipc_rules"][0]["name"] == "Apache-2.0"
    assert "doi:10.1007/s41999-025-01215-x" in out["citation"]
    row5 = out["rows"][4]
    assert (row5["index_class"], row5["marker_class"]) == ("ccb", "diuretic")
    assert row5["supporting"] == ["paper:thinkcascades:drugs_aging_2022"]
    assert out["disclaimer"].startswith("Janus provides information, not medical advice.")


def test_package_missing_is_503(plain: TestClient, tmp_path: Path) -> None:
    original = open_router.PACKAGE_DIR
    open_router.PACKAGE_DIR = tmp_path
    try:
        r = plain.get("/open/cascade-package/pipc")
    finally:
        open_router.PACKAGE_DIR = original
    assert (r.status_code, r.json()) == (503, {"error": "package_unavailable"})
