"""`/seance` routes over HTTP without a database (séance design §6, §8): P17-P20 and examples."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from hypothesis import given
from hypothesis import strategies as st

from janus.main import create_app
from janus.memory.reader import RawCells
from janus.notes.phrases import violations
from janus.seance import service
from janus.seance.catalogue import Catalogue, load_catalogue
from janus.settings import Settings
from tests.harness import capture_logs
from tests.sentinels import ascii_sentinels, leaked

CAT = load_catalogue()
PAIRS = sorted({(c.substance_id, c.condition) for c in CAT.claims} | set(CAT.science))


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    settings = Settings.from_env({})
    app = create_app(settings, configure_logs=False)
    with TestClient(app) as c:
        yield c


def _texts(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for k, v in value.items():  # pyright: ignore[reportUnknownVariableType]
            if k not in ("arabic_span", "heading_ar", "disclaimer"):
                yield from _texts(v)
    elif isinstance(value, list):
        for v in value:  # pyright: ignore[reportUnknownVariableType]
            yield from _texts(v)


def test_every_pair_answers_with_separate_witnesses(client: TestClient) -> None:
    """P17 (Req 2.1-2.3, 1.4): each witness comes back on its own; the count equals the
    supporting sections; missing witnesses are named; translations are labelled; the
    identification is 'identified' only when it matches the gold table."""
    for sub, cond in PAIRS:
        r = client.post("/seance/pair", json={"substance": sub, "condition": cond})
        assert r.status_code == 200, (sub, cond)
        assert r.headers["cache-control"] == "no-store"
        d = r.json()
        w = d["witnesses"]
        supports = [name for name in ("past", "present", "science") if w[name]["supports"]]
        assert d["supporting_witnesses"] == len(supports)
        assert d["missing_witnesses"] == [
            n for n in ("past", "present", "science") if n not in supports
        ]
        for name in ("past", "present", "science"):
            assert bool(w[name]["items"]) == w[name]["supports"]
            assert (w[name]["missing_reason"] is None) == w[name]["supports"]
        # Without a counts file and an evidence store these witnesses say why they are missing.
        assert w["present"]["missing_reason"] in (
            "no_faers_mapping",
            "exposure_differs",
            "counts_unavailable",
        )
        assert w["science"]["missing_reason"] in ("no_study_listed", "integrity_unavailable")
        assert all(i["translation_kind"] == "machine_translation" for i in w["past"]["items"])
        s = d["substance"]
        assert (s["identification_label"] == "identified") == (
            s["identification_status"] == "matches_gold"
        )
        assert d["framing"] == "hypothesis_not_treatment"
        assert d["disclaimer"].startswith("Janus provides information, not medical advice.")


def test_no_forbidden_or_reassuring_words(client: TestClient) -> None:
    """P18 (medical-safety rules 2, 3): no forbidden phrase or reassurance word in any English
    text of the catalogue or of a séance answer (Arabic quotations are not English text)."""
    bodies = [client.get("/seance/catalogue").json()]
    bodies += [
        client.post("/seance/pair", json={"substance": s, "condition": c}).json() for s, c in PAIRS
    ]
    for body in bodies:
        for text in _texts(body):
            assert violations(text, "en") == ([], []), text


@given(ascii_sentinels())
def test_invalid_requests_name_fields_and_echo_nothing(client: TestClient, value: str) -> None:
    """P19 (privacy rules): a bad substance or field gives 422 naming the field only; the value
    is never echoed or logged."""
    with capture_logs() as logs:
        r1 = client.post("/seance/pair", json={"substance": value, "condition": "burn"})
        r2 = client.post("/seance/pair", json={"substance": "henna", "condition": value})
        r3 = client.post("/seance/pair", json={"substance": "henna", "condition": "burn", value: 1})
    for r in (r1, r2, r3):
        assert r.status_code == 422
        assert value not in r.text
    assert not leaked(logs.getvalue(), [value])


def test_logs_carry_no_pair(client: TestClient) -> None:
    """P20 (privacy rules): only the access line is logged; never the substance or condition."""
    with capture_logs() as logs:
        r = client.post("/seance/pair", json={"substance": "vinegar", "condition": "infection"})
    assert r.status_code == 200
    out = logs.getvalue()
    assert not leaked(out, ["vinegar", "infection", "Q47512"])
    assert out.count('"event":"access"') == 1


def test_missing_catalogue_answers_503() -> None:
    app = create_app(Settings.from_env({}), configure_logs=False)
    with TestClient(app) as c:
        app.state.seance = None
        assert c.get("/seance/catalogue").status_code == 503
        r = c.post("/seance/pair", json={"substance": "henna", "condition": "burn"})
        assert r.status_code == 503 and r.json() == {"error": "seance_unavailable"}


@given(st.sampled_from(PAIRS))
def test_present_witness_example_with_a_protective_pattern(pair: tuple[str, str]) -> None:
    """A component-matched link with a ROR interval below 1 on enough reports supports; the
    same counts for an exposure that differs never do."""
    cat: Catalogue = CAT
    sub, cond = pair
    cells = RawCells(1_000_000, 1_000_000, 10_000, 10_000, 10_000, 10)
    link = cat.present.get(sub)
    out = service.build(cat, sub, cond, cells=cells, snapshot_date="2026-10-28", integrity=None)
    present = out.witnesses.present
    if link is None:
        assert present.missing_reason == "no_faers_mapping"
    elif link.exposure_match == "different":
        assert not present.supports and present.missing_reason == "exposure_differs"
        assert present.observed is not None  # shown as context
    else:
        assert present.supports and present.items[0].ror_ci.high < 1
