"""Outcome loop: P7, P8, P21/P32 (loop routes), P25-P30, migration 0011 (doctor-loop §7-§8).

Real PostgreSQL 16. Tokens are signed with test keys from the settings; findings come from the
synthetic dataset of `notes_db` or from generated payloads.
"""

from __future__ import annotations

import base64
import datetime as dt
import threading
from collections.abc import Iterator
from fractions import Fraction
from typing import Any, cast

import psycopg
import pytest
from alembic import command
from fastapi.routing import APIRoute
from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule, run_state_machine_as_test

from janus.db.pool import Database
from janus.memory import shared
from janus.memory.disclosure import keyed_noise_source
from janus.memory.schemas import SharedIn
from janus.notes import loop, repository
from janus.notes import router as notes_router
from janus.notes.outcomes import OUTCOME_COLUMNS, outcome_rows
from janus.notes.schemas import AnswerIn
from janus.notes.source import OutcomesSource
from janus.notes.token import (
    Keyring,
    Payload,
    Region,
    TokenFinding,
    deletion_hash,
    sign,
    verify,
)
from tests.conftest import DB_EXAMPLES, alembic_config
from tests.harness import assert_stateless, capture_logs, isolated_tempdir
from tests.notes_db import TODAY, Env, make_env, note_body
from tests.notes_strategies import payloads
from tests.sentinels import leaked

pytestmark = pytest.mark.db

KEY = b"\x42" * 32
NOISE = b"\x17" * 32
B64 = base64.urlsafe_b64encode(KEY).decode().rstrip("=")
NOISE_B64 = base64.urlsafe_b64encode(NOISE).decode().rstrip("=")
RING = Keyring({"t1": KEY}, "t1")
NOW = dt.datetime(2026, 11, 7, 12, 0, tzinfo=dt.UTC)  # a Saturday; report week 2026-11-02
LOOP_ENV = {
    "JANUS_NOTE_KEYS": f"t1:{B64}",
    "JANUS_NOTE_SIGNING_KEY_ID": "t1",
    "JANUS_OUTCOME_CONSENT_VERSIONS": "outcome-2026-11",
    "JANUS_DONATION_REGION": "local",
    "JANUS_NOISE_KEY": NOISE_B64,
    "JANUS_PUBLIC_BASE_URL": "https://janus.example",
}


@pytest.fixture(scope="module")
def env(db_url: str) -> Iterator[Env]:
    notes_router.now = lambda: NOW
    yield from make_env(db_url, LOOP_ENV)


def clear(db_url: str) -> None:
    with psycopg.connect(db_url, autocommit=True) as conn:
        conn.execute("DELETE FROM outcomes")
        conn.execute("DELETE FROM used_note_tokens")


def outcomes(db_url: str) -> list[dict[str, Any]]:
    with psycopg.connect(db_url, autocommit=True) as conn:
        cur = conn.execute("SELECT * FROM outcomes ORDER BY deletion_hash")
        names = [d.name for d in cur.description or []]
        return [dict(zip(names, r, strict=True)) for r in cur.fetchall()]


def used(db_url: str) -> dict[bytes, str]:
    with psycopg.connect(db_url, autocommit=True) as conn:
        rows = conn.execute("SELECT note_hash, state FROM used_note_tokens").fetchall()
    return {bytes(r[0]): str(r[1]) for r in rows}


