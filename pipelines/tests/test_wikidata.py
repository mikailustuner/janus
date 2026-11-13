"""Tests for the wikidata_ingredients job (P13 and examples). No network."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

from janus_pipelines.core.canonical import Row, content_hash
from janus_pipelines.core.runner import RawInput
from janus_pipelines.core.validation import SchemaMismatchError
from janus_pipelines.jobs.wikidata_ingredients import (
    ENTITY_PREFIX,
    FETCH_LANGS,
    WikidataIngredientsJob,
    labels_query,
    merge,
)
from tests.stub_job import FIXED_NOW

QIDS = st.integers(1, 40).map(lambda n: f"Q{n}")
ATC = st.from_regex(r"[A-V][0-9]{2}[A-Z]{2}[0-9]{2}", fullmatch=True)
RXCUI = st.integers(1, 10**6).map(str)
LABEL = st.text(alphabet=st.characters(categories=["L", "Zs"]), min_size=1, max_size=10)


def _uri(q: str) -> dict[str, str]:
    return {"type": "uri", "value": ENTITY_PREFIX + q}


def _lit(v: str) -> dict[str, str]:
    return {"type": "literal", "value": v}


def _code(q: str, a: str, r: str | None) -> dict[str, Any]:
    return {"item": _uri(q), "atc": _lit(a), **({"rxcui": _lit(r)} if r else {})}


def _label(q: str, label: str | None, alias: str | None) -> dict[str, Any]:
    return {
        "item": _uri(q),
        **({"label": _lit(label)} if label else {}),
        **({"alias": _lit(alias)} if alias else {}),
    }


CODE_BINDING = st.builds(
    _code,
    QIDS,
    ATC,
    st.one_of(st.none(), RXCUI),
)
LABEL_BINDING = st.builds(
    _label,
    QIDS,
    st.one_of(st.none(), LABEL),
    st.one_of(st.none(), LABEL),
)


def _partition(draw: Callable[[st.SearchStrategy[Any]], Any], items: list[Any]) -> list[Any]:
    """Shuffle, split into parts (as split queries return) and repeat some items (an item
    with several ATC codes appears in several letter parts)."""
    shuffled: list[Any] = list(draw(st.permutations(items)))
    repeats: list[Any] = list(draw(st.lists(st.sampled_from(items), max_size=5))) if items else []
    return shuffled + repeats


@given(
    st.lists(CODE_BINDING, max_size=30),
    st.fixed_dictionaries({lang: st.lists(LABEL_BINDING, max_size=15) for lang in FETCH_LANGS}),
    st.data(),
)
def test_merge_independent_of_order_and_split(
    codes: list[dict[str, Any]], labels: dict[str, list[dict[str, Any]]], data: st.DataObject
) -> None:
    """Feature: data-pipelines, Property P13 — Validates: Req 7.3, 7.4.

    Merging does not depend on binding order or on how bindings were split across queries;
    each QID appears once, with at least one ATC code.
    """
    base = merge(codes, labels)
    again = merge(
        _partition(data.draw, codes),
        {lang: _partition(data.draw, b) for lang, b in labels.items()},
    )
    assert content_hash(base.rows, "t") == content_hash(again.rows, "t")
    qids = [r["qid"] for r in base.rows]
    assert len(qids) == len(set(qids))
    assert all(r["atc_codes"] for r in base.rows)
    assert set(qids) == {b["item"]["value"].removeprefix(ENTITY_PREFIX) for b in codes}


def _response(vars_: list[str], bindings: list[dict[str, Any]]) -> bytes:
    return json.dumps({"head": {"vars": vars_}, "results": {"bindings": bindings}}).encode()


def _raw(payload: dict[str, list[bytes]]) -> RawInput[dict[str, list[bytes]]]:
    return RawInput(
        payload=payload,
        source_urls=("https://query.wikidata.org/sparql",),
        source_sha256="x",
        retrieved_at=FIXED_NOW,
        snapshot_date=FIXED_NOW.isoformat(),
        snapshot_date_is_retrieval_time=True,
    )


def _payload() -> dict[str, list[bytes]]:
    codes = _response(
        ["item", "atc", "rxcui"],
        [
            {"item": _uri("Q18216"), "atc": _lit("C08CA01"), "rxcui": _lit("17767")},
            {"item": _uri("Q18216"), "atc": _lit("C08CA01")},
            {"item": {"type": "uri", "value": "http://example.org/bad"}, "atc": _lit("A01")},
        ],
    )
    payload = {"codes": [codes]}
    for lang in FETCH_LANGS:
        name = {"en": "amlodipine", "tr": "amlodipin", "de": "Amlodipin", "pt": "anlodipino"}.get(
            lang
        )
        bindings = [{"item": _uri("Q18216"), **({"label": _lit(name)} if name else {})}]
        payload[f"labels_{lang}"] = [_response(["item", "label", "alias"], bindings)]
    return payload


def test_parse_example() -> None:
    """Validates: Req 7.1, 7.2, 7.4, 1.5."""
    result = WikidataIngredientsJob().parse(_raw(_payload()))
    assert len(result.rows) == 1
    row: Row = result.rows[0]
    assert row["qid"] == "Q18216"
    assert row["atc_codes"] == ["C08CA01"]
    assert row["label_pt"] == "anlodipino"
    assert result.metrics["items_with_label_pt"] == 1
    assert row["rxcuis"] == ["17767"]
    assert row["label_tr"] == "amlodipin"
    assert row["label_fr"] is None
    assert result.excluded == {"invalid_qid": 1}
    assert result.input_rows == len(result.rows) + 1


def test_missing_var_is_schema_failure() -> None:
    payload = _payload()
    payload["codes"] = [_response(["item", "code"], [])]
    with pytest.raises(SchemaMismatchError, match="atc"):
        WikidataIngredientsJob().parse(_raw(payload))


def test_label_query_rejects_unknown_language() -> None:
    with pytest.raises(ValueError):
        labels_query("xx")
    assert 'STRSTARTS(?a, "C")' in labels_query("tr", "C")


def _lang_binding(lang: str, qid_: str, label: str | None = None, alias: str | None = None) -> Any:
    cells = {"item": _uri(qid_)}
    if label:
        cells["label"] = _lit(label)
    if alias:
        cells["alias"] = _lit(alias)
    return lang, cells


def _merge_pt(*entries: Any) -> dict[str, Row]:
    codes = [{"item": _uri(q), "atc": _lit("A01")} for q in ("Q1", "Q2", "Q3")]
    by_lang: dict[str, list[Any]] = {lang: [] for lang in FETCH_LANGS}
    for lang, cells in entries:
        by_lang[lang].append(cells)
    return {str(r["qid"]): r for r in merge(codes, by_lang).rows}


def test_pt_label_wins_and_pt_br_variants_become_aliases() -> None:
    rows = _merge_pt(
        _lang_binding("pt", "Q1", "xenón"),
        _lang_binding("pt-br", "Q1", "xenônio", "Xe"),
        _lang_binding("pt-br", "Q2", "dalbavancina"),
        _lang_binding("pt", "Q3", None, "apelido"),
    )
    assert rows["Q1"]["label_pt"] == "xenón"
    assert rows["Q1"]["aliases_pt"] == ["Xe", "xenônio"]
    # No `pt` label: the `pt-br` label stands in.
    assert rows["Q2"]["label_pt"] == "dalbavancina"
    assert rows["Q2"]["aliases_pt"] == []
    # Aliases alone never become the label.
    assert rows["Q3"]["label_pt"] is None
    assert rows["Q3"]["aliases_pt"] == ["apelido"]
    assert "label_pt-br" not in rows["Q1"]


def test_pt_br_label_equal_to_pt_label_adds_no_alias() -> None:
    rows = _merge_pt(
        _lang_binding("pt", "Q1", "riboflavina"), _lang_binding("pt-br", "Q1", "riboflavina")
    )
    assert rows["Q1"]["aliases_pt"] == []
