"""`POST /notes/document`: P17, P21, P22, P24 and examples (doctor-loop design §4, §13).

Real PostgreSQL 16 (synthetic resolution dataset, real rule base, evidence), a small counts file,
and a synthetic accepted glossary.
"""

from __future__ import annotations

import json
import random
import types
from collections.abc import Iterator
from typing import Any, get_args, get_origin

import pytest
from fastapi.testclient import TestClient
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import BaseModel

from janus.memory.reader import CountsHolder
from janus.notes import schemas as note_schemas
from janus.notes import service
from janus.notes.schemas import NoteIn
from tests.conftest import DB_EXAMPLES
from tests.harness import assert_stateless, capture_logs, isolated_tempdir
from tests.notes_db import TODAY, Env, make_env, note_body, note_glossary, patient
from tests.sentinels import leaked

pytestmark = pytest.mark.db


@pytest.fixture(scope="module")
def env(db_url: str) -> Iterator[Env]:
    yield from make_env(db_url)


def post(client: TestClient, body: Any) -> Any:
    return client.post("/notes/document", json=body)


def blocks(doc: dict[str, Any], section: str) -> list[dict[str, Any]]:
    for s in doc["sections"]:
        if s["id"] == section:
            return s["blocks"]
    return []


def section_ids(doc: dict[str, Any]) -> list[str]:
    return [s["id"] for s in doc["sections"]]


# --- examples ---------------------------------------------------------------------------------


def test_synthetic_patient_note(env: Env) -> None:
    r = post(env.client, note_body(env))
    assert r.status_code == 200, r.text
    assert r.headers["cache-control"] == "no-store"
    note = r.json()
    assert note["note_format"] == "janus-note-1"
    assert note["versions"]["dataset_version"] == env.dataset
    assert note["versions"]["glossary_version"] == env.app.state.glossary.version
    assert [d["language"] for d in note["documents"]] == ["en", "de"]
    en = note["documents"][0]
    assert section_ids(en)[:3] == ["header", "safety", "medicines"]  # depression has a safety line
    cascades = [b["id"] for b in blocks(en, "findings") if b.get("template") == "finding.cascade"]
    assert {c.split(":")[1] for c in cascades} == {"3", "5"}
    meds = blocks(en, "medicines")
    assert [m["item"] for m in meds] == [0, 1, 2, 3, 4]
    assert [m["abrupt_stop"] is not None for m in meds] == [False, False, True, True, False]
    assert all(m["product_name_slot"] is True for m in meds)
    stats = [b for b in blocks(en, "statistics") if b["type"] == "stat"]
    assert stats and all(s["citation"]["evidence_id"] == "dataset:faers" for s in stats)
    assert note["removals"] == []


def test_counts_file_missing_gives_statistics_unavailable(db_url: str) -> None:
    gen = make_env(db_url, {"JANUS_DATA_DIR": "/nonexistent-janus-dir"})
    e = next(gen)
    try:
        r = post(e.client, note_body(e))
        assert r.status_code == 200
        doc = r.json()["documents"][0]
        stat = blocks(doc, "statistics")
        assert [b["template"] for b in stat] == ["statistics_unavailable"]
        assert r.json()["versions"]["counts_build_id"] is None
    finally:
        gen.close()


def test_errors(env: Env) -> None:
    pins = {"rule_base_version": "0" * 64, "integrity_version": "1" * 64}
    r = post(env.client, note_body(env, pins=pins))
    assert r.status_code == 409
    assert r.json() == {
        "error": "version_mismatch",
        "fields": ["pins.rule_base_version", "pins.integrity_version"],
    }
    body = note_body(env)
    body["evaluation"]["dataset_version"] = "f" * 64
    assert post(env.client, body).json() == {"error": "dataset_version_mismatch"}
    assert post(env.client, note_body(env, languages=["en", "en"])).status_code == 422
    unknown = note_body(env, demo=True)
    r = post(env.client, unknown)
    assert r.status_code == 422 and "demo" not in r.text
    env.app.state.glossary = note_glossary("proposed")
    try:
        r = post(env.client, note_body(env))
        assert r.status_code == 422
        assert r.json() == {
            "error": "note_language_unavailable",
            "fields": ["languages.0", "languages.1"],
        }
    finally:
        env.app.state.glossary = note_glossary()
    db = env.app.state.database
    env.app.state.database = None
    try:
        assert post(env.client, note_body(env)).json() == {"error": "notes_unavailable"}
    finally:
        env.app.state.database = db