def issue(env: Env, **kw: Any) -> dict[str, Any]:
    body = {
        "note": note_body(env, languages=["de"]),
        "consent_version": "outcome-2026-11",
        "outcome_region": "EU",
        **kw,
    }
    r = env.client.post("/notes/token", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def payload_for(
    n: int, *, event: str = "peripheral_oedema", week: dt.date = dt.date(2026, 11, 2)
) -> Payload:
    f = TokenFinding(5, "Q3", "Q900001", ("C08CA01",), ("C03CA01",), event, "adverse", True)
    g = TokenFinding(
        3, "Q900020", "Q900006", ("C07AB02",), ("N06AB06",), "depression", "adverse", False
    )
    findings = (f, g)[:n]
    return Payload("t1", bytes(16), week, "de", "EU", "outcome-2026-11", findings)


# --- migration 0011 (task 9.1) ----------------------------------------------------------------


def test_migration_0011_columns_and_reversibility(db_url: str) -> None:
    with psycopg.connect(db_url, autocommit=True) as conn:
        cols = {
            t: [
                r[0]
                for r in conn.execute(
                    "SELECT column_name FROM information_schema.columns WHERE table_name = %s "
                    "ORDER BY ordinal_position",
                    (t,),
                ).fetchall()
            ]
            for t in ("outcomes", "used_note_tokens")
        }
        assert tuple(cols["outcomes"]) == OUTCOME_COLUMNS
        assert cols["used_note_tokens"] == ["note_hash", "expires_on", "state"]
        defaults = conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name IN "
            "('outcomes', 'used_note_tokens') AND column_default IS NOT NULL"
        ).fetchall()
        assert [r[0] for r in defaults] == ["id"]  # no clock default anywhere
        insert = "INSERT INTO used_note_tokens VALUES (decode(repeat('00', %s), 'hex'), %s, 'used')"
        for size, day in ((32, "2026-11-03"), (31, "2026-11-02")):  # not a Monday; short hash
            with pytest.raises(psycopg.errors.CheckViolation):
                conn.execute(insert, (size, day))
    cfg = alembic_config(db_url)
    command.downgrade(cfg, "0010")
    with psycopg.connect(db_url, autocommit=True) as conn:
        assert conn.execute("SELECT to_regclass('outcomes')").fetchone() == (None,)
    command.upgrade(cfg, "head")


# --- P25 --------------------------------------------------------------------------------------


def test_p25_token_carries_the_notes_findings(env: Env) -> None:
    """Feature: doctor-loop, Property P25. Validates Req 2.1, 12.1, 12.2."""
    clear(env.db_url)
    body = {
        "note": note_body(env, languages=["de"]),
        "consent_version": "outcome-2026-11",
        "outcome_region": "EU",
    }
    with isolated_tempdir() as tmp, psycopg.connect(env.db_url, autocommit=True) as conn:
        r = assert_stateless(conn, tmp, lambda: env.client.post("/notes/token", json=body))
    assert r.status_code == 200, r.text
    out = r.json()
    payload = verify(RING, out["token"], TODAY)
    doc = out["note"]["documents"][0]
    order = [
        b["id"].rsplit(":", 1)[0]
        for sec in doc["sections"]
        if sec["id"] in ("findings", "findings_form_unconfirmed")
        for b in sec["blocks"]
        if b.get("template") == "finding.cascade"
    ]
    carried = [f"pipc:{f.row}:{f.index_key}:{f.marker_key}" for f in payload.findings]
    assert carried == order[: out["findings_covered"]] and out["findings_total"] == len(order)
    assert (payload.language, payload.region, payload.consent_version) == (
        "de",
        "EU",
        "outcome-2026-11",
    )
    assert out["qr_url"] == "https://janus.example/o#" + out["token"]
    assert out["expires_on"] == "2026-12-07"
    loop_section = [s for s in doc["sections"] if s["id"] == "outcome_loop"]
    assert loop_section and loop_section[0]["blocks"][1]["numbers"] == [
        str(len(order)),
        str(len(order)),
    ]
    # refusals
    bad = env.client.post("/notes/token", json={**body, "consent_version": "other-1"})
    assert bad.status_code == 422 and bad.json()["fields"] == ["consent_version"]
    nothing = {
        **body,
        "note": note_body(
            env, items=[{"product": env.ids["EPSI US"], "started": None}], languages=["de"]
        ),
    }
    assert env.client.post("/notes/token", json=nothing).json() == {"error": "no_findings"}
    two = {**body, "note": note_body(env, languages=["de", "en"])}
    assert env.client.post("/notes/token", json=two).status_code == 422
    ring = env.app.state.note_keyring
    env.app.state.note_keyring = None
    try:
        assert env.client.post("/notes/token", json=body).json() == {"error": "notes_unavailable"}
    finally:
        env.app.state.note_keyring = ring


# --- P30 and the error codes -------------------------------------------------------------------


