"""Database and counts-file setup for doctor-loop route tests (design §12).

A synthetic US-shaped resolution dataset with invented brand names (no real product data), the
real curated rule base, the evidence records the engine cites (PIPC, the curated papers,
`dataset:faers`), a small counts file, and a synthetic accepted glossary whose English cascade
hashes match the PIPC table, so every language is available.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import tempfile
from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psycopg
from fastapi import FastAPI
from fastapi.testclient import TestClient

from janus.cascades import router as cascades_router
from janus.cascades.load import load as load_rule_base
from janus.cascades.load import read_files
from janus.db.pool import Database
from janus.integrity.load import LoadInputs
from janus.integrity.load import load as integrity_load
from janus.integrity.model import EvidenceRecord
from janus.integrity.records import records_from_papers
from janus.integrity.registry import read_sources
from janus.main import create_app
from janus.memory import router as memory_router
from janus.memory.vocabulary import load_events
from janus.notes import glossary as gl
from janus.notes import router as notes_router
from janus.resolution.atc import DATA_DIR, CombinationRules, RouteMap
from janus.resolution.load import Inputs
from janus.resolution.load import load as load_resolution
from janus.settings import EVENT_VOCABULARY, Settings
from tests.integrity_db import reset as reset_evidence
from tests.memory_counts import make_counts
from tests.notes_strategies import (
    cascade_rows,
    csv_text,
    ingredient_row,
    sentence_rows,
)
from tests.resolution_db import inputs
from tests.resolution_db import reset as reset_resolution
from tests.resolution_strategies import us_row, wikidata_row
from tests.test_faers_build_properties import ReportFact

TODAY = dt.date(2026, 11, 7)
REGISTRY = DATA_DIR.parent / "pipelines" / "sources.toml"
PIPC_DOI = "10.1007/s41999-025-01215-x"

WD = [
    wikidata_row("Q3", ["C08CA01"], {"en": "amlodipine", "de": "Amlodipin"}),
    wikidata_row("Q900001", ["C03CA01"], {"en": "furosemide", "de": "Furosemid"}),
    wikidata_row("Q900020", ["C07AB02"], {"en": "metoprolol", "de": "Metoprolol"}),
    wikidata_row("Q900006", ["N06AB06"], {"en": "sertraline", "de": "Sertralin"}),
    wikidata_row("Q900030", ["A10BA02"], {"en": "metformin"}),
]
US = [
    us_row("11111-111", ["11111-111-11"], ["amlodipine besylate"], ["ORAL"], brand="ALFA US"),
    us_row("22222-222", ["22222-222-22"], ["furosemide"], ["ORAL"], brand="BETA US"),
    us_row("44444-444", ["44444-444-44"], ["metoprolol tartrate"], ["ORAL"], brand="GAMMA US"),
    us_row("55555-555", ["55555-555-55"], ["sertraline hydrochloride"], ["ORAL"], brand="DELTA US"),
    us_row("66666-666", ["66666-666-66"], ["metformin hydrochloride"], ["ORAL"], brand="EPSI US"),
]


def pipc_english() -> dict[int, tuple[str, str, str]]:
    rows = csv.DictReader(io.StringIO((DATA_DIR / "pipc.csv").read_text(encoding="utf-8")))
    return {int(r["position"]): (r["drug_a"], r["adverse_event"], r["drug_b"]) for r in rows}


def note_glossary(status: str = "accepted") -> gl.Glossary:
    ingredients = [
        ingredient_row("Q3", {"en": "amlodipine", "de": "Amlodipin", "fr": "amlodipine"}),
        ingredient_row("Q900001", {"en": "furosemide", "de": "Furosemid"}),
        ingredient_row("Q900020", {"en": "metoprolol"}),
    ]
    return gl.parse(
        csv_text(gl.INGREDIENT_HEADER, ingredients),
        csv_text(gl.CASCADE_HEADER, cascade_rows(status, pipc_english())),
        csv_text(gl.SENTENCE_HEADER, sentence_rows(status)),
    )


def oedema_pts() -> list[str]:
    vocab = load_events(EVENT_VOCABULARY)
    key = vocab.get("peripheral_oedema")
    assert key is not None
    return list(key.pts)


def facts() -> list[ReportFact]:
    pt = oedema_pts()[0]
    out = [
        ReportFact(str(100000 + i), "2026Q3", "US", (("PS", ("AMLODIPINE BESYLATE",)),), (pt,))
        for i in range(6)
    ]
    out += [
        ReportFact(str(200000 + i), "2026Q2", "EU", (("PS", ("ASPIRIN",)),), ("Cough",))
        for i in range(10)
    ]
    out.append(ReportFact("300000", "2026Q1", "TR", (("PS", ("AMLODIPINE BESYLATE",)),), (pt,)))
    return out


def seed_evidence(db: Database) -> None:
    sources = read_sources(REGISTRY)
    common: dict[str, Any] = {"kind": "dataset", "snapshot_is_retrieval_time": False}
    pipc = EvidenceRecord(
        id="dataset:pipc",
        source_id="pipc",
        source_url="https://www.ebi.ac.uk/europepmc/webservices/rest/PMC12712104/fullTextXML",
        license="CC BY 4.0",
        region=None,
        snapshot_date=dt.date(2025, 7, 31),
        doi=PIPC_DOI,
        title="PIPC list of prescribing cascades",
        **common,
    )
    faers = EvidenceRecord(
        id="dataset:faers",
        source_id="faers",
        source_url="https://fis.fda.gov/extensions/FPD-QDE-FAERS/FPD-QDE-FAERS.html",
        license="CC0 1.0",
        region="US",
        snapshot_date=dt.date(2026, 10, 28),
        doi=None,
        title=None,
        **common,
    )
    with (DATA_DIR / "evidence_papers.csv").open(encoding="utf-8", newline="") as f:
        papers = records_from_papers(list(csv.DictReader(f)), sources)
    integrity_load(db, LoadInputs((pipc, faers, *papers), sources, {}, None), TODAY)


@dataclass
class Env:
    client: TestClient
    app: FastAPI
    database: Database
    db_url: str
    dataset: str
    ids: dict[str, str]  # brand -> candidate id
    data_dir: Path


def make_env(db_url: str, settings_env: dict[str, str] | None = None) -> Generator[Env, None, None]:
    database = Database(db_url)
    database.open()
    with psycopg.connect(db_url, autocommit=True) as conn:
        reset_resolution(conn)
        conn.execute("DELETE FROM cascade_rule_base_current")
        conn.execute("DELETE FROM cascade_rule_base")
        reset_evidence(conn)
    base = inputs([], US, WD)
    load_resolution(
        database,
        Inputs(base.artifacts, CombinationRules.load(), RouteMap.load(), (), "test", base.cadences),
    )
    seed_evidence(database)
    load_rule_base(database, read_files(), TODAY)
    with database.read_only_tx() as conn:
        row = conn.execute("SELECT dataset_id FROM res_current").fetchone()
        assert row is not None
        dataset = str(row[0])
        rows = conn.execute(
            "SELECT region, source_id, product_id, coalesce(product_name, brand_name) "
            "FROM res_product WHERE dataset_id = %s",
            (dataset,),
        ).fetchall()
    ids = {str(r[3]): f"{r[0]}:{r[1]}:{r[2]}" for r in rows}
    with tempfile.TemporaryDirectory() as d:
        make_counts(Path(d), facts())
        for module in (cascades_router, memory_router, notes_router):
            module.today = lambda: TODAY  # pyright: ignore[reportAttributeAccessIssue]
        env = {"JANUS_DATA_DIR": d, **(settings_env or {})}
        app = create_app(Settings.from_env(env), database=database)
        app.state.glossary = note_glossary()
        with TestClient(app, raise_server_exceptions=False) as client:
            yield Env(client, app, database, db_url, dataset, ids, Path(d))
    database.close()


def patient(env: Env) -> list[dict[str, Any]]:
    """Synthetic patient: CCB then a diuretic (row 5), a beta-blocker then an antidepressant
    (row 3), metformin with no pattern."""
    return [
        {"product": env.ids["ALFA US"], "started": "2024-01"},
        {"product": env.ids["BETA US"], "started": "2024-06"},
        {"product": env.ids["GAMMA US"], "started": "2021-03"},
        {"product": env.ids["DELTA US"], "started": "2021-09"},
        {"product": env.ids["EPSI US"], "started": None},
    ]


def note_body(env: Env, items: list[dict[str, Any]] | None = None, **kw: Any) -> dict[str, Any]:
    return {
        "evaluation": {"dataset_version": env.dataset, "items": items or patient(env)},
        "languages": kw.pop("languages", ["en", "de"]),
        "region": kw.pop("region", "EU"),
        **kw,
    }
