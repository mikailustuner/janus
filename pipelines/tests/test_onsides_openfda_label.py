"""Tests for the onsides and openfda_label jobs (light-face design §3). Synthetic; no network."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import polars as pl
import pytest
from hypothesis import given
from hypothesis import strategies as st

from janus_pipelines.core.validation import SchemaMismatchError
from janus_pipelines.jobs.onsides import (
    SHA256,
    TABLES,
    ReleaseHashError,
    check_release,
    parse_release,
)
from janus_pipelines.jobs.openfda_label import (
    case_ingredients,
    names_ingredient,
    parse_responses,
    query_params,
)

REPO = Path(__file__).resolve().parents[2]


def _csv(header: tuple[str, ...], rows: list[tuple[object, ...]]) -> str:
    out = io.StringIO()
    out.write(",".join(header) + "\n")
    for r in rows:
        out.write(",".join(f'"{v}"' if isinstance(v, str) else str(v) for v in r) + "\n")
    return out.getvalue()


def release(
    labels: list[tuple[int, str]],
    effects: list[tuple[int, str, int]],
    links: list[tuple[int, str]],
    *,
    drop: str | None = None,
) -> bytes:
    """A zip shaped like the OnSIDES release (`csv/<table>.csv`)."""
    tables = {
        "product_label": [(i, src, f"P{i}", f"set{i}.1", f"https://x/{i}") for i, src in labels],
        "product_adverse_effect": [(lid, sec, mid) for lid, sec, mid in effects],
        "product_to_rxnorm": [(lid, f"p{ing}") for lid, ing in links],
        "vocab_rxnorm_ingredient_to_product": [(ing, f"p{ing}") for _l, ing in links],
        "vocab_rxnorm_ingredient": [
            ("101", "aspirin", "Ingredient"),
            ("102", "metformin", "Ingredient"),
        ],
        "vocab_meddra_adverse_effect": [(1, "Term one", "PT"), (2, "Term two", "LLT")],
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, cols in TABLES.items():
            if name == drop:
                continue
            zf.writestr(f"csv/{name}.csv", _csv(cols, tables[name]))  # pyright: ignore[reportArgumentType]
    return buf.getvalue()


def test_pinned_hash_is_enforced() -> None:
    with pytest.raises(ReleaseHashError):
        check_release(b"not the release")
    check_release(b"x", expected="2d711642b726b04401627ca9fbac32f5c8530fb1903cc4db02258717921a4881")
    assert len(SHA256) == 64


@given(
    st.lists(st.sampled_from(["US", "EU", "UK", "JP"]), min_size=1, max_size=8),
    st.lists(
        st.tuples(
            st.integers(1, 8), st.sampled_from(["AR", "WP", "BW", "NA"]), st.sampled_from([1, 2])
        ),
        max_size=20,
    ),
    st.lists(st.tuples(st.integers(1, 8), st.sampled_from(["101", "102"])), max_size=12),
)
def test_parse_accounts_for_every_label(
    tmp_path_factory: pytest.TempPathFactory,
    sources: list[str],
    effects: list[tuple[int, str, int]],
    links: list[tuple[int, str]],
) -> None:
    """Every label is output or excluded with a reason; effects are distinct per label."""
    labels = list(enumerate(sources, start=1))
    effects = [e for e in effects if e[0] <= len(labels)]
    links = [lk for lk in links if lk[0] <= len(labels)]
    res = parse_release(release(labels, effects, links), tmp_path_factory.mktemp("o"))
    assert res.input_rows == len(labels)
    assert res.n_output + sum(res.excluded.values()) == len(labels)
    assert res.rows_file is not None
    rows = pl.read_parquet(res.rows_file)
    linked = {lid for lid, _ in links}
    with_effect = {lid for lid, _, _ in effects}
    assert set(rows["label_id"].to_list()) == linked & with_effect
    for r in rows.iter_rows(named=True):
        pairs = [(e["meddra_id"], e["section"]) for e in r["effects"]]
        assert pairs == sorted(set(pairs))
        assert r["ingredient_ids"] == sorted({ing for lid, ing in links if lid == r["label_id"]})
    assert set(res.side_tables) == {"meddra", "ingredients"}


def test_missing_table_or_unknown_region_is_refused(tmp_path: Path) -> None:
    with pytest.raises(SchemaMismatchError):
        parse_release(release([(1, "US")], [], [], drop="product_to_rxnorm"), tmp_path / "a")
    with pytest.raises(SchemaMismatchError):
        parse_release(release([(1, "XX")], [(1, "AR", 1)], [(1, "101")]), tmp_path / "b")


# --- openfda_label --------------------------------------------------------------------------------


def test_case_ingredients_come_from_the_committed_cases() -> None:
    names = case_ingredients(REPO)
    assert names == sorted(set(names)) and "minoxidil" in names and "sildenafil" in names
    assert query_params("minoxidil") == {
        "search": 'openfda.generic_name:"minoxidil"',
        "limit": "1000",
    }


def test_names_ingredient_is_whole_word() -> None:
    assert names_ingredient("sildenafil citrate", "sildenafil")
    assert names_ingredient("phentermine and topiramate", "topiramate")
    assert not names_ingredient("glycopyrrolate", "glycopyrronium")
    assert not names_ingredient("xminoxidil", "minoxidil")


def test_parse_responses_filters_and_accounts() -> None:
    body = json.dumps(
        {
            "results": [
                {
                    "set_id": "a",
                    "version": "3",
                    "openfda": {"generic_name": ["MINOXIDIL"]},
                    "indications_and_usage": ["For hypertension."],
                },
                {"set_id": "a", "openfda": {"generic_name": ["MINOXIDIL"]}},
                {"set_id": "b", "openfda": {"generic_name": ["OTHER"]}},
                {"openfda": {"generic_name": ["MINOXIDIL"]}},
                "junk",
            ]
        }
    ).encode()
    res = parse_responses({"minoxidil": body, "thalidomide": b""})
    assert res.input_rows == 5
    assert len(res.rows) + sum(res.excluded.values()) == 5
    assert [r["set_id"] for r in res.rows] == ["a"]
    assert res.rows[0]["indications"] == "For hypertension."
    assert res.metrics["labels_per_query"] == {"minoxidil": 1, "thalidomide": 0}