def test_p30_form_lists_the_tokens_findings(env: Env) -> None:
    """Feature: doctor-loop, Property P30. Validates Req 3.1, 2.2."""
    clear(env.db_url)
    out = issue(env)
    token = out["token"]
    payload = verify(RING, token, TODAY)
    with isolated_tempdir() as tmp, psycopg.connect(env.db_url, autocommit=True) as conn:
        r = assert_stateless(
            conn, tmp, lambda: env.client.post("/outcomes/form", json={"token": token})
        )
    assert r.status_code == 200, r.text
    form = r.json()
    assert form["language"] == "de" and form["expires_on"] == payload.expires_on.isoformat()
    assert [
        (f["ref"], f["rule_id"], f["index"]["key"], f["marker"]["key"]) for f in form["findings"]
    ] == [(i, f"pipc:{f.row}", f.index_key, f.marker_key) for i, f in enumerate(payload.findings)]
    assert [f["index"]["atc"] for f in form["findings"]] == [
        list(f.index_codes) for f in payload.findings
    ]
    assert [o["code"] for o in form["options"]["assessment"]] == ["confirmed", "not_a_cascade"]
    assert "action_on" not in form["options"]
    for f in form["findings"]:  # one action per finding; the label carries the ingredient name
        assert [o["code"] for o in f["action_on"]] == ["index", "marker"]
        assert f["index"]["name"] in f["action_on"][0]["text"]
        assert f["marker"]["name"] in f["action_on"][1]["text"]
    assert form["texts"]["disclaimer"] == env.app.state.glossary.text("disclaimer", "de")
    forged = token[:-3] + ("AAA" if token[-3:] != "AAA" else "BBB")
    assert env.client.post("/outcomes/form", json={"token": forged}).json() == {
        "error": "invalid_token"
    }
    expired = sign(RING, payload_for(1, week=dt.date(2026, 9, 7)))
    assert env.client.post("/outcomes/form", json={"token": expired}).json() == {
        "error": "token_expired"
    }
    assert env.client.post(
        "/outcomes", json={"token": token, "answers": [{"ref": 0, "assessment": "confirmed"}]}
    ).json() == {"stored": 1}
    assert env.client.post("/outcomes/form", json={"token": token}).json() == {
        "error": "token_used"
    }
    other = issue(env)["token"]
    assert env.client.post("/notes/withdraw", json={"token": other}).json() == {
        "status": "withdrawn"
    }
    assert env.client.post("/outcomes/form", json={"token": other}).json() == {
        "error": "token_not_usable"
    }


# --- P26 --------------------------------------------------------------------------------------


def _answer(ref: int, assessment: str, action: str | None, on: str) -> dict[str, Any]:
    out: dict[str, Any] = {"ref": ref, "assessment": assessment}
    if action is not None:
        out["action"] = action
        if action in ("dose_changed", "medicine_changed", "stopped"):
            out["action_on"] = on
    return out


answers_st = st.lists(
    st.builds(
        _answer,
        st.integers(0, 2),
        st.sampled_from(["confirmed", "not_a_cascade"]),
        st.none() | st.sampled_from(["dose_changed", "medicine_changed", "stopped", "no_change"]),
        st.sampled_from(["index", "marker"]),
    ),
    min_size=1,
    max_size=3,
)


