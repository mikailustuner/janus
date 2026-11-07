"""Shared Hypothesis strategies."""

from __future__ import annotations

import unicodedata

from hypothesis import strategies as st

from janus_pipelines.core.canonical import Json

# Text with Turkish letters, accents and combining marks (exercises NFC normalisation).
_CHARS = unicodedata.normalize(
    "NFC", "abcçdefgğhıijklmnoöprsştuüvyzABCÇDEFGĞHIİJKLMNOÖPRSŞTUÜVYZ0123456789 %-().,/+"
)
# Precomposed and combining forms: é, combining acute, ñ, combining tilde, ß, ä, diaeresis.
_EXTRA = ["\u00e9", "\u0301", "\u00f1", "\u0303", "\u00df", "\u00e4", "\u0308"]
TEXT = st.text(alphabet=st.sampled_from(sorted(set(_CHARS)) + _EXTRA), max_size=20)

SCALAR: st.SearchStrategy[Json] = st.one_of(
    st.none(), st.booleans(), st.integers(-(10**12), 10**12), TEXT
)


def rows(min_size: int = 0, max_size: int = 30) -> st.SearchStrategy[list[dict[str, Json]]]:
    """Rows with a fixed key set, as pipelines produce them."""
    row = st.fixed_dictionaries(
        {
            "id": TEXT,
            "n": st.one_of(st.none(), st.integers(0, 10**9)),
            "names": st.lists(TEXT, max_size=4),
            "flag": st.booleans(),
        }
    )
    return st.lists(row, min_size=min_size, max_size=max_size)  # type: ignore[return-value]
