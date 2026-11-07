"""Property tests for canonical rows and the content hash."""

from __future__ import annotations

import copy
import unicodedata

from hypothesis import given
from hypothesis import strategies as st

from janus_pipelines.core.canonical import Json, content_hash
from tests.strategies import rows


@given(st.data(), rows())
def test_permuting_rows_keeps_hash(data: st.DataObject, rs: list[dict[str, Json]]) -> None:
    """Feature: data-pipelines, Property P2 — Validates: Req 1.3.

    Any permutation of input rows gives the same content hash.
    """
    permuted = data.draw(st.permutations(rs))
    assert content_hash(permuted, "v1") == content_hash(rs, "v1")


@given(rows())
def test_same_rows_same_hash(rs: list[dict[str, Json]]) -> None:
    """Feature: data-pipelines, Property P1 (pure part) — Validates: Req 1.1, 1.3.

    Serialising the same rows twice (including an independent deep copy) gives the same hash.
    """
    assert content_hash(rs, "v1") == content_hash(copy.deepcopy(rs), "v1")


@given(rows(min_size=1))
def test_nfc_forms_hash_equal(rs: list[dict[str, Json]]) -> None:
    """NFD and NFC spellings of the same text hash the same (supports P1/P2)."""

    def nfd(v: Json) -> Json:
        if isinstance(v, str):
            return unicodedata.normalize("NFD", v)
        if isinstance(v, list):
            return [nfd(x) for x in v]
        return v

    decomposed = [{k: nfd(v) for k, v in r.items()} for r in rs]
    assert content_hash(decomposed, "v1") == content_hash(rs, "v1")


@given(rows(min_size=1))
def test_schema_version_is_part_of_hash(rs: list[dict[str, Json]]) -> None:
    assert content_hash(rs, "v1") != content_hash(rs, "v2")