# --- P22 --------------------------------------------------------------------------------------

months = st.none() | st.sampled_from(["2019-05", "2021-03", "2023-01", "2024-01", "2024-06"])


@settings(max_examples=DB_EXAMPLES, deadline=None)
@given(data=st.data())
def test_p22_findings_equal_the_engine(env: Env, data: st.DataObject) -> None:
    """Feature: doctor-loop, Property P22. Validates Req 4.3, 4.5."""
    pool = patient(env)
    chosen = data.draw(
        st.lists(st.sampled_from(range(len(pool))), min_size=1, max_size=5, unique=True)
    )
    items: list[dict[str, Any]] = []
    for i in chosen:
        if data.draw(st.booleans()):
            items.append({**pool[i], "started": data.draw(months)})
        else:
            key = {0: "Q3", 1: "Q900001", 2: "Q900020", 3: "Q900006", 4: "Q900030"}[i]
            items.append({"ingredient": key, "started": data.draw(months)})
    evaluation = {"dataset_version": env.dataset, "items": items}
    engine = env.client.post("/cascades/evaluate", json=evaluation).json()
    r = post(env.client, note_body(env, items=items, languages=["fr"]))
    assert r.status_code == 200, r.text
    note = r.json()
    doc = note["documents"][0]
    found = {
        b["id"].rsplit(":", 1)[0]: sec
        for sec in ("findings", "findings_form_unconfirmed")
        for b in blocks(doc, sec)
        if b.get("template") == "finding.cascade"
    }
    expected = {
        f["finding_id"]: "findings" if f["form_confirmed"] else "findings_form_unconfirmed"
        for f in engine["findings"]
    }
    assert found == expected
    warned = {w["item"] for w in engine["item_warnings"]}
    assert {m["item"] for m in blocks(doc, "medicines") if m["abrupt_stop"]} == warned
    assert note["versions"]["rule_base_version"] == engine["rule_base_version"]
    assert note["versions"]["integrity_version"] == engine["integrity_version"]
    again = post(env.client, note_body(env, items=items, languages=["fr"]))
    assert again.content == r.content  # byte-identical repeats


# --- P17 --------------------------------------------------------------------------------------


def test_p17_stat_rows_equal_memory_pair(env: Env) -> None:
    """Feature: doctor-loop, Property P17. Validates Req 9.1-9.4, 9.7."""
    for region in (None, "US", "TR"):
        kw: dict[str, Any] = {} if region is None else {"statistics_region": region}
        doc = post(env.client, note_body(env, languages=["en"], **kw)).json()["documents"][0]
        rows = [b for b in blocks(doc, "statistics") if b["type"] == "stat"]
        assert {r["region"] for r in rows} == {"ALL", *([region] if region else [])}
        printed_pt = False
        for row in rows:
            pair = env.client.post(
                "/memory/pair",
                json={
                    "ingredient": row["ingredient_key"],
                    "event": {"key": row["event_key"]},
                    "region": row["region"],
                    "scope": "suspect",
                },
            ).json()
            stats = pair["stats"]
            assert row["citation"] == pair["citation"]
            assert row["assessment"] == stats["assessment"]
            hidden = stats["assessment"] in ("no_reports", "insufficient_data")
            if hidden:
                assert row["reports"] is None and row["estimates"] is None
                assert all(not any(ch.isdigit() for ch in s["text"]) for s in row["sentences"])
            else:
                assert row["reports"] == stats["cells"]["a"]
                assert row["estimates"] == {
                    "ror": stats["estimates"]["ror"],
                    "low": stats["estimates"]["ror_ci"]["low"],
                    "high": stats["estimates"]["ror_ci"]["high"],
                }
            printed_pt = printed_pt or row["pts"] is not None
        templates = [b.get("template") for b in blocks(doc, "statistics")]
        assert ("stat.meddra_long" in templates) == printed_pt
        assert "stat.screening" in templates and "stat.attribution" in templates