@settings(max_examples=DB_EXAMPLES, deadline=None)
@given(
    answers=answers_st,
    broken=st.sampled_from([None, "repeat", "action_on_missing", "action_on_extra"]),
)
def test_p26_outcome_rows(env: Env, answers: list[dict[str, Any]], broken: str | None) -> None:
    """Feature: doctor-loop, Property P26. Validates Req 3.1, 3.2, 3.4."""
    clear(env.db_url)
    p = payload_for(2)
    token = sign(
        RING,
        Payload(
            "t1", bytes(range(16)), dt.date(2026, 11, 2), "de", "EU", "outcome-2026-11", p.findings
        ),
    )
    body_answers = [dict(a) for a in answers]
    if broken == "repeat":
        body_answers.append(dict(body_answers[0]))
    elif broken == "action_on_missing":
        body_answers[0] = {
            "ref": body_answers[0]["ref"],
            "assessment": "confirmed",
            "action": "stopped",
        }
    elif broken == "action_on_extra":
        body_answers[0] = {
            "ref": body_answers[0]["ref"],
            "assessment": "confirmed",
            "action_on": "index",
        }
    refs = [a["ref"] for a in body_answers]
    r = env.client.post("/outcomes", json={"token": token, "answers": body_answers})
    invalid = broken is not None or len(set(refs)) != len(refs) or any(x >= 2 for x in refs)
    if invalid:
        assert r.status_code == 422, r.text
        assert outcomes(env.db_url) == [] and used(env.db_url) == {}
        assert "outcome-2026-11" not in r.text
        return
    assert r.json() == {"stored": len(body_answers)}
    rows = outcomes(env.db_url)
    assert all(tuple(row) == OUTCOME_COLUMNS for row in rows)
    by_hash = {bytes(row["deletion_hash"]): row for row in rows}
    for a in body_answers:
        ref = int(a["ref"])
        f = p.findings[ref]
        row = by_hash[deletion_hash(bytes(range(16)), ref)]
        assert row["report_week"] == dt.date(2026, 11, 2)
        assert (
            row["region"],
            row["rule_id"],
            row["index_key"],
            row["marker_key"],
            row["event"],
        ) == (
            "EU",
            f"pipc:{f.row}",
            f.index_key,
            f.marker_key,
            f.event,
        )
        assert row["ingredients"] == sorted([f.index_key, f.marker_key])
        assert (row["assessment"], row["action"], row["action_on"]) == (
            a["assessment"],
            a.get("action"),
            a.get("action_on"),
        )
        assert (
            row["form_confirmed"] == f.form_confirmed
            and row["consent_version"] == "outcome-2026-11"
        )


# --- P7 ---------------------------------------------------------------------------------------


class InjectedError(RuntimeError):
    pass


class LoopMachine(RuleBasedStateMachine):
    """Feature: doctor-loop, Properties P7 and P27. Validates Req 2.7, 3.2, 12.2, 12.4."""

    database: Database
    db_url: str

    def __init__(self) -> None:
        super().__init__()
        clear(self.db_url)
        self.today = dt.date(2026, 11, 7)
        self.tokens: list[Payload] = []
        self.state: dict[bytes, str] = {}  # note hash -> used / withdrawn (model)
        self.stored: set[bytes] = set()  # deletion hashes (model)

    @rule(n=st.integers(1, 2), weeks_ago=st.integers(0, 6), seed=st.integers(0, 2**32 - 1))
    def issue(self, n: int, weeks_ago: int, seed: int) -> None:
        week = dt.date(2026, 11, 2) - dt.timedelta(weeks=weeks_ago)
        nid = seed.to_bytes(4, "big") + bytes(12)
        p = Payload("t1", nid, week, "en", "TR", "outcome-2026-11", payload_for(n).findings)
        if all(t.note_id != nid for t in self.tokens):
            self.tokens.append(p)

    def _pick(self, data: st.DataObject) -> Payload | None:
        return data.draw(st.sampled_from(self.tokens)) if self.tokens else None

    @rule(data=st.data(), fail_at=st.none() | st.sampled_from(["mark", "insert", "commit"]))
    def submit(self, data: st.DataObject, fail_at: str | None) -> None:
        p = self._pick(data)
        if p is None or not self.today < p.expires_on:
            return
        refs = data.draw(st.lists(st.integers(0, len(p.findings) - 1), min_size=1, unique=True))
        rows = outcome_rows(p, [AnswerIn(ref=r, assessment="confirmed") for r in refs], NOW)

        def hook(step: str) -> None:
            if step == fail_at:
                raise InjectedError

        try:
            result = repository.submit(self.database, p.note_hash, p.expires_on, rows, hook)
        except InjectedError:
            return  # nothing written; the token stays usable
        expected = self.state.get(p.note_hash)
        if expected is None:
            assert result is repository.SubmitResult.stored
            self.state[p.note_hash] = "used"
            self.stored |= {r.deletion_hash for r in rows}
        else:
            assert result.value == expected

    @rule(data=st.data())
    def withdraw(self, data: st.DataObject) -> None:
        p = self._pick(data)
        if p is None:
            return
        loop.withdraw(self.database, p, self.today)
        self.stored -= {deletion_hash(p.note_id, r) for r in range(len(p.findings))}
        if self.today < p.expires_on:
            self.state[p.note_hash] = "withdrawn"

    @rule(days=st.integers(1, 20))
    def advance(self, days: int) -> None:
        self.today += dt.timedelta(days=days)

    @rule()
    def purge(self) -> None:
        repository.purge(self.database, self.today)
        for p in self.tokens:
            if p.expires_on <= self.today:
                self.state.pop(p.note_hash, None)

    @invariant()
    def store_equals_model(self) -> None:
        assert {bytes(r["deletion_hash"]) for r in outcomes(self.db_url)} == self.stored
        db_state = used(self.db_url)
        for h, s in self.state.items():
            assert db_state.get(h) == s
        assert set(db_state) <= set(self.state) | {p.note_hash for p in self.tokens}


