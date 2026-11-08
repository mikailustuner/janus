"""Property tests for canonical rows and the content hash."""

from __future__ import annotations

import copy
import unicodedata

from hypothesis import given
from hypothesis import strategies as st

from janus_pipelines.core.canonical import Json, content_hash, content_hash_stream
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


def test_golden_hash_vector() -> None:
    """Shared with apps/api (drug-resolution design §6.2): the API's loader re-implements the
    canonical hash, and both suites assert this value so the two cannot drift."""
    rows = (
        {"barcode": "8680199094206", "ingredients": ["b", "a"], "atc_code": "C09BB03", "n": 1},
        {"barcode": None, "name_only": True, "product_name": "İ\u0307ç", "x": {"k": [1.5, False]}},
    )
    assert (
        content_hash(rows, "golden-1")
        == "a7b073198be149895d161e694542975078a69999dd7fb1c284f8dcf1b6c5ec8b"
    )


@given(rows(), st.integers(1, 10))
def test_streamed_hash_equals_in_memory_hash(rs: list[dict[str, Json]], chunk: int) -> None:
    """Feature: data-pipelines, Property P17 (hash part) — Validates: Req 14.1, 1.3.
    For any rows and any chunk size the streamed hash equals the in-memory hash (also when empty).
    """
    assert content_hash_stream(iter(rs), "v1", chunk=chunk) == content_hash(rs, "v1")


def test_golden_hash_vector_streamed() -> None:
    rows = (
        {"barcode": "8680199094206", "ingredients": ["b", "a"], "atc_code": "C09BB03", "n": 1},
        {"barcode": None, "name_only": True, "product_name": "İ\u0307ç", "x": {"k": [1.5, False]}},
    )
    assert (
        content_hash_stream(rows, "golden-1", chunk=1)
        == "a7b073198be149895d161e694542975078a69999dd7fb1c284f8dcf1b6c5ec8b"
    )