# --- P21 --------------------------------------------------------------------------------------


def _string_fields(model: type[BaseModel], path: str = "") -> list[tuple[str, Any]]:
    out: list[tuple[str, Any]] = []
    for name, field in model.model_fields.items():
        out += _walk(field.annotation, field.metadata, f"{path}{name}")
    return out


def _walk(tp: Any, metadata: list[Any], path: str) -> list[tuple[str, Any]]:
    origin = get_origin(tp)
    if isinstance(tp, type) and issubclass(tp, BaseModel):
        return _string_fields(tp, path + ".")
    if origin in (list, types.UnionType) or str(origin) == "typing.Union":
        out: list[tuple[str, Any]] = []
        for arg in get_args(tp):
            out += _walk(arg, metadata, path)
        return out
    if str(origin).endswith("Annotated"):
        args = get_args(tp)
        return _walk(args[0], [*metadata, *args[1:]], path)
    if tp is str:
        return [(path, metadata)]
    return []


@pytest.mark.parametrize(
    "model",
    [note_schemas.NoteIn, note_schemas.TokenIn, note_schemas.OutcomeIn, note_schemas.TokenBodyIn],
)
def test_p21_no_free_text_field(model: type[BaseModel]) -> None:
    """Feature: doctor-loop, Property P21 (closed schema). Validates Req 1.2."""
    fields = _string_fields(model)
    assert fields
    for path, metadata in fields:
        assert any(getattr(m, "pattern", None) for m in metadata), path


@settings(max_examples=max(10, DB_EXAMPLES // 5), deadline=None)
@given(data=st.data())
def test_p21_stateless_and_silent(env: Env, data: st.DataObject) -> None:
    """Feature: doctor-loop, Property P21 (route). Validates Req 4.1, 4.7, 13."""
    pool = patient(env)
    items = data.draw(
        st.lists(st.sampled_from(pool), min_size=1, max_size=5, unique_by=lambda x: x["product"])
    )
    kind = data.draw(st.sampled_from(["ok", "422", "409", "lang"]))
    body = note_body(env, items=items)
    if kind == "422":
        body["evaluation"]["items"][0]["started"] = "2024-13"
    elif kind == "409":
        body["pins"] = {"integrity_version": "0" * 64}
    elif kind == "lang":
        body["languages"] = ["xx"]
    secrets = [i["product"] for i in items] + [i["started"] for i in items if i["started"]]
    with isolated_tempdir() as tmp, capture_logs() as logs:
        import psycopg

        with psycopg.connect(env.db_url, autocommit=True) as conn:
            r = assert_stateless(conn, tmp, lambda: post(env.client, body))
    assert r.headers["cache-control"] == "no-store"
    assert leaked(logs.getvalue(), secrets) == []
    if r.status_code == 422:
        assert all(s not in r.text for s in secrets)


# --- P24 --------------------------------------------------------------------------------------


def test_p24_statements_do_not_depend_on_languages(env: Env) -> None:
    """Feature: doctor-loop, Property P24. Validates Req 15.2."""
    counts: list[int] = []
    for langs in (["en"], ["en", "de"]):
        body = NoteIn.model_validate(note_body(env, languages=langs, statistics_region="US"))
        holder = CountsHolder(env.data_dir)
        with env.database.read_only_tx() as conn, holder.current().session() as session:
            service.compose(
                conn,
                body,
                today=TODAY,
                vocab=env.app.state.event_vocabulary,
                glossary=env.app.state.glossary,
                session=session,
            )
            counts.append(session.statements)
    assert counts[0] == counts[1] > 0


def test_random_order_gives_the_same_findings(env: Env) -> None:
    items = patient(env)
    shuffled = items[:]
    random.Random(7).shuffle(shuffled)  # noqa: S311 (test order, not a secret)
    a = post(env.client, note_body(env, items=items, languages=["en"])).json()
    b = post(env.client, note_body(env, items=shuffled, languages=["en"])).json()

    def ids(note: dict[str, Any]) -> set[str]:
        doc = note["documents"][0]
        return {x["id"] for x in blocks(doc, "findings") if x.get("template") == "finding.cascade"}

    assert ids(a) == ids(b)
    assert json.dumps(a["versions"]) == json.dumps(b["versions"])