def test_p7_single_use_and_atomic_submit(env: Env) -> None:
    LoopMachine.database = env.database
    LoopMachine.db_url = env.db_url
    run_state_machine_as_test(
        LoopMachine,
        settings=settings(
            max_examples=max(10, DB_EXAMPLES // 2), stateful_step_count=15, deadline=None
        ),
    )


# --- P8 ---------------------------------------------------------------------------------------


def test_p8_concurrent_submissions(env: Env) -> None:
    """Feature: doctor-loop, Property P8. Validates Req 2.7."""
    for n in (2, 4, 8):
        clear(env.db_url)
        p = Payload(
            "t1",
            n.to_bytes(16, "big"),
            dt.date(2026, 11, 2),
            "en",
            "US",
            "outcome-2026-11",
            payload_for(2).findings,
        )
        token = sign(RING, p)
        results: list[int] = []
        barrier = threading.Barrier(n)

        def go(
            barrier: threading.Barrier = barrier, token: str = token, results: list[int] = results
        ) -> None:
            barrier.wait()
            r = env.client.post(
                "/outcomes",
                json={
                    "token": token,
                    "answers": [
                        {"ref": 0, "assessment": "confirmed"},
                        {"ref": 1, "assessment": "not_a_cascade"},
                    ],
                },
            )
            results.append(r.status_code)

        threads = [threading.Thread(target=go) for _ in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert sorted(results) == [200] + [409] * (n - 1)
        assert len(outcomes(env.db_url)) == 2


# --- P21 / P32 for the loop routes --------------------------------------------------------------


def test_p32_no_route_reads_a_path_or_query_parameter(env: Env) -> None:
    """Feature: doctor-loop, Property P32 (routes). Validates Req 2.1, 13.2."""
    for route in env.app.routes:
        if isinstance(route, APIRoute):
            assert not route.dependant.path_params, route.path
            assert not route.dependant.query_params, route.path
            assert "{" not in route.path


@settings(max_examples=max(10, DB_EXAMPLES // 5), deadline=None)
@given(p=payloads(kid="t1", max_findings=2))
def test_p21_p32_loop_routes_are_silent(env: Env, p: Payload) -> None:
    """Feature: doctor-loop, Properties P21 and P32 (loop routes). Validates Req 3.6, 13."""
    token = sign(RING, p)
    with capture_logs() as logs:
        for path in ("/outcomes/form", "/outcomes", "/notes/withdraw"):
            r = env.client.post(f"{path}?token={token}")  # no body: the query is never read
            assert r.status_code in (415, 422) and token not in r.text
            r = env.client.post(path, json={"token": token, "demo": True})
            assert r.status_code == 422
        env.client.post("/outcomes/form", json={"token": token})
        env.client.post(f"/o/{token}", json={})
    assert leaked(logs.getvalue(), [token, token[:24]]) == []


# --- P28 --------------------------------------------------------------------------------------


@settings(max_examples=max(10, DB_EXAMPLES // 5), deadline=None)
@given(
    weeks=st.lists(st.integers(0, 130), min_size=1, max_size=6), today_offset=st.integers(0, 900)
)
def test_p28_purge(env: Env, weeks: list[int], today_offset: int) -> None:
    """Feature: doctor-loop, Property P28. Validates Req 3.5, 12.2."""
    from janus.contributions.retention import retention_cutoff

    clear(env.db_url)
    base = dt.date(2024, 1, 1)  # a Monday
    for i, w in enumerate(weeks):
        week = base + dt.timedelta(weeks=w)
        p = Payload(
            "t1",
            i.to_bytes(16, "big"),
            week,
            "en",
            "US",
            "outcome-2026-11",
            payload_for(1).findings,
        )
        rows = outcome_rows(
            p,
            [AnswerIn(ref=0, assessment="confirmed")],
            dt.datetime.combine(week, dt.time(9), dt.UTC),
        )
        repository.submit(env.database, p.note_hash, p.expires_on, rows)
    today = base + dt.timedelta(days=today_offset)
    repository.purge(env.database, today)
    left = outcomes(env.db_url)
    assert sorted(r["report_week"] for r in left) == sorted(
        base + dt.timedelta(weeks=w)
        for w in weeks
        if base + dt.timedelta(weeks=w) > retention_cutoff(today)
    )
    with psycopg.connect(env.db_url, autocommit=True) as conn:
        exp = [r[0] for r in conn.execute("SELECT expires_on FROM used_note_tokens").fetchall()]
    assert all(e > today for e in exp)


# --- P29 --------------------------------------------------------------------------------------


@settings(max_examples=max(10, DB_EXAMPLES // 5), deadline=None)
@given(
    spec=st.lists(
        st.tuples(
            st.sampled_from(["TR", "EU", "US"]),
            st.sampled_from(["confirmed", "not_a_cascade"]),
            st.integers(0, 1),
        ),
        min_size=0,
        max_size=50,
    ),
    query=st.sampled_from([["Q3"], ["Q900001"], ["Q3", "Q900001"], ["Q900020"], ["Q3", "Q900020"]]),
)
def test_p29_outcomes_layer(env: Env, spec: list[tuple[str, str, int]], query: list[str]) -> None:
    """Feature: doctor-loop, Property P29. Validates Req 11."""
    clear(env.db_url)
    findings = payload_for(2).findings
    for i, (region, assessment, which) in enumerate(spec):
        p = Payload(
            "t1",
            (10_000 + i).to_bytes(16, "big"),
            dt.date(2026, 11, 2),
            "en",
            cast(Region, region),
            "outcome-2026-11",
            (findings[which],),
        )
        answer = AnswerIn.model_validate({"ref": 0, "assessment": assessment})
        rows = outcome_rows(p, [answer], NOW)
        repository.submit(env.database, p.note_hash, p.expires_on, rows)
    event = "peripheral_oedema"
    with env.database.read_only_tx() as conn:
        cells = {c.region: c for c in OutcomesSource().cells(conn, query, event, "adverse")}
        out = shared.shared(
            SharedIn.model_validate(
                {"layer": "outcomes", "ingredients": query, "event": event, "direction": "adverse"}
            ),
            sources={"outcomes": OutcomesSource()},
            conn=conn,
            noise_source=keyed_noise_source(NOISE),
            k=20,
            epsilon=Fraction(1),
        )
    expected: dict[str, int] = {}
    for region, assessment, which in spec:
        f = findings[which]
        if (
            assessment == "confirmed"
            and f.event == event
            and set(query) <= {f.index_key, f.marker_key}
        ):
            expected[region] = expected.get(region, 0) + 1
    assert {r: c.n for r, c in cells.items()} == expected
    for c in out.cells:
        if expected.get(c.region, 0) < 20:
            assert c.status == "hidden" and c.value is None
    assert out.status == "ok"
    # the route answers through the same code path
    r = env.client.post(
        "/memory/shared",
        json={"layer": "outcomes", "ingredients": query, "event": event, "direction": "adverse"},
    )
    assert r.status_code == 200 and r.json()["status"] == "ok"
    assert "faers" not in r.text


def test_snapshot_reports_the_outcomes_layer(env: Env) -> None:
    body = env.client.get("/memory/snapshot").json()
    assert body["layers"]["outcomes"] == "ok"
