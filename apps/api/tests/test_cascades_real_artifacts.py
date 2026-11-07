"""Gate 1 on the real local data (cascade-engine task 13). Local only: skipped in CI and unless
`JANUS_REAL_DATABASE_URL` points to a database loaded with the real resolution dataset, the
integrity load and the rule base. Barcodes other than AMLIPIN's are chosen from that database at
run time, so no TİTCK data is in the repository.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from janus.cascades import router as cascades_router
from janus.db.pool import Database
from janus.main import create_app
from janus.settings import Settings
from tests.cascades_strategies import TODAY

URL = os.environ.get("JANUS_REAL_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    os.environ.get("CI") == "true" or not URL, reason="no local real database"
)

AMLIPIN = "8680199094206"  # amlodipine + lisinopril, published code C09BB03
# The other eight medicines of the Istanbul patient, by the single ingredient code they carry.
OTHERS = {
    "C03CA01": "2024-06",  # furosemide, five months after AMLIPIN
    "A10BA02": "2022-05",  # metformin
    "C10AA05": "2023-01",  # atorvastatin
    "N02BE01": "2023-05",  # paracetamol
    "A02BC01": None,  # omeprazole
    "N06AB06": "2021-03",  # sertraline
    "A06AD11": "2024-03",  # lactulose
    "N05BA12": None,  # alprazolam
}


@pytest.fixture(scope="module")
def env() -> Iterator[tuple[TestClient, Database]]:
    assert URL is not None
    db = Database(URL)
    db.open()
    cascades_router.today = lambda: TODAY
    app = create_app(Settings.from_env({}), database=db)
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c, db
    db.close()


def _barcode_for(db: Database, code: str) -> str:
    with db.read_only_tx() as conn:
        row = conn.execute(
            "SELECT c.code FROM res_current cur "
            "JOIN res_product p ON p.dataset_id = cur.dataset_id AND p.region = 'TR' "
            "JOIN res_product_code c ON c.dataset_id = p.dataset_id AND c.source_id = p.source_id "
            "  AND c.product_id = p.product_id AND c.kind = 'tr_barcode' "
            "WHERE p.published_atc = %s AND NOT p.name_only "
            "AND (SELECT count(*) FROM res_product_ingredient i WHERE i.dataset_id = p.dataset_id "
            "     AND i.source_id = p.source_id AND i.product_id = p.product_id) = 1 "
            "AND EXISTS (SELECT 1 FROM res_product_ingredient i WHERE i.dataset_id = p.dataset_id "
            "     AND i.source_id = p.source_id AND i.product_id = p.product_id "
            "     AND i.status = 'mapped') "
            "ORDER BY c.code LIMIT 1",
            (code,),
        ).fetchone()
    assert row is not None, "no single-ingredient product for a test code"
    return str(row[0])


def _scan(client: TestClient, barcode: str) -> tuple[str, str]:
    r = client.post("/resolve/scan", json={"content": "0" + barcode, "region": "TR"})
    assert r.status_code == 200, r.text
    body: dict[str, Any] = r.json()
    return body["candidates"][0]["candidate_id"], body["dataset_version"]


def test_gate1_istanbul_patient_on_real_data(env: tuple[TestClient, Database]) -> None:
    """Gate 1: AMLIPIN (C09BB03) plus eight medicines, resolved by scanning and evaluated through
    the API, gives the CCB → diuretic cascade from the amlodipine inside AMLIPIN. Req 9.8."""
    client, db = env
    amlipin, dataset = _scan(client, AMLIPIN)
    items: list[dict[str, str | None]] = [{"product": amlipin, "started": "2024-01"}]
    for code, started in OTHERS.items():
        cid, ds = _scan(client, _barcode_for(db, code))
        assert ds == dataset
        items.append({"product": cid, "started": started})
    r = client.post("/cascades/evaluate", json={"dataset_version": dataset, "items": items})
    assert r.status_code == 200, r.text
    body = r.json()
    by_rule = {f["rule_id"]: f for f in body["findings"]}
    f5 = by_rule["pipc:5"]
    assert f5["index"]["items"] == [0] and f5["index"]["matched_codes"] == ["C08CA01"]
    assert (f5["status"], f5["months_between"]) == ("probable", 5)
    assert "corrected_notice" in f5["integrity_codes"]
    assert {"pipc:6", "pipc:9"} <= set(by_rule)
    assert body["rules"]["checked"] == 63
    print(  # counts only, for the task report
        f"gate 1: {len(body['findings'])} findings, {len(body['chains'])} chains, "
        f"{len(body['item_warnings'])} abrupt-stop warnings; rules "
        f"{sorted(by_rule)}"
    )
