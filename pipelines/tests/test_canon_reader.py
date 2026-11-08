"""Reader step (séance design §3.4): fake readers only, no network, no API key."""

from __future__ import annotations

import csv
import json
from collections.abc import Mapping
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

from janus_pipelines.jobs.canon_reader import (
    AGREE,
    CONDITION_VALUES,
    MODEL,
    READER_COLUMNS,
    AnthropicReader,
    ReaderError,
    SpanInput,
    read_spans,
    validate,
)

PKG = Path(__file__).resolve().parents[2] / "datasets" / "canon"
SPAN = {
    "arabic_span": "ينفع من حرق النار.",
    "conditions_en": "fire burns",
    "rule_forms": "",
    "rule_vehicles": "",
    "rule_parts": "",
    "rule_actions": "is useful",
}


def good(**over: Any) -> dict[str, Any]:
    out: dict[str, Any] = {
        "conditions": ["burn"],
        "body_site": "skin",
        "use_en": "Not stated.",
        "machine_translation_en": "It helps fire burns.",
        "rule_theme_agrees": "yes",
        "rule_use_agrees": "partial",
        "reader_note": "",
    }
    out.update(over)
    return out


class Fake:
    def __init__(self, out: Mapping[str, Any]) -> None:
        self.out = out
        self.seen: list[Mapping[str, str]] = []

    def read(self, span: Mapping[str, str]) -> Mapping[str, Any]:
        self.seen.append(span)
        return self.out


def test_valid_output_becomes_a_reader_row() -> None:
    rows = read_spans([SpanInput("s1", "galium", SPAN)], Fake(good()))
    assert rows == [
        {
            "span_id": "s1",
            "substance_id": "galium",
            "conditions": "burn",
            "body_site": "skin",
            "use_en": "Not stated.",
            "machine_translation_en": "It helps fire burns.",
            "rule_theme_agrees": "yes",
            "rule_use_agrees": "partial",
            "reader_note": "",
        }
    ]
    assert tuple(rows[0]) == READER_COLUMNS


@given(
    st.lists(st.text(max_size=12), min_size=0, max_size=4),
    st.text(max_size=8),
)
def test_invalid_conditions_or_agreement_are_refused(conds: list[str], agree: str) -> None:
    """Reader output is validated, never repaired: unknown conditions, out_of_scope mixed with
    a condition, or an unknown agreement value is refused."""
    ok_conds = (
        bool(conds)
        and all(c in CONDITION_VALUES for c in conds)
        and len(set(conds)) == len(conds)
        and not ("out_of_scope" in conds and len(conds) > 1)
    )
    out = good(conditions=conds, rule_use_agrees=agree)
    if ok_conds and agree in AGREE:
        assert validate(out, "s", "x")["conditions"]
    else:
        with pytest.raises(ReaderError):
            validate(out, "s", "x")


@pytest.mark.parametrize("word", ["cure", "Cures", "treatment for", "diagnosis"])
def test_forbidden_words_are_refused(word: str) -> None:
    with pytest.raises(ReaderError, match="machine_translation_en"):
        validate(good(machine_translation_en=f"It is a {word} burns."), "s", "x")


def test_extra_fields_are_refused() -> None:
    with pytest.raises(ReaderError):
        validate({**good(), "score": 1}, "s", "x")


def _client(text: str, stop: str = "end_turn") -> tuple[Any, list[dict[str, Any]]]:
    calls: list[dict[str, Any]] = []

    def create(**kw: Any) -> Any:
        calls.append(kw)
        return SimpleNamespace(stop_reason=stop, content=[SimpleNamespace(type="text", text=text)])

    return SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=create))), calls


def test_anthropic_reader_request_shape_and_parse() -> None:
    client, calls = _client(json.dumps(good()))
    out = AnthropicReader(client).read(SPAN)
    assert out == good()
    kw = calls[0]
    assert kw["model"] == MODEL
    assert kw["output_config"]["format"]["type"] == "json_schema"
    assert kw["timeout"] > 0
    assert "حرق النار" in kw["messages"][0]["content"]


def test_anthropic_reader_refusal_and_bad_json_fail_loudly() -> None:
    with pytest.raises(ReaderError):
        AnthropicReader(_client("{}", stop="refusal")[0]).read(SPAN)
    with pytest.raises(ReaderError):
        AnthropicReader(_client("not json")[0]).read(SPAN)


@pytest.mark.skipif(not (PKG / "reader_ai.csv").exists(), reason="data package not built")
def test_committed_offline_reading_validates() -> None:
    """The offline AI reading (no key configured) passes the same validation as an LLM row."""
    with (PKG / "reader_ai.csv").open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert 30 <= len(rows) <= 50
    for r in rows:
        out = {k: r[k] for k in READER_COLUMNS if k not in ("span_id", "substance_id")}
        out["conditions"] = r["conditions"].split("|")
        got = validate(out, r["span_id"], r["substance_id"])
        assert set(got.pop("conditions").split("|")) == set(r.pop("conditions").split("|"))
        assert got == r
